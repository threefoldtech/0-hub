import json
import random
import string
import urllib.parse
import pprint
import requests
import nacl.public
import nacl.signing
import base64
import urllib.parse
import time
import re
from flask import Flask, request, redirect, session


"""
# Generate an x25519 key
openssl genpkey -algorithm x25519 -out private.key

# Extract raw private key, encode it in base64
openssl pkey -in private.key -text | xargs | sed -e 's/.*priv\:\(.*\)pub\:.*/\1/' | xxd -r -p | base64

# Extract raw public key, encode it in base64 (this is not needed on this code)
# Public key is generated from private key automatically
openssl pkey -in private.key -text_pub | grep '^ ' | xargs | xxd -r -p | base64
"""

class ThreeBotAuthenticator:
    def __init__(self, app, appid, privatekey, signseed):
        self.app = app
        self.appid = appid

        # Private key used to uncrypt ciphertext
        self.privkey = nacl.public.PrivateKey(privatekey, nacl.encoding.Base64Encoder)

        # Generate public key from the private key
        self.pubkey = self.privkey.public_key.encode(nacl.encoding.Base64Encoder).decode('utf-8')

        # SigningKey based on the configured seed
        self.signkey = nacl.signing.SigningKey(signseed)

        self.routes()

    def signed(self):
        # Verify that bearer authorization comes from us
        # and is signed from our privatekey
        header = request.headers.get("Authorization")
        match = re.compile("^bearer (.*)$", re.IGNORECASE).match(header)
        if not match:
            return "invalid authorization header", 400

        token = match.group(1)
        print(token)

        try:
            signed = self.signkey.verify_key.verify(token, None, nacl.encoding.URLSafeBase64Encoder)
            print(signed)

        except:
            print("Invalid signature")
            return "invalid signature", 401

        print("Authorized", signed)

        payload = signed.decode('utf-8')
        userdata = json.loads(payload)

        return userdata[0], 200

    def authorize(self):
        if request.args.get("error"):
            message = urllib.parse.quote(request.args.get("error"))
            return "Authentication failed: %s" % message, 400

        if not request.args.get('signedAttempt'):
            return "Could not parse server response" % message, 400

        payload = json.loads(request.args.get('signedAttempt'))
        username = payload['doubleName']

        # Signedhash contains state signed by user's bot key
        signedhash = payload['signedAttempt']

        print(signedhash)

        # Fetching user's bot information (including public key)
        userinfo = requests.get("https://login.threefold.me/api/users/%s" % username).json()
        userpk = userinfo['publicKey']

        # Verifying state signature
        try:
            vkey = nacl.signing.VerifyKey(userpk, nacl.encoding.Base64Encoder)
            data = vkey.verify(base64.b64decode(signedhash))
            data = json.loads(data.decode('utf-8'))

        except:
            print("Invalid signed hash")
            return 'Unable to verify state signature, denied.', 400

        ukey = vkey.to_curve25519_public_key()

        # Decrypt the ciphertext with our private key and bot's public key
        try:
            box = nacl.public.Box(self.privkey, ukey)
            ciphertext = base64.b64decode(data['data']['ciphertext'])
            nonce = base64.b64decode(data['data']['nonce'])

            response = box.decrypt(ciphertext, nonce)

        except:
            print("Could not decrypt cipher")
            return 'Unable to decrypt payload, denied.', 400

        values = json.loads(response.decode('utf-8'))

        if values.get("email") is not None:
            if values['email']['verified'] == None:
                return 'Email unverified, access denied.', 400

        print("[+] threebot: user '%s' authenticated" % username)

        return username, 200

    def logrequest(self, callback):
        # Public backend authenticator service
        authurl = "https://login.threefold.me"

        # State is a random string
        allowed = string.ascii_letters + string.digits
        state = ''.join(random.SystemRandom().choice(allowed) for _ in range(32))

        # Encode payload with urlencode then passing data to the GET request
        payload = {
            'appid': self.appid,
            'publickey': self.pubkey,
            'state': state,
            'redirecturl': callback,
            'scope': {},
        }

        result = urllib.parse.urlencode(payload, quote_via=urllib.parse.quote_plus)

        return redirect("%s/?%s" % (authurl, result), code=302)

    def routes(self):
        @self.app.route('/callback_threebot')
        def callback_login():
            message, code = self.authorize()

            if code is not 200:
                return message, code

            username = message

            session['authenticated'] = True
            session['username'] = username
            session['accounts'] = [username]

            return redirect("/")

        @self.app.route('/callback_token')
        def callback_token():
            message, code = self.authorize()

            if code is not 200:
                return message, code

            payload = [message, int(time.time())]

            bpayload = json.dumps(payload).encode()
            signed = self.signkey.sign(bpayload, nacl.encoding.URLSafeBase64Encoder)
            hexsign = signed.decode('utf-8')

            return redirect("/token/%s" % hexsign, code=302)

        @self.app.route('/login')
        def login():
            return self.logrequest("/callback_threebot")

        @self.app.route('/token')
        def token():
            return self.logrequest("/callback_token")

def configure(app, appid, privatekey, signseed):
    app.config['threebot_config'] = dict(
        appid=appid,
        privatekey=privatekey
    )

    auth = ThreeBotAuthenticator(app, appid, privatekey, signseed)

    app.config['threebot_config']['auth'] = auth

