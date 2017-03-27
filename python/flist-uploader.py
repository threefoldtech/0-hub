import os
import tarfile
import shutil
from flask import Flask, request, redirect, url_for
from werkzeug.utils import secure_filename
from JumpScale import j

UPLOAD_FOLDER = 'CHANGEME/distfiles'
ALLOWED_EXTENSIONS = set(['.tar.gz', '.md'])
FLIST_TEMPDIR = 'CHANGEME/temp'
STATIC_FOLDER = 'CHANGEME/users'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ARDB_HOST = CHANGEME
ARDB_PORT = CHANGEME

def allowed_file(filename):
    for ext in ALLOWED_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False

def handle_flist(request, filepath, filename):
    t = tarfile.open(filepath, "r:gz")

    username = request.headers['X-Iyo-Username']

    # print(t.getnames())
    # ADD SECURITY CHECK

    target = os.path.join(FLIST_TEMPDIR, filename)
    if os.path.exists(target):
        return "Already processing"

    os.mkdir(target)
    t.extractall(path=target)

    dbtemp = '%s.db' % target

    kvs = j.servers.kvs.getRocksDBStore('flist', namespace=None, dbpath=dbtemp)
    f = j.tools.flist.getFlist(rootpath=target, kvs=kvs)
    f.add(target)
    hashs = f.upload(ARDB_HOST, ARDB_PORT)

    cleanfilename = filename
    for ext in ALLOWED_EXTENSIONS:
        if cleanfilename.endswith(ext):
            cleanfilename = cleanfilename[:-len(ext)]

    home = os.path.join(STATIC_FOLDER, username)
    if not os.path.exists(home):
        os.mkdir(home)

    dbpath = "%s/flist-%s.tar.gz" % (home, cleanfilename)

    with tarfile.open(dbpath, "w:gz") as tar:
        tar.add(dbtemp, arcname="")

    # cleaning
    shutil.rmtree(target)
    shutil.rmtree(dbtemp)

    output  = "<pre>"
    output += "--- DEBUG PAGE ---\n\n"
    output += "OK: %d files found.\n" % len(t.getnames())
    output += "Your flist is available at: http://CHANGEME/%s" % username
    output += "</pre>"

    return output

def uploadTemplate(request):
    with open("static/upload.html", "r") as f:
        content = f.read()

    content = content.replace("%Username%", request.headers['X-Iyo-Username'])

    return content

def uploadError(request, errstr):
    print("Error: %s" % errstr)
    content = uploadTemplate(request)

    content = content.replace("<!-- Error Template", "")
    content = content.replace("%Error Message%", errstr)
    content = content.replace("End Error Template -->", "")

    return content

def uploadDefault(request):
    print("Default Upload page")
    content = uploadTemplate(request)
    content = content.replace("%Error Message%", "")

    return content

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not request.headers.get('X-Iyo-Username'):
        return "Access denied."

    if request.method == 'POST':
        # check if the post request has the file part
        print(request.files)
        if 'file' not in request.files:
            return uploadError(request, "No file found")

        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return uploadError(request, "No file selected")

        print(file.filename)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            target = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(target)

            return handle_flist(request, target, filename)

        else:
            return uploadError(request, "This file is not allowed.")

    return uploadDefault(request)

app.run(host="0.0.0.0", debug=True, threaded=True)
