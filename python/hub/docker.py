import os
import docker
import uuid
import tempfile
import subprocess
import pytoml as toml
from hub.flist import HubPublicFlist


class HubDocker:
    def __init__(self, config):
        self.dockerclient = docker.from_env()
        self.config = config

    def container_boot(self, cn):
        command = []
        args = []
        env = {}
        cwd = '/'

        if cn.attrs['Config']['Entrypoint']:
            command = cn.attrs['Config']['Entrypoint'][0]
            args = cn.attrs['Config']['Cmd']

        else:
            command = cn.attrs['Config']['Cmd'][0]
            args = cn.attrs['Config']['Cmd'][1:]

        if cn.attrs['Config']['Env']:
            for entry in cn.attrs['Config']['Env']:
                k, v = entry.split("=")
                env[k] = v

        if cn.attrs['Config']['WorkingDir']:
            cwd = cn.attrs['Config']['WorkingDir']

        return command, args, env, cwd

    def convert(self, dockerimage, username="dockers"):
        dockername = uuid.uuid4().hex
        print("[+] docker-convert: temporary docker name: %s" % dockername)

        if ":" not in dockerimage:
            dockerimage = "%s:latest" % dockerimage

        #
        # loading image from docker-hub
        #
        print("[+] docker-convert: pulling image: %s" % dockerimage)
        try:
            image = self.dockerclient.images.pull(dockerimage)

        except docker.errors.ImageNotFound:
            return {'status': 'error', 'message': 'docker image not found'}

        #
        # building init-command line
        #
        command = None

        if not image.attrs['Config']['Cmd'] and not image.attrs['Config']['Entrypoint']:
            command = "/bin/sh"

        print("[+] docker-convert: starting temporary container")
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

        print("[+] docker-convert: dumping files to: %s" % tmpdir.name)
        subprocess.call(['sh', '-c', 'docker export %s | tar -xpf - -C %s' % (dockername, tmpdir.name)])

        #
        # docker init command to container startup command
        #
        print("[+] docker-convert: creating container entrypoint")
        command, args, env, cwd = self.container_boot(cn)

        boot = {
            'startup.entry':      {'name': "core.system", 'running_delay': -1},
            'startup.entry.args': {'name': command, 'args': args, 'env': env, 'dir': cwd}
        }

        with open(os.path.join(tmpdir.name, '.startup.toml'), 'w') as f:
            f.write(toml.dumps(boot))

        #
        # bundle the image
        #
        print("[+] docker-convert: parsing the flist")
        flistname = dockerimage.replace(":", "-").replace('/', '-')

        flist = HubPublicFlist(self.config, username, flistname)
        flist.raw.initialize(tmpdir.name)
        flist.raw.insert(tmpdir.name)
        flist.raw.upload()
        flist.user_create()
        flist.raw.pack(flist.target)

        print("[+] docker-convert: cleaning temporary files")
        tmpdir.cleanup()

        print("[+] docker-convert: destroying the container")
        cn.remove(force=True)

        print("[+] docker-convert: cleaning up the docker image")
        self.dockerclient.images.remove(dockerimage, force=True)

        return {'status': 'success', 'flist': flist.filename, 'count': 0, 'timing': {}}
