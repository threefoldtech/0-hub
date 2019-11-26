import re
import time
import uuid
import requests
import json
from jose import jwt
from flask import current_app, redirect, request, session, flash
from functools import wraps
from urllib.parse import urlencode

__version__ = '0.0.1'

ITSYOUONLINEV1 = "https://itsyou.online/v1"
JWT_AUTH_HEADER = re.compile("^bearer (.*)$", re.IGNORECASE)
ITSYOUONLINE_KEY = """-----BEGIN PUBLIC KEY-----
MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAES5X8XrfKdx9gYayFITc89wad4usrk0n2
7MjiGYvqalizeSWTHEpnd7oea9IQ8T5oJjMVH5cc0H5tFSKilFFeh//wngxIyny6
6+Vq5t5B0V0Ehy01+2ceEon2Y0XDkIKv
-----END PUBLIC KEY-----"""


def force_invalidate_session():
    items = ['_iyo_authenticated', 'iyo_jwt', 'accounts', 'username']
    for item in items:
        if item in session:
            del session[item]

def _invalidate_session():
    authenticated_ = session.get('_iyo_authenticated')

    if not authenticated_ or authenticated_ + 300 < time.time():
        force_invalidate_session()


def disabled(app):
    app.config['authentication'] = False

def configure(app, client_id, client_secret, callback_uri, callback_route, scope=None, get_jwt=False, offline_access=False, orgfromrequest=False):
    """
    @param app: Flask app object
    @param client_id: Itsyou.Online api client id
    @param client_secret: Itsyou.Online api key client_secret
    @param callback_uri: Uri Itsyou.Online will target in the oauth flow.
                         Must be the same as the one configured in the Itsyou.Online
                         api key of the corresponding client_secret parameter.
    @param callback_route: Route to bind the callback handler to.
    @param scope: Extra scope to request from Itsyou.Online
    @param get_jwt: Set to True to also create a jwt for the authenticated user
    """
    app.before_request(_invalidate_session)
    app.config['authentication'] = True
    app.config['iyo_config'] = dict(
        client_id=client_id,
        client_secret=client_secret,
        callback_uri=callback_uri,
        callback_route=callback_route,
        scope=scope,
        get_jwt=get_jwt,
        offline_access=offline_access,
        orgfromrequest=orgfromrequest
    )

    app.add_url_rule(callback_route, '_callback', _callback)

def get_auth_org(org_from_request=False):
    if org_from_request and isinstance(org_from_request, str):
        return org_from_request

    config = current_app.config["iyo_config"]

    if org_from_request is True:
        return request.values[config['orgfromrequest']]

    return config['client_id']

def _extract_accounts(username, scopes):
    accounts = [username]

    for account in scopes:
        if not account:
            continue

        # parsing user:memberof:[organization]
        fields = account.split(':')
        if len(fields) < 3:
            continue

        accounts.append(fields[2])

    return accounts

def requires_auth():
    def decorator(handler):
        """
        Wraps route handler to be only accessible after authentication via Itsyou.Online
        """
        @wraps(handler)
        def _wrapper(*args, **kwargs):
            if not current_app.config['authentication']:
                session['accounts'] = ['Administrator']
                session['username'] = 'Administrator'
                return handler(*args, **kwargs)

            if session.get("_iyo_authenticated"):
                if request.cookies.get("active-user") in session['accounts']:
                    print("[+] using special user: %s" % request.cookies.get('active-user'))
                    session['username'] = request.cookies.get('active-user')

                return handler(*args, **kwargs)

            config = current_app.config["iyo_config"]
            scopes = []

            if config["scope"]:
                scopes.append(config['scope'])

            scope = ','.join(scopes)
            jwt_string = None

            # first check for Authorizaton method
            header = request.headers.get("Authorization")
            if header:
                match = JWT_AUTH_HEADER.match(header)
                if match:
                    jwt_string = match.group(1)

            # then, fallback to old caddy behavior
            if not jwt_string:
                jwt_string = request.cookies.get("caddyoauth")

            # checking jwt provided (if any set)
            if jwt_string:
                try:
                    jwt_info = jwt.decode(jwt_string, ITSYOUONLINE_KEY)
                    jwt_scope = jwt_info["scope"]
                    username = jwt_info["username"]

                except:
                    return json.dumps({"status": "error", "message": "invalid token"}) + "\n", 403

                session["_iyo_authenticated"] = time.time()
                session["iyo_jwt"] = jwt_string
                session['username'] = username
                session['accounts'] = _extract_accounts(jwt_info['username'], jwt_info['scope'])

                # check again for user-switch flag
                if request.cookies.get("active-user") in session['accounts']:
                    print("[+] using special user: %s" % request.cookies.get('active-user'))
                    session['username'] = request.cookies.get('active-user')

                return handler(*args, **kwargs)

            state = str(uuid.uuid4())
            session["_iyo_state"] = state
            session["_iyo_auth_complete_uri"] = request.full_path

            params = {
                "response_type": "code",
                "client_id": config["client_id"],
                "redirect_uri": config["callback_uri"],
                "scope": scope,
                "state": state
            }

            base_url = "{}/oauth/authorize?".format(ITSYOUONLINEV1)
            login_url = base_url + urlencode(params)
            return redirect(login_url)

        return _wrapper
    return decorator


def _callback():
    code = request.args.get("code")
    state = request.args.get("state")
    session_state = session.get("_iyo_state")
    on_complete_uri = session.get("_iyo_auth_complete_uri")

    if not on_complete_uri:
        return "Invalid request.", 400

    if session_state != state:
        return "Invalid state received. Cannot authenticate request!", 400

    if not code:
        return "Invalid code received. Cannot authenticate request!", 400

    # Get access token
    config = current_app.config["iyo_config"]

    params = {
        "code": code,
        "state": state,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": config["callback_uri"],
    }

    base_url = "{}/oauth/access_token?".format(ITSYOUONLINEV1)
    url = base_url + urlencode(params)

    response = requests.post(url)
    response.raise_for_status()
    response = response.json()
    scope_parts = response["scope"].split(",")

    """
    if not "user:memberof:{}".format(authorg) in scope_parts:
        flash("User is not authorized", "danger")
        return redirect("/")
    """

    access_token = response["access_token"]
    username = response["info"]["username"]

    # Get user info
    session['_iyo_authenticated'] = time.time()
    session['accounts'] = _extract_accounts(username, response['scope'])
    session['username'] = username

    if config['get_jwt']:
        params = dict()
        scopestr = ""

        if config["scope"]:
            scopestr += "user:memberof:{}".format(config['scope'])

            if config['offline_access']:
                scopestr += ",offline_access"

        params = dict(scope=scopestr)
        jwturl = "https://itsyou.online/v1/oauth/jwt?%s" % urlencode(params)
        headers = {"Authorization": "token %s" % access_token}

        response = requests.get(jwturl, headers=headers)
        response.raise_for_status()
        session['iyo_jwt'] = response.text

    return redirect(on_complete_uri)


