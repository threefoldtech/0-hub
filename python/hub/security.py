from flask import request, redirect, session
from functools import wraps
from config import config
import hub.itsyouonline
import hub.threebot

def protected():
    def decorator(handler):
        @wraps(handler)
        def _wrapper(*args, **kwargs):
            if not config['authentication']:
                session['accounts'] = ['Administrator']
                session['username'] = 'Administrator'
                return handler(*args, **kwargs)

            print(session.get("authenticated"))

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

