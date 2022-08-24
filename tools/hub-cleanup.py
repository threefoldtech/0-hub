import redis
import subprocess
import json
import sys
import os
from collections import defaultdict

sys.path.insert(1, os.path.join(sys.path[0], '../python'))
from config import config

# FIXME for debug purpose
config['backend-internal-host'] = "hub.grid.tf"

class HubCleanup:
    def __init__(self):
        self.r = redis.Redis(config['backend-internal-host'], config['backend-internal-port'])
        self.environ = dict(
            os.environ,
            ZFLIST_JSON="1",
            ZFLIST_MNT="/tmp/zflistcleanup"
        )

        self.chunks = defaultdict(int)
        self.stats = {
            'total-chunks': 0,
        }

        try:
            # close any previously opened flist
            self.execute(["close"])

        except Exception:
            pass

    def execute(self, command):
        command = [config['zflist-bin']] + command
        # print(command)

        p = subprocess.Popen(command, env=self.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.stdout.readline()
        result = json.loads(output)

        if result['success'] != True:
            raise RuntimeError(result['error'])

        return result

    def chunks_file(self, filename):
        self.execute(["open", filename])
        chunks = self.execute(["chunks"])
        self.execute(["close"])

        # returns array of bytes string from hex string
        return [bytes.fromhex(a) for a in chunks['response']['content']]

    def chunks_all(self):
        usersdir = os.path.join(config['userdata-root-path'], "users")
        users = os.listdir(usersdir)

        for user in users:
            userdir = os.path.join(usersdir, user)
            if not os.path.isdir(userdir):
                print(f"[-] skipping: {userdir}")
                continue

            files = os.listdir(userdir)

            for file in files:
                print(f"[+] loading chunks: {user}/{file}")

                chunks = self.chunks_file(os.path.join(userdir, file))
                self.stats['total-chunks'] += len(chunks)

                for chunk in chunks:
                    self.chunks[chunk] += 1

    def chunks_stats(self):
        chunks = len(self.chunks)

        print(f"[+] unique chunks: {chunks}")
        print(f"[+] total chunks : {self.stats['total-chunks']}")

    def cleanup(self):
        pass


if __name__ == '__main__':
    cleaner = HubCleanup()
    cleaner.chunks_all()
    cleaner.chunks_stats()
    cleaner.cleanup()
