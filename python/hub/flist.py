import os
import subprocess
import tempfile
import hashlib
import tarfile
import redis
import json
import shutil

class HubFlist:
    def __init__(self, config):
        self.config = config

        if 'zflist-bin' not in config:
            config['zflist-bin'] = "/opt/0-flist/zflist/zflist"

        self.zflist = config['zflist-bin']

        """
        self.backopt = {
            'host': "172.17.0.10",
            'port': 46379,
            'password': '....',
            'ssl': True
        }
        """

        self.backopt = {
            'host': config['backend-internal-host'],
            'port': config['backend-internal-port'],
            'nspass': config['backend-internal-pass'],
            'password': None,
            'ssl': False
        }

        self.tmpdir = None
        self.flist = None

    def ensure(self, target):
        if not os.path.exists(target):
            os.mkdir(target)

    def backend(self):
        """
        Connect the backend
        """
        return redis.Redis(
            self.backopt['host'],
            self.backopt['port'],
            password=self.backopt['password'],
            ssl=self.backopt['ssl']
        )

    def unpack(self, filepath, target=None):
        """
        Unpack tar archive `filepath` into `target` directory
        """
        if target is None:
            target = self.tmpdir.name

        self.ensure(target)

        print("[+] upacking: %s" % filepath)
        args = ["tar", "-xpf", filepath, "-C", target]
        p = subprocess.Popen(args)
        p.wait()

        return 0
    def workspace(self, prefix="workspace-"):
        return tempfile.TemporaryDirectory(prefix=prefix, dir=self.config['flist-work-directory'])

    def loadsv2(self, source):
        self.sourcev2 = source

    def listingv2(self):
        args = [self.zflist, "--list", "--action", "json", "--archive", self.sourcev2]

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        p.wait()

        return json.loads(output.decode('utf-8'))

    def validatev2(self):
        backend = "%s:%d" % (self.backopt['host'], self.backopt['port'])
        args = [self.zflist, "--list", "--action", "check", "--archive", self.sourcev2, "--backend", backend, "--json"]

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        p.wait()

        print(output)

        return json.loads(output.decode('utf-8'))

    def create(self, rootdir, target):
        backend = "%s:%d" % (self.backopt['host'], self.backopt['port'])
        args = [self.zflist, "--create", rootdir, "--archive", target, "--backend", backend, '--json']

        if self.config['backend-internal-pass']:
            args.append('--password')
            args.append(self.config['backend-internal-pass'])

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        # p = subprocess.Popen(args)
        # p.wait()

        print(output)
        print(err)

        return json.loads(output.decode('utf-8'))
        # return True

    def checksum(self, target):
        """
        Compute md5 hash of the flist
        """
        print("[+] md5: %s" % target)

        hash_md5 = hashlib.md5()

        if not os.path.isfile(target):
            return None

        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)

        return hash_md5.hexdigest()

    def merge(self, target, sources):
        fixedsources = []
        for source in sources:
            fixedsources.append("--merge")
            fixedsources.append(os.path.join(self.config['public-directory'], source))

        args = [self.zflist, "--archive", target, "--json"] + fixedsources
        print(args)

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        p.wait()

        # return json.loads(output.decode('utf-8'))
        return True

class HubPublicFlist:
    def __init__(self, config, username, flistname):
        self.rootpath = config['public-directory']
        self.username = username
        self.filename = flistname

        # ensure we accept flist-name and flist-filename
        if not self.filename.endswith(".flist"):
            self.filename += ".flist"

        self.raw = HubFlist(config)

    def commit(self):
        if self.raw.sourcev2 != self.target:
            self.user_create()
            shutil.copyfile(self.raw.sourcev2, self.target)

    @property
    def target(self):
        return os.path.join(self.rootpath, self.username, self.filename)

    @property
    def user_path(self):
        return os.path.join(self.rootpath, self.username)

    @property
    def user_exists(self):
        return os.path.isdir(self.user_path)

    def user_create(self):
        if not self.user_exists:
            os.mkdir(self.user_path)

    @property
    def file_exists(self):
        print("[+] flist exists: %s" % self.target)
        return (os.path.isfile(self.target) or os.path.islink(self.target))

    @property
    def checksum(self):
        return self.raw.checksum(self.target)

    def merge(self, sources):
        return self.raw.merge(self.target, sources)
