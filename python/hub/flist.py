import os
import subprocess
import tempfile
import hashlib
import tarfile
import redis
import json
import uuid
import shutil

class HubFlist:
    def __init__(self, config, announcer=None):
        self.config = config

        if 'zflist-bin' not in config:
            config['zflist-bin'] = "/opt/0-flist/zflist/zflist"

        self.zflist = config['zflist-bin']

        self.backstr = json.dumps({
            'host': config['backend-internal-host'],
            'port': config['backend-internal-port'],
            'password': config['backend-internal-pass'],
        })

        self.tmpdir = None
        self.worksp = self.workspace()
        self.workdir = self.worksp.name
        self.source = None
        self.opened = False
        self.jobid = str(uuid.uuid4())
        self.announcer = announcer

        self.environ = dict(
            os.environ,
            ZFLIST_MNT=self.workdir,
            ZFLIST_BACKEND=self.backstr,
            ZFLIST_JSON="1",
            ZFLIST_PROGRESS="1"
        )


    def newtask(self):
        print("[+] initializing flist new task")
        self.announcer.initialize(self.jobid)

    def ensure(self, target):
        if not os.path.exists(target):
            os.mkdir(target)

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

    def execute(self, command, args=[], raw=False):
        command = [self.zflist, command] + args
        print(command)

        # set json output depending on raw output or not
        # this is useful for cat command
        self.environ['ZFLIST_JSON'] = "1" if raw == False else "0"

        value = b''
        p = subprocess.Popen(command, env=self.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # (output, err) = p.communicate()

        # progressing tracking
        percentage = 0

        while True:
            output = p.stdout.readline()
            if output == b'' and p.poll() is not None:
                # end of stream
                code = p.poll()
                break

            value = output.strip()
            try:
                content = json.loads(value.decode('utf-8'))
                # print(content)

            except Exception as e:
                print(e)

                # print zflist output to debug and forward error
                print(value.decode('utf-8'))
                raise e

            if 'status' in content and content['status'] == 'progress':
                # only parse processing message
                if content['message'] != 'processing':
                    continue

                # update percentage only if updated for client view
                percent = int((content['current'] / content['total']) * 100)
                if percent != percentage:
                    message = "processing item %d of %d" % (content['current'], content['total'])
                    self.progress("Building: %s" % message, percent)
                    percentage = percent

        # print(code, output, err)
        output = value
        print("Code: %d, %s" % (code, output))
        print("Error: %s" % p.stderr.read())

        if raw == True:
            payload = {'content': output.decode("utf-8")}

        else:
            payload = json.loads(output.decode("utf-8")) if output else {}

        payload['status'] = code

        return payload

    def workspace(self, prefix="workspace-"):
        return tempfile.TemporaryDirectory(prefix=prefix, dir=self.config['flist-work-directory'])

    def loads(self, source):
        self.source = source

    def open(self):
        if self.opened:
            return False

        self.execute("open", [self.source])
        self.opened = True

        return True

    def close(self):
        if not self.opened:
            return False

        self.execute("close")
        self.opened = False

        return True

    def contents(self):
        self.open()
        ls = self.execute("find")
        self.close()

        return ls

    def validate(self):
        valbackend = [
            "--host", self.config['backend-internal-host'],
            "--port", str(self.config['backend-internal-port'])
        ]

        self.open()
        self.execute("metadata", ["backend"] + valbackend)
        check = self.execute("check")
        self.close()

        return check

    def readme(self, rootdir):
        files = [".README.md", ".README"]

        for f in files:
            fp = os.path.join(rootdir, f)

            if os.path.exists(fp):
                self.setreadme(fp)

    def create(self, rootdir, target):
        self.execute("init")
        putdir = self.execute("putdir", [rootdir, "/"])

        # include optional readme
        self.readme(rootdir)

        self.execute("commit", [target])
        self.execute("close")

        return putdir

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
            fixedsources.append(os.path.join(self.config['public-directory'], source))

        self.execute("open", [fixedsources[0]])

        for source in fixedsources[1:]:
            merge = self.execute("merge", [source])

            if not merge["success"]:
                return False

        self.execute("commit", [target])

        return True

    def exists(self, filename):
        if not self.opened:
            return False

        found = self.execute("stat", [filename])
        return found['success']

    def metadata(self, metadata):
        payload = self.execute("metadata", [metadata])

        if not payload["success"]:
            return None

        return payload["response"]["value"]


    def allmetadata(self):
        if not self.opened:
            self.open()

        data = {}
        entries = ["readme", "backend", "entrypoint", "environ", "port", "volume"]

        for entry in entries:
            data[entry] = self.metadata(entry)

        self.close()

        return data

    def localbackend(self, password=False):
        host = self.config['backend-public-host']
        port = self.config['backend-public-port']

        self.execute("metadata", ["backend", "--host", host, "--port", str(port)])

    def privatebackend(self, password=False):
        host = self.config['backend-internal-host']
        port = self.config['backend-internal-port']
        pwd = self.config['backend-internal-pass']

        self.execute("metadata", ["backend", "--host", host, "--port", str(port), '--password', pwd])

    def setreadme(self, filename):
        self.execute("metadata", ["readme", "--import", filename])

    def notify(self, message):
        if self.announcer is None:
            return

        self.announcer.push(self.jobid, message)

    def progress(self, message, progression):
        status = {"status": "update", "message": message, "progress": progression}
        return self.notify(status)

    # run precheck (testing zflist and backend connectivity)
    def check(self):
        print("[+] flist: running 0-flist self-check")
        test = self.execute("init")
        if test['status'] != 0:
            return False

        self.privatebackend()

        test = self.execute("check")
        if test['status'] != 0:
            return False

        return True

class HubPublicFlist:
    def __init__(self, config, username, flistname, announcer=None):
        self.rootpath = config['public-directory']
        self.username = username
        self.filename = flistname
        self.announcer = announcer

        # ensure we accept flist-name and flist-filename
        if not self.filename.endswith(".flist"):
            self.filename += ".flist"

        self.raw = HubFlist(config, announcer)

    def commit(self):
        if self.raw.source != self.target:
            self.user_create()
            shutil.copyfile(self.raw.source, self.target)

    def loads(self, source):
        return self.raw.loads(source)

    def contents(self):
        return self.raw.contents()

    def validate(self):
        return self.raw.validate()

    def create(self, source):
        self.user_create()

        workspace = self.raw.workspace()
        self.raw.unpack(source, workspace.name)
        stats = self.raw.create(workspace.name, self.target)
        os.unlink(source)

        info = {"filename": self.filename, "flist": stats['response']}

        self.raw.progress("Image ready !", 100)
        self.raw.notify({"status": "info", "info": info})
        self.announcer.finalize(self.raw.jobid)

        return None

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

    def allmetadata(self):
        return self.raw.allmetadata()
