import datetime
import traceback
import io
import os
import re

import pycmarkgfm as md
from flask import Response, flash, redirect, render_template, request, send_file, url_for, jsonify

from cryptography import fernet
from magic import Magic
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

from app import app, db, worker, info, warn, error, die
from app.models import File, BanList

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return paste(api=True)

    quote, quote_author = worker.get_quote_from_db()
    announcements = worker.get_announcements()

    return render_template(
            "index.html",
            title="home",
            quote=quote,
            quote_author=quote_author,
            announcements=announcements,
            host=request.host,
            max_file_size=app.config["MAX_FILE_SIZE"],
            version=app.config["VERSION"])


@app.route("/paste", methods=["GET", "POST"])
def paste(api=False):
    if request.method == "GET":
        return "Wrong method, use a POST request for this route.", 400

    # fernet key
    key = fernet.Fernet(app.config["ENC_KEY"])

    # Check if a user is banned
    ban_check = db.session.query(BanList).filter_by(ip=request.headers.get("X-Real-IP", request.remote_addr)).first()
    if ban_check is not None:
        return render_template("banned.html", ip=ban_check.ip, date=ban_check.date, reason=ban_check.reason), 403

    # grab detect checkbox status from page, this helps block bots as they check every box
    detect = request.form.get("detect")
    if detect:
        return "Bot traffic detected, scrapers are not permitted on pasted.sh", 403

    # Determine whether we have text or a file
    uploaded_file = request.files.get("file")
    uploaded_text = request.form.get("file")

    # Change it to a filestorage object so we can work with it the same way as uploaded files.
    if uploaded_text:
        current_file = FileStorage(
            stream=io.BytesIO(uploaded_text.encode()),
            filename="paste.txt",
            content_type="text/plain",
        )

    elif uploaded_file:
        current_file = uploaded_file

    else:
        return "No file or text provided, go back and upload a file or enter some text.", 400

    mgmt = worker.create_mgmt_token()

    sample = current_file.stream.read(2048)
    mime = Magic(mime=True).from_buffer(sample)
    current_file.stream.seek(0)  # Reset the stream position after reading for magic

    ext = current_file.filename.split(".")[-1] # type: ignore       # grab the extension
    ext = ext if re.fullmatch(r"[A-Za-z0-9]{1,10}", ext) else "bin" # and then make sure its valid

    if request.form.get("private"):  # If it holds any value at all, we can set it to true.
        private = True
    else:
        private = False

    # Get a free filename
    # (tell the user to email me if it cant find one)
    for _ in range(128):
        filename = f"{worker.name_randomiser()}.{ext}"
        path = os.path.join(app.config["LOCAL_DATA"], filename)

        try:
            dst = open(path, "xb")
        except FileExistsError:
            continue
        break
    else:
        return f"""Sorry, couldn't assign a filename. 
                Please email the site admin with this error message, 
                as pasted is likely close to running out of available filenames.
                {app.config['SITE_ADMIN']}""", 500

    hasher = worker.sha256gen()
    try:
        with dst:
            worker.enc_stream(current_file.stream, dst, key, on_chunk=hasher)
    except Exception:
        os.remove(path)
        raise

    sha256 = hasher.hexdigest()
    filesize = hasher.size

    ok = worker.create_db_entry(
        request.headers.get("X-Real-IP", request.remote_addr),  # IP
        datetime.datetime.now(),  # Date
        filename,  # Filename
        worker.generate_hash(mgmt),  # Hash mgmt token
        filesize,  # Size
        mime,  # MimeType
        sha256,  # SHA256
        private,  # Exclude from recent
    )

    current_file.close()

    if not ok:
        os.remove(os.path.join(app.config["LOCAL_DATA"], filename))
        return "Upload failed. Please try again later.", 500

    if api:
        return jsonify({"mgmt": mgmt, "filename": filename})
    else:
        return render_template(
            "success.html", mgmt=mgmt, filename=filename, host=request.host
        )

@app.route("/<filename>")  # type: ignore
def view(filename):
    if request.method == "GET" or request.method == "HEAD":
        file = db.session.query(File).filter_by(filename=filename).first()
        key = fernet.Fernet(app.config["ENC_KEY"])

        api = False
        if "text/html" not in request.headers.get("Accept", ""):
            api=True

        if file is None:
            return "File not found.", 404

        filesize = file.size

        view = True

        filetype = file.mime.split("/")[
            0
        ]  # Get the type of the file (e.g., text, image, audio)

        url = f"/file/{filename}"

        if api:
            return serve_file(filename)

        is_markdown = False
        content = None
        truncated = False
        try:
            if filetype == "text":
                with open(os.path.join(app.config["LOCAL_DATA"], filename), "rb") as f:
                    # get header, we need to check whether this is new or old style file encryption
                    header = f.read(4)
                    f.seek(0)

                    if header == b'gAAA':   # if the header isnt new-style, use old method
                        if file.size > app.config['MAX_PREVIEW_SIZE']:
                            content = "This file is too large to preview. Please use the download link."
                            truncated = True

                        else:
                            encrypted = f.read()                                    # read full file
                            content = key.decrypt(encrypted)                        # decrypt full file
                            content = content.decode("utf-8", errors="replace")     # decode

                    elif header == b'PST1': # new-style header, way more memory efficient
                        chunk = b''

                        for data in worker.dec_stream(f, key):          # passes data one chunk at a time
                            chunk += data

                            if len(chunk) >= app.config['MAX_PREVIEW_SIZE']:
                                break

                        content = chunk[:app.config['MAX_PREVIEW_SIZE']].decode("utf-8", errors="replace")
                        truncated = file.size > app.config['MAX_PREVIEW_SIZE']

                    else:
                        return f"""
                        Unexpected header found on your file, it's likely its corrupted.
                        Your file is given a new header when encrypted,
                        we expect a header of either b'PST1', or b'gAAA', your file returned neither.
                        This usually indicates a part of your file is missing or corrupted.
                        Please email the site admin if this file was important, we will try to recover it.
                        {app.config['SITE_ADMIN']}
                        """, 500

                    is_markdown = worker.is_markdown(file.filename, content) if truncated is False else False

                    if is_markdown:
                        content = md.gfm_to_html(content) # type: ignore
        except Exception as e:
            error(f"Loading file {filename} failed. See exception printed below.") # log exception
            print(e)
            traceback.print_exc()
            return f"<p>Sorry, something has went really wrong here, please email me with the below info. {app.config["SITE_ADMIN"]}</p>", 500

        return render_template(
            "view.html",
            sha256=file.sha256,
            is_markdown=is_markdown,
            content=content,
            filesize=filesize,
            filetype=filetype,
            mime=file.mime,
            url=url,
            view=view,
            filename=filename,
            title=filename,
            truncated=truncated
        )


@app.route("/file/<filename>")
def serve_file(filename):
    """Serve encrypted files by decrypting and streaming them."""
    file = db.session.query(File).filter_by(filename=filename).first()

    if file is None:
        return "File not found.", 404

    key = fernet.Fernet(app.config["ENC_KEY"])

    mime = worker.is_renderable(file.mime)

    if request.method == "HEAD":        # This is for link previews, only wants headers, dont decrypt file
        resp = Response(mimetype=mime)
        resp.headers["Content-Length"] = str(file.size)
        resp.headers["Accept-Ranges"] = "none"
        return resp

    f = None
    try:
        f = open(os.path.join(app.config["LOCAL_DATA"], filename), "rb")

        # get header, we need to check whether this is new or old style file encryption
        header = f.read(4)
        f.seek(0)

        if header == b'PST1':                   # if we are in new-style, then stream the file
            chunk = worker.dec_stream(f, key)
            first = next(chunk, b'')            # check the first chunk now, so we can see if file is corrupt

            def generate():
                try:
                    if first:
                        yield first
                    yield from chunk
                except Exception as e:
                    error(f"Streaming {filename} failed part-way through. File may be corrupt.")
                    raise
                finally:
                    f.close()

            resp = Response(generate(), mimetype=mime)
            resp.headers["Content-Length"] = str(file.size)     # plaintext size from db
            resp.headers["Accept-Ranges"] = "none"              # no range while streaming
            resp.headers.set("Content-Disposition", "inline", filename=filename)
            return resp

        elif header == b'gAAA':
            data = key.decrypt(f.read())
            f.close()
            return send_file(io.BytesIO(data), as_attachment=False, download_name=filename, mimetype=mime)

        else:
            f.close()
            error(f"Unexpected header found on file {filename}, this file is likely corrupted.")
            return "Unexpected header on file, unable to decrypt. File is likely corrupted.", 500

    except Exception as e:
        if f:
            f.close()
        error(f"Failed to serve file {filename}. See traceback below.")
        print(e)
        traceback.print_exc()
        return f"""
                Sorry, something happened that I don't have an explanation for. 
                Please try again, 
                if this keeps happening, email the site admin. 
                {app.config["SITE_ADMIN"]}
                """, 500


@app.route("/delete", methods=["GET", "POST"])
def delete():
    if request.method == "POST":
        name = request.form["name"].strip()
        mgmt_token = request.form["mgmt_token"].strip()

        if len(mgmt_token.encode()) > 72:
            return "Management token incorrect.", 400

        file = db.session.query(File).filter_by(filename=name).first()

        if file is None:
            return "File not found", 404

        if worker.check_hash(mgmt_token, file.mgmt):
            db.session.delete(file)
            db.session.commit()
            try:
                os.remove(os.path.join(app.config["LOCAL_DATA"], name))
            except FileNotFoundError:
                pass
                return "Could not remove file, file is not present on local storage directory, removed from DB."

            return "File deleted."
        else:
            return "Management token incorrect.", 400
    else:
        return render_template("delete.html", title="manage")


### Render-Only Routes below ###


@app.route("/faq")
def faq():
    return render_template("faq.html", title="faq")


@app.route("/tos")
def tos():
    return render_template("tos.html", title="ToS")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", title="Privacy Policy")

# Handlers

@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    flash("File too large, try something smaller.")
    return redirect(url_for("index"))

@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp