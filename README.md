# ZOS Flist Hub

A container image registry and management service for distributing flists, a lightweight container format used to package and deploy workloads on decentralized infrastructure.

## What this is

ZOS Flist Hub enables users to publish, discover, and deploy containerized applications using flists. It acts as a central repository for workload images and provides on-the-fly conversion from Docker images, direct archive upload, flist merging, and a REST API for automation.

Flist files are databases of metadata that describe container or VM contents. They allow workloads to be mounted on demand without shipping full image layers, making distribution efficient across a decentralized network.

## What this repository contains

- Web application and REST API for flist management
- Docker image-to-flist converter integration
- Archive upload and automatic flist generation
- Flist merging and cross-repository promotion tools
- Tag and symbolic link management
- Authentication layer (3bot)
- Docker deployment configuration in the `deployment/` directory

## Role in the stack

## ZOS / Zero-OS

ZOS, also known as Zero-OS, is the operating system layer used to run and manage nodes. It provides the low-level runtime environment for workloads, networking, storage, and automation.

ZOS Flist Hub is the distribution point for workload images consumed by ZOS nodes. When a user deploys a container or virtual machine, ZOS fetches the referenced flist from the hub and mounts the contents on the node. The hub therefore sits between image publishers and the runtime environment.

## Relation to ThreeFold

This technology is used within the ThreeFold ecosystem and was first deployed on the ThreeFold Grid. The component itself is designed as reusable infrastructure technology and should be understood by its technical function first, independent of any specific deployment.

## Ownership

This repository is owned and maintained by TF-Tech NV, a Belgian company responsible for the development and maintenance of this technology.

## Releases

- `master` — stable production version
- `playground` — development playground version

## Docker Image

You can use the GitHub Package directly:

```bash
docker pull ghcr.io/threefoldtech/0-hub:master
```

Mount points required:
- `/hub/src/config.py` — your configuration file
- `/public` — target public directories
- `/workdir` — target temporary directory
- `/var/run/docker.sock` — host Docker socket (for the image converter)

Configuration note:
- `zflist-bin` should be unset or set to `/usr/bin/zflist` (included in the image). Comment this line in the config to keep it simple.

The Dockerfile can be found in the `deployment/` directory.

## Features

### Public centralization of flists

The hub provides an easy way to distribute flist files. Flist files are databases of metadata that can be used in any Zero-OS container or VM.

### Uploading files

Upload a `.tar.gz` archive and the hub converts it automatically to a flist, storing the contents in the backend. After conversion the flist can be used directly on a container.

### Merging multiple flists

Flist allows you to keep different products and files separately, then merge them together. For example, you can create a flist containing your application files and merge it with an official base-system flist. The resulting flist contains your product on the latest version of the base system.

### Converting Docker images

Convert a Docker image (e.g., `busybox`, `ubuntu`, `fedora`, `couchdb`) to a flist directly from the backend. This allows existing Docker images to be used in the infrastructure out-of-the-box.

### Uploading existing flists

Using the hub-client, you can efficiently upload file contents to bring the backend up-to-date and upload a self-made flist. The only restriction is that the file contents referenced by the flist must exist on the backend; otherwise the flist will be rejected.

## API

The hub exposes a REST API for querying and managing flists.

### Public endpoints (no authentication)

- `/api/flist` (**GET**) — returns all repository/flist entries
- `/api/repositories` (**GET**) — returns all repositories
- `/api/fileslist` (**GET**) — returns all repositories and files
- `/api/flist/<repository>` (**GET**) — returns flists in the specified repository
- `/api/flist/<repository>/<flist>` (**GET**, **INFO**) — **GET**: full file list; **INFO**: reduced information
- `/api/flist/<repository>/<flist>/light` (**GET**) — same as **INFO**
- `/api/flist/<repository>/<flist>/taglink` (**GET**) — get target of a taglink
- `/api/flist/<repository>/tags/<tag>` (**GET**) — returns contents of a tag

### Restricted endpoints (authentication required)

- `/api/flist/me` (**GET**) — basic information about the authenticated user
- `/api/flist/me/<flist>` (**GET**, **DELETE**) — get or remove a specific flist
- `/api/flist/me/<source>/link/<linkname>` (**GET**) — create a symbolic link
- `/api/flist/me/<linkname>/crosslink/<repository>/<sourcename>` (**GET**) — create a cross-repository link
- `/api/flist/me/<source>/rename/<destination>` (**GET**) — rename a flist
- `/api/flist/me/promote/<sourcerepo>/<sourcefile>/<localname>` (**GET**) — copy a flist across repositories
- `/api/flist/me/upload` (**POST**) — upload a `.tar.gz` and convert it to a flist
- `/api/flist/me/upload-flist` (**POST**) — upload a `.flist` file directly
- `/api/flist/me/merge/<target>` (**POST**) — merge multiple flists
- `/api/flist/me/docker` (**POST**) — convert a Docker image to a flist
- `/api/flist/me/<tagname>/<name>/tag/<repository>/<flist>` (**GET**, **DELETE**) — add or remove a flist from a tag
- `/api/flist/me/<name>/crosstag/<repository>/<tagname>` (**GET**, **DELETE**) — create a cross-repository tag link

### Examples

Upload an archive:

```bash
curl -H "Authorization: bearer ...token..." -X POST -F file=@my-local-archive.tar.gz \
    https://hub.grid.tf/api/flist/me/upload
```

Promote a flist across repositories (assuming `member-of` in JWT):

```bash
curl -b "active-user=userX;" -H "Authorization: bearer ...token..." \
    "https://hub.grid.tf/api/flist/me/promote/user2/my-app-0.1.0/official-app-0.1.0"
```

## Backend

Flist creation uses [0-flist](https://github.com/threefoldtech/0-flist) and the storage backend is [0-db](https://github.com/threefoldtech/0-db). Both must be available before the hub is fully operational.

## Installation

To deploy your own hub, you need a working `0-flist` binary. See `deployment/deploy.sh` for compilation instructions, or download a precompiled release from the [0-flist releases](https://github.com/threefoldtech/0-flist/releases) page.

Copy `src/config.py.sample` to `src/config.py`, then start the server:

```bash
cd src
python flist-uploader.py
```

## Dependencies

The latest hub requires Flask > 2.0. Ubuntu 22.04 is recommended.

```bash
apt-get install python3-flask python3-requests python3-jose python3-nacl \
    python3-redis python3-docker python3-pytoml
```

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.
