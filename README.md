# Zero-OS Hub

This is the repository for the Zero-OS Hub website.
It contains all the source code needed to make the public Zero-OS Hub website.

## Releases
- [master](https://github.com/threefoldtech/0-hub/tree/master) - stable production version
- [playground](https://github.com/threefoldtech/0-hub/tree/playground) - development playground version

# Docker Image

You can use GitHub Package directly: `docker pull ghcr.io/threefoldtech/0-hub:master`

Here are some point you need to run the hub:
- Mount `/hub/src/config.py` with your configuration file
- Mount `/public` with your target public directories
- Mount `/workdir` with your target temporary directory
- Mount host docker.sock to `/var/run/docker.sock` to be able to run docker converter

Regarding configuration, here are some requirement:
- `zflist-bin` have to be set to: `/usr/bin/zflist` (it's part of the image)

Dockerfile can be found on `deployment` directory.

# The Hub
The Zero OS Hub allows you to do multiple things.

## Public centralization of flists
The hub is mainly there to gives an easy way to distribute flist files.
Flist are database of metadata you can use in any Zero-OS container/vm.

## Uploading your files
In order to publish easily your files, you can upload a `.tar.gz` and the hub will convert it automatically to a flist
and store the contents in the hub backend. After that you can use your flist directly on a container.

## Merging multiple flists
In order to reduce the maintenance of your images, products, etc. flist allows you to keep your
different products and files separately and then merge them with another flist to make it usable without
keeping the system up-to-date.

Example: there is an official `ubuntu 16.04` flist image, you can make a flist which contains your application files
and then merge your flist with ubuntu, so the resulting flist is your product on the last version of ubunbu.
You don't need to take care about the base system yourself, just merge it with the one provided.

## Convert a docker hub's image to a flist on-the-fly
You can convert a docker image (eg: `busybox`, `ubuntu`, `fedora`, `couchdb`, ...) to a flist directly from
the backend, this allows you to use your existing docker image in our infrastructure out-of-the-box.

## Upload your existing flist to reduce bandwidth
In addition with the hub-client (a side product) you can upload efficiently contents of file
to make the backend up-to-date and upload a self-made flist. This allows you to do all the jobs yourself
and gives you the full control of the chain. The only restriction is that the contents of the files you host
on the flist needs to exists on the backend, otherwise your flist will be rejected.

## Authentication via 3bot or itsyou.online
All the operations on the hub needs to be done via a `3bot` (default) or `itsyou.online` (deprecated) authentication.
Only downloading a flist can be done anonymously.

## Getting information through API
The hub host a basic REST API which can gives you some informations about flists, renaming them, remove them, etc.

To use authenticated endpoints, you need to provide a itsyou.online valid `jwt` via `Authorization: bearer <jwt>` header.
This `jwt` can contains special `memberof` to allows you cross-repository actions.

If your `jwt` contains memberof, you can choose which user you want to use by specifying cookie `active-user`.
See example below.

### Public API endpoints (no authentication needed)
- `/api/flist` (**GET**)
  - Returns a json array with all repository/flists found
- `/api/repositories` (**GET**)
  - Returns a json array with all repositories found
- `/api/fileslist` (**GET**)
  - Returns a json array with all repositories and files found
- `/api/flist/<repository>` (**GET**)
  - Returns a json array of each flist found inside specified repository.
  - Each entry contains `filename`, `size`, `updated` date and `type` (regular, symlink, taglink) and optionally `target` if it's a link.
- `/api/flist/<repository>/<flist>` (**GET**, **INFO**)
  - **GET**: returns json object with flist dumps (full file list)
  - **INFO**: returns a reduced information (no files dumps) about flist
- `/api/flist/<repository>/<flist>/light` (**GET**)
  - Same as **INFO** above
- `/api/flist/<repository>/<flist>/taglink` (**GET**)
  - Get target of a `taglink` (link to a tag)
- `/api/flist/<repository>/tags/<tag>` (**GET**)
  - Returns content of a tags (links inside a tag)

### Restricted API endpoints (authentication required)
- `/api/flist/me` (**GET**)
  - Returns json object with some basic information about yourself (authenticated user)
- `/api/flist/me/<flist>` (**GET**, **DELETE**)
  - **GET**: same as `/api/flist/<your-repository>/<flist>`
  - **DELETE**: remove that specific flist (or taglink)
- `/api/flist/me/<source>/link/<linkname>` (**GET**)
  - Create a symbolic link `linkname` pointing to `source`
- `/api/flist/me/<linkname>/crosslink/<repository>/<sourcename>` (**GET**)
  - Create a cross-repository symbolic link `linkname` pointing to `repository/sourcename`
- `/api/flist/me/<source>/rename/<destination>` (**GET**)
  - Rename `source` to `destination`
- `/api/flist/me/promote/<sourcerepo>/<sourcefile>/<localname>` (**GET**)
  - Copy cross-repository `sourcerepo/sourcefile` to your `[local-repository]/localname` file
  - This is useful when you want to copy flist from one repository to another one, if your jwt allows it
- `/api/flist/me/upload` (**POST**)
  - **POST**: uploads a `.tar.gz` archive and convert it to an flist
  - Your file needs to be passed via `file` form attribute
- `/api/flist/me/upload-flist` (**POST**)
  - **POST**: uploads a `.flist` file and store it
  - Note: the flist is checked and full contents is verified to be found on the backend, if some chunks are missing, the file will be discarded.
  - Your file needs to be passed via `file` form attribute
- `/api/flist/me/merge/<target>` (**POST**)
  - **POST**: merge multiple flist together
  - You need to passes a json array of flists (in form `repository/file`) as POST body
- `/api/flist/me/docker` (**POST**)
  - **POST**: converts a docker image to an flist
  - You need to passes `image` form argument with docker-image name
  - The resulting conversion will stay on your repository
- `/api/flist/me/<tagname>/<name>/tag/<repository>/<flist>` (**GET**, **DELETE**)
  - **GET**: add flist `repository/flist` in user tag `tagname` with name `name`
  - **DELETE**: remove `name` from `tagname`, if tag become empty, tag is removed
- `/api/flist/me/<name>/crosstag/<repository>/<tagname>` (**GET**, **DELETE**)
  - **GET**: create a link `name` inside your repository, pointing to `repository/tag`
 
### Example
Simple example how to upload to the hub in command line. Your token can be generated on the website.
```bash
curl -H "Authorization: bearer ...token..." -X POST -F file=@my-local-archive.tar.gz \
    https://hub.grid.tf/api/flist/me/upload
```

Simple example how to use all feature to do some flist promotion. In this case, let assume:
- The real user is `user1`
- This user have `member-of` field for `userX` in his jwt
- This user want to promote `user2/my-app-0.1.0` flist to `userX/official-app-0.1.0`

```bash
curl -b "active-user=userX;" -H "Authorization: bearer ...token..." \
    "https://hub.grid.tf/api/flist/me/promote/user2/my-app-0.1.0/official-app-0.1.0"
```

# Backend
Creation of flists are made using [0-flist](https://github.com/threefoldtech/0-flist) and storage backend is [0-db](https://github.com/threefoldtech/0-db).
You need both of them working before getting a working hub.

# Installation
In order to deploy your own hub, you need a working `0-flist` binary. You can see in `deployment/deploy.sh` script how to compile it.
Alternatively, you can just download a precompiled version from [0-flist release](https://github.com/threefoldtech/0-flist/releases) page.

Copy the `src/config.py.sample` file to `src/config.py`, the file itself is well documented, then you can start the server:
```sh
cd src
python flist-uploader.py
```

# Dependencies

To run latest hub, you need Flask >2.0. We recommend using Ubuntu 22.04.

```
apt-get install python3-flask python3-requests python3-jose python3-nacl \
    python3-redis python3-docker python3-pytoml
```

# Repository Owner
- [Maxime Daniel](https://github.com/maxux), Telegram: [@maxux](http://t.me/maxux)
