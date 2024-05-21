#!/usr/bin/env bash
# creates a virtual machine using multipass for development use
set -e
multipass launch --name pgai lts
multipass exec pgai -- bash <<EOF
set -e
echo 'debconf debconf/frontend select Noninteractive' | sudo debconf-set-selections
sudo apt-get install -y gnupg postgresql-common apt-transport-https lsb-release wget
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    postgresql-16 \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    python3-full \
    python3-openai \
    python3-tiktoken

# dev requirements
sudo apt-get install -y python3-pip
echo 'PATH="$PATH:~/.local/bin"' >> ~/.profile
pip install --break-system-packages pgspot

sudo chmod go+w /usr/share/postgresql/16/extension/
sudo chmod go+w /usr/lib/postgresql/16/lib/

echo "/usr/bin/psql -U postgres -c \"create user ubuntu superuser login password 'ubuntu'\"" | sudo su postgres -
echo "/usr/bin/psql -U postgres -c \"create database ubuntu owner ubuntu\"" | sudo su postgres -
EOF
multipass stop pgai
multipass mount -t native . pgai:/pgai
multipass start pgai
multipass exec pgai -d /pgai -- cp ai--*.sql /usr/share/postgresql/16/extension/
multipass exec pgai -d /pgai -- cp ai.control /usr/share/postgresql/16/extension/
multipass shell pgai
