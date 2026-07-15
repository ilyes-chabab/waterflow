# Parcours utilisateurs - Waterflow 2

Schémas fonctionnels dérivés de la logique de routage dans `ui.py` (`st.navigation` selon
`st.session_state.role`) et des actions déclenchées dans `views/*.py` / `dashboard_qualite.py`.

Pour visualiser : coller un bloc dans [mermaid.live](https://mermaid.live), ou utiliser
l'extension "Markdown Preview Mermaid Support" dans VS Code pour prévisualiser ce fichier
directement.

## 0. Authentification & aiguillage par rôle (commun à tous)

```mermaid
flowchart TD
    A([Écran de connexion]) -->|Saisie de la clé API| B[POST /api/login]
    B -->|401 Clé invalide| A
    B -->|200 OK + role| C{Rôle renvoyé ?}
    C -->|Client| D[Panel de Test + Historique]
    C -->|Quality_Analyst| E[Dashboard Qualité]
    C -->|Admin| F[Registre des comptes + Sécurité]
    D & E & F --> G[Bouton Se déconnecter, sidebar]
    G --> A
```

## 1. Parcours Client (`views/panel_test.py` + `views/historique.py`)

```mermaid
flowchart TD
    Start([Connecté - rôle Client]) --> Panel[Page : Panel de Test]

    Panel --> Choice{Comment renseigner les 9 mesures ?}
    Choice -->|Upload fiche labo image/PDF| OCR[Bouton : Analyser via l'OCR]
    OCR --> OCRcall[POST /api/ocr/lab-report]
    OCRcall -->|200 complet| Fields[Champs remplis]
    OCRcall -->|202/206 partiel| Warn[Avertissement : champs manquants] --> Fields
    OCRcall -->|415/422/502/504| ErrOCR[Message d'erreur affiché]

    Choice -->|Échantillon aléatoire / potable garanti| Sample[Charge une ligne de X_test.csv] --> Fields
    Choice -->|Saisie manuelle| Manual[Remplir les 9 champs numériques] --> Fields

    Fields --> Impute{Des valeurs restent à 0.0 ?}
    Impute -->|Oui - bouton Imputer| ImputeCall[Complète via mean_features.json] --> Fields
    Impute -->|Non| Predict[Bouton : Lancer la prédiction API]

    Predict --> PredictCall[POST /api/measurements]
    PredictCall -->|201| Result[Résultat Potable / Non Potable + probabilité<br/>prélèvement enregistré en base]
    PredictCall -->|401/422/503| ErrPred[Message d'erreur affiché]

    Start --> Hist[Page : Historique des Analyses]
    Hist --> HistCall[GET /api/measurements]
    HistCall --> Table[Tableau des prélèvements + export CSV]
    Result -.->|navigation via sidebar| Hist
```

## 2. Parcours Quality_Analyst (`dashboard_qualite.py`, 3 onglets)

```mermaid
flowchart TD
    Start([Connecté - rôle Quality_Analyst]) --> Dash[Page unique : Dashboard Qualité]

    Dash --> Tab1[Onglet : Prélèvements]
    Tab1 --> Filter[Filtres : client_id, source, date_from, date_to]
    Filter --> Call1[GET /api/dashboard/measurements]
    Call1 --> Table1[Tableau de tous les prélèvements]

    Dash --> Tab2[Onglet : Métriques du modèle]
    Tab2 --> Call2[GET /api/dashboard/metrics]
    Call2 -->|200| Metrics[Version Production : métriques + paramètres]
    Call2 -->|404| NoProd[Avertissement : aucune version Production]

    Dash --> Tab3[Onglet : Comparaison des versions]
    Tab3 --> Call3[GET /api/dashboard/model-versions]
    Call3 --> VersionsTable[Tableau de toutes les versions MLflow]
    VersionsTable --> Select[Choisir un run_id + saisir les 9 mesures]
    Select --> Replay[Bouton : Rejouer la prédiction]
    Replay --> Call4[POST /api/dashboard/replay]
    Call4 --> ReplayResult[Résultat + probabilité pour cette version précise]
```

## 3. Parcours Admin (`views/accueil_admin.py` + `views/securite_admin.py`)

```mermaid
flowchart TD
    Start([Connecté - rôle Admin]) --> Registre[Page : Registre des comptes]

    Registre --> Call1[GET /api/clients] --> Users[Tableau des utilisateurs]
    Registre --> Call2[GET /api/audit-logs] --> Logs[Tableau des logs d'audit]
    Registre --> Refresh[Bouton : Actualiser toute la page] --> Registre

    Start --> Securite[Page : Sécurité & Gestion des Accès]

    Securite --> Create[Formulaire : nom d'utilisateur + rôle]
    Create --> CreateCall[POST /api/clients]
    CreateCall -->|201| FlashKey[Clé API en clair affichée une seule fois]
    FlashKey --> ClearBtn[Bouton : Effacer l'affichage] --> Securite
    CreateCall -->|400/403| ErrCreate[Message d'erreur]

    Securite --> RotateList[GET /api/clients - alimente la liste déroulante]
    RotateList --> SelectTarget[Sélectionner un compte cible]
    SelectTarget --> RotateBtn[Bouton : Régénérer la clé]
    RotateBtn --> RotateCall[POST /api/clients/id/rotate-key]
    RotateCall -->|200| FlashRot[Nouvelle clé en clair affichée une seule fois<br/>l'ancienne clé est révoquée]
    FlashRot --> HideBtn[Bouton : Masquer la clé] --> Securite
    RotateCall -->|404| ErrRot[Compte introuvable]
```