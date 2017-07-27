# Zero-OS Hub

This is the repository for the Zero-OS Hub website.
It contains all the source code needed to make the public Zero-OS Hub website.

## Releases
- [master](https://github.com/zero-os/0-hub/) - current running version
- [1.0.0](https://github.com/zero-os/0-hub/tree/1.0.0) - initial release

# The Hub
The Zero OS Hub allows you to do multiple things.

## Public centralization of flists
The hub is mainly there to gives an easy way to distribute flist files.
Flist are database of metadata you can use in any Zero-OS container.

## Uploading your files
In order to publish easily your files, you can upload a `.tar.gz` and the hub will convert it automaticaly to a flist
and store the contents in the hub backend. After that you can use your flist directly on a container.

## Merging multiple flists
In order to reduce the maintenance of your images, products, etc. flist allows you to keep your
differents products and files separatly and then merge them with another flist to make it usable without
keeping the system up-to-date.

Exemple: there is an officiel `ubuntu 16.04` flist image, you can make a flist which contains your application files
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

## Authentification via itsyou.online
All the operations on the hub needs to be done via a `itsyou.online` authentification. Only downloading
a flist can be done anonymously.

## Getting information through API
The hub host a basic REST API which can gives you some informations about flists, renaming them, remove them, etc.
Please see the documentation to have more information.

# Documentation
For full documentation, see the [`/docs`](/docs) directory.
