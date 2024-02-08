import redis
import tempfile
import requests
import subprocess
import json
import os
import sys

class FListRemoteClone:
    def __init__(self, host, port, basehub="https://hub.grid.tf"):
        self.host = host
        self.port = port
        self.basehub = basehub

        self.local = redis.Redis(host, port)
        self.remote = redis.Redis("hub.grid.tf", 9900)

        self.zflist = "/home/maxux/git/0-flist/zflist/zflist"
        self.backend = ""
        self.workdir = tempfile.mkdtemp(prefix="zflist-cloning")
        self.tempdir = tempfile.mkdtemp(prefix="zflist-source")

        print(self.workdir)
        print(self.tempdir)

        self.environ = dict(
            os.environ,
            ZFLIST_JSON="1",
            ZFLIST_MNT=self.workdir
        )

    def authenticate(self):
        pass

    def download(self, target):
        url = f"{self.basehub}/{target}"
        destination = f"{self.tempdir}/download.flist"

        print(f"[+] fetching: {url}")

        r = requests.get(url)
        with open(destination, "wb") as f:
            f.write(r.content)

        length = len(r.content) / 1024
        print(f"[+] fetched {length:.2f} KB into {destination}")

        return destination

    def execute(self, args):
        command = [self.zflist] + args

        print(command)
        p = subprocess.Popen(command, env=self.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, err) = p.communicate()

        return json.loads(output)

    def chunks(self, flist):
        self.execute(["open", flist])
        reply = self.execute(["chunks"])

        chunks = reply["response"]["content"]
        bchunks = []

        for chunk in chunks:
            bchunk = bytes.fromhex(chunk)
            bchunks.append(bchunk)

        return bchunks

    def metadata(self):
        pass

    def commit(self, destination):
        self.execute(["commit", destination])

    def sync(self, chunks):
        proceed = 0
        total = len(chunks)

        print("[+] syncing database...")

        for chunk in chunks:
            data = self.remote.get(chunk)
            self.local.execute_command("SETX", chunk, data)

            proceed += 1
            percent = (proceed / total) * 100

            sys.stdout.write(f"\r[+] syncing database: {proceed} / {total} [{percent:.2f} %%]")
            sys.stdout.flush()

        print("[+] database synchronized")

    def clone(self, target):
        flist = self.download(target)
        chunks = self.chunks(flist)
        self.sync(chunks)
        self.metadata()
        self.commit("/tmp/destination.flist")


if len(sys.argv) < 2:
    print("[-] missing target flist to clone")
    sys.exit(1)

target = sys.argv[1]

x = FListRemoteClone("127.0.0.1", 9900)
x.clone(target)
