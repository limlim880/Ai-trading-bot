# Production image for the AI Trading Assistant.
# Slim base keeps the image small; nothing here needs a full OS.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer between builds
# whenever only application code (not requirements.txt) changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the application code.
COPY . .

# Railway (and most PaaS hosts) inject PORT at runtime -- the app must
# listen on whatever value that is, not a hardcoded port.
ENV PORT=8000
EXPOSE 8000

# Shell form so ${PORT} is expanded at container start, not build time.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
