FROM python:3.12-slim

# Install system FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure data directory exists
RUN mkdir -p data/uploads data/exports && chmod -R 777 data

# HuggingFace default port
EXPOSE 7860

# Run server on port 7860
CMD ["python", "main.py", "--server", "--port", "7860", "--host", "0.0.0.0"]
