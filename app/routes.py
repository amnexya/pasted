from app import app, db, worker, config, file_view_templates
from flask import render_template, request, redirect, url_for
import datetime
import os
from app.models import File, User

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/paste', methods=['GET', 'POST'])
def paste():
    if request.method == 'POST':    
        try:
            
            mgmt = worker.create_mgmt_token()
            mime, ext = worker.determine_mime_and_ext(request.files['file'])
            filename = worker.name_randomiser() + '.' + ext
            s3_path = "/pasted/" + filename

            filesize = request.files['file'].seek(0, os.SEEK_END)
            request.files['file'].seek(0)

            user = None

            # We will upload the file to s3 before we add it to the db,
            # I dont really care if we have files in s3 that are not in the db.
            # TODO: Set up a cleanup service on s3 to clean stuff that isn't in the db.
            worker.upload_s3(request.files['file'], filename, mime)

            worker.create_db_entry(s3_path, 
                                   request.remote_addr, 
                                   datetime.datetime.now(), 
                                   filename, 
                                   user, 
                                   mgmt,
                                   filesize,
                                   mime,
                                   worker.sha256gen(request.files['file']),
                                   False)

            return render_template('success.html', mgmt=mgmt, filename=filename, host=request.host, user=user)
        except Exception as e:
            print(e)
            return "nope"
        
    return "Wrong method, buddy."

@app.route('/<filename>')
def view(filename):
    file = db.session.query(File).filter_by(filename=filename).first()
    
    if file is None:
        return "File not found, sorry."

    # Check if the file is deleted
    if file.deleted:
        return "This file has been marked for deletion, you are no longer able to view this."
        
    view = False

    if file.mime in app.config['VIEWABLE_FILE_TYPES']:
        view = True

    # Right lets grab the file from s3
    try:
        data = worker.get_file_from_s3(file.s3_path, file.mime)
    except Exception as e:
        print(e)
        return "Error getting file, this is a bug, please report it."
    
    
    hash_warn = False
    # Compare the sha256 of the file to the one in the db
    if worker.sha256gen(data) != file.sha256:
        hash_warn = True
        # Set view to false as a precaution
        view = False

    url = config['endpoint'] + file.s3_path
    filetype = file.mime.split('/')[0]

    return render_template('view.html', filetype=filetype, url=url, view=view, hash_warn=hash_warn, filename=filename)