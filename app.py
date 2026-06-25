import mlflow.xgboost
import numpy as np
import functools
from flask import Flask, jsonify, request
from data.db.WaterFlowDB import WaterFlowDB

# ── Import du Blueprint OCR ──────────────────────────────
from ocr_api import ocr_bp

app = Flask(__name__)
app.register_blueprint(ocr_bp)

# ──────────────────────────────────────────────
# Système d'Authentification par Clé API (Headers)
# ──────────────────────────────────────────────

def require_api_key(f):
	@functools.wraps(f)
	def decorated(*args, **kwargs):
		api_key = request.headers.get("X-API-Key")
		if not api_key:
			return jsonify({"error": "Cle API manquante dans les en-têtes (X-API-Key)"}), 401
		
		try:
			db = WaterFlowDB()
			all_users = db.get_users()
			db.close()
			
			# On cherche l'utilisateur qui possède cette clé API
			# Structure u : (user_id, username, api_key, right, ...)
			matched_user = next((u for u in all_users if u[2] == api_key), None)
			
			if not matched_user:
				return jsonify({"error": "Cle API invalide"}), 401
			
			current_client = {
				"id": matched_user[0],
				"username": matched_user[1],
				"role": matched_user[3]
			}
			
		except Exception as e:
			return jsonify({"error": f"Erreur d'authentification : {str(e)}"}), 500
			
		return f(current_client, *args, **kwargs)
	return decorated


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
# Nouvelles Routes de l'API Client
# ──────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def login():
    """Vérifie la clé API reçue dans le header et renvoie les infos utilisateur."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Cle API manquante dans les en-têtes (X-API-Key)"}), 401

    try:
        db = WaterFlowDB()
        all_users = db.get_users()
        db.close()

        # Recherche de l'utilisateur uniquement via sa clé API
        matched_user = next((u for u in all_users if u[2] == api_key), None)

        if matched_user:
            return jsonify({
                "authenticated": True,
                "user_id": matched_user[0],
                "username": matched_user[1],
                "role": matched_user[3]
            }), 200
        else:
            return jsonify({"authenticated": False, "error": "Cle API invalide"}), 401

    except Exception as e:
        return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500

@app.route("/api/measurements", methods=["POST"])
@require_api_key
def add_measurement(current_client):
    """Soumettre des mesures, lier au client, et retourner la prédiction."""
    if model is None:
        return jsonify({"error": "Modèle ML indisponible."}), 503

    data = request.get_json()
    if not data or "features" not in data:
        return jsonify({"error": "Format attendu : {'features': [val1, ..., val9]}"}), 400

    try:
        features_list = data["features"]
        if len(features_list) != 9:
            return jsonify({"error": f"9 mesures requises, reçu : {len(features_list)}"}), 400

        features_array = np.array(features_list).reshape(1, -1)
        probabilities = model.predict_proba(features_array)
        prob_potable = float(probabilities[0][1])
        prediction_result = 1 if prob_potable >= BEST_THRESHOLD else 0
        status = "Potable (Safe)" if prediction_result == 1 else "Non Potable (Unsafe)"

        db = WaterFlowDB()
        db.add_prediction(
            user_id=current_client["id"],
            ph=features_list[0],
            hardness=features_list[1],
            solids=features_list[2],
            chloramines=features_list[3],
            sulfate=features_list[4],
            conductivity=features_list[5],
            organic_carbon=features_list[6],
            trihalomethanes=features_list[7],
            turbidity=features_list[8],
            potability=prediction_result
        )
        db.close()

        return jsonify({
            "client_id": current_client["id"],
            "prediction": prediction_result,
            "probability_potable": prob_potable,
            "water_status": status,
            "msg": "Prelèvement et prediction sauvegardes avec succès."
        }), 201

    except Exception as e:
        return jsonify({"error": f"Erreur traitement : {str(e)}"}), 500


@app.route("/api/measurements", methods=["GET"])
@require_api_key
def get_client_measurements(current_client):
    """Consulter l'historique STRICTEMENT limité au client connecté (RGPD)."""
    try:
        db = WaterFlowDB()
        client_data = db.get_predictions_by_user(current_client["id"]) 
        db.close()

        history = []
        for row in client_data:
            history.append({
                "id_prediction": row[0],
                "measures": {
                    "ph": row[2],
                    "hardness": row[3],
                    "solids": row[4],
                    "chloramines": row[5],
                    "sulfate": row[6],
                    "conductivity": row[7],
                    "organic_carbon": row[8],
                    "trihalomethanes": row[9],
                    "turbidity": row[10]
                },
                "potability_result": row[11]
            })

        return jsonify({
            "client_id": current_client["id"],
            "username": current_client["username"],
            "total_records": len(history),
            "history": history
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Erreur récupération : {str(e)}"}), 500


@app.route("/api/me", methods=["GET"])
@require_api_key
def rgpd_info(current_client):
	"""Droit à l'information (RGPD) : renvoie les données du compte."""
	return jsonify({
		"declaration": "Conformement au RGPD, voici vos donnees stockees.",
		"donnees_personnelles": {
			"id_client": current_client["id"],
			"nom_utilisateur": current_client["username"],
			"role": current_client["role"]
		},
		"regle_conservation": "Les mesures de prelevements anonymisees sont conservees 5 ans. Vos donnees d'identification sont supprimees a la cloture du compte."
	}), 200


# NOTE : Pour la route OCR (POST /api/ocr/lab-report), appliquez le décorateur @require_api_key 
# directement à l'intérieur de votre fichier `ocr_api.py` sur la fonction correspondante.

@app.route("/health", methods=["GET"])
def health():
	return jsonify({"status": "healthy", "model_loaded": model is not None})

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8000, debug=False)