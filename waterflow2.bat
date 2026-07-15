@echo off
echo Lancement de MLflow (http://127.0.0.1:5000)...
start "MLflow" python -m mlflow server --host 127.0.0.1 --port 5000

echo Lancement de l'API FastAPI (http://localhost:8000)...
start "API" python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

echo Lancement de l'interface Streamlit (http://localhost:8501)...
streamlit run ui.py

echo Tous les services sont demarres.
