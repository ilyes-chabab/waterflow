FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY data/db/__init__.py data/db/WaterFlowDB.py ./data/db/

# MLFLOW_TRACKING_URI doit pointer vers un serveur MLflow joignable depuis le
# conteneur (127.0.0.1 designerait le conteneur lui-meme, pas l'hote).
ENV MLFLOW_TRACKING_URI=http://127.0.0.1:5000

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
