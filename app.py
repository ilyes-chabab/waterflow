import mlflow.xgboost
import numpy as np
from flask import Flask, jsonify, request

app = Flask(__name__)

# 1. Connexion au serveur de tracking MLflow
mlflow.set_tracking_uri("http://127.0.0.1:5000")

BEST_THRESHOLD = 0.37

MODEL_NAME = "water_quality_model"
model_uri = f"models:/{MODEL_NAME}/Production"

try:
    print(f"Chargement du modèle XGBoost depuis le Registry MLflow ({model_uri})...")
    model = mlflow.xgboost.load_model(model_uri)
    print("API Flask : Modèle XGBoost chargé avec succès et prêt à l'emploi !")
except Exception as e:
    print(f"Erreur lors du chargement du modèle : {e}")
    model = None


@app.route("/health", methods=["GET"])
def health():
    """Vérifier que l'API et le modèle sont opérationnels."""
    return jsonify({"status": "healthy", "model_loaded": model is not None})


@app.route("/predict", methods=["POST"])
def predict():
    """Endpoint pour prédire la potabilité de l'eau en temps réel avec seuil optimisé."""
    if model is None:
        return (
            jsonify({"error": "Modèle indisponible sur le serveur."}),
            503,
        )

    data = request.get_json()

    if not data or "features" not in data:
        return (
            jsonify(
                {
                    "error": "Format incorrect. Format attendu : {'features': [val1, ..., val9]}"
                }
            ),
            400,
        )

    try:
        features = np.array(data["features"]).reshape(1, -1)

        if features.shape[1] != 9:
            return (
                jsonify(
                    {
                        "error": f"Le modèle requiert exactement 9 mesures. Reçu : {features.shape[1]}"
                    }
                ),
                400,
            )

        probabilities = model.predict_proba(features)
        prob_potable = float(probabilities[0][1])

        if prob_potable >= BEST_THRESHOLD:
            prediction_result = 1
            status = "Potable (Safe)"
        else:
            prediction_result = 0
            status = "Non Potable (Unsafe)"

        return jsonify(
            {
                "prediction": prediction_result,
                "probability_potable": prob_potable,
                "decision_threshold_used": BEST_THRESHOLD,
                "water_status": status,
                "model_version_used": "Production",
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"error": f"Erreur interne lors de la prédiction : {str(e)}"}
            ),
            500,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)