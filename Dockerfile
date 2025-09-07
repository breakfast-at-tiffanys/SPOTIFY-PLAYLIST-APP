FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (optional). Keep lean for Pi.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code and static assets
COPY . /app

# Default to bash; workflow or compose passes the command.
ENTRYPOINT ["bash", "-lc"]
CMD ["python --version"]

