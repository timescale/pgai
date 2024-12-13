echo "Installing docker images and starting up containers..."
docker compose up -d 

echo "Pulling the embedding models through Ollama..."
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull mxbai-embed-large
docker compose exec ollama ollama pull bge-m3

echo "Saving the dataset in the db container..."
docker cp "./paul_graham_essays.csv" pgai-ollama-db-1:/tmp/
