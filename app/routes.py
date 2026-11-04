import datetime
import io
import os

import pycmarkgfm as md
from cryptography import fernet
from flask import (
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from magic import Magic
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

from app import app, db, worker
from app.models import File, BanList

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return paste(api=True)

    quote, quote_author = worker.get_quote_from_db()
    announcements = worker.get_announcements()

    resp = make_response(
        render_template(
            "index.html",
            title="home",
            quote=quote,
            quote_author=quote_author,
            announcements=announcements,
            host=request.host,
            max_file_size=app.config["MAX_FILE_SIZE"],
            version=app.config["VERSION"],
        )
    )
    resp.set_cookie("browserIdent", "1")

    return resp


@app.route("/paste", methods=["GET", "POST"])
def paste(api=False):
    if request.method == "GET":
        return "Wrong method, use a POST request for this route."

    # Check if a user is banned
    ban_check = db.session.query(BanList).filter_by(ip=request.remote_addr).first()
    if ban_check != None:
        return render_template("banned.html", ip=ban_check.ip, date=ban_check.date, reason=ban_check.reason)

    # Get fernet key
    key = fernet.Fernet(app.config["ENC_KEY"])

    # grab detect checkbox status from page, this helps block bots as they usually check every box
    detect = request.form.get("detect")
    if detect:
        return "Bot traffic detected. Bots are not permitted to upload to pasted.sh", 403

    try:
        # Determine whether we have text or a file
        uploaded_file = request.files.get("file")
        uploaded_text = request.form.get("file")

        # Change it to a filestorage object so we can work with it the same way as uploaded files.
        if uploaded_text:
            current_file = FileStorage(
                stream=io.BytesIO(uploaded_text.encode()),
                filename='p.txt',
                content_type="text/plain" # force text/plain
            )

        elif uploaded_file:
            current_file = uploaded_file

        else:
            flash("No file or text provided.")
            return redirect(url_for("index"))

        # Clear these variables to save memory
        del uploaded_file
        del uploaded_text

        mgmt = worker.create_mgmt_token()

        mime = Magic(mime=True).from_buffer(current_file.stream.read(2048))  # try and get mimetype
        current_file.stream.seek(0)  # Reset the stream position after reading for magic

        ext = current_file.filename.split(".")[-1]  # type: ignore

        if ext == "":
            ext = "bin"  # Default to bin if no extension provided, just to be safe.

        # find usable filename
        c = 0 # counter for max retries
        while True:
            filename = worker.name_randomiser() + "." + ext  # Just in case, we dont want any funny business with the filename.
            if c < 128 and db.session.query(File).filter_by(filename=filename).first() is None:
                break
            elif c >= 128:
                return f"""We couldn't find you a filename, it's possible that pasted may have run out of, or be close to running out of 4 character file names. 
                Please E-mail {app.config['SITE_ADMIN']} and say you got this message.""", 500
            else:
                c+=1


        filesize = current_file.seek(0, os.SEEK_END)
        current_file.seek(0)

        # Check if file should be made private
        private = False
        if request.form.get("private"):
            private = True

        # encrypt the file
        encrypted_content = key.encrypt(current_file.read())

        # save the encrypted content to a filestorage object
        current_file = FileStorage(
            stream=io.BytesIO(encrypted_content),
            filename=current_file.filename,
            content_type=current_file.content_type,
        )
        current_file.seek(0)

        # We will save the file before we add it to the db,
        # it'll get cleaned up if the upload fails.
        worker.save_file(current_file, filename)

        ok = worker.create_db_entry(
            request.remote_addr,  # IP
            datetime.datetime.now(),  # Date
            filename,  # Filename
            worker.generate_hash(mgmt),  # Hash mgmt token
            filesize,  # Size
            mime,  # MimeType
            worker.sha256gen(current_file),  # SHA256
            private,  # Exclude from recent
            False,
        )

        current_file.close()

        if not ok:
            os.remove(os.path.join(app.config["LOCAL_DATA"], filename))
            return "Sorry, upload failed. Please try again later", 500

        if api:
            return {"mgmt": mgmt, "filename": filename}
        else:
            return render_template(
                "success.html", mgmt=mgmt, filename=filename, host=request.host
            )
    except RequestEntityTooLarge:
        flash("File too large, try something smaller.")
        return redirect(url_for("index"))


@app.route("/<filename>")  # type: ignore
def view(filename):
    if request.method == "GET":
        api = False if request.cookies.get("browserIdent") else True
        file = db.session.query(File).filter_by(filename=filename).first()
        key = fernet.Fernet(app.config["ENC_KEY"])

        if file is None:
            flash("File not found, sorry.")
            return redirect(url_for("index"))

        filesize = file.size

        view = True

        filetype = file.mime.split("/")[
            0
        ]  # Get the type of the file (e.g., text, image, audio)

        url = f"/file/{filename}"

        is_markdown = False
        content = None
        try:
            # If it's text, we will pass the content to the template, otherwise we'll just pass the url and let the browser handle it.
            if filetype == "text":
                with open(os.path.join(app.config["LOCAL_DATA"], filename), "rb") as f:
                    encrypted = f.read()
                    content = key.decrypt(encrypted)
                    content = content.decode(
                        "utf-8", errors="replace"
                    )  # Just in case, we dont want the page to break if the text is not valid utf-8.
                    is_markdown = worker.is_markdown(file.filename, content)
                    print(is_markdown)
                    if is_markdown:
                        content = md.gfm_to_html(content)
        except Exception as e:
            return f"""
                <p>Sorry, something has went really wrong here, please email me with the below info. {app.config["SITE_ADMIN"]}</p>
                <pre>{str(e)}</pre>
                """

        if api:
            return serve_file(filename)
        else:
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
            )


@app.route("/file/<filename>")
def serve_file(filename):
    """Serve encrypted files by decrypting and streaming them."""
    file = db.session.query(File).filter_by(filename=filename).first()
    key = fernet.Fernet(app.config["ENC_KEY"])

    if file is None or file.deleted:
        flash("File not found, sorry.")
        return redirect(url_for("index"))

    try:
        with open(os.path.join(app.config["LOCAL_DATA"], filename), "rb") as f:
            encrypted_content = f.read()
            decrypted_content = key.decrypt(encrypted_content)

        mime = worker.is_renderable(file.mime)

        download=False
        if mime == "download":
            mime="application/octet-stream"
            download=True

        return send_file(
            io.BytesIO(decrypted_content),
            as_attachment=download,
            mimetype=mime,
            download_name=filename
        )
    except Exception as e:
        return f"""
                <p>Sorry, something has went really wrong here, please email me with the below info. {app.config["SITE_ADMIN"]}</p>
                <pre>{str(e)}</pre>
                """


@app.route("/delete", methods=["GET", "POST"])
def delete():
    if request.method == "POST":
        name = request.form["name"].strip()
        mgmt_token = request.form["mgmt_token"].strip()

        file = db.session.query(File).filter_by(filename=name).first()

        if file is None:
            flash("File not found, sorry.")
            return redirect(url_for("index"))

        if worker.check_hash(mgmt_token, file.mgmt):
            db.session.delete(file)
            os.remove(os.path.join(app.config['LOCAL_DATA'], name))
            db.session.commit()
            flash("File deleted.")
            return redirect(url_for("index"))
        else:
            flash("Management token incorrect.")
            return redirect(url_for("index"))
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
