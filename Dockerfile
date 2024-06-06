# syntax=docker/dockerfile:1.3-labs
FROM postgres:16

ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
    postgresql-16 \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    python3-pip \
    make

RUN pip install --break-system-packages pgspot
WORKDIR /tmp
COPY requirements.txt /tmp/
RUN pip install --break-system-packages -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY LICENSE /usr/share/doc/pgai/
COPY README.md /usr/share/doc/pgai/
COPY ./ai.control /usr/share/postgresql/16/extension/
COPY ./ai--*.sql /usr/share/postgresql/16/extension/
RUN chmod -R go+w /usr/share/postgresql/16/extension/
RUN chmod -R go+w /usr/lib/postgresql/16/lib/
WORKDIR /pgai
