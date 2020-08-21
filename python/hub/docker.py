import os
import docker
import uuid
import tempfile
import subprocess
import uuid
import traceback
import pprint
import pytoml as toml
from hub.flist import HubPublicFlist


class HubDocker:
    def __init__(self, config, announcer):
        self.dockerclient = docker.from_env()
        self.lowlevel = docker.APIClient()
        self.config = config
        self.jobid = str(uuid.uuid4())
        self.announcer = announcer

        self.announcer.initialize(self.jobid)
        self.progress("Initializing docker converter", 0)

    def container_boot(self, cn):
        command = []
        args = []
        env = {}
        cwd = '/'

        if cn.attrs['Config']['Entrypoint']:
            command = cn.attrs['Config']['Entrypoint'][0]

            if len(cn.attrs['Config']['Entrypoint']) > 1:
                args = cn.attrs['Config']['Entrypoint'][1:]

            else:
                args = cn.attrs['Config']['Cmd']

        else:
            command = cn.attrs['Config']['Cmd'][0]
            args = cn.attrs['Config']['Cmd'][1:]

        if cn.attrs['Config']['Env']:
            for entry in cn.attrs['Config']['Env']:
                k, e, v = entry.partition("=")
                env[k] = v

        if cn.attrs['Config']['WorkingDir']:
            cwd = cn.attrs['Config']['WorkingDir']

        return command, args, env, cwd

    def notify(self, message):
        self.announcer.push(self.jobid, message)

    def progress(self, message, progression):
        status = {"status": "update", "message": message, "progress": progression}
        return self.notify(status)


    def convert(self, dockerimage, username="dockers"):
        try:
            response = self.converter(dockerimage, username)

        except Exception as e:
            print(traceback.format_exc())
            response = {'status': 'error', 'message': str(e)}

        if response['status'] == 'success':
            self.progress("Image ready !", 100)
            self.notify({"status": "info", "info": response})

        if response['status'] == 'error':
            self.notify({"status": "error", "message": response['message']})

        self.announcer.finalize(self.jobid)

    def converter(self, dockerimage, username="dockers"):
        dockername = uuid.uuid4().hex
        print("[+] docker-convert: temporary docker name: %s" % dockername)

        if ":" not in dockerimage:
            dockerimage = "%s:latest" % dockerimage

        #
        # loading image from docker-hub
        #
        print("[+] docker-convert: pulling image: %s" % dockerimage)
        self.progress("Pulling docker image: %s" % dockerimage, 10)

        try:
            # progress pull
            self.pull(dockerimage)

            # fetch real image name
            image = self.dockerclient.images.pull(dockerimage)

        except docker.errors.ImageNotFound:
            return {'status': 'error', 'message': 'docker image not found'}

        except docker.errors.APIError:
            return {'status': 'error', 'message': 'could not pull this image'}

        #
        # building init-command line
        #
        command = None

        if not image.attrs['Config']['Cmd'] and not image.attrs['Config']['Entrypoint']:
            command = "/bin/sh"

        print("[+] docker-convert: starting temporary container")
        self.progress("Initializing temporary container", 55)

        cn = self.dockerclient.containers.create(
            dockerimage,
            name=dockername,
            hostname=dockername,
            command=command
        )

        #
        # exporting docker
        #
        print("[+] docker-convert: creating target directory")
        tmpdir = tempfile.TemporaryDirectory(prefix=dockername, dir=self.config['docker-work-directory'])
        os.chmod(tmpdir.name, 0o755)

        print("[+] docker-convert: dumping files to: %s" % tmpdir.name)
        self.progress("Extracting container root filesystem", 60)

        subprocess.call(['sh', '-c', 'docker export %s | tar -xpf - -C %s' % (dockername, tmpdir.name)])

        #
        # docker init command to container startup command
        #
        print("[+] docker-convert: creating container entrypoint")
        self.progress("Creating container metadata", 65)

        command, args, env, cwd = self.container_boot(cn)

        boot = {
            'startup': {
                'entry': {
                    'name': "core.system",
                    'args': {
                        'name': command,
                        'args': args,
                        'env': env,
                        'dir': cwd,
                    }
                }
            }
        }

        with open(os.path.join(tmpdir.name, '.startup.toml'), 'w') as f:
            f.write(toml.dumps(boot))

        #
        # bundle the image
        #
        print("[+] docker-convert: parsing the flist")
        self.progress("Building filesystem flist", 80)

        flistname = dockerimage.replace(":", "-").replace('/', '-')

        flist = HubPublicFlist(self.config, username, flistname, self.announcer)
        flist.user_create()
        info = flist.raw.create(tmpdir.name, flist.target)

        print("[+] docker-convert: cleaning temporary files")
        self.progress("Cleaning up environment", 95)

        tmpdir.cleanup()

        print("[+] docker-convert: destroying the container")
        cn.remove(force=True)

        print("[+] docker-convert: cleaning up the docker image")
        self.dockerclient.images.remove(dockerimage, force=True)

        if info['success'] == False:
            return {'status': 'error', 'message': info['error']['message']}

        self.progress("Image ready !", 100)

        return {'status': 'success', 'file': flist.filename, 'flist': info['response'], 'timing': {}}


    #
    # docker pull handler
    #
    def pull_done(self, layers, category):
        done = 0

        for l in layers:
            if layers[l][category]['done'] == True:
                done += 1

        return done

    def pull_size(self, size):
        if size < 2048:
            return "%.1f KB" % (size / (1 << 10))

        return "%.0f MB" % (size / (1 << 20))

    def progress_download(self, layers):
        total = 0
        downloaded = 0
        done = 0
        todo = len(layers)

        for i in layers:
            total += layers[i]['download']['total']
            downloaded += layers[i]['download']['current']

            # force validating complete download
            if layers[i]['download']['current'] == layers[i]['download']['total']:
                layers[i]['download']['done'] = True

            if layers[i]['download']['done'] == True:
                done += 1

        percent = self.progress_percent(layers)
        self.progress("Downloading layers [%s / %s]" % (self.pull_size(downloaded), self.pull_size(total)), percent)

    def progress_extract(self, layers, layer):
        done = self.pull_done(layers, 'extract')
        todo = len(layers)

        percent = self.progress_percent(layers)
        current = layer['progressDetail']['current'] / (1 << 20)
        total = layer['progressDetail']['total'] / (1 << 20)

        # do not print size progress on small image
        if layer['progressDetail']['total'] < 5 * (1 << 20):
            self.progress("Extracting layer %d / %d" % (done, todo), percent)
            return

        self.progress("Extracting layer %d / %d [%.0f MB / %.0f MB]" % (done, todo, current, total), percent)

    def progress_percent(self, layers):
        # sum download and extract
        done = self.pull_done(layers, 'download') + self.pull_done(layers, 'extract')
        todo = len(layers) * 2

        # percentage bar goes from 10 to 50% (which is 40%)
        return int(10 + ((done / todo) * 40))

    def pull_downloaded(self, layers):
        for i in layers:
            if layers[i]['download']['done'] == False:
                return False

        return True

    def pull(self, image):
        layers = {}
        downloaded = False

        for line in self.lowlevel.pull(image, stream=True, decode=True):
            print(line)

            if line['status'] == 'Pulling fs layer':
                layers[line['id']] = {
                    'download': {'current': 0, 'total': 1, 'done': False},
                    'extract': {'current': 0, 'total': 0, 'done': False}
                }

            # notify download
            if line['status'] == 'Downloading':
                layers[line['id']]['download']['current'] = line['progressDetail']['current']
                layers[line['id']]['download']['total'] = line['progressDetail']['total']
                self.progress_download(layers)

            # we can now notify extracting
            if line['status'] == 'Download complete':
                layers[line['id']]['download']['done'] = True

            if line['status'] == 'Verifying Checksum':
                layers[line['id']]['download']['done'] = True

            if line['status'] == 'Pull complete':
                layers[line['id']]['extract']['done'] = True

            if line['status'] == 'Extracting':
                if self.pull_downloaded(layers):
                    self.progress_extract(layers, line)


