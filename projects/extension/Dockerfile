# syntax=docker/dockerfile:1.3-labs
ARG PG_MAJOR=17
ARG PGVECTORSCALE_VERSION=0.5.1

###############################################################################
# base image
FROM postgres:${PG_MAJOR} as base
ARG PGVECTORSCALE_VERSION
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
    git \
    curl \
    vim \
    && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin/

# install timescaledb
RUN set -e; \
    apt-get install -y gnupg postgresql-common apt-transport-https lsb-release wget; \
    /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y; \
    echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main" | tee /etc/apt/sources.list.d/timescaledb.list; \
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg; \
    apt-get update -y; \
    apt-get install -y timescaledb-2-postgresql-${PG_MAJOR}

# install pgvectorscale
RUN set -e; \
    apt-get install -y unzip; \
    TARGET_ARCH=$(if [ "$(uname -m)" = "x86_64" ]; then echo "amd64"; elif [ "$(uname -m)" = "aarch64" ]; then echo "arm64"; fi); \
    wget https://github.com/timescale/pgvectorscale/releases/download/${PGVECTORSCALE_VERSION}/pgvectorscale-${PGVECTORSCALE_VERSION}-pg${PG_MAJOR}-"$TARGET_ARCH".zip; \
    unzip pgvectorscale-${PGVECTORSCALE_VERSION}-pg${PG_MAJOR}-"$TARGET_ARCH".zip; \
    dpkg -i pgvectorscale-postgresql-${PG_MAJOR}_${PGVECTORSCALE_VERSION}-Linux_"$TARGET_ARCH".deb; \
    rm pgvectorscale-${PGVECTORSCALE_VERSION}-pg${PG_MAJOR}-"$TARGET_ARCH".zip pgvectorscale-postgresql-${PG_MAJOR}_${PGVECTORSCALE_VERSION}-Linux_"$TARGET_ARCH".deb

###############################################################################
# image for use in testing the pgai library
FROM base AS pgai-test-db
ENV PG_MAJOR=${PG_MAJOR}
ENV PIP_BREAK_SYSTEM_PACKAGES=1
WORKDIR /pgai
COPY . .
RUN just build install

# Create a custom config file in docker-entrypoint-initdb.d
RUN mkdir -p /docker-entrypoint-initdb.d && \
    echo "#!/bin/bash" > /docker-entrypoint-initdb.d/configure-timescaledb.sh && \
    echo "echo \"shared_preload_libraries = 'timescaledb'\" >> \${PGDATA}/postgresql.conf" >> /docker-entrypoint-initdb.d/configure-timescaledb.sh && \
    chmod +x /docker-entrypoint-initdb.d/configure-timescaledb.sh



###############################################################################
# image for use in extension development
FROM base
ENV WHERE_AM_I=docker
USER root

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
