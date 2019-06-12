#!/bin/bash

if [ -z "$1" ]; then
    echo "Missing hub deployment target directory"
    exit 1
fi

makeopts="-j 5"

clean() {
    rm -rf /opt/0-flist
    rm -rf /opt/c-capnproto
    rm -rf /opt/curl
    rm -rf $1
}

dependencies() {
    apt-get update

    apt-get install -y build-essential git libsnappy-dev libz-dev \
        libtar-dev libb2-dev autoconf libtool libjansson-dev \
        libhiredis-dev libsqlite3-dev tmux vim \
        python3-flask python3-redis python3-docker python3-pytoml \
        libssl-dev
}

libcurl() {
    git clone --depth=1 -b curl-7_62_0 https://github.com/curl/curl
    pushd curl
    autoreconf -f -i -s

    ./configure --disable-debug --enable-optimize --disable-curldebug --disable-symbol-hiding --disable-rt \
        --disable-ftp --disable-ldap --disable-ldaps --disable-rtsp --disable-proxy --disable-dict \
        --disable-telnet --disable-tftp --disable-pop3 --disable-imap --disable-smb --disable-smtp --disable-gopher \
        --disable-manual --disable-libcurl-option --disable-sspi --disable-ntlm-wb --without-brotli --without-librtmp --without-winidn \
        --disable-threaded-resolver \
        --with-openssl

    make ${makeopts}
    make install
    ldconfig

    popd
}

capnp() {
    git clone https://github.com/opensourcerouting/c-capnproto
    pushd c-capnproto
    git submodule update --init --recursive
    autoreconf -f -i -s

    ./configure
    make ${makeopts}
    make install
    ldconfig

    popd
}

zeroflist() {
    git clone -b development https://github.com/threefoldtech/0-flist
    pushd 0-flist

    pushd libflist
    make
    popd

    pushd zflist
    make production
    popd

    cp zflist/zflist /tmp/zflist
    strip -s /tmp/zflist

    popd
}

hub() {
    git clone -b zflist https://github.com/threefoldtech/0-hub $1

    cp $1/python/config.py.sample $1/python/config.py
    cp $1/Caddyfile.sample $1/Caddyfile

    sed -i "s/__PYTHON_HOST__:5000/127.0.0.1:5555/g" $1/Caddyfile
    sed -i "s/0.0.0.0:2015/0.0.0.0:80/g" $1/Caddyfile

    # FIXME: missing caddy
}

set -ex

pushd /opt

clean $1
dependencies
capnp
libcurl
zeroflist
hub $1

set +ex

echo "================================================"
echo " - Please edit $1/python/config.py"
echo " - And then run your hub inside a tmux, with:"
echo "    cd $1/python && python3 flist-uploader.py"
echo "================================================"

popd

