from werkzeug.wrappers import Request
import json

class ItsYouChecker(object):
    """
    Create a common bridge between itsyou-online caddy integration
    and this app.

    Caddy-integration should be configured to forward-payload.
    We check the headers and can determine if the user is logged-in
    and if he is part of some official organization, this allows
    the user to upload « propoted-files » (officials)
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        req = Request(environ, shallow=True)
        environ['username'] = None
        environ['accounts'] = []

        # extracting the username set by the plugin
        if req.headers.get('X-Iyo-Username'):
            environ['username'] = req.headers.get('X-Iyo-Username')

        # caddy should forward the jwt-payload as json
        if req.headers.get('X-Iyo-Token'):
            data = json.loads(req.headers.get('X-Iyo-Token'))

            # extracting username from jwt and accounts from scopes
            if data.get('username'):
                environ['username'] = data['username']
                environ['accounts'] = [data['username']]

                for account in data['scope']:
                    if not account:
                        continue

                    # parsing user:memberof:[organization]
                    fields = account.split(':')
                    if len(fields) < 3:
                        continue

                    environ['accounts'].append(fields[2])

        # switch user if requested and allowed
        if req.cookies.get('active-user'):
            if req.cookies.get('active-user') in environ['accounts']:
                print("[+] switching user to %s" % req.cookies.get('active-user'))
                environ['username'] = req.cookies.get('active-user')

        return self.app(environ, start_response)
