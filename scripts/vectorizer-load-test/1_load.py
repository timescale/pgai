import os
from dotenv import load_dotenv
from datasets import load_dataset
import psycopg


load_dotenv()

DB_URL = os.environ["DB_URL"]

print("fetching dataset...")
data = load_dataset(f"Cohere/wikipedia-22-12", 'en', split='train', streaming=True, trust_remote_code=True)

def batches():
    batch = []
    for i, row in enumerate(data):
        batch.append((i, row))
        if len(batch) == 1000:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch


print("connecting to the database...")
with psycopg.connect(DB_URL) as con:
    with con.cursor() as cur:
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
                    if i % 1000 == 0:
                        print(f"{i}")
            con.commit()

print("done")