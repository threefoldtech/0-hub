from flask import request, redirect, session, current_app, jsonify
from functools import wraps
from config import config
import hub.itsyouonline
import hub.threebot

def apicall():
    def decorator(handler):
        @wraps(handler)
        def _wrapper(*args, **kwargs):
            if not config['authentication']:
                session['accounts'] = ['Administrator']
                session['username'] = 'Administrator'
                return handler(*args, **kwargs)

            threebot = current_app.config['threebot_config']['auth']

            if not request.headers.get("Authorization"):
                return jsonify({"message": "no authorization provided", "status": "error"}), 401

            # We won't have any dot in threebot base64 token
            # if we have some dots in the token, it's the jwt from
            # itsyou online
            if "." in request.headers.get("Authorization"):
                error, code = hub.itsyouonline.authenticate()

                if code != 200:
                    return error, code

                return handler(*args, **kwargs)

            # Let's authenticate using new threebot login
            authorized, code = threebot.signed()

            print("Authorized", authorized)

            if code == 200:
                session['accounts'] = [authorized]
                session['username'] = authorized
                return handler(*args, **kwargs)

            return jsonify({"message": authorized, "status": "error"}), code

        return _wrapper
    return decorator

def protected():
    def decorator(handler):
        @wraps(handler)
        def _wrapper(*args, **kwargs):
            if not config['authentication']:
                session['accounts'] = ['Administrator']
                session['username'] = 'Administrator'
                return handler(*args, **kwargs)

            if not session.get('authenticated'):
                return redirect("/login-method")

            return handler(*args, **kwargs)

        return _wrapper
    return decorator

def invalidate():
    items = ['authenticated', '_iyo_authenticated', 'iyo_jwt', 'accounts', 'username']

    for item in items:
        if item in session:
            del session[item]

