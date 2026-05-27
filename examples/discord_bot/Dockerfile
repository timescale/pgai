# Use Python 3.13 as base image
FROM python:3.14

# Set working directory
WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Copy requirements file
COPY uv.lock pyproject.toml ./

# Install dependencies
RUN uv sync

# Copy the rest of the application
COPY . .
COPY --from=docs /. /app/docs

ENV DOCS_PATH=/app/docs

# Make the start script executable
RUN chmod +x start.sh

# Use the start script as entrypoint
ENTRYPOINT ["./start.sh"]