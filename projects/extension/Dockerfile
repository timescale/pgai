# syntax=docker/dockerfile:1.3-labs
ARG PG_MAJOR
FROM postgres:${PG_MAJOR}

ENV WHERE_AM_I=docker
ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN set -e; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
    postgresql-plpython3-${PG_MAJOR} \
    postgresql-${PG_MAJOR}-pgvector \
    postgresql-${PG_MAJOR}-pgextwlist \
    postgresql-server-dev-${PG_MAJOR} \
    python3-pip \
    build-essential \
    pkg-config \
    make \
    cmake \
    clang \
    git \
    curl \
    vim

# install timescaledb
RUN set -e; \
    mkdir -p /build/timescaledb; \
    git clone https://github.com/timescale/timescaledb.git --branch 2.17.1 /build/timescaledb; \
    cd /build/timescaledb;  \
    bash ./bootstrap; \
    cd build && make; \
    make install; \
    rm -rf /build/timescaledb

# install pgvectorscale
ARG RUSTFLAGS
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN set -e; \
    rustup install stable; \
    cargo install cargo-pgrx --version 0.12.5 --locked; \
    cargo pgrx init --pg${PG_MAJOR} pg_config; \
    mkdir -p /build/pgvectorscale; \
    git clone --branch 0.4.0 https://github.com/timescale/pgvectorscale /build/pgvectorscale; \
    cd /build/pgvectorscale/pgvectorscale; \
    if [ -n "$RUSTFLAGS" ]; then \
      export RUSTFLAGS=${RUSTFLAGS}; \
    fi; \
    cargo pgrx install --release --features pg${PG_MAJOR}; \
    rm -rf /build/pgvectorscale

# install pgspot
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN set -eux; \
    git clone https://github.com/timescale/pgspot.git /build/pgspot; \
    pip install /build/pgspot; \
    rm -rf /build/pgspot

# install our test python dependencies
ENV PIP_BREAK_SYSTEM_PACKAGES=1
COPY requirements-test.txt /build/requirements-test.txt
RUN pip install -r /build/requirements-test.txt
RUN rm -r /build

WORKDIR /pgai
