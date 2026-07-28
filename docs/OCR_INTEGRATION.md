# Intégration du service OCR — Waterflow 2

Preuve documentaire pour **C8** (paramétrage d'un service d'IA préexistant, Bloc 2, E2).
Complète `docs/veille/SYNTHESE_OCR_IA.md` (C6) et le benchmark de sélection (C7, voir
`docs/rapports/Rapport_bloc_E2_Ilyes_Chabab.md`).

## Service retenu

[OCR.space](https://ocr.space) — choisi pour sa gratuité pérenne (25 000 requêtes/mois), son
intégration en une seule requête HTTP multipart (pas de SDK ni de compte cloud à provisionner),
et son support natif de la détection tabulaire (`isTable`), pertinent pour une fiche labo
structurée en lignes/colonnes.

## Gestion des accès

Un compte est créé sur [ocr.space/ocrapi](https://ocr.space/ocrapi) avec une simple adresse
e-mail (aucune carte bancaire requise), qui génère une clé API gratuite.

**Rotation / configuration** : la clé n'est jamais codée en dur ni versionnée. Elle est fournie
via un fichier `.env` local (gitignoré, voir `.env.example` à la racine du dépôt) :
```
OCR_SPACE_API_KEY=<cle-dediee>
```
`docker-compose.yml` l'injecte dans le conteneur `api` :
```yaml
environment:
  OCR_SPACE_API_KEY: ${OCR_SPACE_API_KEY:-helloworld}
```
En l'absence de fichier `.env`, l'application retombe sur `"helloworld"`, la clé de démonstration
publique d'OCR.space (limitée à 1 page, 1 Mo par fichier) — suffisant pour développer et tester
localement sans dépendre d'un compte dédié, mais insuffisant en usage réel. Le endpoint
`GET /api/ocr/health` (`api/ocr_router.py`) expose explicitement cet état :
```python
key_ok = OCR_SPACE_API_KEY not in ("", "helloworld")
"warning": None if key_ok else "Clé de démo active — limites : 1 page, 1 Mo, 25 000 req/mois."
```

## Installation et test en local

1. `cp .env.example .env` puis renseigner `OCR_SPACE_API_KEY`.
2. `docker compose up --build api` (ou la stack complète).
3. Vérifier la configuration : `curl http://localhost:8000/api/ocr/health`.
4. Tester une extraction : upload d'une fiche labo (image ou PDF) sur
   `POST /api/ocr/lab-report`, avec le header `X-API-Key` d'un compte Client valide.

## Configuration du service

Chaque paramètre du payload envoyé à OCR.space répond à une contrainte de cadrage du projet
(`api/ocr_router.py`, fonction `_call_ocr_space`) :

| Paramètre | Valeur | Raison |
|---|---|---|
| Endpoint | `api.ocr.space/parse/image` | Point d'entrée REST unique, pas de SDK |
| `OCREngine` | `2` | Meilleure gestion des tableaux et du français |
| `language` | `fre` | Fiches rédigées en français |
| `isTable` | `true` | Structure ligne/colonne de la fiche labo |
| `scale` | `true` | Compense les photos basse résolution prises au téléphone |
| `detectOrientation` | `true` | Photos terrain prises en portrait ou paysage |
| Timeout | `8s` | Contrainte de latence du cadrage (quelques secondes), avec marge |

## Interconnexions

- **Dépendance externe** : `requests` (déjà dans `requirements.txt`), appel HTTP synchrone vers
  `api.ocr.space`.
- **Interne** : le texte brut renvoyé par OCR.space passe dans `_parse_lab_report()` (regex sur
  les libellés — « pH », « Dureté »…) pour reconstituer les 9 champs attendus par le modèle. Ces
  valeurs pré-remplissent le panel de saisie (`views/panel_test.py`) ; **le Client valide
  manuellement avant tout appel à `POST /api/measurements`** — aucune prédiction n'est enregistrée
  sans relecture humaine.

## Données impliquées

L'image/le PDF uploadé est traité **en mémoire uniquement** (`await file.read()`), jamais écrit
sur disque côté API. Seuls le texte extrait puis les 9 valeurs validées par le Client sont
persistés en base ; l'image source n'est jamais conservée. Traduction concrète du principe de
minimisation RGPD identifié lors de la veille (C6).

## Monitorage opérationnel

Métrique Prometheus `ocr_failures_total{reason=...}`, labellisée par cause d'échec (`timeout`,
`connection_error`, `http_error`, `processing_error`) — voir `docs/MONITORING.md`. Labelliser par
`reason` permet de distinguer une panne du prestataire (attendre le rétablissement) d'un problème
du document fourni par l'utilisateur (demander une meilleure photo), deux actions différentes.

Conforme à la recommandation OWASP API10 (*Unsafe Consumption of APIs*) : chaque cas d'erreur de
l'appel externe est intercepté explicitement (`Timeout`, `ConnectionError`, `HTTPError`,
`ValueError`), aucune confiance aveugle dans la réponse du service tiers.

## Accessibilité de cette documentation

Rédigée en Markdown texte brut — mêmes standards que le reste de la documentation du projet
(voir `docs/ACCESSIBILITE_DOCUMENTATION.md`).
