echo "Installing docker images and starting up containers..."
docker compose up -d 

echo "Pulling the embedding models through Ollama..."
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull mxbai-embed-large
docker compose exec ollama ollama pull bge-m3

echo "Pulling the generative model for question generation..."
docker compose exec ollama ollama pull llama3.2
