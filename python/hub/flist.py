import os
import subprocess
import tempfile
import g8storclient
import hashlib
import tarfile
import redis
import json
from js9 import j

class HubFlist:
    def __init__(self, config):
        self.config = config

        """
        self.backopt = {
            'host': "172.17.0.10",
            'port': 46379,
            'password': '....',
            'ssl': True
        }
        """

        self.backopt = {
            'host': config['PRIVATE_ARDB_HOST'],
            'port': config['PRIVATE_ARDB_PORT'],
            'password': None,
            'ssl': False
        }

        self.tmpdir = None
        self.flist = None

    def dummy(self, dirobj=None, type=None, name=None, subobj=None, args=None, key=None):
        pass

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

    def pack(self, target):
        """
        Pack database into archive
        """
        with tarfile.open(target, "w:gz") as tar:
            tar.add(self.tmpdir.name, arcname="")

        return True

    def unpack(self, filepath, target=None):
        """
        Unpack tar archive `filepath` into `target` directory
        """
        if target is None:
            target = self.tmpdir.name

        self.ensure(target)

        print(filepath)
        t = tarfile.open(filepath, "r:*")
        t.extractall(path=target)

        filescount = len(t.getnames())
        t.close()

        return filescount

    def initialize(self, rootpath, prefix="flist-"):
        self.tmpdir = self.workspace("flist-")
        self.flist = self.open(rootpath, self.tmpdir.name)

        print("[+] flist initialized: %s, %s\n" % (rootpath, self.tmpdir.name))

        return True

    def open(self, rootpath, sourcepath):
        kvs = j.data.kvs.getRocksDBStore('flist', namespace=None, dbpath=sourcepath)
        flist = j.tools.flist.getFlist(rootpath=rootpath, kvs=kvs)

        return flist

    def workspace(self, prefix="workspace-"):
        return tempfile.TemporaryDirectory(prefix=prefix, dir=self.config['flist-work-directory'])

    def insert(self, directory, excludes=[".*\.pyc", ".*__pycache__"]):
        self.flist.add(directory, excludes=excludes)

    def commit(self):
        """
        This is a workaround to ensure file are written and not in a unstable state
        this access 'protected' class member, this could be improved
        """
        print("[+] flist: committing (compacting db)")
        self.flist.dirCollection._db.rocksdb.compact_range()

    def upload(self):
        print("[+] flist: populating contents")
        self.flist.populate()
        self.commit()

        r = self.backend()
        self.proceed = 0

        def procFile(dirobj, type, name, subobj, args):
            fullpath = "%s/%s/%s" % (self.flist.rootpath, dirobj.dbobj.location, name)
            # print("[+] uploading: %s" % fullpath)

            self.proceed += 1
            if self.proceed % 150 == 0:
                print("[+] still uploading [%d]" % self.proceed)

            """
            import hashlib
            m = hashlib.md5()

            with open(fullpath, "rb") as x:
                data = x.read()

            print(len(data))
            m.update(data)
            key = m.hexdigest()
            print(key)
            r.set(key, data)
            """

            hashs = g8storclient.encrypt(fullpath)

            if hashs is None:
                return

            for hash in hashs:
                if not r.exists(hash['hash']):
                    r.set(hash['hash'], hash['data'])

        print("[+] uploading contents")
        self.process(procFile)

    def process(self, callback):
        """
        Walk over the flist and call user-defined file callback
        """
        result = []
        self.flist.walk(
            dirFunction=self.dummy,
            fileFunction=callback,
            specialFunction=self.dummy,
            linkFunction=self.dummy,
            args=result
        )

        return result

    def loads(self, source):
        """
        Load an existing flist into this object
        """
        self.tmpdir = self.workspace('flist-')
        self.unpack(source)
        self.flist = self.open("/", self.tmpdir.name)

        return True

    def loadsv2(self, source):
        self.sourcev2 = source

    def validate(self):
        """
        This validate (confirm) all contents from the flist are available on the
        backend, this is useful when you want to ensure consistancy between one
        flist archive and the backend (ensure all files will be found)

        Returns True if backend is fully-sync, False if (at least) a single key is missing
        """
        r = self.backend()
        pipe = r.pipeline()

        def procFile(dirobj, type, name, subobj, args):
            for chunk in subobj.attributes.file.blocks:
                rkey = chunk.hash.decode('utf-8')
                pipe.exists(rkey)

        self.process(procFile)
        result = pipe.execute()

        return (not False in result)

    def listing(self):
        """
        Walk over the full contents and returns a summary of the contents
        """
        contents = {
            'content': [],
            'regular': 0,
            'directory': 0,
            'symlink': 0,
            'special': 0
        }

        def getPath(location, name):
            if location:
                return "/%s/%s" % (location, name)

            return "/%s" % name

        def procDir(dirobj, type, name, args, key):
            contents['directory'] += 1
            contents['content'].append({'path': getPath(dirobj.dbobj.location, name), 'size': 0})

        def procSpecial(dirobj, type, name, subobj, args):
            contents['special'] += 1
            contents['content'].append({'path': getPath(dirobj.dbobj.location, name), 'size': 0})

        def procFile(dirobj, type, name, subobj, args):
            contents['regular'] += 1
            contents['content'].append({'path': getPath(dirobj.dbobj.location, name), 'size': dirobj.dbobj.size})

        def procLink(dirobj, type, name, subobj, args):
            contents['symlink'] += 1
            contents['content'].append({'path': getPath(dirobj.dbobj.location, name), 'size': 0})

        print("[+] parsing database")
        result = []
        self.flist.walk(
            dirFunction=procDir,
            fileFunction=procFile,
            specialFunction=procSpecial,
            linkFunction=procLink,
            args=result
        )

        return contents

    def listingv2(self):
        args = ["/opt/flister/flister", "--list", "--output", "json", "--archive", self.sourcev2]

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        p.wait()

        return json.loads(output.decode('utf-8'))

    def create(self, rootdir):
        backend = "%s:%d" % (self.backopt['host'], self.backopt['port'])
        args = ["/opt/flister/flister", "--create", rootdir, "--archive", self.target, "--upload", backend]

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        p.wait()

        print(output)
        print(err)

        return output.decode('utf-8')

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

class HubPublicFlist:
    def __init__(self, config, username, flistname):
        self.rootpath = config['public-directory']
        self.username = username
        self.filename = flistname

        # ensure we accept flist-name and flist-filename
        if not self.filename.endswith(".flist"):
            self.filename += ".flist"

        self.raw = HubFlist(config)

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
        print(self.target)
        return (os.path.isfile(self.target) or os.path.islink(self.target))

    @property
    def checksum(self):
        return self.raw.checksum(self.target)


