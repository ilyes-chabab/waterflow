FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir mlflow

EXPOSE 5000

# Meme commande que le lancement local (README/CLAUDE.md), sans --backend-store-uri :
# stockage sur fichiers (./mlruns), monte en volume pour persister entre redemarrages.
# --allowed-hosts : sans ca, le middleware de securite MLflow rejette (403) les
# requetes dont le header Host n'est pas "localhost" - ce qui inclut l'appel de
# l'API via le nom de service Docker Compose "mlflow".
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--allowed-hosts", "mlflow:5000,mlflow,localhost:5000,localhost,127.0.0.1:5000,127.0.0.1"]
