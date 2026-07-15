# Monitoring — Waterflow 2

Chaîne de supervision de l'API : Prometheus scrape les métriques exposées par FastAPI, Grafana
les visualise en temps réel. Sert de preuve pour C11.

## Architecture

```
FastAPI (Waterflow 2)          Prometheus              Grafana
   GET /metrics  ── scrape 15s ──►  :9090  ── query PromQL ──►  :3000
```

- **FastAPI** (`api/main.py`) expose les métriques via `prometheus-client`, montées sur
  `GET /metrics` (non protégé par authentification — posture standard des exports Prometheus,
  la sécurisation se fait au niveau réseau, pas applicatif).
- **Prometheus** interroge cet endpoint toutes les 15 secondes (`prometheus.yml`) et stocke
  l'historique en séries temporelles.
- **Grafana** interroge Prometheus (PromQL) pour construire des tableaux de bord.

## Métriques exposées (expliquées)

Les 3 métriques RED, standard pour superviser la santé d'une API :

| Métrique | Nom Prometheus | Ce qu'elle mesure | Pourquoi c'est utile |
|---|---|---|---|
| **Rate** | `http_requests_total` (compteur, par méthode/endpoint/statut) | Le nombre de requêtes reçues | Détecter un pic de trafic anormal ou, à l'inverse, une chute brutale (signe que l'API ne reçoit plus rien) |
| **Errors** | `http_requests_total{status=~"5.."}` | La part des requêtes qui échouent côté serveur (5xx) | Détecter une panne (ex. dépendance externe indisponible) avant qu'un client ne s'en plaigne |
| **Duration** | `http_request_duration_seconds` (histogramme, par endpoint) | Le temps de réponse de chaque requête | Détecter un ralentissement progressif (fuite de ressource, dépendance lente) avant qu'il ne devienne un incident |

Métrique additionnelle spécifique au projet : `ocr_failures_total{reason=...}` — compte les
échecs d'appel à OCR.space par type de cause (timeout, injoignable, erreur HTTP, erreur de
traitement), pour distinguer une panne du service externe d'un problème de fichier envoyé par
l'utilisateur.

Ces métriques renseignent sur la santé de l'**API**, pas directement sur la qualité des
**prédictions** du modèle (accuracy/F1/etc.) — celles-ci sont visibles séparément dans l'onglet
"Métriques du modèle" du Dashboard Qualité (`dashboard_qualite.py`), issues de MLflow.

## Installation et configuration

Fait partie de `docker-compose.yml` :

```bash
docker compose up --build
```

Démarre `mlflow`, `api`, `streamlit`, `prometheus` (config : `prometheus.yml`, monté en volume) et
`grafana`. Aucune configuration supplémentaire n'est nécessaire pour Prometheus (le fichier de
configuration est déjà fourni et monté automatiquement).

**Configurer la source de données dans Grafana** (à faire une fois, à chaque nouvelle instance
Grafana — non persisté par défaut) :
1. `http://localhost:3000`, identifiants par défaut `admin` / `admin`.
2. **Connections → Data sources → Add data source → Prometheus**.
3. URL : `http://prometheus:9090` (nom du service Docker, pas `localhost`).
4. **Save & test**.

## Utilisation

- Vérifier que Prometheus voit bien l'API : `http://localhost:9090/targets` → job `waterflow2`
  doit être **UP**.
- Requêtes PromQL de base (dans Prometheus ou dans un panel Grafana) :
  ```
  rate(http_requests_total[5m])                                        # Rate
  rate(http_requests_total{status=~"5.."}[5m])                          # Errors
  histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))  # Duration p95
  ```
- Métriques brutes consultables directement, sans Grafana : `http://localhost:8000/metrics`.

## Testé dans un environnement dédié

La chaîne a été testée dans l'environnement Docker Compose local (pas en production) avant
d'être considérée fonctionnelle : Prometheus confirmé en état `UP` sur sa page `/targets`, et des
courbes non vides constatées dans Grafana pour Rate/Duration après génération de trafic réel via
l'UI Streamlit.

## Accessibilité de l'outil de restitution

Grafana est une interface **visuelle** (graphiques, couleurs) et n'a pas été auditée avec un
lecteur d'écran — c'est une limite assumée pour un outil de supervision technique, destiné à une
équipe technique restreinte plutôt qu'à l'ensemble des parties prenantes du projet. Deux
mitigations existent néanmoins :
- Les métriques brutes restent consultables en texte brut, sans interface graphique, via
  `GET /metrics` et l'API HTTP de Prometheus (`/api/v1/query`) — un accès non-visuel existe donc
  toujours en complément du dashboard.
- Grafana propose nativement des tables de données (pas seulement des graphiques) pour la plupart
  des panels, une alternative plus accessible qu'une courbe pour qui utilise un lecteur d'écran.

## Limite connue

Sans `--backend-store-uri` explicite, le service `mlflow` stocke son registre dans un fichier
SQLite (`mlflow.db`) et ses artefacts dans le répertoire de travail du conteneur plutôt que dans
un dossier `mlruns/` classique — d'où le montage de tout `/app` (`./mlflow_data:/app`) plutôt que
d'un seul sous-dossier, pour que rien ne soit perdu au redémarrage du conteneur.
