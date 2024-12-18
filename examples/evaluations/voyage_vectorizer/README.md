Domain-specific vs. General-purpose Embedding Model Evaluation
Author: Jacky Liang

Prerequisites:
1. Docker and Docker Compose installed (compose.yaml is included)
2. OpenAI API key
3. PostgreSQL with pgai extension running
4. SEC Filings dataset: https://huggingface.co/datasets/MemGPT/example-sec-filings/tree/main
5. Your choice of embedding models to evaluate

Virtual Environment Setup:
1. Create and activate virtual environment:   

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

Configuration (default values):
1. NUM_CHUNKS = 20               # Number of random text chunks to evaluate
2. NUM_QUESTIONS_PER_CHUNK = 20  # Total questions per chunk (4 of each type)
3. TOP_K = 10                    # Number of closest chunks to retrieve
4. QUESTION_DISTRIBUTION = {      # Distribution of question types
    'short': 4,    # Direct, simple questions under 10 words
    'long': 4,     # Detailed questions requiring comprehensive answers
    'direct': 4,   # Questions about explicit information
    'implied': 4,  # Questions requiring context understanding
    'unclear': 4   # Vague or ambiguous questions
}
5. EMBEDDING_TABLES = [          # Database tables containing embeddings
    'sec_filings_openai_embeddings',  # OpenAI text-embedding-3-small (768 dim)
    'sec_filings_voyage_embeddings'   # Voyage finance-2 (1024 dim)
]

Installation and Setup:
1. Create directory with compose.yaml - make sure you enter your Voyage AI and OpenAI API keys in compose.yaml
2. Start services: `docker compose up -d`
3. Connect to the database: `docker compose exec -it db psql`
3. Enable pgai extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS ai CASCADE;
   ```

Dataset Setup:
1. Create a `sec_filings` table in the database with primary key (required for pgai Vectorizer):

   ```sql
   CREATE TABLE sec_filings (
       id SERIAL PRIMARY KEY,
       text text
   );
   ```

2. Load SEC filings dataset (the name is case-sensitive):
   ```sql
   SELECT ai.load_dataset(
       name => 'MemGPT/example-sec-filings',
       table_name => 'sec_filings',
       batch_size => 1000,
       max_batches => 10,
       if_table_exists => 'append'
   );
   ```

2. Create vectorizers for each model:
   ```sql
   -- OpenAI text-embedding-3-small (768 dim)
   SELECT ai.create_vectorizer(
       'sec_filings'::regclass,
       destination => 'sec_filings_openai_embeddings',
       embedding => ai.embedding_openai('text-embedding-3-small', 768),
       chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );

   -- Voyage finance-2 (1024 dim)
   SELECT ai.create_vectorizer(
       'sec_filings'::regclass,
       destination => 'sec_filings_voyage_embeddings',
       embedding => ai.embedding_voyageai('voyage-finance-2', 1024),
       chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );
   ```

3. Verify vectorization status:

   ```sql
   SELECT * FROM ai.vectorizer_status;
   ```

4. Query embedding views:

   ```sql
      SELECT text FROM sec_filings_openai_embeddings LIMIT 5;
      SELECT text FROM sec_filings_voyage_embeddings LIMIT 5;
   ```

Usage:
1. First-time setup:
   - Ensure PostgreSQL Docker container is running with pgai extension
   - Ensure OpenAI and Voyage AI API keys are entered in compose.yaml (required)
   - Configure Config class parameters if needed (top of file)

2. Generate chunks - chunks are randomly selected from db, so you can run
                     this multiple times until you get a good sample
   evaluator = StepByStepEvaluator()
   chunks = evaluator.step1_get_chunks()
   pd.DataFrame(chunks).to_csv('chunks.csv')

3. Generate questions (can be run independently):
   chunks = pd.read_csv('chunks.csv', index_col=0).to_dict('records')
   evaluator.chunks = chunks
   questions = evaluator.step2_generate_questions()
   pd.DataFrame(questions).to_csv('questions.csv')

4. Evaluate models (can be run independently):
   results = evaluator.step3_evaluate_models()  # Reads from questions.csv
   pd.DataFrame(results).to_csv('results.csv')
   evaluator.print_results()

Outputs:
- chunks.csv: Random text chunks from database
- questions.csv: Generated questions for each chunk
- results.csv: Overall model performance metrics
- detailed_results.csv: Per-question evaluation results

Links:
1. Voyage AI x pgai Vectorizer Quickstart: https://github.com/timescale/pgai/blob/main/docs/vectorizer-quick-start-voyage.md
2. SEC Filings dataset: https://huggingface.co/datasets/MemGPT/example-sec-filings/tree/main
3. Voyage AI Text Embedding API docs: https://docs.voyageai.com/docs/embeddings