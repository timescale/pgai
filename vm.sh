#!/usr/bin/env bash
# creates a virtual machine using multipass for development use
set -eux
multipass launch --name pgai lts
multipass stop pgai
multipass mount -t native . pgai:/pgai
multipass start pgai
multipass exec pgai -- bash <<EOF
set -eux
sudo su root -

echo 'debconf debconf/frontend select Noninteractive' | sudo debconf-set-selections
apt-get update
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    postgresql-16 \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    python3-pip \
    make

pip install --break-system-packages -r /pgai/requirements.txt
pip install --break-system-packages pgspot

chmod go+w /usr/share/postgresql/16/extension/
chmod go+w /usr/lib/postgresql/16/lib/

echo "/usr/bin/psql -U postgres -c \"create user ubuntu superuser login password 'ubuntu'\"" | sudo su postgres -
echo "/usr/bin/psql -U postgres -c \"create database ubuntu owner ubuntu\"" | sudo su postgres -

exit

cp /pgai/ai--*.sql /usr/share/postgresql/16/extension/
cp /pgai/ai.control /usr/share/postgresql/16/extension/
EOF
multipass restart pgai
multipass shell pgai
