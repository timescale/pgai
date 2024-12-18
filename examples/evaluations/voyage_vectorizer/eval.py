import psycopg2
import openai
import pandas as pd
from typing import List, Dict, Tuple
import os

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
        'sec_filings_voyage_embeddings',
        'sec_filings_openai_embeddings'
    ]
    
    @classmethod
    def validate(cls):
        assert sum(cls.QUESTION_DISTRIBUTION.values()) == cls.NUM_QUESTIONS_PER_CHUNK

class DatabaseConnection:
    def __init__(self):
        self.conn = psycopg2.connect("postgres://postgres:postgres@localhost:5432/postgres")
        
    def select_random_chunks(self) -> List[Dict]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, chunk_seq, chunk, text 
                FROM sec_filings_openai_embeddings 
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
        if not question or pd.isna(question):
            print(f"Skipping empty question in {table}")
            return []
        
        with self.conn.cursor() as cur:
            if 'voyage' in table:
                cur.execute(f"""
                    SELECT id, chunk_seq 
                    FROM {table} 
                    ORDER BY embedding <=> ai.voyageai_embed('voyage-finance-2', %s)
                    LIMIT %s
                """, (question, k))
            elif 'openai' in table:
                cur.execute(f"""
                    SELECT id, chunk_seq 
                    FROM {table} 
                    ORDER BY embedding <=> ai.openai_embed('text-embedding-3-small', %s, dimensions => 768)
                    LIMIT %s
                """, (question, k))
                
            return cur.fetchall()

class QuestionGenerator:
    def __init__(self):
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
    def generate_questions(self, chunk: str, question_type: str, count: int) -> List[str]:
        prompts = {
            'short': "Generate {count} short but challenging finance-specific questions about this SEC filing text. Questions should be under 10 words but test deep understanding:",
            'long': "Generate {count} detailed questions that require analyzing financial metrics, trends, and implications from this SEC filing text:",
            'direct': "Generate {count} questions about specific financial data, numbers, or statements explicitly mentioned in this SEC filing:",
            'implied': "Generate {count} questions about potential business risks, market implications, or strategic insights that can be inferred from this SEC filing:",
            'unclear': "Generate {count} intentionally ambiguous questions about financial concepts or business implications that require careful analysis of this SEC filing:"
        }
        
        system_prompt = """You are an expert in financial analysis and SEC filings.
Generate challenging, finance-specific questions that test deep understanding of financial concepts, 
business implications, and regulatory compliance. Questions should be difficult enough to 
challenge both general-purpose and finance-specialized language models.
Each question must be on a new line. Do not include empty lines or blank questions."""

        prompt = prompts[question_type].format(count=count) + f"\n\nSEC Filing Text: {chunk}"
        
        max_retries = 3
        questions = []
        
        for attempt in range(max_retries):
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
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
                'overall_accuracy': sum(scores) / len(scores),
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

    # Step 1: Get chunks
    chunks = evaluator.step1_get_chunks()

    pd.DataFrame(chunks).to_csv('chunks.csv')
    print(f"Number of chunks: {len(chunks)}")
    print("Sample chunk:", chunks[0])

    chunks = pd.read_csv('chunks.csv', index_col=0).to_dict('records')
    evaluator.chunks = chunks
    print(f"Loaded {len(chunks)} chunks from chunks.csv")
    print("Sample chunk:", chunks[0])

    # Step 2: Generate questions
    questions = evaluator.step2_generate_questions()

    pd.DataFrame(questions).to_csv('questions.csv')

    # Step 3: Evaluate models
    results = evaluator.step3_evaluate_models()

    pd.DataFrame(results).to_csv('results.csv')

    evaluator.print_results()

if __name__ == "__main__":
    main()