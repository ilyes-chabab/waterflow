import mlflow.xgboost
from mlflow.tracking import MlflowClient
import numpy as np
import functools
import secrets
import hashlib
from flask import Flask, jsonify, request
from data.db.WaterFlowDB import WaterFlowDB

# ── Import du Blueprint OCR ──────────────────────────────
from ocr_api import ocr_bp

app = Flask(__name__)
app.register_blueprint(ocr_bp)

# ──────────────────────────────────────────────
# Système d'Authentification par Clé API (Headers)
# ──────────────────────────────────────────────
def generate_api_key():
    return secrets.token_hex(32)

def hash_key(k):
    return hashlib.sha256(k.encode()).hexdigest()

def require_api_key(f):
	@functools.wraps(f)
	def decorated(*args, **kwargs):
		api_key_recue = request.headers.get("X-API-Key")
		if not api_key_recue:
			return jsonify({"error": "Cle API manquante"}), 401

		hash_api_key_recue = hashlib.sha256(api_key_recue.encode()).hexdigest()
		
		try:
			db = WaterFlowDB()
			all_users = db.get_users()
			db.close()
			
			# On cherche l'utilisateur qui possède cette clé API
			# Structure u : (user_id, username, api_key, right, ...)
			matched_user = next((u for u in all_users if u[2] == hash_api_key_recue), None)
			
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


def require_role(*allowed_roles):
	"""Décorateur combiné : vérifie la clé API ET le rôle du client.
	Usage : @require_role("Quality_Analyst", "Admin")"""
	def wrapper(f):
		@functools.wraps(f)
		@require_api_key
		def decorated(current_client, *args, **kwargs):
			if current_client["role"] not in allowed_roles:
				return jsonify({"error": "Acces refuse. Role insuffisant."}), 403
			return f(current_client, *args, **kwargs)
		return decorated
	return wrapper


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
# Helpers MLflow : métriques & versions du modèle
# ──────────────────────────────────────────────
def get_model_metrics():
	"""Récupère les métriques (accuracy, recall, etc.) de la version
	'Production' du modèle, directement depuis le run MLflow associé."""
	client = MlflowClient()
	versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
	if not versions:
		return None

	version = versions[0]
	run = client.get_run(version.run_id)
	return {
		"version": version.version,
		"run_id": version.run_id,
		"stage": version.current_stage,
		"metrics": run.data.metrics,
		"params": run.data.params,
	}


def get_all_model_versions():
	"""Liste toutes les versions enregistrées du modèle, avec leurs métriques,
	pour permettre la comparaison entre versions."""
	client = MlflowClient()
	versions = client.search_model_versions(f"name='{MODEL_NAME}'")

	result = []
	for v in versions:
		try:
			run = client.get_run(v.run_id)
			metrics = run.data.metrics
			params = run.data.params
		except Exception:
			metrics, params = {}, {}

		result.append({
			"version": v.version,
			"stage": v.current_stage,
			"run_id": v.run_id,
			"metrics": metrics,
			"params": params,
		})

	# Plus récente version en premier
	result.sort(key=lambda x: int(x["version"]), reverse=True)
	return result


def predict_with_run(run_id, features_list):
	"""Recharge le modèle d'une version MLflow précise (via son run_id) et
	rejoue une prédiction. Utile pour comparer l'impact des versions."""
	versioned_model = mlflow.xgboost.load_model(f"runs:/{run_id}/model")
	features_array = np.array(features_list).reshape(1, -1)
	probabilities = versioned_model.predict_proba(features_array)
	prob_potable = float(probabilities[0][1])
	prediction_result = 1 if prob_potable >= BEST_THRESHOLD else 0
	return prediction_result, prob_potable


# ──────────────────────────────────────────────
# Nouvelles Routes de l'API Client
# ──────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def login():
    """Vérifie la clé API reçue dans le header et renvoie les infos utilisateur."""
    api_key_recue = request.headers.get("X-API-Key")
    if not api_key_recue:
        return jsonify({"error": "Cle API manquante"}), 401
    
    hash_api_key_recue = hashlib.sha256(api_key_recue.encode()).hexdigest()

    try:
        db = WaterFlowDB()
        all_users = db.get_users()
        db.close()

        # Recherche de l'utilisateur uniquement via sa clé API
        matched_user = next((u for u in all_users if u[2] == hash_api_key_recue), None)

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
            potability=prediction_result,
            source="manuel"
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

@app.route("/api/clients", methods=["POST"])
@require_api_key
def create_client(current_client):
    """Cree un client en stockant le hash de sa cle API."""
    if current_client["role"] != "Admin":
        return jsonify({"error": "Acces refuse. Cette action est reservee aux administrateurs."}), 403

    data = request.get_json()
    if not data or "username" not in data:
        return jsonify({"error": "Format attendu : {'username': 'nom_du_client'}"}), 400

    username = data["username"]
    role = data.get("role", "Client")

    try:
        plain_key = generate_api_key()
        
        hashed_key = hash_key(plain_key)

        db = WaterFlowDB()
        db.add_user(username=username, api_key=hashed_key, right=role)
        
        all_users = db.get_users()
        db.close()

        new_user = next((u for u in all_users if u[2] == hashed_key), None)
        user_id = new_user[0] if new_user else "Inconnu"

        return jsonify({
            "message": "Client cree avec succes.",
            "client": {
                "id": user_id,
                "username": username,
                "role": role,
                "api_key_plain": plain_key
            }
        }), 201

    except Exception as e:
        return jsonify({"error": f"Erreur lors de la creation du client : {str(e)}"}), 500


@app.route("/api/clients", methods=["GET"])
@require_api_key
def list_clients(current_client):
    """Recupere la liste de tous les clients (Affiche les hashs)."""
    if current_client["role"] != "Admin":
        return jsonify({"error": "Acces refuse. Cette action est reservee aux administrateurs."}), 403

    try:
        db = WaterFlowDB()
        all_users = db.get_users()
        db.close()

        clients_list = []
        for row in all_users:
            clients_list.append({
                "id": row[0],
                "username": row[1],
                "api_key_hash": row[2],
                "role": row[3]
            })

        return jsonify({
            "total_clients": len(clients_list),
            "clients": clients_list
        }), 200

    except Exception as e:
        return jsonify({"error": f"Erreur lors de la recuperation des clients : {str(e)}"}), 500

@app.route("/api/dashboard/measurements", methods=["GET"])
@require_role("Quality_Analyst", "Admin")
def dashboard_measurements(current_client):
    """Dashboard global : tous les prélèvements, toutes provenances,
    avec filtres optionnels (client, source, dates, zone)."""
    client_id = request.args.get("client_id")
    source = request.args.get("source")  # "manuel" ou "ocr"
    date_from = request.args.get("date_from")  # format YYYY-MM-DD
    date_to = request.args.get("date_to")
    zone = request.args.get("zone")

    try:
        db = WaterFlowDB()
        rows = db.get_all_predictions_filtered(
            client_id=client_id, source=source,
            date_from=date_from, date_to=date_to, zone=zone
        )
        db.close()

        data = []
        for row in rows:
            data.append({
                "id_prediction": row[0],
                "client": {"id": row[1], "username": row[2], "role": row[3]},
                "measures": {
                    "ph": row[4],
                    "hardness": row[5],
                    "solids": row[6],
                    "chloramines": row[7],
                    "sulfate": row[8],
                    "conductivity": row[9],
                    "organic_carbon": row[10],
                    "trihalomethanes": row[11],
                    "turbidity": row[12]
                },
                "potability_result": row[13],
                "source": row[14],
                "created_at": row[15]
            })

        return jsonify({"total_records": len(data), "data": data}), 200

    except Exception as e:
        return jsonify({"error": f"Erreur récupération dashboard : {str(e)}"}), 500


@app.route("/api/dashboard/metrics", methods=["GET"])
@require_role("Quality_Analyst", "Admin")
def dashboard_metrics(current_client):
    """Métriques du modèle en Production, récupérées depuis MLflow."""
    try:
        metrics = get_model_metrics()
        if metrics is None:
            return jsonify({"error": "Aucune version 'Production' trouvée sur MLflow."}), 404
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({"error": f"Erreur MLflow : {str(e)}"}), 500


@app.route("/api/dashboard/model-versions", methods=["GET"])
@require_role("Quality_Analyst", "Admin")
def dashboard_model_versions(current_client):
    """Liste toutes les versions du modèle (pour comparaison)."""
    try:
        versions = get_all_model_versions()
        return jsonify({"total_versions": len(versions), "versions": versions}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur MLflow : {str(e)}"}), 500


@app.route("/api/dashboard/replay", methods=["POST"])
@require_role("Quality_Analyst", "Admin")
def dashboard_replay(current_client):
    """Rejoue une prédiction existante avec une version spécifique du modèle
    (via son run_id MLflow), pour comparer l'impact d'une nouvelle version."""
    data = request.get_json()
    if not data or "run_id" not in data or "features" not in data:
        return jsonify({"error": "Format attendu : {'run_id': '...', 'features': [9 valeurs]}"}), 400

    try:
        features_list = data["features"]
        if len(features_list) != 9:
            return jsonify({"error": f"9 mesures requises, reçu : {len(features_list)}"}), 400

        prediction_result, prob_potable = predict_with_run(data["run_id"], features_list)
        status = "Potable (Safe)" if prediction_result == 1 else "Non Potable (Unsafe)"

        return jsonify({
            "run_id": data["run_id"],
            "prediction": prediction_result,
            "probability_potable": prob_potable,
            "water_status": status
        }), 200

    except Exception as e:
        return jsonify({"error": f"Erreur lors du rejeu de prédiction : {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
	return jsonify({"status": "healthy", "model_loaded": model is not None})

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8000, debug=False)