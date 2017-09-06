import requests

class ZeroHubClient:
    def __init__(self, jwt):
        self.baseurl = 'https://hub.gig.tech'
        self.cookies = dict(caddyoauth=jwt)

    def upload(self, filename):
        files = {'file': open(filename,'rb')}
        r = requests.post('%s/upload' % self.baseurl, files=files, cookies=self.cookies)
        print(r.text)

        return True

    def merge(self, sources, target):
        arguments = []

        for source in sources:
            arguments.append(('flists[]', source))

        arguments.append(('name', target))
        r = requests.post('%s/merge' % self.baseurl, data=arguments, cookies=self.cookies)
        print(r.text)

        return True
