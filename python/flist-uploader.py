import os
import tarfile
import shutil
from flask import Flask, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
from JumpScale import j
from config import config

#
# Theses location should works out-of-box if you use default settings
#
thispath = os.path.dirname(os.path.realpath(__file__))
BASEPATH = os.path.join(thispath, "..")

UPLOAD_FOLDER = os.path.join(BASEPATH, "workdir/distfiles")
FLIST_TEMPDIR = os.path.join(BASEPATH, "workdir/temp")
PUBLIC_FOLDER = os.path.join(BASEPATH, "public/users/")
ALLOWED_EXTENSIONS = set(['.tar.gz'])

print("[+] upload directory: %s" % UPLOAD_FOLDER)
print("[+] flist creation  : %s" % FLIST_TEMPDIR)
print("[+] public directory: %s" % PUBLIC_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    for ext in ALLOWED_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False

def handle_flist(context, filepath, filename):
    username = context['username']

    #
    # checking and extracting files
    #
    target = os.path.join(FLIST_TEMPDIR, filename)
    if os.path.exists(target):
        return uploadError(request, "We are already processing this file.")

    os.mkdir(target)

    # print(t.getnames())
    # ADD SECURITY CHECK

    t = tarfile.open(filepath, "r:gz")
    t.extractall(path=target)

    filescount = len(t.getnames())
    t.close()

    #
    # building flist from extracted files
    #
    dbtemp = '%s.db' % target

    kvs = j.servers.kvs.getRocksDBStore('flist', namespace=None, dbpath=dbtemp)
    f = j.tools.flist.getFlist(rootpath=target, kvs=kvs)
    f.add(target)
    f.upload(config['PRIVATE_ARDB_HOST'], config['PRIVATE_ARDB_PORT'])

    #
    # creating the flist archive
    #
    cleanfilename = filename
    for ext in ALLOWED_EXTENSIONS:
        if cleanfilename.endswith(ext):
            cleanfilename = cleanfilename[:-len(ext)]

    home = os.path.join(PUBLIC_FOLDER, username)
    if not os.path.exists(home):
        os.mkdir(home)

    flistname = "flist-%s.flist" % cleanfilename
    dbpath = os.path.join(home, flistname)

    #
    # UGLY WORKAROUND
    # No way to check if rocksdb have finished yet
    # We waits until tar was correctly able to pack stuff
    # THIS NEED TO BE FIXED
    #
    notGood = True

    while notGood:
        try:
            with tarfile.open(dbpath, "w:gz") as tar:
                tar.add(dbtemp, arcname="")

            notGood = False
        except FileNotFoundError:
            time.sleep(0.1)
            pass

        except Exception:
            return "Someting went wrong, please contact support to report this issue."

    #
    # FIXME: UGLY WORKAROUND
    #

    # with tarfile.open(dbpath, "w:gz") as tar:
    #    tar.add(dbtemp, arcname="")

    # cleaning
    shutil.rmtree(target)
    shutil.rmtree(dbtemp)
    os.unlink(filepath)

    #
    # rendering summary page
    #
    return uploadSuccess(context, flistname, filescount, home)

def uploadSuccess(context, flistname, filescount, home):
    template = os.path.join("success.html")

    username = context['username']
    settings = {
        'username': username,
        'flistname': flistname,
        'filescount': filescount,
        'flisturl': "%s/%s/%s" % (config['PUBLIC_WEBADD'], username, flistname),
        'ardbhost': 'ardb://%s:%d' % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT']),
    }

    readme  = "# %s\n\n" % flistname
    readme += "Source: `%s`\n\n" % settings['flisturl']
    readme += "Storage: `%s`\n" % settings['ardbhost']

    # remove .flist extension
    readmefile = "%s.md" % flistname[:-6]
    readmepath = os.path.join(home, readmefile)

    with open(readmepath, "w") as f:
        f.write(readme)

    return render_template(template, **settings)

def uploadError(context, errstr):
    template = os.path.join("upload.html")
    settings = {
        'username': context['username'],
        'error': errstr
    }

    return render_template(template, **settings)

def uploadDefault(context):
    template = os.path.join("upload.html")
    settings = {'username': context['username']}

    return render_template(template, **settings)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not request.headers.get('X-Iyo-Username'):
        return "Access denied."

    context = {
        'username': request.headers.get('X-Iyo-Username'),
        'organization': ""
    }

    if request.method == 'POST':
        # check if the post request has the file part
        print(request.files)
        if 'file' not in request.files:
            return uploadError(context, "No file found")

        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return uploadError(context, "No file selected")

        print(file.filename)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            target = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(target)

            return handle_flist(context, target, filename)

        else:
            return uploadError(context, "This file is not allowed.")

    return uploadDefault(context)

print("[+] listening")
app.run(host="0.0.0.0", debug=False, threaded=True)
