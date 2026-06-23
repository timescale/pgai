#!/usr/bin/env python3
"""
Evaluation script for pgai Discord bot.
Tests the bot's RAG pipeline against a list of questions and uses an LLM judge to evaluate responses.
"""

import asyncio
import json
import logging
import sys

from dotenv import load_dotenv

# Import the refactored functions from main.py
from pgai_discord_bot.main import (
    generate_rag_response,
    openai_client,
    retrieve_relevant_documents,
)

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def evaluate_response_with_llm(
    question: str, bot_response: str, relevant_docs: str
) -> dict:
    """Use an LLM judge to evaluate if the bot response adequately answers the question."""
    judge_prompt = f"""
    You are an expert evaluator for a technical documentation chatbot. Your task is to evaluate whether a bot response adequately answers a user's question about pgai (a PostgreSQL AI extension).

    USER QUESTION: {question}

    BOT RESPONSE: {bot_response}

    RELEVANT DOCUMENTATION USED: {relevant_docs}

    Please evaluate the response on these criteria:
    1. ACCURACY: Is the information provided factually correct based on the documentation?
    2. COMPLETENESS: Does the response adequately address the user's question?
    3. CLARITY: Is the response clear and easy to understand?
    4. RELEVANCE: Is the response relevant to the question asked?
    5. HELPFULNESS: Would this response help the user solve their problem?

    Provide your evaluation in the following JSON format:
    {{
        "overall_score": <score from 1-10>,
        "accuracy": <score from 1-10>,
        "completeness": <score from 1-10>, 
        "clarity": <score from 1-10>,
        "relevance": <score from 1-10>,
        "helpfulness": <score from 1-10>,
        "reasoning": "<brief explanation of your evaluation>",
        "issues": "<any specific issues you identified>",
        "strengths": "<any specific strengths you identified>"
    }}
    """

    chat_completion = await openai_client.chat.completions.create(
        messages=[{"content": judge_prompt, "role": "user"}],
        model="gpt-4o",
        temperature=0.1,
    )

    try:
        # Extract JSON from the response
        response_content = chat_completion.choices[0].message.content or ""
        # Find JSON in the response (in case there's extra text)
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}") + 1
        json_str = response_content[start_idx:end_idx]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM judge response: {e}")
        return {
            "overall_score": 0,
            "accuracy": 0,
            "completeness": 0,
            "clarity": 0,
            "relevance": 0,
            "helpfulness": 0,
            "reasoning": "Failed to parse evaluation",
            "issues": f"JSON parsing error: {e}",
            "strengths": "N/A",
        }


async def run_evaluation(questions_file: str, max_questions: int = None) -> None:
    """Run the complete evaluation pipeline."""
    logger.info("Starting evaluation...")

    # Load questions
    with open(questions_file, encoding="utf-8") as f:
        questions = json.load(f)

    if max_questions:
        questions = questions[:max_questions]
        logger.info(f"Running evaluation on first {len(questions)} questions")
    else:
        logger.info(f"Loaded {len(questions)} questions")

    results = []

    for i, question in enumerate(questions, 1):
        logger.info(f"Processing question {i}/{len(questions)}: {question[:100]}...")

        try:
            # Get relevant docs
            relevant_docs = await retrieve_relevant_documents(question)

            # Generate bot response using the refactored function
            bot_response = await generate_rag_response(question)

            # Evaluate with LLM judge
            evaluation = await evaluate_response_with_llm(
                question, bot_response, relevant_docs
            )

            result = {
                "question_id": i,
                "question": question,
                "bot_response": bot_response,
                "relevant_docs": relevant_docs,
                "evaluation": evaluation,
            }

            results.append(result)

            logger.info(
                f"Question {i} - Overall Score: {evaluation.get('overall_score', 'N/A')}"
            )

        except Exception as e:
            logger.error(f"Error processing question {i}: {e}")
            results.append(
                {
                    "question_id": i,
                    "question": question,
                    "bot_response": f"ERROR: {str(e)}",
                    "relevant_docs": "",
                    "evaluation": {
                        "overall_score": 0,
                        "reasoning": f"Processing error: {e}",
                        "issues": str(e),
                        "accuracy": 0,
                        "completeness": 0,
                        "clarity": 0,
                        "relevance": 0,
                        "helpfulness": 0,
                        "strengths": "N/A",
                    },
                }
            )

    # Save results
    output_file = "eval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    scores = [r["evaluation"].get("overall_score", 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0

    print("\n=== EVALUATION SUMMARY ===")
    print(f"Total questions: {len(questions)}")
    print(f"Average overall score: {avg_score:.2f}/10")
    print("Score distribution:")
    print(f"  - Excellent (9-10): {sum(1 for s in scores if s >= 9)}")
    print(f"  - Good (7-8): {sum(1 for s in scores if 7 <= s < 9)}")
    print(f"  - Fair (5-6): {sum(1 for s in scores if 5 <= s < 7)}")
    print(f"  - Poor (1-4): {sum(1 for s in scores if 1 <= s < 5)}")
    print(f"  - Failed (0): {sum(1 for s in scores if s == 0)}")
    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    max_questions = None
    if len(sys.argv) > 2:
        try:
            max_questions = int(sys.argv[2])
        except ValueError:
            print("Usage: python eval.py <questions_file> [max_questions]")
            sys.exit(1)

    questions_file = (
        sys.argv[1] if len(sys.argv) > 1 else "discord_questions_20250619_151250.json"
    )
    asyncio.run(run_evaluation(questions_file, max_questions))
