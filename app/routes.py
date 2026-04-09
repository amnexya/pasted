from app import app, db, worker, config
from flask import render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
import datetime
import os
from app.models import File
import io

@app.route('/', methods=['GET', 'POST'])
def index():
    quote, quote_author = worker.get_quote_from_db()
    recent_files = worker.generate_recent_pastes()
    return render_template('index.html', title='home', quote=quote, quote_author=quote_author, recent_files=recent_files, host=request.host)

@app.route('/paste', methods=['GET', 'POST'])
def paste():
    if request.method == 'POST':    
        try:
            # Determine whether we have text or a file
            uploaded_file = request.files.get('file')
            uploaded_text = request.form.get('file')

            if uploaded_file and uploaded_file.filename != '':
                worker.save_file(uploaded_file, uploaded_file.filename) # Save the file to the local storage, it'll get cleaned up if the upload fails.
                
            else:
                current_file = io.BytesIO(uploaded_text.encode('utf-8'))  # type: ignore
                current_file.filename = 'text.txt'  # Set a default name for the text file # type: ignore
                current_file.content_type = 'text/plain'  # Set a default content type # type: ignore

            mgmt = worker.create_mgmt_token()
            mime, ext = worker.determine_mime_and_ext(current_file)
            filename = worker.name_randomiser() + '.' + ext

            filesize = current_file.seek(0, os.SEEK_END)
            current_file.seek(0)

            if request.form.get('private'): # If it holds any value at all, we can set it to true.
                private = True
            else:
                private = False

            # We will save the file before we add it to the db,
            # it'll get cleaned up if the upload fails.
            worker.save_file(current_file, filename)

            worker.create_db_entry(request.headers.get('X-Real-IP', request.remote_addr), # IP
                                   datetime.datetime.now(), # Date
                                   filename, # Filename
                                   worker.generate_hash(mgmt), # Hash mgmt token
                                   filesize, # Size
                                   mime, # MimeType
                                   worker.sha256gen(current_file), # SHA256
                                   private, # Exclude from recent
                                   False) # Deleted, always false on upload, don't change unless you want to really fuck with your users :kekw:

            return render_template('success.html', mgmt=mgmt, filename=filename, host=request.host)
        except RequestEntityTooLarge:
            return "File too large, sorry. <a href='/'>Go back</a>."
        
    return "Wrong method, use a POST request for this route."

@app.route('/<filename>', methods=['GET', 'POST']) # type: ignore
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

        filetype = file.mime.split('/')[0]  # Get the type of the file (e.g., text, image, audio)

        # Allow for viewing of all viewable types, and add application/pdf, 
        # fixes bugs with files not being viewable as magic was messing with mime types.
        if filetype in ['text', 'image', 'audio', 'video'] or file.mime.startswith('application/pdf'):
            view = True

        size_warn = False
        hash_warn = False

        # If it's text, we will pass the content to the template, otherwise we'll just pass the url and let the browser handle it.
        if filetype == 'text':
            url = None
            with open(os.path.join(config['local_data'], filename), 'r') as f:
                content = f.read()
        else:
            content = None
            url = config['srv_data_location'] + '/' + filename

        return render_template('view.html', sha256=file.sha256, content=content, size_warn=size_warn, filetype=filetype, mime=file.mime, url=url, view=view, hash_warn=hash_warn, filename=filename, title=filename)
   
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