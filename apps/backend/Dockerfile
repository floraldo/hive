FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy shared packages first
COPY ../../packages /packages

# Install shared packages if they exist
RUN if [ -d "/packages" ]; then \
    for pkg in /packages/*/; do \
        if [ -f "$pkg/setup.py" ] || [ -f "$pkg/pyproject.toml" ]; then \
            pip install -e "$pkg"; \
        fi \
    done \
    fi

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["python", "app.py"]