# LUNCH.md

Ce fichier vous permet d'initaliser le projet et de le lancer.

## Projet

Waterflow 2 est une plateforme MLOps qui prédit la **potabilité** de l'eau (potable/non potable) à partir de 9
mesures physico-chimiques (ph, hardness, solids, chloramines, sulfate, conductivity,
organic_carbon, trihalomethanes, turbidity), à l'aide d'un modèle XGBoost suivi et servi via
le Model Registry de MLflow. Le projet expose un backend FastAPI, une interface Streamlit, et une ingestion
par OCR de rapports de laboratoire (images/PDF).

## Lancer la stack

### Option A — Docker Compose (recommandée, tous les services orchestrés ensemble)

```bash
docker compose up --build
```

Démarre `mlflow` (:5000), `api` (:8000), `streamlit` (:8501), `prometheus` (:9090) et `grafana`
(:3000). Le service `mlflow` persiste son registre/ses artefacts dans `./mlflow_data` (monté en bind) —
sans cela, le backend SQLite propre au conteneur (`mlflow.db`, créé dans le répertoire de travail du
conteneur quand aucun `--backend-store-uri` n'est passé) serait perdu à chaque rebuild. Le service `api`
lit `MLFLOW_TRACKING_URI` (par défaut `http://127.0.0.1:5000`, surchargé en
`http://mlflow:5000` dans `docker-compose.yml`) et persiste `data/db/waterflow.db` via un bind mount.

Sur un `mlflow_data/` tout neuf (premier lancement, ou après l'avoir supprimé), le registre de modèles
est vide et `/api/measurements` renvoie `503` tant qu'un modèle n'a pas été entraîné et promu :

```bash
python scripts/experiment.py   # pointe vers http://127.0.0.1:5000, mappé depuis le conteneur mlflow
docker compose restart api     # recharge le nouveau modèle "Production" enregistré
```

### Option B — lancer les services individuellement (sans Docker)

```bash
# 1. Serveur de tracking MLflow + registre de modèles (UI sur http://127.0.0.1:5000)
python -m mlflow server --host 127.0.0.1 --port 5000

# 2. Backend FastAPI (charge le stage "Production" de water_quality_model depuis MLflow au démarrage)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Interface Streamlit (http://localhost:8501), communique avec l'API sur 127.0.0.1:8000
python -m streamlit run ui.py
```

`waterflow2.bat` exécute les trois mêmes commandes que l'Option B, dans l'ordre, sous Windows.

Configuration initiale : créer la première clé API Admin avec `python scripts/init_admin.py` (affiche la
clé en clair une seule fois — elle n'est ensuite stockée en base que sous forme de hash SHA-256).

Entraîner une nouvelle version de modèle : `python scripts/experiment.py` (charge
`data/processed/processed_data.pkl`, applique SMOTE, entraîne XGBoost, journalise paramètres/métriques/modèle dans
MLflow, l'enregistre sous le nom `water_quality_model`, et fait passer la dernière version au stage
`Production` — cela affecte immédiatement ce que l'API en cours d'exécution sert au prochain (re)chargement
du modèle).

## Tests

```bash
pytest
```

`pytest.ini` restreint la découverte des tests à `tests/`. `tests/test_pipeline.py` couvre l'application FastAPI
directement (via `fastapi.testclient.TestClient`, avec des fixtures dans `tests/conftest.py` qui mockent MLflow/OCR pour
qu'aucun service externe ne soit nécessaire) ; `tests/test_ui_integration.py` couvre les pages Streamlit
(`views/*.py`, `scripts\dashboard_qualite.py`) via `streamlit.testing.v1.AppTest`, relié au même
`TestClient` afin que le code de l'UI exerce les vraies routes de l'API. Voir `tests/test_README.md` pour la
configuration/les commandes de couverture, et `tests/bugTrouvé_README.md` pour un journal des bugs réels
trouvés et corrigés pendant la construction de cette suite.

## Architecture

- **`api/main.py`** — Application FastAPI. Charge le modèle MLflow `Production` une seule fois au démarrage
  (`lifespan`), et applique un seuil de décision fixe (`app.state.best_threshold`, actuellement
  0.37) à la sortie de `predict_proba` plutôt que le seuil par défaut de 0.5 du modèle. Pile de middlewares :
  `metrics_middleware` (métriques Prometheus RED, exposées sur `GET /metrics`), `security_headers`
  (X-Content-Type-Options/X-Frame-Options/Referrer-Policy), `access_log` (écrit chaque requête dans
  la table `audit_logs`, en résolvant l'utilisateur demandeur par re-hachage de l'en-tête `X-API-Key`).
  `/api/login` et `/api/measurements` sont soumis à une limitation de débit (`slowapi`).
- **`api/auth.py`** — dépendances FastAPI partagées `get_current_user` / `require_role(*roles)`, utilisées
  à la fois par `api/main.py` et `api/ocr_router.py`. L'authentification repose sur une clé API (en-tête `X-API-Key`,
  hachée en SHA-256, recherchée dans la table `users`) ; les rôles sont `Client`, `Quality_Analyst`, `Admin`.
  Seul le rôle Admin peut créer/lister des clients, faire tourner les clés, ou lire les logs d'audit ; Quality_Analyst et
  Admin peuvent accéder aux routes `/api/dashboard/*`.
- **`api/ocr_router.py`** — `/api/ocr/lab-report` envoie une image/un PDF téléversé à l'API OCR.space,
  parse par regex le texte retourné pour en extraire les 9 mêmes caractéristiques (plus quelques champs
  supplémentaires comme les nitrates), et exécute le même chemin de prédiction que `/api/measurements`. Le client_id
  provient toujours de la clé API authentifiée, jamais de l'OCR ni d'une saisie utilisateur (choix
  délibéré pour la sécurité RGPD). Les échecs d'OCR (timeout/service injoignable/erreur HTTP/erreur de traitement)
  sont journalisés de façon structurée et comptabilisés dans la métrique Prometheus
  `ocr_failures_total`, et se dégradent proprement (code d'erreur HTTP approprié) plutôt que de faire planter l'application.
- **`api/logging_config.py`** — journalisation structurée en JSON (`logger` du logger `waterflow2`), utilisée
  à la place de `print()` dans tout `api/`. Chaque ligne de log est un événement JSON avec du contexte via
  `extra={...}`, filtrable/agrégeable lors du diagnostic d'incidents (voir `docs/incidents/`).
- **`data/db/WaterFlowDB.py`** — l'unique couche d'accès aux données, encapsulant un seul fichier SQLite à
  `data/db/waterflow.db` (ignoré par git — vrais hashs de clés API + logs d'audit, jamais versionnés). Tables :
  `users` (api_key stockée en hash SHA-256, `right` = rôle, `is_active` permet la révocation de clé),
  `prediction` (une ligne par mesure + résultat de potabilité + `source` : `manuel` ou `ocr`),
  `audit_logs`. `_ensure_prediction_columns()` exécute une migration légère (ajoute des
  colonnes si elles manquent) à chaque connexion — il n'existe pas d'outil de migration séparé. Chaque route
  ouvre/ferme sa propre connexion `WaterFlowDB()` plutôt que d'en partager une.
- **`scripts/experiment.py`** — script d'entraînement MLflow autonome (non importé par l'API) : charge
  le split train/val prétraité, équilibre les classes avec SMOTE, entraîne XGBoost, balaie les seuils
  de 0.30 à 0.70 pour trouver le meilleur F1, journalise tout dans l'expérience MLflow
  `experiment_water_quality`, puis enregistre et promeut le modèle en `Production`. Le seuil trouvé ici doit être
  maintenu manuellement synchronisé avec `app.state.best_threshold` dans `api/main.py`.
- **`scripts/validate_data.py`**, **`scripts/validate_model.py`** — verrous CI (`.github/workflows/ci.yml`) :
  vérification du schéma/des valeurs manquantes sur le CSV brut, et un ré-entraînement hors MLflow avec
  vérification du seuil de score F1.
- **`scripts/compute_means.py`**, **`scripts/init_admin.py`**, **`scripts/pile.py`** — scripts
  ponctuels/de configuration. `pile.py` est un premier prototype d'OCR local (pytesseract), remplacé par
  l'implémentation basée sur OCR.space de `api/ocr_router.py` ; conservé pour référence, non utilisé par l'application.
- **`ui.py` + `views/`** — Application Streamlit multi-pages. Le rôle lu dans la réponse `/api/login` de l'API
  détermine quelles pages (`st.navigation`) sont affichées : `Admin` obtient
  `views/accueil_admin.py` + `views/securite_admin.py` ; `Quality_Analyst` obtient
  `scripts/dashboard_qualite.py` ; `Client` obtient `views/panel_test.py`, `views/historique.py`, et
  `views/mes_donnees.py` (libre-service RGPD : `GET`/`DELETE /api/me`). L'état de session
  (`st.session_state`) conserve la clé API et l'envoie en tant que `X-API-Key` à chaque appel backend — il n'y a
  pas de session côté serveur. `API_BASE_URL` (dans tous les `ui.py`/`views/*.py`/`dashboard_qualite.py`) et
  `MLFLOW_TRACKING_URI` (`api/main.py`) sont tous deux surchargeables via des variables d'environnement, avec
  `127.0.0.1` par défaut pour un usage sans Docker, et surchargés vers les noms de services Docker Compose dans
  `docker-compose.yml`.
- **`data/`** — `raw/` contient le CSV source de type Kaggle ; `processed/` contient le split
  train/val/test sérialisé (pickle) consommé par `scripts/experiment.py` ; `description/` et `output/` contiennent des notes
  et des graphiques d'analyse exploratoire issus des notebooks dans `notebooks/`.
- **`notebooks/`** — uniquement de vrais notebooks Jupyter (`data-analysis.ipynb`,
  `water_quality_analysis.ipynb`). Les spécifications/documents de conception se trouvent dans `docs/` (voir
  ci-dessous).
- **`docs/`** — `user_stories.md` (spécifications fonctionnelles, critères WCAG par user story), `parcours_utilisateurs.md`
  (diagrammes de parcours utilisateur Mermaid), `checklist_C9_C19.md` (checklist d'audit RNCP),
  `Slidesupport/MCD.txt` + `Slidesupport/MPD.txt` (modèle de données, formalisme Merise),
  `ACCESSIBILITE_DOCUMENTATION.md` (accessibilité du format de la documentation elle-même),
  `incidents/` (modèle de rapport d'incident et retours d'expérience réels, format DDCR).

## Conventions à préserver

- Les réponses de l'API et les commentaires dans le code sont en français ; garder les nouveaux
  endpoints/docstrings cohérents avec ce style (voir les regroupements `tags=[...]` dans `api/main.py` : Auth,
  Prélèvements, Clients, RGPD, Dashboard, Admin).
- Les clés API ne sont retournées en clair qu'une seule fois (à la création ou lors d'une rotation de clé) —
  ne jamais les re-journaliser ni persister la valeur en clair ailleurs.
- Les endpoints RGPD (`/api/me` GET/DELETE) sont importants pour ce projet : la suppression de compte anonymise
  `audit_logs.user_id` en NULL au lieu de supprimer les lignes d'audit, tout en supprimant réellement les lignes
  `prediction` de l'utilisateur. Exposé dans l'UI via `views/mes_donnees.py`.
- Les chemins de fichiers relatifs dans le code (`data/processed/...`, `data/db/waterflow.db`, `data\processed\mean_features.json`)
  sont résolus par rapport au répertoire de travail courant, et non à l'emplacement du script — toujours exécuter
  les scripts depuis la racine du dépôt. Ne jamais coder en dur des chemins Windows avec des antislashs (casse sous
  Linux/Docker).
</content>
