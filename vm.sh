#!/usr/bin/env bash
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
    postgresql-server-dev-16 \
    postgresql-plpython3-16 \
    postgresql-16-pgvector \
    python3-full \
    python3-pip \
    python3-openai \
    python3-tiktoken

echo "/usr/bin/psql -U postgres -c \"create user ubuntu superuser login password 'ubuntu'\"" | sudo su postgres -
echo "/usr/bin/psql -U postgres -c \"create database ubuntu owner ubuntu\"" | sudo su postgres -
EOF
multipass stop pgai
# mount cwd to /pgai in the vm
multipass mount -t native . pgai:/pgai
multipass start pgai
#multipass exec pgai -- psql -c "create user bob; create user fred; create user joe; create user jill;"
multipass exec pgai -- ./build.sh
