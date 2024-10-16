# Vectorizer Load Test

This directory contains scripts to help with load testing the vectorizer. The 
scripts create a table named `wiki` with approximately 1.5M rows to be 
vectorized.

1. Add a `.env` file and put a `DB_URL` in it. The value should be a Postgres DB connection URL. It can be a local DB or a remote DB.
2. Run `./load.sh`. This script will
   1. Download a dataset from HuggingFace
   2. Load it into a working table named `wiki_orig`
   3. Process the data into the `wiki` table. The original data is already chunked. We have to dechunk it.
   4. [optionally] drop the working tables
   5. [optionally] dump the `wiki` table to `wiki.dump`

If you already have a `wiki.dump` file, you can use `./restore.sh` to recreate
the `wiki` table without having to go through the process above. This is much
faster.

Once you have created the `wiki` table, you are ready to create one or more
vectorizers on the table. Happy testing!
