# Base Image
FROM python:3.9-slim

# Install system dependencies for Playwright & Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for cache
COPY execution/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Browsers and Dependencies
RUN playwright install --with-deps chromium

# Setup App Directory
WORKDIR /app
COPY execution/ execution/
COPY config.json .

# Default port for Streamlit
EXPOSE 8080

# Environment variables to force Headless
ENV HEADLESS_MODE=true
ENV PYTHONUNBUFFERED=1

# Default Entrypoint (Can be overridden by Cloud Run Job)
ENTRYPOINT ["streamlit", "run", "execution/saturday_ui.py", "--server.port=8080", "--server.address=0.0.0.0"]
