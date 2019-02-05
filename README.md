# Zero-OS Hub

This is the repository for the Zero-OS Hub website.
It contains all the source code needed to make the public Zero-OS Hub website.

## Releases
- [zflist](https://github.com/threefoldtech/0-hub/tree/zflist) - current running production version
- [1.0.0](https://github.com/threefoldtech/0-hub/tree/1.0.0) - initial release

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

## Authentication via itsyou.online
All the operations on the hub needs to be done via a `itsyou.online` authentication. Only downloading
a flist can be done anonymously.

## Getting information through API
The hub host a basic REST API which can gives you some informations about flists, renaming them, remove them, etc.

To use authenticated endpoints, you need to provide a itsyou.online valid `jwt` via cookie `caddyoauth`.
This `jwt` can contains special `memberof` to allows you cross-repository actions.

If your `jwt` contains memberof, you can choose which user you want to use by specifying cookie `active-user`.
See example below.

### Public API endpoints (no authentication needed)
- `/api/flist` (**GET**)
  - Returns a json array with all repository/flists found
- `/api/repositories` (**GET**)
  - Returns a json array with all repositories found
- `/api/flist/<repository>` (**GET**)
  - Returns a json array of each flist found inside specified repository.
  - Each entry contains `filename`, `size`, `updated` date and `type` (regular or symlink), optionally `target` if it's a symbolic link.
- `/api/flist/<repository>/<flist>` (**GET**)
  - Returns json object with flist dumps (full file list)

### Restricted API endpoints (authentication required)
- `/api/flist/me` (**GET**)
  - Returns json object with some basic information about yourself (authenticated user)
- `/api/flist/me/<flist>` (**GET**, **DELETE**)
  - **GET**: same as `/api/flist/<your-repository>/<flist>`
  - **DELETE**: remove that specific flist
- `/api/flist/me/<source>/link/<linkname>` (**GET**)
  - Create a symbolic link `linkname` pointing to `source`
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

### Example
Simple example how to use all feature to do some flist promotion. In this case, let assume:
- The real user is `user1`
- This user have `member-of` field for `userX` in his jwt
- This user want to promote `user2/my-app-0.1.0` flist to `userX/official-app-0.1.0`

```
curl -b "active-user=userX; caddyoauth=[...jwt...]" \
    "https://hub.grid.tf/api/flist/me/promote/user2/my-app-0.1.0/official-app-0.1.0"
```

### Client
There is a python client which can be found on the [client](client) directory.
This make all of this more easy.

# Backend
Creation of flists are made using [0-flist](https://github.com/threefoldtech/0-flist) and storage backend is [0-db](https://github.com/threefoldtech/0-db)

# Documentation
For full documentation, see the [`/docs`](/docs) directory.

# Repository Owner
- [Maxime Daniel](https://github.com/maxux), Telegram: [@maxux](http://t.me/maxux)
