# syntax=docker/dockerfile:1.3-labs
FROM postgres:16 as pgai

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
    make \
    vim

COPY requirements.txt /tmp/
RUN pip install --break-system-packages -r /tmp/requirements.txt

COPY ./ai.control /usr/share/postgresql/16/extension/
COPY ./ai--*.sql /usr/share/postgresql/16/extension/
RUN chmod -R go+w /usr/share/postgresql/16/extension/
RUN chmod -R go+w /usr/lib/postgresql/16/lib/
WORKDIR /pgai

FROM pgai as pgai-tests

COPY tests/hoverfly.crt /usr/local/share/ca-certificates/hoverfly.crt
COPY tests/mockserver.crt /usr/local/share/ca-certificates/mockserver.crt

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    update-ca-certificates
