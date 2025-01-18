from app import app, db, worker
from flask import render_template, request, redirect, url_for

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/paste', methods=['GET', 'POST'])
def paste():
    if request.method == 'POST':    
        try:

            worker.upload_s3(request.files['file'], request.files['file'].filename)
            return "yep"
        except Exception as e:
            print(e)
            return "nope"
    return "Wrong method, buddy."