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
        libssl-dev python3-pip python3-requests python3-nacl

    pip3 install python-jose
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

    popd
}

hub() {
    git clone -b playground https://github.com/threefoldtech/0-hub $1

    cp $1/python/config.py.sample $1/python/config.py

    sed -i "s/'authentication': True/'authentication': False/" $1/python/config.py
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

