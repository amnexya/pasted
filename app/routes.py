from app import app, db, worker, config
from flask import render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
import datetime
import os
from app.models import File

@app.route('/', methods=['GET', 'POST'])
def index():
    quote, quote_author = worker.get_quote_from_db()
    recent_files = worker.generate_recent_pastes()
    print(recent_files)
    return render_template('index.html', title='home', quote=quote, quote_author=quote_author, recent_files=recent_files)

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

            if request.form.get('private'): # If it holds any value at all, we can set it to true.
                private = True
            else:
                private = False

            # We will upload the file to s3 before we add it to the db,
            # I dont really care if we have files in s3 that are not in the db.
            worker.upload_s3(request.files['file'], filename, mime)

            worker.create_db_entry(s3_path, # S3 Path
                                   request.headers.get('X-Real-IP', request.remote_addr), # IP
                                   datetime.datetime.now(), # Date
                                   filename, # Filename
                                   worker.generate_hash(mgmt), # Hash mgmt token
                                   filesize, # Size
                                   mime, # MimeType
                                   worker.sha256gen(request.files['file']), # SHA256
                                   private, # Exclude from recent
                                   False) # Deleted, always false on upload, don't change unless you want to really fuck with your users :kekw:

            return render_template('success.html', mgmt=mgmt, filename=filename, host=request.host)
        except RequestEntityTooLarge:
            return "File too large, max size is 128MB. <a href='/'>Go back</a>."
        
    return "Wrong method, use a POST request for this route."

@app.route('/<filename>', methods=['GET', 'POST'])
def view(filename):
    if request.method == 'GET':
        file = db.session.query(File).filter_by(filename=filename).first()
        
        if file is None:
            return "File not found, sorry. <a href='/'>Go back</a>.", 404

        # Check if the file is deleted
        if file.deleted:
            return f"""This file has been marked for deletion, you are no longer able to view this.
            If you need this file urgently, contact {config['site_admin']} with your filename. <a href='/'>Go back</a>.""", 404
            
        view = False

        if file.mime in app.config['VIEWABLE_FILE_TYPES']:
            view = True

        size_warn = False
        hash_warn = False
        # Right lets grab the file from s3
        if file.size < config['max_view_size'] * 1024 * 1024:
            try:
                data = worker.get_file_from_s3(file.s3_path, file.mime)
            except Exception as e:
                print(e)
                return "Error getting file, this is a bug, please report it."
        
            # Compare the sha256 of the file to the one in the db
            if worker.sha256gen(data) != file.sha256:
                hash_warn = True
                # Set view to false as a precaution
                view = False
        else:
            size_warn = True

        url = config['endpoint'] + file.s3_path
        filetype = file.mime.split('/')[0]

        # If the file is just text then we should pass through the contents
        if filetype == 'text':
            try: # if this fails, chances are whatever they uploaded is buggered, just tell them to download it.
                data = data.stream.read().decode('utf-8')
            except UnicodeDecodeError:
                data = "We've encountered a bug and can't display your file, please download it and try it in a text editor instead."
        else:
            data = None

        return render_template('view.html', sha256=file.sha256, size_warn=size_warn, data=data, filetype=filetype, url=url, view=view, hash_warn=hash_warn, filename=filename, title=filename)
   
    elif request.method == 'POST':
        file = db.session.query(File).filter_by(filename=filename).first()

        # If it doesnt exist or its marked for deletion, say its not found.
        if file is None or file.deleted:
            return "File not found, sorry.", 404
        
        if worker.check_hash(request.form['mgmt'], file.mgmt):
            file.deleted = True
            db.session.commit()
            return "File marked for deletion.", 200
        
        else:
            return "Management token incorrect.", 401
        
### Render-Only Routes below ###

@app.route('/faq')
def faq():
    return render_template('faq.html', title='faq')

@app.route('/tos')
def tos():
    return render_template('tos.html', title='ToS')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html', title='Privacy Policy')