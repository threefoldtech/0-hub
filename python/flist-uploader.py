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
import pytoml as toml
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

def dummy1(dirobj, type, name, args, key):
    pass

def dummy2(dirobj, type, name, subobj, args):
    pass

def mkflist(directory, target):
    #
    # Precision: since 'compact_range', this is probably
    # not needed anymore, but need more tests to confirm.
    #

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

        except FileNotFoundError as e:
            print("Workaround, not good")
            print(e)
            time.sleep(0.1)
            pass

        except Exception:
            return None

    #
    # FIXME: UGLY WORKAROUND
    #
    return True

def handle_flist_upload(f):
    print("[+] populating contents")
    f.populate()

    # this is a workaround to ensure file are written
    # and not in a unstable state
    # this access 'protected' class member, this should be
    # improved
    print("[+] compacting db")
    f.dirCollection._db.rocksdb.compact_range()

    r = redis.Redis(config['PRIVATE_ARDB_HOST'], config['PRIVATE_ARDB_PORT'])
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
        dirFunction=dummy1,
        fileFunction=procFile,
        specialFunction=dummy2,
        linkFunction=dummy2,
        args=result
    )

def handle_flist(filepath, filename):
    username = request.environ['username']

    #
    # checking and extracting files
    #
    target = os.path.join(FLIST_TEMPDIR, filename)
    if os.path.exists(target):
        return internalRedirect("upload.html", "We are already processing this file.")

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
    try:
        image = dockerclient.images.pull(dockerimage)

    except docker.errors.ImageNotFound:
        variables = {'error': "Docker image not found"}
        return globalTemplate("docker.html", variables)

    command = None

    if not image.attrs['Config']['Cmd'] and not image.attrs['Config']['Entrypoint']:
        command = "/bin/sh"

    print("[+] starting temporary container")
    cn = dockerclient.containers.create(dockerimage, name=dockername, hostname=dockername, command=command)

    print("[+] creating target directory")
    tmpdir = tempfile.TemporaryDirectory(prefix=dockername)

    print("[+] dumping files to: %s" % tmpdir.name)
    subprocess.call(['sh', '-c', 'docker export %s | tar -xpf - -C %s' % (dockername, tmpdir.name)])

    print("[+] creating container entrypoint")
    command = []
    args = []

    if cn.attrs['Config']['Entrypoint']:
        command = cn.attrs['Config']['Entrypoint'][0]
        args = cn.attrs['Config']['Cmd']

    else:
        command = cn.attrs['Config']['Cmd'][0]
        args = cn.attrs['Config']['Cmd'][1:]

    boot = {
        'startup.entry':      {'name': "core.system", 'running_delay': -1},
        'startup.entry.args': {'name': command, 'args': args}
    }

    with open(os.path.join(tmpdir.name, '.startup.toml'), 'w') as f:
        f.write(toml.dumps(boot))

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

    flistname = "%s.flist" % dockerimage.replace(":", "-").replace('/', '-')
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
    return uploadSuccess(flistname, 0, home, "dockers")

def handle_existing_flist(filepath, filename):
    username = request.environ['username']

    #
    # checking and extracting files
    #
    target = os.path.join(FLIST_TEMPDIR, filename)
    if os.path.exists(target):
        return internalRedirect("upload-flist.html", "We are already processing this file.")

    os.mkdir(target)

    print("[+] extracting database")
    t = tarfile.open(filepath, "r:gz")
    t.extractall(path=target)
    t.close()

    #
    # parsing database
    #
    kvs = j.data.kvs.getRocksDBStore('flist', namespace=None, dbpath=target)
    f = j.tools.flist.getFlist(rootpath=target, kvs=kvs)

    r = redis.Redis(config['PRIVATE_ARDB_HOST'], config['PRIVATE_ARDB_PORT'])
    pipe = r.pipeline()

    def procFile(dirobj, type, name, subobj, args):
        for chunk in subobj.attributes.file.blocks:
            rkey = chunk.hash.decode('utf-8')
            pipe.exists(rkey)

    result = []
    f.walk(
        dirFunction=dummy1,
        fileFunction=procFile,
        specialFunction=dummy2,
        linkFunction=dummy2,
        args=result
    )

    result = pipe.execute()
    shutil.rmtree(target)

    if False in result:
        os.unlink(filepath)
        return internalRedirect("upload-flist.html", "Sorry, some files was not found in the backend.")

    home = os.path.join(PUBLIC_FOLDER, username)
    if not os.path.exists(home):
        os.mkdir(home)

    dbpath = os.path.join(home, filename)
    os.rename(filepath, dbpath)

    return uploadSuccess(filename, 0, home)

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

        kvs = j.data.kvs.getRocksDBStore(name='flist', namespace=None, dbpath=workdir.name)
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
    kvs = j.data.kvs.getRocksDBStore(name='flist', namespace=None, dbpath=target.name)
    ktarget = j.tools.flist.getFlist(rootpath='/', kvs=kvs)

    merger.add_destination(ktarget)
    merger.merge()

    home = os.path.join(PUBLIC_FOLDER, username)
    if not os.path.exists(home):
        os.mkdir(home)

    flist = os.path.join(home, targetname)

    #
    # Release new build
    #
    if not mkflist(target.name, flist):
        return "Someting went wrong, please contact support to report this issue."

    return True

def flist_listing(source):
    target = tempfile.TemporaryDirectory(prefix="listing-")

    print("[+] Unpacking flist database")
    t = tarfile.open(source, "r:gz")
    t.extractall(path=target.name)
    t.close()

    kvs = j.data.kvs.getRocksDBStore(name='flist', namespace=None, dbpath=target.name)
    ktarget = j.tools.flist.getFlist(rootpath='/', kvs=kvs)

    contents = {
        'content': [],
        'regular': 0,
        'directory': 0,
        'symlink': 0,
        'special': 0
    }

    def procDir(dirobj, type, name, args, key):
        contents['directory'] += 1
        contents['content'].append({'path': "%s/%s" % (dirobj.dbobj.location, name), 'size': 0})

    def procSpecial(dirobj, type, name, subobj, args):
        contents['special'] += 1
        contents['content'].append({'path': "/%s/%s" % (dirobj.dbobj.location, name), 'size': 0})

    def procFile(dirobj, type, name, subobj, args):
        contents['regular'] += 1
        contents['content'].append({'path': "/%s/%s" % (dirobj.dbobj.location, name), 'size': dirobj.dbobj.size})

    def procLink(dirobj, type, name, subobj, args):
        contents['symlink'] += 1
        contents['content'].append({'path': "/%s/%s" % (dirobj.dbobj.location, name), 'size': 0})

    print("[+] parsing database")
    result = []
    ktarget.walk(
        dirFunction=procDir,
        fileFunction=procFile,
        specialFunction=procSpecial,
        linkFunction=procLink,
        args=result
    )

    return contents

def uploadSuccess(flistname, filescount, home, username=None):
    if username is None:
        username = request.environ['username']

    settings = {
        'username': username,
        'flistname': flistname,
        'filescount': filescount,
        'flisturl': "%s/%s/%s" % (config['PUBLIC_WEBADD'], username, flistname),
        'ardbhost': 'ardb://%s:%d' % (config['PUBLIC_ARDB_HOST'], config['PUBLIC_ARDB_PORT']),
    }

    return globalTemplate("success.html", settings)

def internalRedirect(target, error=None):
    settings = {
        'username': request.environ['username'],
    }

    if error:
        settings['error'] = error

    return globalTemplate(target, settings)


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
            return internalRedirect("upload.html", "No file found")

        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return internalRedirect("upload.html", "No file selected")

        print(file.filename)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            print("[+] saving file")
            target = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(target)

            return handle_flist(target, filename)

        else:
            return internalRedirect("upload.html", "This file is not allowed.")

    return internalRedirect("upload.html")

@app.route('/upload-flist', methods=['GET', 'POST'])
def upload_file_flist():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return internalRedirect("upload-flist.html", "No file found")

        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            return internalRedirect("upload-flist.html", "No file selected")

        print(file.filename)
        if file and file.filename.endswith(".flist"):
            filename = secure_filename(file.filename)

            print("[+] saving file")
            target = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(target)

            return handle_existing_flist(target, filename)

        else:
            return internalRedirect("upload-flist.html", "This file is not allowed.")

    return internalRedirect("upload-flist.html")

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

@app.route('/api/inspect/<username>/<flist>')
def api_inspect(username, flist):
    target = os.path.join(PUBLIC_FOLDER, username)

    if not os.path.isdir(target):
        return "User not found"

    sourcefile = os.path.join(target, flist)
    if not os.path.isfile(sourcefile):
        return "Source not found"

    contents = flist_listing(sourcefile)

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/rename/<source>/<destination>')
def api_rename(source, destination):
    if not request.environ['username']:
        return "Access denied."

    if not destination.endswith(".flist"):
        return "Invalid destination name"

    username = request.environ['username']
    target = os.path.join(PUBLIC_FOLDER, username)

    if not os.path.isdir(target):
        return "User not found"

    sourcefile = os.path.join(target, source)
    if not os.path.isfile(sourcefile):
        return "Source not found"

    destfile = os.path.join(target, destination)
    os.rename(sourcefile, destfile)

    return "OK"

@app.route('/api/delete/<source>')
def api_delete(source):
    if not request.environ['username']:
        return "Access denied."

    username = request.environ['username']
    target = os.path.join(PUBLIC_FOLDER, username)

    if not os.path.isdir(target):
        return "User not found"

    sourcefile = os.path.join(target, source)
    if not os.path.isfile(sourcefile):
        return "Source not found"

    os.unlink(sourcefile)

    return "OK"

@app.route('/merge', methods=['GET', 'POST'])
def flist_merge():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        data = flist_merge_post()

        if data['error']:
            return internalRedirect("merge.html", data['error'])

        return handle_merge(data['sources'], data['targetname'])

    # Merge page
    return internalRedirect("merge.html")

@app.route('/docker-convert', methods=['GET', 'POST'])
def docker_handler():
    if not request.environ['username']:
        return "Access denied."

    if request.method == 'POST':
        if not request.form.get("docker-input"):
            return internalRedirect("docker.html", "Missing docker image name")

        return handle_docker_import(request.form.get("docker-input"))

    # Docker page
    return internalRedirect("docker.html")

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
