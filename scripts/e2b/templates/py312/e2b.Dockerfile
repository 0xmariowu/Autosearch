FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# System deps
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl git ca-certificates \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && python3.12 -m ensurepip --upgrade \
    && python3.12 -m pip install --upgrade pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pre-install autosearch and its deps (speeds up test setup)
RUN python3.12 -m pip install \
    httpx \
    structlog \
    pydantic \
    typer \
    "mcp[cli]" \
    e2b \
    pytest \
    pytest-asyncio \
    --quiet

# Verify
RUN python3.12 --version && python3.12 -m pip --version
