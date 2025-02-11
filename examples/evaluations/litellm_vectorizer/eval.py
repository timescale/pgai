"""
Embedding Models Evaluation using pgai Vectorizer and LiteLLM
Author: Jacky Liang

Prerequisites:
1. Docker and Docker Compose installed (compose.yaml is included)
2. PostgreSQL with pgai extension running
3. HuggingFace dataset: https://huggingface.co/datasets/sgoel9/paul_graham_essays?row=0
4. API Keys for:
   - Cohere (COHERE_API_KEY)
   - Mistral (MISTRAL_API_KEY)
   - OpenAI (OPENAI_API_KEY)
   - HuggingFace (HUGGINGFACE_API_KEY)

Configuration:
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

Installation and Setup:
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

Usage:
1. Run the script after vectorizers are created and processing is complete
2. Generate chunks - chunks are randomly selected from the vectorized table
3. Generate questions using GPT-4o-mini
4. Evaluate models

Outputs:
- chunks.csv: Random text chunks from database
- questions.csv: Generated questions for each chunk
- results.csv: Overall model performance metrics
- detailed_results.csv: Per-question evaluation results
"""

import psycopg2
import openai
import pandas as pd
from typing import List, Dict, Tuple
import os
import time

class Config:
    NUM_CHUNKS = 20
    NUM_QUESTIONS_PER_CHUNK = 20
    TOP_K = 10
    QUESTION_DISTRIBUTION = {
        'short': 4,
        'long': 4,
        'direct': 4,
        'implied': 4,
        'unclear': 4
    }
    EMBEDDING_TABLES = [
        'essays_cohere_embeddings',
        'essays_mistral_embeddings',
        'essays_openai_small_embeddings'
    ]
    
    @classmethod
    def validate(cls):
        assert sum(cls.QUESTION_DISTRIBUTION.values()) == cls.NUM_QUESTIONS_PER_CHUNK

class DatabaseConnection:
    def __init__(self):
        self.api_key = os.getenv('HUGGINGFACE_API_KEY')
        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY environment variable is not set")
            
        self.conn = psycopg2.connect("postgres://postgres:postgres@localhost:5432/postgres")
        
        with self.conn.cursor() as cur:
            cur.execute("SET ai.huggingface_api_key = %s", (self.api_key,))
    
    def select_random_chunks(self) -> List[Dict]:
        # Select chunks from one of the vectorized destination tables.
        # Here we use 'essays_cohere_embeddings' for example.
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, chunk_seq, chunk, title 
                FROM essays_cohere_embeddings 
                ORDER BY RANDOM() 
                LIMIT %s
            """, (Config.NUM_CHUNKS,))
            
            chunks = []
            for row in cur.fetchall():
                chunks.append({
                    'id': row[0],
                    'chunk_seq': row[1],
                    'chunk': row[2],
                    'title': row[3]
                })
            return chunks

    def vector_search(self, table: str, question: str, k: int) -> List[Tuple[int, int]]:
        # Skips empty questions, as empty questions causes program to crash
        if not question or pd.isna(question):
            print(f"Skipping empty question in {table}")
            return []
        
        max_retries = 3
        base_delay = 1  # Start with 1 second delay
        
        for attempt in range(max_retries):
            try:
                with self.conn.cursor() as cur:
                    # Rollback any failed transaction
                    self.conn.rollback()
                    
                    # Map each destination table to its model name
                    model_mapping = {
                        'essays_cohere_embeddings': 'cohere/embed-english-v3.0',
                        'essays_mistral_embeddings': 'mistral/mistral-embed',
                        'essays_openai_small_embeddings': 'text-embedding-3-small'
                    }
                    model = model_mapping.get(table)
                    
                    if table == 'essays_openai_small_embeddings':
                        # Use OpenAI's embedding function with correct format
                        cur.execute("""
                            SELECT id, chunk_seq 
                            FROM {table}
                            ORDER BY embedding <=> ai.openai_embed(%s, %s, dimensions => 1024)
                            LIMIT %s
                        """.format(table=table), (model, question, k))
                    else:
                        # Use LiteLLM for other models
                        cur.execute("""
                            SELECT id, chunk_seq 
                            FROM {table}
                            ORDER BY embedding <=> ai.litellm_embed(%s, %s)
                            LIMIT %s
                        """.format(table=table), (model, question, k))
                    
                    results = cur.fetchall()
                    print(f"Query results for {table}: {results}")  # Debug print
                    return results
                    
            except Exception as e:
                # Ensure transaction is rolled back on error
                self.conn.rollback()
                print(f"Error details: {str(e)}")  # Debug print
                
                if "rate limit" in str(e).lower():
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Rate limit hit for {table}, waiting {delay} seconds...")
                    time.sleep(delay)
                    if attempt == max_retries - 1:
                        print(f"Max retries reached for {table}, skipping question")
                        return []
                else:
                    print(f"Unexpected error for {table}: {e}")
                    return []

class QuestionGenerator:
    def __init__(self):
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
    def generate_questions(self, chunk: str, question_type: str, count: int) -> List[str]:
        prompts = {
            'short': "Generate {count} short, simple questions about this text. Questions should be direct and under 10 words:",
            'long': "Generate {count} detailed, comprehensive questions about this text. Include specific details:",
            'direct': "Generate {count} questions that directly ask about explicit information in this text:",
            'implied': "Generate {count} questions that require understanding context and implications of the text:",
            'unclear': "Generate {count} vague, ambiguous questions about the general topic of this text:"
        }
        
        prompt = prompts[question_type].format(count=count) + f"\n\nText: {chunk}"
        
        max_retries = 3
        questions = []
        
        for attempt in range(max_retries):
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Generate different types of questions about the given text. Each question must be on a new line. Do not include empty lines or blank questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7 + (attempt * 0.1)
            )
            
            new_questions = [
                q.strip("1234567890. ")  # Remove leading numbers and periods
                for q in response.choices[0].message.content.strip().split("\n")
                if q.strip("1234567890. ").strip()  # Remove leading numbers and periods
            ]
            
            questions.extend(new_questions)
            
            # WORKAROUND: Sometimes GPT generates < N questions, I don't know why. Retry with higher temperature
            # up to 3 times. If still not enough, pad with placeholders to maintain consistent
            # question count across all chunks.
            if len(questions) >= count:
                questions = questions[:count]
                break
            elif attempt < max_retries - 1:
                print(f"Only generated {len(questions)} questions, retrying... (attempt {attempt + 1}/{max_retries})")
        
        print(f"\nGenerated {question_type} questions:")
        for q in questions:
            print(f"  - {q}")
        
        while len(questions) < count:
            placeholder = f"[Placeholder {question_type} question {len(questions) + 1}]"
            questions.append(placeholder)
            print(f"  - {placeholder} (added placeholder)")
        
        return questions

class StepByStepEvaluator:
    def __init__(self):
        self.db = DatabaseConnection()
        self.qgen = QuestionGenerator()
        self.chunks = None
        self.questions_data = None
        self.results = None

    def step1_get_chunks(self):
        """Step 1: Get random chunks from database"""
        print("Step 1: Selecting random chunks...")
        self.chunks = self.db.select_random_chunks()
        print(f"Selected {len(self.chunks)} chunks")
        return self.chunks

    def step2_generate_questions(self):
        """Step 2: Generate questions for each chunk"""
        if not self.chunks:
            raise ValueError("Must run step1_get_chunks first")

        print("Step 2: Generating questions...")
        self.questions_data = []
        for i, chunk in enumerate(self.chunks, 1):
            print(f"Processing chunk {i}/{len(self.chunks)}")
            for q_type, count in Config.QUESTION_DISTRIBUTION.items():
                questions = self.qgen.generate_questions(
                    chunk['chunk'], 
                    q_type, 
                    count
                )
                for q in questions:
                    self.questions_data.append({
                        'question': q,
                        'source_chunk_id': chunk['id'],
                        'source_chunk_seq': chunk['chunk_seq'],
                        'question_type': q_type,
                        'chunk': chunk['chunk']
                    })
        print(f"Generated {len(self.questions_data)} questions total")
        return self.questions_data

    def step3_evaluate_models(self):
        """Step 3: Test each embedding model"""
        print("Loading questions from questions.csv...")
        questions_df = pd.read_csv('questions.csv')
        self.questions_data = questions_df.to_dict('records')
        print(f"Loaded {len(self.questions_data)} questions")

        print("Step 3: Evaluating models...")
        self.results = {}
        detailed_results = []
        
        for table in Config.EMBEDDING_TABLES:
            print(f"Testing {table}...")
            scores = []
            for q in self.questions_data:
                search_results = self.db.vector_search(table, q['question'], Config.TOP_K)
                found = any(
                    r[0] == q['source_chunk_id'] and r[1] == q['source_chunk_seq'] 
                    for r in search_results
                )
                scores.append(1 if found else 0)
                
                detailed_results.append({
                    'model': table,
                    'question': q['question'],
                    'question_type': q['question_type'],
                    'source_chunk_id': q['source_chunk_id'],
                    'source_chunk_seq': q['source_chunk_seq'],
                    'found_correct_chunk': found,
                    'num_results': len(search_results)
                })
            
            self.results[table] = {
                'overall_accuracy': sum(scores) / len(scores) if scores else 0,
                'by_type': {
                    q_type: sum(scores[i] for i, q in enumerate(self.questions_data) 
                               if q['question_type'] == q_type) / Config.QUESTION_DISTRIBUTION[q_type] / Config.NUM_CHUNKS
                    for q_type in Config.QUESTION_DISTRIBUTION.keys()
                }
            }
        
        pd.DataFrame(detailed_results).to_csv('detailed_results.csv', index=False)
        return self.results

    def print_results(self):
        """Print the final results"""
        if not self.results:
            raise ValueError("Must run step3_evaluate_models first")

        print("\nEvaluation Results:")
        for model, scores in self.results.items():
            print(f"\n{model}:")
            print(f"Overall Accuracy: {scores['overall_accuracy']:.2%}")
            print("Accuracy by question type:")
            for q_type, acc in scores['by_type'].items():
                print(f"- {q_type}: {acc:.2%}")

def main():
    Config.validate()
    evaluator = StepByStepEvaluator()
    
    # # Step 1: Get chunks from one of the vectorized tables.
    # chunks = evaluator.step1_get_chunks()
    # pd.DataFrame(chunks).to_csv('chunks.csv')
    # print(f"Number of chunks: {len(chunks)}")
    # print("Sample chunk:", chunks[0])

    # chunks = pd.read_csv('chunks.csv', index_col=0).to_dict('records')
    # evaluator.chunks = chunks
    # print(f"Loaded {len(chunks)} chunks from chunks.csv")
    # print("Sample chunk:", chunks[0])

    # # Step 2: Generate questions
    # questions = evaluator.step2_generate_questions()
    # pd.DataFrame(questions).to_csv('questions.csv')

    # Step 3: Evaluate models
    results = evaluator.step3_evaluate_models()
    pd.DataFrame(results).to_csv('results.csv')
    evaluator.print_results()

if __name__ == "__main__":
    main()