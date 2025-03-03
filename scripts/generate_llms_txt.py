#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
#     "python-dotenv",
# ]
# ///

"""
This script generates an llms.txt file for the pgai repository following the
standardized llms.txt specification.

It uses the Anthropic API to automatically generate descriptions for documentation files
and intelligently categorize them.

The llms.txt file provides information to help LLMs understand and use the repository
at inference time, including key documentation files and examples.
"""

import os
import glob
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize Anthropic client
from anthropic import Anthropic
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Repository root directory
REPO_ROOT = Path(__file__).parent.parent.absolute()

# Output file path
LLMS_TXT_PATH = REPO_ROOT / "llms.txt"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_repo_name() -> str:
    """Get the repository name."""
    return "pgai"

def get_repo_description() -> str:
    """Get a concise description."""
    return "Supercharge your PostgreSQL database with AI capabilities. Supports automatic creation and synchronization of vector embeddings, seamless vector and semantic search, Retrieval Augmented Generation (RAG) directly in SQL, and ability to call leading LLMs like OpenAI, Ollama, Cohere, and more via SQL."

def get_file_content(file_path: str) -> str:
    """Get the content of a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        return ""

def get_first_heading(content: str) -> str:
    """Extract the first heading from markdown content."""
    match = re.search(r'^#\s+(.*?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None

def extract_metadata_from_file(file_path: str) -> Dict[str, Any]:
    """Extract metadata from a file including title and content."""
    content = get_file_content(file_path)
    
    # Get title from first heading
    title = get_first_heading(content)
    if not title:
        title = os.path.basename(file_path).replace('.md', '').replace('-', ' ').title()
    
    return {
        "title": title,
        "content": content[:2000],  # limit content to first 2000 chars
        "filename": os.path.basename(file_path),
        "path": file_path,
        "rel_path": os.path.relpath(file_path, REPO_ROOT),
        "directory": os.path.basename(os.path.dirname(file_path)),
    }

def get_related_files(file_path: str) -> List[str]:
    """Get related files in the same directory."""
    directory_path = os.path.dirname(file_path)
    related_files = []
    try:
        for file in os.listdir(directory_path):
            if file != os.path.basename(file_path) and not file.startswith('.') and not file.startswith('__'):
                related_files.append(file)
    except Exception:
        pass
    return related_files

def generate_description_with_claude(metadata: Dict[str, Any]) -> Tuple[str, str]:
    """
    Generate a description and category for a documentation file using Claude.
    Returns a tuple of (description, category)
    """
    try:
        related_files = get_related_files(metadata['path'])
        
        prompt = f"""You're analyzing documentation for a PostgreSQL extension called pgai.

Information about the file:
- Filename: {metadata['filename']}
- Title: {metadata['title']}
- Directory: {metadata['directory']}
- Related files in same directory: {', '.join(related_files[:5]) + ('...' if len(related_files) > 5 else '') if related_files else 'None'}
- Beginning of content: {metadata['content'][:1000]}...

Part 1: Write a concise one-line description (maximum 100 characters) of what this documentation page covers.
If this file is describing the use of a specific AI provider (OpenAI, Ollama, Voyage, etc.), mention that explicitly.

Part 2: Categorize this documentation file into one of the following categories:
- installation: Documentation about installing pgai
- core: Documentation about core pgai extension features (model calling, text processing, dataset loading, security)
- vectorizer: Documentation specific to the pgai Vectorizer (embedding creation, vector store management)

The pgai Vectorizer is a specific feature of pgai that automatically creates and synchronizes vector embeddings.

Return your response in this JSON format:
{{
  "description": "your concise description here",
  "category": "category_name_here"
}}
"""
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0,
            system="You analyze documentation files and generate concise descriptions and categories.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Try to extract JSON from the response
        match = re.search(r'```json\s*(.*?)\s*```|({.*})', response.content[0].text, re.DOTALL)
        if match:
            json_str = match.group(1) if match.group(1) else match.group(2)
            result = json.loads(json_str)
            return result.get("description", ""), result.get("category", "core")
        else:
            logger.warning(f"Failed to extract JSON from Claude response for {metadata['filename']}")
            return metadata.get("title", ""), "core"
            
    except Exception as e:
        logger.error(f"Error generating description with Claude for {metadata['filename']}: {e}")
        return metadata.get("title", ""), "core"

def get_docs_files() -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Get documentation files from docs/ directory, categorized by section.
    Uses Claude to generate descriptions and categorize files.
    """
    docs_path = REPO_ROOT / "docs"
    
    # File categories
    install_docs = []
    core_docs = []
    vectorizer_docs = []
    
    # Get all markdown files
    md_files = glob.glob(f"{docs_path}/**/*.md", recursive=True)
    
    # Skip README.md files at the root of directories
    md_files = [f for f in md_files if not (os.path.basename(f) == "README.md" and 
                                            os.path.dirname(os.path.relpath(f, REPO_ROOT)) == "docs")]
    
    # Extract metadata from files
    file_metadata = []
    for file_path in md_files:
        metadata = extract_metadata_from_file(file_path)
        file_metadata.append(metadata)
    
    # Use ThreadPoolExecutor to parallelize API calls
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_metadata = {
            executor.submit(generate_description_with_claude, metadata): metadata 
            for metadata in file_metadata
        }
        
        for future in as_completed(future_to_metadata):
            metadata = future_to_metadata[future]
            try:
                description, category = future.result()
                
                # Add to appropriate category
                doc_tuple = (metadata["title"], metadata["rel_path"], description)
                if category == "installation":
                    install_docs.append(doc_tuple)
                elif category == "vectorizer":
                    vectorizer_docs.append(doc_tuple)
                else:  # Default to core
                    core_docs.append(doc_tuple)
                    
            except Exception as e:
                logger.error(f"Error processing {metadata['filename']}: {e}")
                # Fallback: add to core docs with title as description
                core_docs.append((metadata["title"], metadata["rel_path"], metadata["title"]))
    
    # Sort files within each category by path
    install_docs = sorted(install_docs, key=lambda x: x[1])
    core_docs = sorted(core_docs, key=lambda x: x[1])
    vectorizer_docs = sorted(vectorizer_docs, key=lambda x: x[1])
    
    return {
        "install": install_docs,
        "core": core_docs,
        "vectorizer": vectorizer_docs
    }

def generate_example_description(file_path: str) -> str:
    """Generate a description for an example file using Claude."""
    try:
        filename = os.path.basename(file_path)
        content = get_file_content(file_path)
        related_files = get_related_files(file_path)
        
        prompt = f"""You're analyzing an example file from the pgai PostgreSQL extension codebase.

Information about the file:
- Filename: {filename}
- File type: {os.path.splitext(filename)[1]}
- Directory: {os.path.basename(os.path.dirname(file_path))}
- Related files in same directory: {', '.join(related_files[:5]) + ('...' if len(related_files) > 5 else '') if related_files else 'None'}
- Beginning of content: {content[:1000]}...

Write a concise one-line description (maximum 150 characters) explaining what this example demonstrates.
Focus on functionality, not implementation details.
If the example uses a specific AI provider (OpenAI, Anthropic, Ollama, etc.), mention that explicitly.
End with a period and make sure your description is a complete sentence.
"""
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=150,
            temperature=0,
            system="You analyze code examples and generate concise descriptions.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Clean up response
        description = response.content[0].text.strip()
        # Remove quotes if present
        description = description.strip('"\'')
        # Make sure the description ends with a period to avoid looking cut off
        if description and not description.endswith(('.', '!', '?')):
            description += "."
        return description
            
    except Exception as e:
        logger.error(f"Error generating description for example {filename}: {e}")
        return None

def get_example_files() -> List[Tuple[str, str, str]]:
    """Get example files and generate descriptions."""
    example_files = []
    examples_path = REPO_ROOT / "examples"
    
    # Find all example files (focusing on SQL, Python, Notebooks, and READMEs)
    example_paths = []
    
    # SQL examples (root level and nested)
    for sql_file in glob.glob(f"{examples_path}/**/*.sql", recursive=True):
        example_paths.append(sql_file)
        
    # Jupyter notebooks
    for notebook_file in glob.glob(f"{examples_path}/**/*.ipynb", recursive=True):
        example_paths.append(notebook_file)
        
    # Important README files (filtering to avoid utility files)
    for readme_file in glob.glob(f"{examples_path}/**/README.md", recursive=True):
        # Only include READMEs in the main project directories, not utility folders
        if "migrations" not in readme_file and "__pycache__" not in readme_file:
            example_paths.append(readme_file)
            
    # Create file tuples with metadata
    for file_path in example_paths:
        rel_path = os.path.relpath(file_path, REPO_ROOT)
        filename = os.path.basename(file_path)
        
        # Determine title based on file type
        if filename.endswith('.md'):
            dir_name = os.path.basename(os.path.dirname(file_path))
            title = f"{dir_name.replace('_', ' ').title()} Documentation"
        else:
            title = filename.replace('.sql', '').replace('.ipynb', '').replace('_', ' ').title()
        
        # Generate description for non-README files
        if filename.endswith(('.sql', '.ipynb')):
            description = generate_example_description(file_path)
            if description:
                example_files.append((title, rel_path, description))
            else:
                example_files.append((title, rel_path, "Example from the pgai extension."))
        else:
            # For README files, use a generic description based on the directory
            dir_name = os.path.basename(os.path.dirname(file_path)).replace('_', ' ')
            example_files.append((title, rel_path, f"Documentation for the {dir_name} example."))
    
    # Sort files by path
    return sorted(example_files, key=lambda x: x[1])

def generate_llms_txt():
    """Generate the llms.txt file."""
    repo_name = get_repo_name()
    repo_description = get_repo_description()
    
    logger.info("Getting documentation files and generating descriptions...")
    docs_files_dict = get_docs_files()
    
    logger.info("Getting example files and generating descriptions...")
    example_files = get_example_files()
    
    logger.info(f"Writing llms.txt to {LLMS_TXT_PATH}...")
    with open(LLMS_TXT_PATH, "w") as f:
        # Title
        f.write(f"# {repo_name}\n\n")
        
        # Description
        f.write(f"> {repo_description}\n\n")
        
        # Additional context
        f.write("pgai is a PostgreSQL extension that provides AI capabilities within your database. ")
        f.write("It consists of two main components:\n\n")
        f.write("1. The core PostgreSQL extension which allows you to call various LLM models directly from SQL ")
        f.write("for tasks like generating content, vector search, and RAG applications.\n\n")
        f.write("2. The pgai Vectorizer system which automatically creates and synchronizes vector embeddings ")
        f.write("for your data using a worker process that runs alongside your database.\n\n")
        f.write("The project is maintained by Timescale, a PostgreSQL database company.\n\n")
        
        # Installation documentation
        f.write("## Installation\n\n")
        for title, path, description in docs_files_dict["install"]:
            f.write(f"- [{title}]({path}): {description}\n")
        
        # Core pgai documentation
        f.write("\n## Core pgai Extension\n\n")
        for title, path, description in docs_files_dict["core"]:
            f.write(f"- [{title}]({path}): {description}\n")
        
        # Vectorizer documentation
        f.write("\n## pgai Vectorizer\n\n")
        f.write("The pgai Vectorizer is a system that automatically creates and synchronizes vector embeddings ")
        f.write("for your data. It requires a worker process that runs alongside your database.\n\n")
        for title, path, description in docs_files_dict["vectorizer"]:
            f.write(f"- [{title}]({path}): {description}\n")
        
        # Example files (optional section)
        f.write("\n## Optional\n\n")
        for title, path, description in example_files:
            f.write(f"- [{title}]({path}): {description}\n")
    
    logger.info(f"Successfully generated llms.txt at {LLMS_TXT_PATH}")

if __name__ == "__main__":
    logger.info("Starting llms.txt generation...")
    generate_llms_txt()