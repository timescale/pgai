# syntax=docker/dockerfile:1.3-labs
FROM postgres:16

ENV WHERE_AM_I=docker
ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN set -e; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    postgresql-16-cron \
    postgresql-server-dev-16 \
    python3-pip \
    make \
    cmake \
    clang \
    git \
    vim

RUN set -e; \
    mkdir -p /build/timescaledb; \
    git clone https://github.com/timescale/timescaledb.git --branch 2.16.1 /build/timescaledb; \
    cd /build/timescaledb;  \
    bash ./bootstrap; \
    cd build && make; \
    make install; \
    rm -rf /build/timescaledb

ENV PIP_BREAK_SYSTEM_PACKAGES=1
COPY requirements-test.txt /build/requirements-test.txt
RUN pip install -r /build/requirements-test.txt
RUN rm -r /build

RUN set -eux; \
    git clone https://github.com/timescale/pgspot.git /build/pgspot; \
    pip install /build/pgspot; \
    rm -r /build

WORKDIR /pgai