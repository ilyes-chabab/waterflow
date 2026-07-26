FROM python:3.10-slim

WORKDIR /app

# CA locale optionnelle (proxy/antivirus faisant de l'inspection TLS sur la machine
# de build, ex. Norton) : docker/certs/ est vide sauf ajout local (gitignored), donc
# ces deux lignes sont un no-op inoffensif sur une machine/CI sans interception TLS.
COPY docker/certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY data/db/__init__.py data/db/WaterFlowDB.py ./data/db/

# MLFLOW_TRACKING_URI doit pointer vers un serveur MLflow joignable depuis le
# conteneur (127.0.0.1 designerait le conteneur lui-meme, pas l'hote).
ENV MLFLOW_TRACKING_URI=http://127.0.0.1:5000

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
