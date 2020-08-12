import queue
import json

class EventNotifier:
    def __init__(self):
        self.listeners = {}

    def initialize(self, id):
        q = queue.Queue(maxsize=16)
        self.listeners[id] = q
        return q

    def error(self, msg):
        return {"status": "error", "message": msg}

    # flag this id as ended, should be cleaned up later
    def finalize(self, id):
        self.listeners[id].put_nowait(None)
        return True

    # clean the task id
    def terminate(self, id):
        print("[+] notify: cleaning up: %s" % id)
        del self.listeners[id]
        return True

    # push an object to a channel
    def push(self, id, item):
        return self.announce(id, json.dumps(item))

    # returns pushable object over the wire
    def raw(self, item):
        return self.format(json.dumps(item))

    # grab queue channel if exists
    def listen(self, id):
        if id not in self.listeners:
            return None

        return self.listeners[id]

    def format(self, data):
        return f'data: {data}\n\n'

    def announce(self, id, msg):
        # print(id, msg)
        msg = self.format(msg)

        if id not in self.listeners:
            return None

        self.listeners[id].put_nowait(msg)


