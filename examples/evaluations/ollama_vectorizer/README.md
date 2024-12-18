Evaluating Embedding Models: OpenAI vs. Nomic vs. BGE vs. OpenAI Large
Author: Jacky Liang

Prerequisites:
1. Docker and Docker Compose installed (compose.yaml is included)
2. OpenAI API key
3. PostgreSQL with pgai extension running
4. HuggingFace paul_graham_essays.csv dataset: https://huggingface.co/datasets/sgoel9/paul_graham_essays?row=0
5. Your choice of embedding models to evaluate

Configuration:
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
5. EMBEDDING_TABLES = [          # Database tables containing embeddings (your choice)
    'essays_nomic_embeddings',        # Nomic embed-text (768 dim)
    'essays_openai_small_embeddings', # OpenAI text-embedding-3-small (768 dim)
    'essays_bge_large_embeddings',    # BGE Large (1024 dim)
    'essays_openai_large_embeddings'  # OpenAI text-embedding-3-large (1536 dim)
]

Installation and Setup:
1. Create directory with compose.yaml. **MAKE SURE YOU HAVE OPENAI_API_KEY IN compose.yaml, VERY IMPORTANT!!!**
    - services.db.environment.OPENAI_API_KEY="sk-project-.."
    - services.vectorizer-worker.environment.OPENAI_API_KEY="sk-project-.."=
2. Start services: docker compose up -d
3. Connect to the database:

   docker compose exec -ti db psql

4. Pull embedding models (these are the ones I'm using, you can use others):

   docker compose exec ollama ollama pull nomic-embed-text
   docker compose exec ollama ollama pull bge-large

5. Enable pgai extension:

   CREATE EXTENSION IF NOT EXISTS ai CASCADE;

Dataset Setup:
1. Create table with primary key and load Paul Graham Essays dataset:
   CREATE TABLE pg_essays (
       id SERIAL PRIMARY KEY,
       title TEXT,
       date TEXT,
       text TEXT
   );
   
   SELECT ai.load_dataset('sgoel9/paul_graham_essays', table_name => 'pg_essays', if_table_exists => 'append');

2. Create vectorizers for each model:

   -- Nomic embed-text
   SELECT ai.create_vectorizer(
      'pg_essays'::regclass,
      destination => 'essays_nomic_embeddings',
      embedding => ai.embedding_ollama('nomic-embed-text', 768),
      chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );

   -- OpenAI text-embedding-3-small
   SELECT ai.create_vectorizer(
      'pg_essays'::regclass,
      destination => 'essays_openai_small_embeddings',
      embedding => ai.embedding_openai('text-embedding-3-small', 768),
      chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );

   -- BGE Large (1024 dim)
   SELECT ai.create_vectorizer(
      'pg_essays'::regclass,
      destination => 'essays_bge_large_embeddings',
      embedding => ai.embedding_ollama('bge-large', 1024),
      chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );

   -- OpenAI text-embedding-3-large (1536 dim)
   SELECT ai.create_vectorizer(
      'pg_essays'::regclass,
      destination => 'essays_openai_large_embeddings', 
      embedding => ai.embedding_openai('text-embedding-3-large', 1536),
      chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
   );

-- 3. Verify vectorization status
SELECT * FROM ai.vectorizer_status;

Usage:
1. First-time setup:
   - Ensure PostgreSQL Docker container is running with pgai extension
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