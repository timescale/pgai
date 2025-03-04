import os
import shutil
import subprocess
from multiprocessing import Process
from pathlib import Path

import psycopg
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DB_URL"]


def load():
    print("fetching dataset...")
    data = load_dataset("Cohere/wikipedia-22-12", 'en', split='train', streaming=True, trust_remote_code=True)

    to_load = -1
    ans = 'q'
    while ans.lower() not in {'y', 'n'}:
        ans = input("do you want to load the entire dataset (8.59M rows)? (y/n)    ")
        if ans.lower() == 'n':
            to_load = input("how many rows do you want to load?    ")
            try:
                to_load = int(to_load)
            except ValueError:
                ans = None
                print("invalid input")
                continue
        elif ans.lower() == 'y':
            to_load = -1

    def batches():
        batch = []
        for i, row in enumerate(data):
            batch.append((i, row))
            if len(batch) == 1000 or i == to_load:
                yield batch
                batch = []
                if i == to_load:
                    break
        if len(batch) > 0:
            yield batch

    print("connecting to the database...")
    with psycopg.connect(DB_URL) as con:
        with con.cursor() as cur:
            print("creating wiki_orig table...")
            cur.execute("""
                drop table if exists wiki_orig;
                create table wiki_orig
                ( title text
                , "text" text
                , url text
                , wiki_id int
                , paragraph_id int
                )
            """)
        con.commit()

        print("loading data...")
        for batch in batches():
            with con.cursor(binary=True) as cur:
                with cur.copy("""
                    copy wiki_orig (title, "text", url, wiki_id, paragraph_id) 
                        from stdin (format binary)
                """) as cpy:
                    cpy.set_types(['text', 'text', 'text', 'integer', 'integer'])
                    for i, row in batch:
                        cpy.write_row((row["title"], row["text"], row["url"], row["wiki_id"], row["paragraph_id"]))
                        if i != 0 and (i % 1000 == 0 or i == to_load):
                            print(f"{i}")
                con.commit()

        with con.cursor() as cur:
            print("creating index on wiki_orig...")
            cur.execute("create index on wiki_orig (wiki_id, paragraph_id)")
            print("creating wiki table...")
            cur.execute("""
                drop table if exists wiki;
                create table wiki
                ( id bigint not null primary key generated by default as identity
                , title text not null
                , body text not null
                , wiki_id int not null
                , url text not null
                )
            """)
            print("creating queue table...")
            cur.execute("drop table if exists queue")
            cur.execute("create table queue (wiki_id int not null primary key)")
            cur.execute("insert into queue (wiki_id) select distinct wiki_id from wiki_orig")


def dechunk():
    load_dotenv()
    with psycopg.connect(os.environ["DB_URL"], autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("""
                do language plpgsql $$
                declare
                    _wiki_id int;
                begin
                    loop
                
                        select wiki_id into _wiki_id
                        from queue
                        for update skip locked
                        limit 1
                        ;
                        exit when not found;
                
                        insert into wiki (title, body, wiki_id, url)
                        select
                          title
                        , string_agg("text", E'\n\n' order by paragraph_id)
                        , wiki_id
                        , url
                        from wiki_orig
                        where wiki_id = _wiki_id
                        group by wiki_id, title, url
                        ;
                
                        delete from queue 
                        where wiki_id = _wiki_id
                        ;
                        commit;
                    end loop;
                end
                $$;
            """)


if __name__ == '__main__':
    load()

    concurrency = 0
    while concurrency < 1:
        concurrency = input("how many processes do you want to use to dechunk?    ")
        try:
            concurrency = int(concurrency)
        except ValueError:
            concurrency = 0
            print("invalid input")
            continue

    print("dechunking...")
    procs = []
    for _ in range(concurrency):
        proc = Process(target=dechunk)
        procs.append(proc)
        proc.start()
    for proc in procs:
        proc.join()

    if input("do you want to drop the intermediate tables? (y/n)    ").lower() == 'y':
        with psycopg.connect(DB_URL) as con:
            with con.cursor() as cur:
                print("dropping wiki_orig...")
                cur.execute("drop table if exists wiki_orig")
                print("dropping queue...")
                cur.execute("drop table if exists queue")

    if shutil.which("pg_dump") is not None:
        if input("do you want to dump the dataset? (y/n)    ").lower() == "y":
            p = Path.cwd().joinpath("wiki.dump")
            if p.is_file():
                p.unlink(missing_ok=True)
            print("dumping dataset to wiki.dump...")
            subprocess.run(f"""pg_dump -d "{DB_URL}" -Fc -v -f wiki.dump --no-owner --no-privileges --table=public.wiki""",
                           check=True,
                           shell=True,
                           env=os.environ,
                           cwd=str(Path.cwd()),
                           )

    print("done")
