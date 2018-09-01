# Zero-Hub Client
This is the official python client module which allows you to browse and upload to the hub easily.

# Installation
You can install this module via pip:
```
pip install -e 'git+https://github.com/threefoldtech/0-hub#egg=zerohub&subdirectory=client'
```

# Usage
This module was generated using [go-raml](https://github.com/Jumpscale/go-raml)

Here is a sample usage, it's better to wrap this module. Some better version will arrive soon.

## Load the module
```python
from zeroos.zerohub import Client as ZHubClient

client = ZHubClient("https://hub.grid.tf/api")
api = client.api
```

## Public Access
```python
# returns available repositories (users) in a list
api.repositories.repositories_get().json()

# list all available flist for all repositories
api.flist.flist_get().json()

# list only flist for a specific repository (username)
api.flist.flist_byUsername_get(username).json()

# get the specification of a specific flist
api.flist.flist_byUsernameflist_get(username, flist).json()
```

## Authentification
The Zero-Hub is protected by [itsyou.online](https://itsyou.online), you can authentificate yourself
by providing a valid jwt token. A valid jwt can be extracted from your brower cookies or generated
using some itsyou.online endpoint.

```python
api.set_token("jwt-token")
```

To allows multi-users (eg: for organization upload), please add a scope `user:memberof:[organization]` to your token.
If you have scope for another username than your, you can switch user using:
```python
api.set_user("another-username")
```

## Authentificated Access
As soon as you are authentificated, you can do:

```python
# upload an archive (tar.gz) to the hub
api.flist.flist_meupload_post({'file': open(filename, 'rb')}, content_type='multipart/form-data')

# rename one of your flist
api.flist.flist_meflistrenametarget_get(source, destination).json()

# symlink one of your flist
api.flist.flist_meflistlinklinkname_get(source, linkname).json()

# delete one of your flist
api.flist.flist_meflist_delete(filename).json()
```
