import os
import sys
import shutil
import json
import threading
import time
import hub.itsyouonline
import hub.threebot
import hub.security
from stat import *
from flask import Flask, Response, request, redirect, url_for, render_template, abort, make_response, send_from_directory, session
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.wrappers import Request
from config import config
from hub.flist import HubPublicFlist, HubFlist
from hub.docker import HubDocker
from hub.notifier import EventNotifier

#
# runtime configuration
# theses location should works out-of-box if you use default settings
#
if not 'userdata-root-path' in config:
    config['userdata-root-path'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../public")

if not 'workdir-root-path' in config:
    config['workdir-root-path'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../workdir")

if not 'public-directory' in config:
    config['public-directory'] = os.path.join(config['userdata-root-path'], "users")

if not 'flist-work-directory' in config:
    config['flist-work-directory'] = os.path.join(config['workdir-root-path'], "temp")

if not 'docker-work-directory' in config:
    config['docker-work-directory'] = os.path.join(config['workdir-root-path'], "temp")

if not 'upload-directory' in config:
    config['upload-directory'] = os.path.join(config['workdir-root-path'], "distfiles")

if not 'allowed-extensions' in config:
    config['allowed-extensions'] = set(['.tar.gz'])

if not 'authentication' in config:
    config['authentication'] = True

print("[+] user  directory : %s" % config['userdata-root-path'])
print("[+] works directory : %s" % config['workdir-root-path'])
print("[+] upload directory: %s" % config['upload-directory'])
print("[+] flist creation  : %s" % config['flist-work-directory'])
print("[+] docker creation : %s" % config['docker-work-directory'])
print("[+] public directory: %s" % config['public-directory'])

#
# pre-check settings
# checking configuration settings needed for runtime
#
hc = HubFlist(config)
if not hc.check():
    print("[-] pre-check: your local configuration seems not correct")
    print("[-] pre-check: please check config.py settings and backend status")
    sys.exit(1)

#
# initialize flask application
#
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.url_map.strict_slashes = False
app.secret_key = os.urandom(24)

# notifications
announcer = EventNotifier()

if config['authentication']:
    hub.itsyouonline.configure(app,
        config['iyo-clientid'], config['iyo-secret'], config['iyo-callback'],
        '/_iyo_callback', None, True, True, 'organization', config['guest-token']
    )

    hub.threebot.configure(app, config['threebot-appid'], config['threebot-privatekey'], config['threebot-seed'])

else:
    hub.itsyouonline.disabled(app)
    config['official-repositories'] = ['Administrator']

    print("[-] -- WARNING -------------------------------------")
    print("[-]                                                 ")
    print("[-]             AUTHENTICATION DISABLED             ")
    print("[-]       FULL CONTROL IS ALLOWED FOR ANYBODY       ")
    print("[-]                                                 ")
    print("[-] This mode should be _exclusively_ used in local ")
    print("[-] development  or  private environment,  never in ")
    print("[-] public  production  environment,  except if you ")
    print("[-] know what you're doing                          ")
    print("[-]                                                 ")
    print("[-] -- WARNING -------------------------------------")


######################################
#
# TEMPLATES MANIPULATION
#
######################################
def allowed_file(filename, validate=False):
    if validate:
        return filename.endswith(".flist")

    for ext in config['allowed-extensions']:
        if filename.endswith(ext):
            return True

    return False

def globalTemplate(filename, args):
    args['debug'] = config['debug']

    if 'username' in session:
        args['username'] = session['username']

    if 'accounts' in session:
        args['accounts'] = session['accounts']

    return render_template(filename, **args)

def file_from_flist(filename):
    cleanfilename = filename
    for ext in config['allowed-extensions']:
        if cleanfilename.endswith(ext):
            cleanfilename = cleanfilename[:-len(ext)]

    return cleanfilename

def uploadSuccess(flistname, filescount, home, username=None):
    if username is None:
        username = session['username']

    settings = {
        'username': username,
        'accounts': session['accounts'],
        'flistname': flistname,
        'filescount': 0,
        'flisturl': "%s/%s/%s" % (config['public-website'], username, flistname),
        'ardbhost': 'zdb://%s:%d' % (config['backend-public-host'], config['backend-public-port']),
    }

    return globalTemplate("success.html", settings)

def internalRedirect(target, error=None, extra={}):
    settings = {
        'username': None,
        'accounts': [],
    }

    settings.update(extra)

    if error:
        settings['error'] = error

    return globalTemplate(target, settings)

def flist_merge_post():
    sources = request.form.getlist('flists[]')
    target = request.form['name']

    return flist_merge_data(sources, target)

def flist_merge_data(sources, target):
    data = {}
    data['error'] = None
    data['sources'] = sources
    data['target'] = target

    if not isinstance(sources, list):
        data['error'] = 'malformed json request'
        return data

    if len(data['sources']) == 0:
        data['error'] = "no source found"
        return data

    # ensure .flist extension to each sources
    fsources = []
    for source in data['sources']:
        # missing username/filename
        if "/" not in source:
            data['error'] = "malformed source filename"
            return data

        cleaned = source if source.endswith(".flist") else source + ".flist"
        fsources.append(cleaned)

    data['sources'] = fsources

    # ensure each sources exists
    for source in data['sources']:
        temp = source.split("/")
        item = HubPublicFlist(config, temp[0], temp[1])

        if not item.file_exists:
            data['error'] = "%s does not exists" % source
            return data

    if not data['target']:
        data['error'] = "missing build (target) name"
        return data

    if "/" in data['target']:
        data['error'] = "build name not allowed"
        return data

    if not data['target'].endswith('.flist'):
        data['target'] += '.flist'

    return data

# tags helper
def tag(name):
    return ".tag-" + name

def utag(username, tagname):
    return username + "/" + tag(tagname)



######################################
#
# ROUTING ACTIONS
#
######################################
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.route('/logout')
def logout():
    hub.security.invalidate()
    return internalRedirect("users.html")

@app.route('/login-method')
def login_method():
    return internalRedirect("logins.html")

@app.route('/login-iyo')
@hub.itsyouonline.force_login()
def login_iyo():
    return internalRedirect("users.html")

@app.route('/token/<token>')
def show_token(token):
    return globalTemplate("token.html", {'token': token, "url": config['public-website']})

@app.route('/upload', methods=['GET', 'POST'])
@hub.security.protected()
def upload_file():
    username = session['username']

    if request.method == 'POST':
        response = api_flist_upload_prepare(request, username)
        return response

        """
        if response['status'] == 'success':
            return uploadSuccess(response['flist'], response['stats'], response['home'])

        if response['status'] == 'error':
            return internalRedirect("upload.html", response['message'])
        """

    return internalRedirect("upload.html")

@app.route('/upload-flist', methods=['GET', 'POST'])
@hub.security.protected()
def upload_file_flist():
    username = session['username']

    if request.method == 'POST':
        response = api_flist_upload(request, username, validate=True)

        if response['status'] == 'success':
            return uploadSuccess(response['flist'], response['stats'], response['home'])

        if response['status'] == 'error':
            return internalRedirect("upload-flist.html", response['message'])

    return internalRedirect("upload-flist.html")

@app.route('/merge', methods=['GET', 'POST'])
@hub.security.protected()
def flist_merge():
    username = session['username']

    if request.method == 'POST':
        data = flist_merge_post()
        print(data)

        if data['error']:
            return internalRedirect("merge.html", data['error'])

        flist = HubPublicFlist(config, username, data['target'])
        status = flist.merge(data['sources'])

        if not status == True:
            variables = {'error': status}
            return globalTemplate("merge.html", variables)

        return uploadSuccess(data['target'], 0, data['target'])

    # Merge page
    return internalRedirect("merge.html")

@app.route('/docker-convert', methods=['GET', 'POST'])
@hub.security.protected()
def docker_handler():
    username = session['username']

    if request.method == 'POST':
        if not request.form.get("docker-input"):
            return internalRedirect("docker.html", "missing docker image name")

        docker = HubDocker(config, announcer)
        print("[+] docker converter id: %s" % docker.jobid)

        job = threading.Thread(target=docker.convert, args=(request.form.get("docker-input"), username, ))
        job.start()

        return internalRedirect("docker-progress.html", None, {'jobid': docker.jobid})

    # Docker page
    return internalRedirect("docker.html")

######################################
#
# ROUTING NAVIGATION
#
######################################
@app.route('/')
def show_users():
    return globalTemplate("users.html", {})

@app.route('/<username>')
def show_user(username):
    flist = HubPublicFlist(config, username, "unknown")
    if not flist.user_exists:
        abort(404)

    return globalTemplate("user.html", {'targetuser': username})

@app.route('/<username>/tags/<tag>')
def show_user_tags(username, tag):
    flist = HubPublicFlist(config, username, "unknown")
    if not flist.user_exists:
        abort(404)

    if not os.path.exists(utag(flist.user_path, tag)):
        abort(404)

    return globalTemplate("tags.html", {'targetuser': username, "targettag": tag})


@app.route('/<username>/<flist>.md')
def show_flist_md(username, flist):
    flist = HubPublicFlist(config, username, flist)
    if not flist.file_exists:
        abort(404)

    variables = {
        'targetuser': username,
        'flistname': flist.filename,
        'flisturl': "%s/%s/%s" % (config['public-website'], username, flist.filename),
        'ardbhost': 'zdb://%s:%d' % (config['backend-public-host'], config['backend-public-port']),
        'checksum': flist.checksum
    }

    return globalTemplate("preview.html", variables)

@app.route('/<username>/<flist>.txt')
def show_flist_txt(username, flist):
    flist = HubPublicFlist(config, username, flist)
    if not flist.file_exists:
        abort(404)

    text  = "File:     %s\n" % flist.filename
    text += "Uploader: %s\n" % username
    text += "Source:   %s/%s/%s\n" % (config['public-website'], username, flist.filename)
    text += "Storage:  zdb://%s:%d\n" % (config['backend-public-host'], config['backend-public-port'])
    text += "Checksum: %s\n" % flist.checksum

    response = make_response(text)
    response.headers["Content-Type"] = "text/plain"

    return response

@app.route('/<username>/<flist>.json')
def show_flist_json(username, flist):
    flist = HubPublicFlist(config, username, flist)
    if not flist.file_exists:
        abort(404)

    data = {
        'flist': flist,
        'uploader': username,
        'source': "%s/%s/%s" % (config['public-website'], username, flist),
        'storage': "zdb://%s:%d" % (config['backend-public-host'], config['backend-public-port']),
        'checksum': flist.checksum
    }

    response = make_response(json.dumps(data) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/<username>/<flist>.flist')
def download_flist(username, flist):
    flist = HubPublicFlist(config, username, flist)
    return send_from_directory(directory=flist.user_path, path=flist.filename)

@app.route('/<username>/tags/<tagname>/<flist>.flist')
def download_flist_tag(username, tagname, flist):
    flist = HubPublicFlist(config, utag(username, tagname), flist)
    return send_from_directory(directory=flist.user_path, path=flist.filename)

@app.route('/<username>/<flist>.flist.md5')
def checksum_flist(username, flist):
    flist = HubPublicFlist(config, username, flist)
    hash = flist.checksum

    if not hash:
        abort(404)

    response = make_response(hash + "\n")
    response.headers["Content-Type"] = "text/plain"

    return response

@app.route('/search')
def search_flist():
    return globalTemplate("search.html", {})


######################################
#
# ROUTING API
#
######################################

#
# Public API
#
@app.route('/api/flist')
def api_list():
    repositories = api_repositories()
    output = []

    for user in repositories:
        target = os.path.join(config['public-directory'], user['name'])

        # ignore files (eg: .keep file)
        if not os.path.isdir(target):
            continue

        flists = sorted(os.listdir(target))
        for flist in flists:
            output.append("%s/%s" % (user['name'], flist))

    response = make_response(json.dumps(output) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/fileslist')
def api_list_files():
    fileslist = api_fileslist()

    response = make_response(json.dumps(fileslist) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/repositories')
def api_list_repositories():
    repositories = api_repositories()

    response = make_response(json.dumps(repositories) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>')
def api_user_contents(username):
    flist = HubPublicFlist(config, username, "unknown")
    if not flist.user_exists:
        abort(404)

    contents = api_user_contents(username, flist.user_path)

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>/tags/<tag>')
def api_user_contents_tags(username, tag):
    flist = HubPublicFlist(config, username, "unknown")
    if not flist.user_exists:
        abort(404)

    if not os.path.exists(flist.user_path + "/.tag-" + tag):
        abort(404)

    contents = api_user_contents_tags(username, flist.user_path, tag)

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>/<flist>', methods=['GET', 'INFO'])
def api_inspect(username, flist):
    flist = HubPublicFlist(config, username, flist)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    if request.method == 'GET':
        contents = api_contents(flist)

    if request.method == 'INFO':
        contents = api_flist_info(flist)

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>/<flist>/light', methods=['GET'])
def api_inspect_light(username, flist):
    flist = HubPublicFlist(config, username, flist)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    contents = api_flist_info(flist)

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>/<flist>/taglink', methods=['GET'])
def api_inspect_taglink(username, flist):
    flist = HubPublicFlist(config, username, flist)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_raw_exists:
        return api_response("source not found", 404)

    target = flist.file_raw_destination()
    if target == None:
        return api_response("could not read tag link", 401)

    contents = {"target": clean_symlink(target)}

    response = make_response(json.dumps(contents) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/<username>/<flist>/metadata')
def api_readme(username, flist):
    flist = HubPublicFlist(config, username, flist)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    readme = api_flist_md(flist)

    response = make_response(json.dumps(readme) + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/api/flist/me', methods=['GET'])
@hub.security.apicall()
def api_my_myself():
    username = session['username']

    return api_response(extra={"username": username})


@app.route('/api/flist/me/<flist>', methods=['GET', 'DELETE'])
@hub.security.apicall()
def api_my_inspect(flist):
    username = session['username']

    if request.method == 'DELETE':
        return api_delete(username, flist)

    return api_inspect(username, flist)

@app.route('/api/flist/me/<source>/link/<linkname>', methods=['GET'])
@hub.security.apicall()
def api_my_symlink(source, linkname):
    username = session['username']

    return api_symlink(username, source, linkname)

@app.route('/api/flist/me/<linkname>/crosslink/<repository>/<sourcename>', methods=['GET'])
@hub.security.apicall()
def api_my_crosssymlink(linkname, repository, sourcename):
    username = session['username']

    return api_cross_symlink(username, repository, sourcename, linkname)

@app.route('/api/flist/me/<linkname>/crosstag/<repository>/<tagname>', methods=['GET'])
@hub.security.apicall()
def api_my_crossstag(linkname, repository, tagname):
    username = session['username']

    return api_symlink_to_tag(username, linkname, repository, tagname)

@app.route('/api/flist/me/<tagname>/<linkname>/tag/<repository>/<sourcename>', methods=['GET', 'DELETE'])
@hub.security.apicall()
def api_my_tag_add(tagname, linkname, repository, sourcename):
    username = session['username']

    if request.method == 'DELETE':
        return api_tag_symlink_delete(username, repository, sourcename, tagname, linkname)

    return api_tag_symlink(username, repository, sourcename, tagname, linkname)

@app.route('/api/flist/me/<source>/rename/<destination>')
@hub.security.apicall()
def api_my_rename(source, destination):
    username = session['username']
    flist = HubPublicFlist(config, username, source)
    destflist = HubPublicFlist(config, username, destination)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    os.rename(flist.target, destflist.target)

    return api_response()

@app.route('/api/flist/me/promote/<sourcerepo>/<sourcefile>/<localname>', methods=['GET'])
@hub.security.apicall()
def api_my_promote(sourcerepo, sourcefile, localname):
    username = session['username']

    return api_promote(username, sourcerepo, sourcefile, localname)

@app.route('/api/flist/me/upload', methods=['POST'])
@hub.security.apicall()
def api_my_upload():
    username = session['username']

    response = api_flist_upload(request, username)
    if response['status'] == 'success':
        if config['debug']:
            return api_response(extra={'name': response['flist'], 'files': response['stats'], 'timing': {}})

        else:
            return api_response(extra={'name': response['flist'], 'files': response['stats']})

    if response['status'] == 'error':
        return api_response(response['message'], 500)

@app.route('/api/flist/me/upload-flist', methods=['POST'])
@hub.security.apicall()
def api_my_upload_flist():
    username = session['username']

    response = api_flist_upload(request, username, validate=True)
    if response['status'] == 'success':
        if config['debug']:
            return api_response(extra={'name': response['flist'], 'files': response['stats'], 'timing': {}})

        else:
            return api_response(extra={'name': response['flist'], 'files': response['stats']})

    if response['status'] == 'error':
        return api_response(response['message'], 500)

@app.route('/api/flist/me/merge/<target>', methods=['POST'])
@hub.security.apicall()
def api_my_merge(target):
    username = session['username']

    sources = request.get_json(silent=True, force=True)
    data = flist_merge_data(sources, target)

    if data['error'] != None:
        return api_response(data['error'], 500)

    flist = HubPublicFlist(config, username, data['target'])
    status = flist.merge(data['sources'])

    if not status == True:
        return api_response(status, 500)

    return api_response()

@app.route('/api/flist/me/docker', methods=['POST'])
@hub.security.apicall()
def api_my_docker():
    username = session['username']

    if not request.form.get("image"):
        return api_response("missing docker image name", 400)

    docker = HubDocker(config, announcer)
    response = docker.convert(request.form.get("image"), username)

    if response['status'] == 'success':
        return api_response(extra={'name': response['flist']})

    if response['status'] == 'error':
        return api_response(response['message'], 500)

    return api_response("unexpected docker convert error", 500)


######################################
#
# API IMPLEMENTATION
#
######################################
def api_delete(username, source):
    flist = HubPublicFlist(config, username, source)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        # delete if it's a tag symlink
        if flist.file_raw_exists:
            os.unlink(flist.file_raw_target)
            return api_response()

        return api_response("source not found", 404)

    # delete regular file
    os.unlink(flist.target)

    return api_response()

def api_symlink(username, source, linkname):
    flist = HubPublicFlist(config, username, source)
    linkflist = HubPublicFlist(config, username, linkname)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    # remove previous symlink if existing
    if os.path.islink(linkflist.target):
        os.unlink(linkflist.target)

    # if it was not a link but a regular file, we don't overwrite
    # existing flist, we only allows updating links
    if os.path.isfile(linkflist.target):
        return api_response("link destination is already a file", 401)

    cwd = os.getcwd()
    os.chdir(flist.user_path)

    os.symlink(flist.filename, linkflist.filename)
    os.chdir(cwd)

    return api_response()

def api_symlink_to_tag(username, linkname, repository, tagname):
    flist = HubPublicFlist(config, utag(repository, tagname), "unknown")
    linkflist = HubPublicFlist(config, username, "unknown")

    if not flist.user_exists:
        return api_response("source tag not found", 404)

    if linkname.endswith(".flist"):
        return api_response("tag symlink cannot ends with .flist", 401)

    if os.path.exists(os.path.join(linkflist.user_path, linkname + ".flist")):
        return api_response("there is a .flist file with the same name existing already", 401)

    # remove previous symlink if existing
    target = os.path.join(linkflist.user_path, linkname)
    if os.path.islink(target):
        os.unlink(target)

    # if it was not a link but a regular file, we don't overwrite
    # existing flist, we only allows updating links
    if os.path.isfile(target):
        return api_response("link destination is already a file", 401)

    cwd = os.getcwd()
    os.chdir(linkflist.user_path)

    os.symlink("../" + utag(repository, tagname), linkname)
    os.chdir(cwd)

    return api_response()


def api_cross_symlink(username, repository, sourcename, linkname):
    flist = HubPublicFlist(config, repository, sourcename)
    linkflist = HubPublicFlist(config, username, linkname)

    if not flist.user_exists:
        return api_response("source repository not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    # remove previous symlink if existing
    if os.path.islink(linkflist.target):
        os.unlink(linkflist.target)

    # if it was not a link but a regular file, we don't overwrite
    # existing flist, we only allows updating links
    if os.path.isfile(linkflist.target):
        return api_response("link destination is already a file", 401)

    cwd = os.getcwd()
    os.chdir(linkflist.user_path)

    os.symlink("../" + flist.username + "/" + flist.filename, linkflist.filename)
    os.chdir(cwd)

    return api_response()

def api_tag_symlink(username, repository, sourcename, tagname, linkname):
    flist = HubPublicFlist(config, repository, sourcename)
    linkflist = HubPublicFlist(config, utag(username, tagname), linkname)

    if not flist.user_exists:
        return api_response("source repository not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    if not os.path.exists(linkflist.user_path):
        os.mkdir(linkflist.user_path)

    # remove previous symlink if existing
    if os.path.islink(linkflist.target):
        os.unlink(linkflist.target)

    cwd = os.getcwd()
    os.chdir(linkflist.user_path)

    os.symlink("../../" + flist.username + "/" + flist.filename, linkflist.filename)
    os.chdir(cwd)

    return api_response()

def api_tag_symlink_delete(username, repository, sourcename, tagname, linkname):
    flist = HubPublicFlist(config, repository, sourcename)
    linkflist = HubPublicFlist(config, username + "/" + tag(tagname), linkname)

    if not flist.user_exists:
        return api_response("source repository not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    # remove previous symlink if existing
    if not os.path.islink(linkflist.target):
        return api_response("target not found on this tag", 404)

    cwd = os.getcwd()
    os.chdir(linkflist.user_path)

    os.remove(linkflist.filename)
    os.chdir(cwd)

    # directory empty, deleting tag
    try:
        if len(os.listdir(linkflist.user_path)) == 0:
            os.rmdir(linkflist.user_path)

    except Exception as e:
        print(e)
        pass

    return api_response()

def api_promote(username, sourcerepo, sourcefile, targetname):
    flist = HubPublicFlist(config, sourcerepo, sourcefile)
    destination = HubPublicFlist(config, username, targetname)

    if not flist.user_exists:
        return api_response("user not found", 404)

    if not flist.file_exists:
        return api_response("source not found", 404)

    # ensure target exists
    if not destination.user_exists:
        destination.user_create()

    # remove previous file if existing
    if os.path.exists(destination.target):
        os.unlink(destination.target)

    print("[+] promote: %s -> %s" % (flist.target, destination.target))
    shutil.copy(flist.target, destination.target)

    status = {
        'source': {
            'username': flist.username,
            'filename': flist.filename,
        },
        'destination': {
            'username': destination.username,
            'filename': destination.filename,
        }
    }

    return api_response(extra=status)

def api_flist_upload(request, username, validate=False):
    # check if the post request has the file part
    if 'file' not in request.files:
        return {'status': 'error', 'message': 'no file found'}

    file = request.files['file']

    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        return {'status': 'error', 'message': 'no file selected'}

    if not allowed_file(file.filename, validate):
        return {'status': 'error', 'message': 'this file is not allowed'}

    metadata = {}

    for field in request.form:
        if field.startswith("metadata-"):
            key = field[9:]

            print("[+] metadata requested: %s" % key)
            metadata[key] = request.form[field]

    #
    # processing the file
    #
    filename = secure_filename(file.filename)

    print("[+] saving file")
    source = os.path.join(config['upload-directory'], filename)
    file.save(source)

    cleanfilename = file_from_flist(filename)
    flist = HubPublicFlist(config, username, cleanfilename)
    flist.user_create()

    # it's a new flist, let's do the normal flow
    if not validate:
        workspace = flist.raw.workspace()
        flist.raw.unpack(source, workspace.name)
        stats = flist.raw.create(workspace.name, flist.target, metadata)

    # we have an existing flist and checking contents
    # we don't need to create the flist, we just ensure the
    # contents is on the backend
    else:
        flist.loads(source)
        stats = flist.validate()
        if stats['response']['failure'] > 0:
            return {'status': 'error', 'message': 'unauthorized upload, contents is not fully present on backend'}

        flist.commit()

    # removing uploaded source file
    os.unlink(source)

    return {'status': 'success', 'flist': flist.filename, 'home': username, 'stats': stats, 'timing': {}}

def api_flist_upload_prepare(request, username, validate=False):
    # check if the post request has the file part
    if 'file' not in request.files:
        return {'status': 'error', 'message': 'no file found'}

    file = request.files['file']

    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        return {'status': 'error', 'message': 'no file selected'}

    if not allowed_file(file.filename, validate):
        return {'status': 'error', 'message': 'this file is not allowed'}

    #
    # processing the file
    #
    filename = secure_filename(file.filename)

    print("[+] saving file")
    source = os.path.join(config['upload-directory'], filename)
    file.save(source)

    cleanfilename = file_from_flist(filename)
    flist = HubPublicFlist(config, username, cleanfilename, announcer)
    flist.raw.newtask()

    print("[+] flist creation id: %s" % flist.raw.jobid)

    job = threading.Thread(target=flist.create, args=(source, ))
    job.start()

    return {'status': 'success', 'jobid': flist.raw.jobid}

    """
    print(flist.raw.jobid)

    flist.user_create()

    # it's a new flist, let's do the normal flow
    if not validate:
        workspace = flist.raw.workspace()
        flist.raw.unpack(source, workspace.name)
        stats = flist.raw.create(workspace.name, flist.target)

    # we have an existing flist and checking contents
    # we don't need to create the flist, we just ensure the
    # contents is on the backend
    else:
        flist.loads(source)
        stats = flist.validate()
        if stats['response']['failure'] > 0:
            return {'status': 'error', 'message': 'unauthorized upload, contents is not fully present on backend'}

        flist.commit()

    # removing uploaded source file
    os.unlink(source)

    return {'status': 'success', 'flist': flist.filename, 'home': username, 'stats': stats, 'timing': {}}
    """

def api_repositories():
    output = []

    try:
        root = sorted(os.listdir(config['public-directory']))

    except FileNotFoundError as e:
        print(e)
        root = []

    for user in root:
        target = os.path.join(config['public-directory'], user)

        # ignore files (eg: .keep file)
        if not os.path.isdir(target):
            continue

        official = (user in config['official-repositories'])
        output.append({'name': user, 'official': official})

    return output

def clean_symlink(linkname):
    linkname = linkname.replace("../", "")
    linkname = linkname.replace(".tag-", "tags/")
    return linkname

def api_user_contents(username, userpath):
    files = sorted(os.listdir(userpath))
    contents = []

    for file in files:
        filepath = os.path.join(config['public-directory'], username, file)
        stat = os.lstat(filepath)

        if S_ISLNK(stat.st_mode):
            target = os.readlink(filepath)
            tstat = stat

            if os.path.exists(filepath):
                tstat = os.stat(filepath)

            stype = 'symlink'
            if '/.tag-' in target:
                stype = 'taglink'

            contents.append({
                'name': file,
                'size': "%.2f KB" % ((tstat.st_size) / 1024),
                'updated': int(tstat.st_mtime),
                'linktime': int(stat.st_mtime),
                'type': stype,
                'target': clean_symlink(target),
            })

        elif S_ISDIR(stat.st_mode):
            # ignore directories which are not tags
            if not file.startswith(".tag-"):
                continue

            contents.append({
                'name': file[5:],
                'size': "0 KB",
                'updated': int(stat.st_mtime),
                'type': 'tag',
            })

        else:
            contents.append({
                'name': file,
                'size': "%.2f KB" % ((stat.st_size) / 1024),
                'updated': int(stat.st_mtime),
                'type': 'regular',
            })

    return contents

def api_user_contents_tags(username, userpath, tag):
    files = sorted(os.listdir(userpath + "/.tag-" + tag))
    contents = []

    for file in files:
        filepath = os.path.join(config['public-directory'], username + "/.tag-" + tag, file)
        stat = os.lstat(filepath)

        if not S_ISLNK(stat.st_mode):
            continue

        target = os.readlink(filepath)
        tstat = stat

        if os.path.exists(filepath):
            tstat = os.stat(filepath)

        contents.append({
            'name': file,
            'size': "%.2f KB" % ((tstat.st_size) / 1024),
            'updated': int(tstat.st_mtime),
            'linktime': int(stat.st_mtime),
            'type': 'symlink',
            'target': clean_symlink(target),
        })

    return contents


def api_fileslist():
    repositories = api_repositories()
    fileslist = {}

    for repository in repositories:
        flist = HubPublicFlist(config, repository['name'], "unknown")
        contents = api_user_contents(flist.username, flist.user_path)

        fileslist[repository['name']] = contents

    return fileslist


def api_contents(flist):
    flist.loads(flist.target)
    contents = flist.contents()

    return contents["response"]

def api_flist_md(flist):
    flist.loads(flist.target)
    response = flist.allmetadata()

    return response

def api_flist_info(flist):
    stat = os.lstat(flist.target)
    file = os.path.basename(flist.target)

    contents = {
        'name': file,
        'size': stat.st_size,
        'updated': int(stat.st_mtime),
        'type': 'regular',
        'md5': flist.checksum,
    }

    if S_ISLNK(stat.st_mode):
        target = os.readlink(flist.target)
        tstat = stat

        if os.path.exists(flist.target):
            tstat = os.stat(flist.target)

        contents['type'] = 'symlink'
        contents['updated'] = int(tstat.st_mtime)
        contents['linktime'] = int(stat.st_mtime)
        contents['target'] = target
        contents['size'] = tstat.st_size

    return contents

def api_response(error=None, code=200, extra=None):
    reply = {"status": "success"}

    if error:
        reply = {"status": "error", "message": error}

    if extra:
        reply['payload'] = extra

    response = make_response(json.dumps(reply) + "\n", code)
    response.headers["Content-Type"] = "application/json"

    return response

#
# request post hook
#
@app.after_request
def cors_global(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

#
# notification subsystem (server-sent event)
#
@app.route('/listen/<id>', methods=['GET'])
def listen(id):
    print("[+] listening id: %s" % id)
    def stream():
        messages = announcer.listen(id)
        while True:
            msg = messages.get()

            # reaching None means there is nothing more expected
            # on this job, we can clean it up
            if msg == None:
                announcer.terminate(id)
                return

            yield msg

    messages = announcer.listen(id)
    if messages == None:
        return announcer.error("job id not found"), 404

    return Response(stream(), mimetype='text/event-stream')



######################################
#
# PROCESSING
#
######################################
print("[+] listening")
app.run(host=config['listen-addr'], port=config['listen-port'], debug=config['debug'], threaded=True)
