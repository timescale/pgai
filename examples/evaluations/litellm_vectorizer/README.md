# Embedding Models Evaluation using pgai Vectorizer and LiteLLM

## Prerequisites:

1. Docker and Docker Compose installed (compose.yaml is included)
2. PostgreSQL with pgai extension running
3. HuggingFace dataset: https://huggingface.co/datasets/sgoel9/paul_graham_essays?row=0
4. API Keys for:
   - Cohere (COHERE_API_KEY)
   - Mistral (MISTRAL_API_KEY)
   - OpenAI (OPENAI_API_KEY)
   - HuggingFace (HUGGINGFACE_API_KEY)

## Configuration:

1. NUM_CHUNKS = 20               # Number of random text chunks to evaluate
2. NUM_QUESTIONS_PER_CHUNK = 20  # Total questions per chunk (4 of each type)
3. TOP_K = 10                    # Number of closest chunks to retrieve
4. QUESTION_DISTRIBUTION = {     # Distribution of question types
    'short': 4,    # Direct, simple questions under 10 words
    'long': 4,     # Detailed questions requiring comprehensive answers
    'direct': 4,   # Questions about explicit information
    'implied': 4,  # Questions requiring context understanding
    'unclear': 4   # Vague or ambiguous questions
}
5. EMBEDDING_TABLES = [          # Database tables containing embeddings
    'essays_cohere_embeddings',
    'essays_mistral_embeddings',
    'essays_openai_small_embeddings'
]

## Installation and Setup:

1. Create directory with compose.yaml. Make sure you have all API keys in compose.yaml:
    - services.db.environment.COHERE_API_KEY="..."
    - services.db.environment.MISTRAL_API_KEY="..."
    - services.db.environment.OPENAI_API_KEY="..."
2. Start services: docker compose up -d
3. Connect to your database: docker exec -it pgai-db-1 psql -U postgres -d postgres
4. Enable pgai extension:
   CREATE EXTENSION IF NOT EXISTS ai CASCADE;
5. Load Paul Graham's essays into the database:
   SELECT ai.load_dataset('sgoel9/paul_graham_essays');
6. Create vectorizers in psql for each embedding model:
   - Cohere embed-english-v3.0 (1024 dimensions)
   - Mistral mistral-embed (1024 dimensions)
   - OpenAI text-embedding-3-small (1024 dimensions)

    SELECT ai.create_vectorizer(
        'paul_graham_essays'::regclass,
        destination => 'essays_cohere_embeddings',
        embedding => ai.embedding_litellm(
            'cohere/embed-english-v3.0',
            1024,
            api_key_name => 'COHERE_API_KEY'
        ),
        chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
    );

    SELECT ai.create_vectorizer(
        'paul_graham_essays'::regclass,
        destination => 'essays_mistral_embeddings',
        embedding => ai.embedding_litellm(
            'mistral/mistral-embed',
            1024,
            api_key_name => 'MISTRAL_API_KEY'
        ),
        chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
    );

    SELECT ai.create_vectorizer(
        'paul_graham_essays'::regclass,
        destination => 'essays_openai_small_embeddings',
        embedding => ai.embedding_openai(
            'text-embedding-3-small', 
            1024, 
            api_key_name => 'OPENAI_API_KEY'
        ),
        chunking => ai.chunking_recursive_character_text_splitter('text', 512, 50)
    );

    Use `SELECT * FROM ai.vectorizer_status;` to check if Vectorizers are ready.

    Use `select * from ai.vectorizer_errors` to check if there are any errors.

## Usage:

1. Run the script after vectorizers are created and processing is complete
2. Generate chunks - chunks are randomly selected from the vectorized table
3. Generate questions using GPT-4o-mini
4. Evaluate models

## Outputs:

- chunks.csv: Random text chunks from database
- questions.csv: Generated questions for each chunk
- results.csv: Overall model performance metrics
- detailed_results.csv: Per-question evaluation results