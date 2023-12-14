# Docker Build for 0-hub

Build the image using the Dockerfile. When it's ready, here are some point you need to run the hub:
- Mount `/hub/src/config.py` with your configuration file
- Mount `/public` with your target public directories
- Mount `/workdir` with your target temporary directory
- Mount host docker.sock to `/var/run/docker.sock` to be able to run docker converter

Regarding configuration, here are some requirement:
- `zflist-bin` have to be set to: `/usr/bin/zflist` (it's part of the image)
