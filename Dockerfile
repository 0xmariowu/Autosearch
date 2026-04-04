FROM python:3.11-slim

WORKDIR /autosearch

# Install deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir openai pytest

# Copy project
COPY . .

ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-x", "-q", "tests/"]
