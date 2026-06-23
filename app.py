"""
app.py – API principale Waterflow 2
Modules : Prédiction (existant) + OCR (nouveau)
"""

import mlflow.xgboost
import numpy as np
from flask import Flask, jsonify, request

# ── Import du Blueprint OCR ──────────────────────────────
from ocr_api import ocr_bp

app = Flask(__name__)

# ── Enregistrement du Blueprint ──────────────────────────
# Toutes les routes OCR sont préfixées /api/ocr
app.register_blueprint(ocr_bp)

# ──────────────────────────────────────────────
# Chargement du modèle MLflow (inchangé)
# ──────────────────────────────────────────────
mlflow.set_tracking_uri("http://127.0.0.1:5000")

BEST_THRESHOLD = 0.37
MODEL_NAME = "water_quality_model"
model_uri = f"models:/{MODEL_NAME}/Production"

try:
    print(f"Chargement du modèle XGBoost depuis le Registry MLflow ({model_uri})...")
    model = mlflow.xgboost.load_model(model_uri)
    print("Modèle XGBoost chargé avec succès !")
except Exception as e:
    print(f"Erreur lors du chargement du modèle : {e}")
    model = None


# ──────────────────────────────────────────────
# Routes existantes (inchangées)
# ──────────────────────────────────────────────

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
        return jsonify({"error": "Format attendu : {'features': [val1, ..., val9]}"}), 400

    try:
        features = np.array(data["features"]).reshape(1, -1)
        if features.shape[1] != 9:
            return jsonify({"error": f"9 mesures requises, reçu : {features.shape[1]}"}), 400

        probabilities = model.predict_proba(features)
        prob_potable = float(probabilities[0][1])
        prediction_result = 1 if prob_potable >= BEST_THRESHOLD else 0
        status = "Potable (Safe)" if prediction_result == 1 else "Non Potable (Unsafe)"

        return jsonify({
            "prediction": prediction_result,
            "probability_potable": prob_potable,
            "decision_threshold_used": BEST_THRESHOLD,
            "water_status": status,
            "model_version_used": "Production",
        })

    except Exception as e:
        return jsonify({"error": f"Erreur interne : {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)