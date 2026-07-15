# CI/CD — Waterflow 2

Ce document couvre la chaîne d'intégration et de livraison continues du projet
(`.github/workflows/ci.yml`), pour le modèle IA (entraînement/validation) comme pour
l'application (tests, packaging). Il sert de preuve pour C13, C18 et C19 : les trois
compétences portent sur la même chaîne, vue sous des angles différents (modèle / application /
livraison).

## Outil retenu

**GitHub Actions**, choisi car le dépôt est déjà hébergé sur GitHub (`github.com/Sonicario49/waterflow2`)
— pas de compte ou d'infrastructure CI supplémentaire à gérer, intégration native aux pull
requests, et gratuit pour un dépôt de cette taille.

## Déclencheurs

Définis dans `ci.yml` :
```yaml
on:
  push:
  pull_request:
```
La chaîne se déclenche sur **tout push** (toute branche) et **toute pull request**. En pratique
sur ce projet : chaque branche de fonctionnalité déclenche un run à son push, avant la revue et
la fusion dans `main`.

## Étapes de la chaîne

| # | Étape | Ce qu'elle fait | Concerne |
|---|---|---|---|
| 1 | `Checkout` | Récupère le code du commit déclencheur | C18 |
| 2 | `Set up Python` | Installe Python 3.10, active le cache pip (`requirements.txt`) | C18 |
| 3 | `Install dependencies` | `pip install -r requirements.txt` | C18 |
| 4 | `Validate raw data` | `python scripts/validate_data.py` — vérifie le schéma et l'absence de dérive sur `data/raw/water_potability.csv` | C13 |
| 5 | `Run tests` | `python -m pytest` — 47 tests (API + intégration UI) | C18 |
| 6 | `Train & validate model` | `python scripts/validate_model.py` — réentraîne (SMOTE + XGBoost) et vérifie le F1-score contre un seuil minimal (gate qualité) | C13 |
| 7 | `Build API Docker image` | `docker build -t waterflow2-api:<sha> .` — packaging de l'API seule | C19 |
| 8 | `Build full docker-compose stack` | `docker compose build` — packaging des 3 images (mlflow, api, streamlit) | C19 |

Chaque étape est bloquante : si l'une échoue, les suivantes ne s'exécutent pas (comportement par
défaut de GitHub Actions), et le commit est marqué en échec sur GitHub.

## Ce qui n'est pas automatisé (volontairement laissé ouvert)

L'étape de **livraison** proprement dite (publication de l'image sur un registre, déploiement)
n'est pas intégrée à la chaîne : la mise en production reste une pull request revue et mergée
manuellement (7+ PR mergées ainsi sur ce projet, voir l'historique GitHub). Ce n'est donc pas une
étape automatisée de `ci.yml`, juste une pratique d'équipe.

## Installation / reproduction en local

1. Cloner le dépôt et se placer à sa racine.
2. `pip install -r requirements.txt`
3. Lancer individuellement les étapes de la chaîne, dans l'ordre :
   ```bash
   python scripts/validate_data.py
   python -m pytest
   python scripts/validate_model.py
   docker build -t waterflow2-api:local .
   docker compose build
   ```

## Configuration

- Fichier unique : `.github/workflows/ci.yml`, versionné avec le reste du code.
- Aucun secret GitHub Actions n'est requis (pas de compte externe, pas de token de déploiement).
- Le cache pip (`cache: "pip"`, `cache-dependency-path: requirements.txt`) accélère les runs
  suivants tant que `requirements.txt` ne change pas.

## Historique d'exécution

Chaque push/PR sur ce projet a déclenché un run visible dans l'onglet **Actions** du dépôt
(`github.com/Sonicario49/waterflow2/actions`). Les runs récents sont verts de bout en bout,
y compris les 2 étapes de build Docker.

## Limite connue

`requirements.txt` ne fixe aucune version de dépendance — un run peut donc installer des versions
plus récentes qu'un run précédent, ce qui a déjà causé un écart de comportement observé entre
environnements (voir `tests/bugTrouvé_README.md`, incident 2). Corrigé au cas par cas, pas encore
par un fichier de lock.
