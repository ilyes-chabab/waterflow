FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui.py .
COPY dashboard_qualite.py .
COPY views/ ./views/
COPY mean_features.json .
COPY data/processed/X_test.csv data/processed/y_test.csv ./data/processed/

EXPOSE 8501

CMD ["streamlit", "run", "ui.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
