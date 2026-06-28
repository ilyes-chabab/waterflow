@echo off
echo Lancement de MLflow...
start /B mlflow ui 

echo Lancement de l'API (app.py)...
start /B python3 app.py

echo Lancement de l'interface Streamlit...
streamlit run ui.py

echo Tous les services sont démarrés.