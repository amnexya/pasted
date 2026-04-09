from app import app, db, worker, config
from cryptography import fernet
from flask import render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.datastructures import FileStorage
import datetime
import os
from app.models import File
import io

@app.route('/', methods=['GET', 'POST'])
def index():
    quote, quote_author = worker.get_quote_from_db()
    recent_files = worker.generate_recent_pastes()
    return render_template('index.html', title='home', quote=quote, quote_author=quote_author, recent_files=recent_files, host=request.host, max_file_size=config['max_file_size'], version=config['version'])

@app.route('/paste', methods=['GET', 'POST'])
def paste():
    if request.method == 'POST':    
        key = fernet.Fernet(app.config['encryption_key'])

        try:
            # Determine whether we have text or a file
            uploaded_file = request.files.get('file')
            uploaded_text = request.form.get('file')

            # Change it to a filestorage object so we can work with it the same way as uploaded files.
            if uploaded_text:
                current_file = FileStorage(stream=io.BytesIO(uploaded_text.encode()), filename='paste.txt', content_type='text/plain')

            elif uploaded_file:
                current_file = uploaded_file

            else:
                return "No file or text provided, sorry. <a href='/'>Go back</a>.", 400

            mgmt = worker.create_mgmt_token()
            mime = current_file.mimetype
            ext = current_file.filename.split('.')[-1]

            if ext == "":
                ext = "bin" # Default to bin if no extension provided, just to be safe.
            filename = worker.name_randomiser() + "." + ext # Just in case, we dont want any funny business with the filename.

            filesize = current_file.seek(0, os.SEEK_END)
            current_file.seek(0)

            if request.form.get('private'): # If it holds any value at all, we can set it to true.
                private = True
            else:
                private = False

            encrypted_content = key.encrypt(current_file.read())
            current_file = FileStorage(stream=io.BytesIO(encrypted_content), filename=current_file.filename, content_type=current_file.content_type)
            current_file.seek(0)

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

            current_file.close()

            return render_template('success.html', mgmt=mgmt, filename=filename, host=request.host)
        except RequestEntityTooLarge:
            return "File too large, sorry. <a href='/'>Go back</a>."
        finally:
            if current_file:
                current_file.close()
        
    return "Wrong method, use a POST request for this route."

@app.route('/<filename>', methods=['GET', 'POST']) # type: ignore
def view(filename):
    if request.method == 'GET':
        file = db.session.query(File).filter_by(filename=filename).first()
        key = fernet.Fernet(app.config['encryption_key'])
        
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
                encrypted = f.read().encode()
                content = key.decrypt(encrypted)
                content = content.decode('utf-8', errors='replace') # Just in case, we dont want the page to break if the text is not valid utf-8.
        else:
            content = None
            url = f'/file/{filename}'
            

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

@app.route('/file/<filename>')
def serve_file(filename):
    """Serve encrypted files by decrypting and streaming them."""
    file = db.session.query(File).filter_by(filename=filename).first()
    key = fernet.Fernet(app.config['encryption_key'])
    
    if file is None or file.deleted:
        return "File not found, sorry.", 404
    
    try:
        with open(os.path.join(config['local_data'], filename), 'rb') as f:
            encrypted_content = f.read()
            decrypted_content = key.decrypt(encrypted_content)
        
        return send_file(
            io.BytesIO(decrypted_content),
            mimetype=file.mime,
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        print(e)
        return "Error serving file.", 500
        
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