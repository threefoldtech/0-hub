# Hosting your own 0-hub (Zero-OS Hub) instance

All the code for the Hub can be found on https://github.com/zero-os/0-hub

## Global remarks

- Create an ItsYou.online API key in order to get a client secret
- Make sure to set the callback URL, including `_iyo_callback`
- Compile Caddy with the OAuth plugin for ItsYou.online, available from https://github.com/itsyouonline/caddy-integration
- Install JumpScale 9, this version contains all dependencies needed by flist, used on the Hub
- Install the legacy storage client (`g8storclient`) available on pypi
- Deploy an ARDB instance for the storage
  - Make it read-write (default)
  - No specific backend is required, RocksDB is a good choice
  - Expose this ARDB instance  as `PRIVATE_ARDB_` in the config
  - Don't expose it publicly
- Deploy a an ARDB instance in `slave-of` mode
  - Make it read-only (default)
  - Expose this Redis instance as `PUBLIC_ARDB_` in the config
  - Exposed it publicly

## Installation

The webservice itself is just a python webserver which should works on any system supported by Python/Flask but
we only support officially Ubuntu 16.04 and we will provide only instruction for this Linux distribution here.

### Dependencies

In order to run the hub correctly, you need some dependencies:

- Direct dependencies for g8storclient:
  - `apt-get install python3 libhiredis-dev libssl-dev libsnappy-dev python3-pip`
- The modules needed by the webservice:
  - `pip3 install -r requirements.txt`
- Install Jumpscale and it's dependencies:
  - `apt-get install git curl ssh`
  - `pip3 install -e git+https://github.com/jumpscale/core9#egg=jumpscale9`
  - `pip3 install -e git+https://github.com/jumpscale/lib9#egg=jumpscale9lib`
- Grab a `caddy` version which supports `itsyouonline-oauth` [caddy-integration](https://github.com/itsyouonline/caddy-integration)
- Clone this repository

### Configuration
- Configure the following:
  - Copy `Caddyfile.sample` to `Caddyfile` and adapt:
    - `0.0.0.0:2015`: change it to your website host (without port, ssl will be generated)
    - `__CLIENT_ID__`: your ItsYou.online organisation's API label
    - `__CLIENT_SECRET__`: your ItsYou.online organization's API secret
    - `__HOST__`: your public host where the callback will be called (need to be set on ItsYou.online too)
  - Copy `python/config.py.sample` to `python/config.py` and adapt:
    - `PUBLIC_ARDB_HOST`: your ARDB public host (read only support)
    - `PUBLIC_ARDB_PORT`: your ARDB public port (read only support)
    - `PRIVATE_ARDB_HOST`: your ARDB private host (read-write support)
    - `PRIVATE_ARDB_PORT`: your ARDB private host (read-write support)
    - `PUBLIC_WEBADD`: your public web url (where the flist will be grabbed publicly)
    - `PUBLIC_IGNORE`: a list of files which are ignored when listing users files
    - `PUBLIC_OFFICIALS`: a list of users who are 'official' repositories (pinned at top of the list)
    - `DEBUG`: boolean in order to enable debug feature of Flask and internal stuff

### Running
- Run the Caddy server: `caddy`
- Run the Python server: `cd python && jspython flist-uploader.py`


## Testing

To make sure everything works:

- You should be able to access the Hub front page, click on the `Upload my files` button, and able to login with your ItsYou.online credentials
- On the upload page, you should see your username in the top right corner
- Create a small `.tar.gz` file with anything you want on it, and upload it
- The summary page should appear with all links working properly
