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

RUN pip install --no-cache-dir mlflow

EXPOSE 5000

# Meme commande que le lancement local (README/CLAUDE.md), sans --backend-store-uri :
# stockage sur fichiers (./mlruns), monte en volume pour persister entre redemarrages.
# --allowed-hosts : sans ca, le middleware de securite MLflow rejette (403) les
# requetes dont le header Host n'est pas "localhost" - ce qui inclut l'appel de
# l'API via le nom de service Docker Compose "mlflow".
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--allowed-hosts", "mlflow:5000,mlflow,localhost:5000,localhost,127.0.0.1:5000,127.0.0.1"]
