# Idempotent SQL Files

This directory contains SQL files which are idempotent. Any code in these
scripts will be executed on EVERY install and/or upgrade. Therefore, it must be
safe to (re)run multiple times. A good rule of thumb is that `CREATE OR REPLACE`
statements are safe in these files.

The files are executed in alphanumeric order by filename.
