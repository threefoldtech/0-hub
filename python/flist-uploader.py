import os
import tarfile
import shutil
import time
import datetime
import json
import hashlib
import tempfile
import redis
import g8storclient
import docker
import uuid
import subprocess
from flask import Flask, request, redirect, url_for, render_template, abort, make_response, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.wrappers import Request
from js9 import j
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

dockerclient = docker.from_env()

print("[+] upload directory: %s" % UPLOAD_FOLDER)
print("[+] flist creation  : %s" % FLIST_TEMPDIR)
print("[+] public directory: %s" % PUBLIC_FOLDER)

class IYOChecker(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        req = Request(environ, shallow=True)
        environ['username'] = None

        if req.headers.get('X-Iyo-Username'):
            environ['username'] = req.headers['X-Iyo-Username']

        return self.app(environ, start_response)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.wsgi_app = IYOChecker(app.wsgi_app)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.url_map.strict_slashes = False

def allowed_file(filename):
    for ext in ALLOWED_EXTENSIONS:
        if filename.endswith(ext):
            return True

    return False

def globalTemplate(filename, args):
    args['debug'] = config['DEBUG']
    return render_template(filename, **args)

def mkflist(directory, target):
    #
    # UGLY WORKAROUND
    # No way to check if rocksdb have finished yet
    # We waits until tar was correctly able to pack stuff
    # THIS NEED TO BE FIXED
    #
    notGood = True

    while notGood:
        try:
            with tarfile.open(target, "w:gz") as tar:
                tar.add(directory, arcname="")

            notGood = False
        except FileNotFoundError:
            time.sleep(0.1)
            pass

        except Exception:
            return None

    #
    # FIXME: UGLY WORKAROUND
    #
    return True

def handle_flist_upload(f):
    f.populate()

    r = redis.Redis(config['PRIVATE_ARDB_HOST'], config['PRIVATE_ARDB_PORT'])
    def procDir(dirobj, type, name, args, key):
        pass

    def procLink(dirobj, type, name, subobj, args):
        pass

    def procSpecial(dirobj, type, name, subobj, args):
        pass

    def procFile(dirobj, type, name, subobj, args):
        fullpath = "%s/%s/%s" % (f.rootpath, dirobj.dbobj.location, name)
        print("[+] uploading: %s" % fullpath)
        hashs = g8storclient.encrypt(fullpath)

        if hashs is None:
            return

        for hash in hashs:
            if not r.exists(hash['hash']):
                r.set(hash['hash'], hash['data'])

    print("[+] uploading contents")
    result = []
    f.walk(
        dirFunction=procDir,
        fileFunction=procFile,
        specialFunction=procSpecial,
        linkFunction=procLink,
        args=result
    )

def handle_flist(filepath, filename):
    username = request.environ['username']

    #
    # checking and extracting files
    #
    target = os.path.join(FLIST_TEMPDIR, filename)
    if os.path.exists(target):
        return uploadError("We are already processing this file.")

    os.mkdir(target)

    # print(t.getnames())
    # ADD SECURITY CHECK

    print("[+] extracting files")
    t = tarfile.open(filepath, "r:*")
    t.extractall(path=target)

    filescount = len(t.getnames())
    t.close()

    #
    # building flist from extracted files
    #
    dbtemp = '%s.db' % target

    print("[+] preparing flist")
    kvs = j.data.kvs.getRocksDBStore('flist', namespace=None, dbpath=dbtemp)
    f = j.tools.flist.getFlist(rootpath=target, kvs=kvs)
    f.add(target, excludes=[".*\.pyc", ".*__pycache__"])

    handle_flist_upload(f)
    # f.upload(config['PRIVATE_ARDB_HOST'], config['PRIVATE_ARDB_PORT'])

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

    flistname = "%s.flist" % cleanfilename
    dbpath = os.path.join(home, flistname)

    if not mkflist(dbtemp, dbpath):
        return "Someting went wrong, please contact support to report this issue."

    # cleaning
    shutil.rmtree(target)
    shutil.rmtree(dbtemp)
    os.unlink(filepath)

    #
    # rendering summary page
    #
    return uploadSuccess(flistname, filescount, home)

def handle_docker_import(dockerimage):
    dockername = uuid.uuid4().hex
    print("[+] temporary docker name: %s" % dockername)

    if ":" not in dockerimage:
        dockerimage = "%s:latest" % dockerimage

    print("[+] pulling image: %s" % dockerimage)
    image = dockerclient.images.pull(dockerimage)

    print("[+] starting temporary container")
    cn = dockerclient.containers.create(dockerimage, name=dockername, hostname=dockername)

    print("[+] creating target directory")
    tmpdir = tempfile.TemporaryDirectory(prefix=dockername)

    print("[+] dumping files to: %s" % tmpdir.name)
    subprocess.call(['sh', '-c', 'docker export %s | tar -xpf - -C %s' % (dockername, tmpdir.name)])

    print("[+] parsing the flist")
    flistdir = tempfile.TemporaryDirectory(prefix="flist-db-%s" % dockername)
    kvs = j.data.kvs.getRocksDBStore('flist', namespace=None, dbpath=flistdir.name)
    f = j.tools.flist.getFlist(rootpath=tmpdir.name, kvs=kvs)
    f.add(tmpdir.name, excludes=[".*\.pyc", ".*__pycache__"])

    handle_flist_upload(f)

    print("[+] creating the flist file")
    home = os.path.join(PUBLIC_FOLDER, "dockers")
    if not os.path.exists(home):
        os.mkdir(home)

    flistname = "%s.flist" % dockerimage.replace(":", "-")
    dbpath = os.path.join(home, flistname)

    if not mkflist(flistdir.name, dbpath):
        return "Someting went wrong, please contact support to report this issue."

    print("[+] cleaning temporary files")
    tmpdir.cleanup()
    flistdir.cleanup()

    print("[+] destroying the container")
    cn.remove(force=True)

    print("[+] cleaning up the docker image")
    dockerclient.images.remove(dockerimage, force=True)

    variables = {}
    return uploadSuccess(dockerimage, 0, home)

def handle_merge(sources, targetname):
    status = flist_merging(sources, targetname)

    if not status == True:
        variables = {'error': "Something went wrong, please contact support"}
        return globalTemplate("merge.html", variables)

    username = request.environ['username']
    home = os.path.join(PUBLIC_FOLDER, username)

    return uploadSuccess(targetname, 0, home)

def flist_merging(sources, targetname):
    items = {}
    merger = j.tools.flist.get_merger()
    username = request.environ['username']

    #
    # Extracting flists to distinct directories
    #
    for source in sources:
        workdir = tempfile.TemporaryDirectory(prefix="merge-")

        print("[+] %s: %s" % (source, workdir.name))
        filepath = os.path.join(PUBLIC_FOLDER, source)

        t = tarfile.open(filepath, "r:*")
        t.extractall(path=workdir.name)
        t.close()

        kvs = j.servers.kvs.getRocksDBStore(name='flist', namespace=None, dbpath=workdir.name)
        kdb = j.tools.flist.getFlist(rootpath=workdir.name, kvs=kvs)
        merger.add_source(kdb)

        items[source] = {
            'workdir': workdir,
            'kvs': kvs,
            'kdb': kdb
        }

    #
    # Merging sources
    #
    target = tempfile.TemporaryDirectory(prefix="merge-target-")
    kvs = j.servers.kvs.getRocksDBStore(name='flist', namespace=None, dbpath=target.name)
    ktarget = j.tools.flist.getFlist(rootpath='/', kvs=kvs)

    merger.add_destination(ktarget)
    merger.merge()

    flist = os.path.join(PUBLIC_FOLDER, username, targetname)

    #
    # Release new build
    #
    if not mkflist(target.name, flist):
        return "Someting went wrong, please contact support to report this issue."

    return True


def uploadSuccess(flistname, filescount, home):
    username = request.environ['username']
    settings = {
        'username': username,
        'flistname': flistname,
        'filescount': filescount,
        'flisturl': "%s/%s/%s" % (config['PUBLIC_WEBADD'], username, flistname),
        'ardbhost': 'ardb://%s:%d' % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT']),
    }

    return globalTemplate("success.html", settings)

def uploadError(errstr):
    settings = {
        'username': request.environ['username'],
        'error': errstr
    }

    return globalTemplate("upload.html", settings)

def uploadDefault():
    settings = {'username': request.environ['username']}

    return globalTemplate("upload.html", settings)


#
# flist operation
#
def flist_md5(username, flistname):
    hash_md5 = hashlib.md5()
    fname = os.path.join(PUBLIC_FOLDER, username, flistname)

    print("[+] md5: %s\n" % fname)

    if not os.path.isfile(fname):
        return None

    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()

#
# navigation
#
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return uploadError("No file found")

        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return uploadError("No file selected")

        print(file.filename)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            print("[+] saving file")
            target = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(target)

            return handle_flist(target, filename)

        else:
            return uploadError("This file is not allowed.")

    return uploadDefault()

@app.route('/')
def show_users():
    dirs = sorted(os.listdir(PUBLIC_FOLDER))

    variables = {
        'officials': [],
        'contributors': []
    }

    for dir in dirs:
        if dir in config['PUBLIC_IGNORE']:
            continue

        if dir in config['PUBLIC_OFFICIALS']:
            variables['officials'].append(dir)

        else:
            variables['contributors'].append(dir)

    return globalTemplate("users.html", variables)

@app.route('/<username>')
def show_user(username):
    path = os.path.join(PUBLIC_FOLDER, username)
    if not os.path.exists(path):
        abort(404)

    files = sorted(os.listdir(path))

    variables = {
        'targetuser': username,
        'files': []
    }

    for file in files:
        stat = os.stat(os.path.join(PUBLIC_FOLDER, username, file))

        updated = datetime.datetime.fromtimestamp(int(stat.st_mtime))

        variables['files'].append({
            'name': file,
            'size': "%.2f KB" % ((stat.st_size) / 1024),
            'updated': updated,
        })

    return globalTemplate("user.html", variables)

#
# flist request
#

@app.route('/<username>/<flist>.md')
def show_flist_md(username, flist):
    path = os.path.join(PUBLIC_FOLDER, username, flist)
    if not os.path.exists(path):
        abort(404)

    variables = {
        'targetuser': username,
        'flistname': flist,
        'flisturl': "%s/%s/%s" % (config['PUBLIC_WEBADD'], username, flist),
        'ardbhost': 'ardb://%s:%d' % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT']),
        'checksum': flist_md5(username, flist)
    }

    return globalTemplate("preview.html", variables)

@app.route('/<username>/<flist>.txt')
def show_flist_txt(username, flist):
    path = os.path.join(PUBLIC_FOLDER, username, flist)
    if not os.path.exists(path):
        abort(404)

    text  = "File:     %s\n" % flist
    text += "Uploader: %s\n" % username
    text += "Source:   %s/%s/%s\n" % (config['PUBLIC_WEBADD'], username, flist)
    text += "Storage:  ardb://%s:%d\n" % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT'])
    text += "Checksum: %s\n" % flist_md5(username, flist)

    response = make_response(text)
    response.headers["Content-Type"] = "text/plain"

    return response

@app.route('/<username>/<flist>.json')
def show_flist_json(username, flist):
    path = os.path.join(PUBLIC_FOLDER, username, flist)
    if not os.path.exists(path):
        abort(404)

    data = {
        'flist': flist,
        'uploader': username,
        'source': "%s/%s/%s" % (config['PUBLIC_WEBADD'], username, flist),
        'storage': "ardb://%s:%d" % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT']),
        'checksum': flist_md5(username, flist)
    }

    response = make_response(json.dumps(data) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/<username>/<flist>.flist')
def download_flist(username, flist):
    source = os.path.join(PUBLIC_FOLDER, username)
    filename = "%s.flist" % flist

    return send_from_directory(directory=source, filename=filename)

@app.route('/<username>/<flist>.flist.md5')
def checksum_flist(username, flist):
    hash = flist_md5(username, "%s.flist" % flist)
    if not hash:
        abort(404)

    response = make_response(hash + "\n")
    response.headers["Content-Type"] = "text/plain"

    return response

@app.route('/api/list')
def api_list():
    root = sorted(os.listdir(PUBLIC_FOLDER))
    output = []

    for user in root:
        target = os.path.join(PUBLIC_FOLDER, user)

        # ignore files (eg: .keep file)
        if not os.path.isdir(target):
            continue

        flists = sorted(os.listdir(target))
        for flist in flists:
            output.append("%s/%s" % (user, flist))

    response = make_response("\n".join(output) + "\n")
    response.headers["Content-Type"] = "text/plain"

    return response

@app.route('/merge', methods=['GET', 'POST'])
def flist_merge():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        data = flist_merge_post()

        if data['error']:
            variables = {'error': data['error']}
            return globalTemplate("merge.html", variables)

        return handle_merge(data['sources'], data['targetname'])

    # Merge page
    variables = {}
    return globalTemplate("merge.html", variables)

@app.route('/docker', methods=['GET', 'POST'])
def docker_handler():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        if not request.form.get("docker-input"):
            variables = {'error': "Missing docker image name"}
            return globalTemplate("docker.html", variables)

        return handle_docker_import(request.form.get("docker-input"))

    # Docker page
    variables = {}
    return globalTemplate("docker.html", variables)

def flist_merge_post():
    data = {}
    data['error'] = None

    data['sources'] = request.form.getlist('flists[]')
    if len(data['sources']) == 0:
        data['error'] = "No source selected"
        return data

    data['targetname'] = request.form['name']
    if not data['targetname']:
        data['error'] = "Missing build name"
        return data

    if "/" in data['targetname']:
        data['error'] = "Build name not allowed"
        return data

    if not data['targetname'].endswith('.flist'):
        data['targetname'] += '.flist'

    return data

print("[+] listening")
app.run(host="0.0.0.0", port=5555, debug=config['DEBUG'], threaded=True)
