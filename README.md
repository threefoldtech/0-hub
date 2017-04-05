# G8OS Hub Website
This is a the G8OS Hub Website repository. It contains all the source code needed to make the public Hub front-end.

## Releases:
- [1.0.0](https://github.com/g8os/hub/tree/1.0.0) - last release

# Installation
- Grab a `caddy` version which supports `itsyouonline-oauth` [caddy-integration](https://github.com/itsyouonline/caddy-integration)
- Clone this repository
- Configure the following:
  - Copy `Caddyfile.sample` to `Caddyfile` and adapt:
    - `0.0.0.0:2015`: change it to your website host (without port, ssl will be generated)
    - `__CLIENT_ID__`: your itsyou.online Organisation's API Label
    - `__CLIENT_SECRET__`: your itsyou.online Organisation's API Secret
    - `__HOST__`: your public host where the callback will be called (need to be set on itsyou.online too)
  - `python/config.py`:
    - `PUBLIC_ARDB_HOST`: your ardb public host (read only support)
    - `PUBLIC_ARDB_PORT`: your ardb public port (read only support)
    - `PRIVATE_ARDB_HOST`: your ardb private host (read-write support)
    - `PRIVATE_ARDB_PORT`: your ardb private host (read-write support)
    - `PUBLIC_WEBADD`: your public web url (where the flist will be grabbed publicly)
- Run the caddy server: `caddy`
- Run the python server: `cd python && jspython flist-uploader.py`

Note: the python server needs `jumpscale 8.2.0` with `g8storclient` to works.

