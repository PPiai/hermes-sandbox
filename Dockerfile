FROM python:3.12-bookworm

# Ferramentas de sistema: clientes de banco, curl, git, jq, node...
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl wget git jq ca-certificates unzip \
      postgresql-client default-mysql-client redis-tools \
      nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Bibliotecas Python
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY app.py /app/app.py

# Usuario sem privilegios; o codigo do agente roda como ele
RUN useradd -m -u 10001 sandbox \
    && mkdir -p /work && chown sandbox:sandbox /work
USER sandbox

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
