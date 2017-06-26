# Zero-OS Hub

This is the repository for the Zero-OS Hub website. It contains all the source code needed to make the public Zero-OS Hub website.

## Releases
- [1.0.0](https://github.com/zero-os/0-hub/tree/1.0.0) - last release

## Installation
- Grab a `caddy` version which supports `itsyouonline-oauth` [caddy-integration](https://github.com/itsyouonline/caddy-integration)
- Clone this repository
- Configure the following:
  - Copy `Caddyfile.sample` to `Caddyfile` and adapt:
    - `0.0.0.0:2015`: change it to your website host (without port, ssl will be generated)
    - `__CLIENT_ID__`: your ItsYou.online organisation's API label
    - `__CLIENT_SECRET__`: your ItsYou.online organization's API secret
    - `__HOST__`: your public host where the callback will be called (need to be set on ItsYou.online too)
  - `python/config.py`:
    - `PUBLIC_ARDB_HOST`: your ARDB public host (read only support)
    - `PUBLIC_ARDB_PORT`: your ARDB public port (read only support)
    - `PRIVATE_ARDB_HOST`: your ARDB private host (read-write support)
    - `PRIVATE_ARDB_PORT`: your ARDB private host (read-write support)
    - `PUBLIC_WEBADD`: your public web url (where the flist will be grabbed publicly)
- Run the Caddy server: `caddy`
- Run the Python server: `cd python && jspython flist-uploader.py`

> Note: the Python server needs `jumpscale 8.2.0` with `g8storclient` to works.

## Documentation

For more documentation see the [`/docs`](./docs) directory.
