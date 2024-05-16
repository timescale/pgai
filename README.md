# Postgres AI


## Development

Prerequisites:

1. [multipass](https://multipass.run/install) - you'll need multipass to run a vm for dev/test

### Creating a VM

Run `vm.sh`. It will create an ubuntu vm in multipass named `pgai`. 
In this vm, it installs postgres, python, and other dependencies.
The repo directory is mounted into the vm at `/pgai`.

```bash
./vm.sh
```

### Getting a shell in the vm

```bash
multipass shell pgai
```

### "Building"

Run `build.sh` from a shell INSIDE the vm. It will copy the extension's SQL and 
control files into the correct spots in the vm. Then it will drop the extension 
if it exists and create it using the new sources.

