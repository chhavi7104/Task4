FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout for logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure output/log directories exist inside the image
RUN mkdir -p exports logs

# Default: run a crawl using whatever .env is mounted/provided
ENTRYPOINT ["python", "cli.py"]
CMD ["crawl"]
