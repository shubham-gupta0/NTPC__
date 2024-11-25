# Use Python 3.9 as the base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (including git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy all project files into the container
COPY . .

# Upgrade pip and install Python dependencies
RUN python -m pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu117 && \
    pip install -r requirements.txt

# Download models
RUN python download_models/download_doctr_model.py && \
    python download_models/download_qwen_model.py

# Expose the port used by FastAPI
EXPOSE 8000

# Command to run the FastAPI application with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
