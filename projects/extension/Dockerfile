# syntax=docker/dockerfile:1.3-labs
ARG PG_MAJOR=16
ARG TIMESCALEDB_IMAGE=timescale/timescaledb-ha:pg${PG_MAJOR}
FROM ${TIMESCALEDB_IMAGE} as timescaledb

FROM postgres:${PG_MAJOR} AS build-latest
ENV PG_MAJOR=${PG_MAJOR}
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get update && \
    apt-get install -y --no-install-recommends make python3-pip git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /pgai
COPY requirements.txt .
COPY ai/__init__.py ai/
RUN version=$(grep -oP '(?<=__version__ = ")[^"]*' ai/__init__.py) && \
    mkdir -p /usr/local/lib/pgai/$version && \
    pip3 install -v --no-deps --compile -t /usr/local/lib/pgai/$version -r requirements.txt
COPY . .
RUN make install-py build-sql install-sql

FROM timescaledb as pgai-test-db
ARG PG_MAJOR=16
COPY --from=build-latest /usr/share/postgresql/${PG_MAJOR}/extension/ai--*.sql /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=build-latest /usr/share/postgresql/${PG_MAJOR}/extension/ai.control /usr/share/postgresql/${PG_MAJOR}/extension/ai.control
COPY --from=build-latest /usr/local/lib/pgai/ /usr/local/lib/pgai/

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
    git \
    curl \
    vim \
    && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin/

# install timescaledb and pgvectorscale
COPY --from=timescaledb /usr/share/postgresql/${PG_MAJOR}/extension/timescaledb--*.sql /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=timescaledb /usr/share/postgresql/${PG_MAJOR}/extension/vectorscale--*.sql /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=timescaledb /usr/share/postgresql/${PG_MAJOR}/extension/timescaledb.control /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=timescaledb /usr/share/postgresql/${PG_MAJOR}/extension/vectorscale.control /usr/share/postgresql/${PG_MAJOR}/extension/
COPY --from=timescaledb /usr/lib/postgresql/${PG_MAJOR}/lib/timescaledb.so /usr/lib/postgresql/${PG_MAJOR}/lib/
COPY --from=timescaledb /usr/lib/postgresql/${PG_MAJOR}/lib/timescaledb-*.so /usr/lib/postgresql/${PG_MAJOR}/lib/
COPY --from=timescaledb /usr/lib/postgresql/${PG_MAJOR}/lib/vectorscale-*.so /usr/lib/postgresql/${PG_MAJOR}/lib/

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
