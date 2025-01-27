FROM ubuntu:20.04 AS build

RUN apt-get update && \
  apt-get install -y build-essential git libsnappy-dev libz-dev \
        libtar-dev libb2-dev autoconf libtool libjansson-dev \
        libhiredis-dev libsqlite3-dev tmux vim \
        python3-flask python3-redis python3-docker python3-pytoml \
        libssl-dev python3-pip python3-requests python3-nacl

RUN git clone --depth=1 -b curl-7_62_0 https://github.com/curl/curl && \
  cd curl && \
  autoreconf -f -i -s && \
  ./configure --disable-debug --enable-optimize --disable-curldebug --disable-symbol-hiding --disable-rt \
        --disable-ftp --disable-ldap --disable-ldaps --disable-rtsp --disable-proxy --disable-dict \
        --disable-telnet --disable-tftp --disable-pop3 --disable-imap --disable-smb --disable-smtp --disable-gopher \
        --disable-manual --disable-libcurl-option --disable-sspi --disable-ntlm-wb --without-brotli --without-librtmp --without-winidn \
        --disable-threaded-resolver \
        --with-openssl && \
  make -j 4 && \
  make install && \
  ldconfig

RUN git clone https://github.com/opensourcerouting/c-capnproto && \
  cd c-capnproto && \
  git submodule update --init --recursive && \
  autoreconf -f -i -s && \
  ./configure && \
  make -j 4 && \
  make install && \
  ldconfig

RUN git clone -b development-v2 https://github.com/threefoldtech/0-flist /0-flist && \
  cd /0-flist/libflist && \
  make && \
  cd ../zflist && \
  make production

RUN git clone https://github.com/threefoldtech/0-hub /hub && tar -cf /hub.tar /hub

FROM ubuntu:22.04

COPY --from=build /0-flist/zflist/zflist /usr/bin/
COPY --from=build /hub.tar /

RUN export DEBIAN_FRONTEND=noninteractive && \
  export DEBCONF_NONINTERACTIVE_SEEN=true && \
  apt-get update && apt-get install -y \
  python3-flask python3-redis python3-docker python3-pytoml \
  python3-requests python3-nacl python3-jose \
  docker.io && \
  tar -xf /hub.tar -C / && rm -f /hub.tar && \
  mkdir /public /workdir && \
  touch /.hub-container && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /hub/src
ENTRYPOINT ["python3", "flist-uploader.py"]
