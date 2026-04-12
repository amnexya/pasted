from app import app, db, worker, config
from cryptography import fernet
from flask import flash, render_template, request, send_file, make_response, redirect, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.datastructures import FileStorage
from magic import Magic
import datetime
import os
from app.models import File
import io
import pycmarkgfm as md

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return paste(api=True)

    quote, quote_author = worker.get_quote_from_db()
    recent_files = worker.generate_recent_pastes()

    resp = make_response(render_template('index.html', title='home', quote=quote, quote_author=quote_author, recent_files=recent_files, host=request.host, max_file_size=config['max_file_size'], version=config['version']))
    resp.set_cookie('browserIdent', "1")

    return resp

@app.route('/paste', methods=['GET', 'POST'])
def paste(api=False):
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
                flash("No file or text provided.")
                return redirect(url_for('index'))

            mgmt = worker.create_mgmt_token()

            mime = Magic(mime=True).from_buffer(current_file.stream.read(2048))#
            current_file.stream.seek(0) # Reset the stream position after reading for magic

            ext = current_file.filename.split('.')[-1] # type: ignore

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

            if api:
                return {"mgmt": mgmt, "filename": filename}
            else:
                return render_template('success.html', mgmt=mgmt, filename=filename, host=request.host)
        except RequestEntityTooLarge:
            flash("File too large, try something smaller.")
            return redirect(url_for("index"))
        
    return "Wrong method, use a POST request for this route."

@app.route('/<filename>') # type: ignore
def view(filename):
    if request.method == 'GET':
        api = False if request.cookies.get('browserIdent') else True
        file = db.session.query(File).filter_by(filename=filename).first()
        key = fernet.Fernet(app.config['encryption_key'])
        
        if file is None:
            flash("File not found, sorry.")
            return redirect(url_for("index"))
        
        filesize = file.size
            
        view = True

        filetype = file.mime.split('/')[0]  # Get the type of the file (e.g., text, image, audio)

        url = f'/file/{filename}'

        is_markdown = False
        content = None

        # If it's text, we will pass the content to the template, otherwise we'll just pass the url and let the browser handle it.
        if filetype == 'text':
            with open(os.path.join(config['local_data'], filename), 'rb') as f:
                encrypted = f.read()
                content = key.decrypt(encrypted)
                content = content.decode('utf-8', errors='replace') # Just in case, we dont want the page to break if the text is not valid utf-8.
                is_markdown = worker.is_markdown(file.filename, content)
                print(is_markdown)
                if is_markdown:
                    content = md.gfm_to_html(content)
            
        if api:
            return content if content else serve_file(filename)
        else:
            return render_template('view.html', sha256=file.sha256, is_markdown=is_markdown, content=content, filesize=filesize, filetype=filetype, mime=file.mime, url=url, view=view, filename=filename, title=filename)

@app.route('/file/<filename>')
def serve_file(filename):
    """Serve encrypted files by decrypting and streaming them."""
    file = db.session.query(File).filter_by(filename=filename).first()
    key = fernet.Fernet(app.config['encryption_key'])
    
    if file is None or file.deleted:
        flash("File not found, sorry.")
        return redirect(url_for("index"))
    
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
        flash("Error serving file.")
        return redirect(url_for("index"))
    
@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if request.method == 'POST':
        name = request.form['name'].strip()
        mgmt_token = request.form['mgmt_token'].strip()

        print(mgmt_token)

        file = db.session.query(File).filter_by(filename=name).first()

        if file is None:
            flash("File not found, sorry.")
            return redirect(url_for("index"))
        
        if worker.check_hash(mgmt_token, file.mgmt):
            db.session.delete(file)
            os.remove(os.path.join(config['local_data'], name))
            db.session.commit()
            flash("File deleted.")
            return redirect(url_for("index"))
        else:
            flash("Management token incorrect.")
            return redirect(url_for("index"))
    else:
        return render_template('delete.html', title='manage')
        
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

