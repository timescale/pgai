# syntax=docker/dockerfile:1.3-labs
ARG PG_MAJOR=16
FROM postgres:$PG_MAJOR
ARG PG_MAJOR

ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN set -eux; \
    apt-get update; \
    apt-mark hold locales; \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    postgresql-server-dev-$PG_MAJOR \
    postgresql-plpython3-$PG_MAJOR \
    python3-full \
    python3-pip

WORKDIR /tmp

RUN set -eux; \
    git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git; \
    cd pgvector; \
    make OPTFLAGS=""; \
    make install

RUN set -eux; \
    rm -r /tmp/pgvector; \
    apt-get remove -y build-essential postgresql-server-dev-$PG_MAJOR; \
    apt-get autoremove -y; \
    apt-mark unhold locales;

RUN pip install --break-system-packages openai tiktoken

COPY LICENSE /usr/share/doc/pgai/
COPY README.md /usr/share/doc/pgai/
COPY ./ai.control /usr/share/postgresql/$PG_MAJOR/extension/
COPY ./ai--*.sql /usr/share/postgresql/$PG_MAJOR/extension/
