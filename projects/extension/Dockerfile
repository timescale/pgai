# syntax=docker/dockerfile:1.3-labs
ARG PG_MAJOR
ARG TIMESCALEDB_IMAGE=timescale/timescaledb-ha:pg${PG_MAJOR}
FROM ${TIMESCALEDB_IMAGE} as timescaledb

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
    make \
    git \
    curl \
    vim

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
