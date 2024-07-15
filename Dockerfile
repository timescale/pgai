# syntax=docker/dockerfile:1.3-labs
FROM postgres:16

ENV WHERE_AM_I=docker
ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    python3-pip \
    make \
    git \
    vim

WORKDIR /pgai