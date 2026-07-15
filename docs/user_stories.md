# Spécifications fonctionnelles - User Stories (Waterflow 2)

Rédigées à partir du comportement réel de l'API (`api/main.py`, `api/ocr_router.py`,
`api/auth.py`) et de l'UI (`ui.py`, `views/*.py`, `dashboard_qualite.py`) — voir
[parcours_utilisateurs.md](parcours_utilisateurs.md) pour les schémas de navigation
correspondants. Quand un critère de validation est déjà couvert par un test automatisé, le
test est cité pour assurer la traçabilité spec ↔ code.

Format : **En tant que** rôle, **je veux** action, **afin de** bénéfice.

Chaque story intègre des critères d'accessibilité formulés selon le référentiel **WCAG 2.1**
(niveau AA visé). Ce sont des **objectifs cibles** pour l'implémentation UI, pas un audit :
aucun contrôle outillé (contraste réel, lecteur d'écran, navigation clavier de bout en bout) n'a
été mené sur l'application Streamlit actuelle.

---

## Rôle : Client

### US-01 — Connexion par clé API

**En tant que** Client, **je veux** m'authentifier avec ma clé API, **afin de** accéder à mon
espace personnel sans créer de mot de passe.

**Contexte** : l'authentification est stateless, basée sur le header `X-API-Key` (SHA-256
haché puis comparé en base). Il n'y a pas d'inscription libre : la clé est fournie par un Admin.
L'authentification repose sur des clés API statiques, sans expiration ; il n'y a donc pas de
mécanisme de renouvellement de jeton (pas de JWT/OAuth2 ni de refresh token) — la révocation ou
la rotation d'une clé est un acte administratif explicite (`POST /api/clients/{cid}/rotate-key`),
jamais un renouvellement automatique déclenché côté client.

**Scénario d'utilisation**
1. L'utilisateur ouvre l'application Streamlit ; seule la page de connexion est visible
   (`st.session_state.logged_in = False`).
2. Il saisit sa clé API dans le champ mot de passe et clique sur "Se connecter".
3. Le frontend envoie `POST /api/login` avec le header `X-API-Key`.
4. En cas de succès, son rôle (`Client`) est stocké en session et la navigation bascule vers
   "Panel de Test" + "Historique des Analyses".

**Critères de validation**
- Une clé valide et active renvoie `200` avec `authenticated: true`, `user_id`, `username`, `role`.
- Une clé absente renvoie `401` ("Clé API manquante").
- Une clé invalide ou inconnue renvoie `401` ("Clé API invalide ou expirée").
- Une clé révoquée (`is_active = 0`) renvoie `403`.
- Couvert par `tests/test_pipeline.py::test_login_valid_key` et `test_login_invalid_key`.
- **Accessibilité (WCAG 2.1.1 Clavier)** : le champ de saisie de la clé et le bouton "Se
  connecter" doivent être atteignables et activables au clavier seul (Tab puis Entrée),
  sans piège de focus.
- **Accessibilité (WCAG 3.3.1 Identification des erreurs)** : le message "Clé API incorrecte"
  doit être restitué aux technologies d'assistance (pas seulement affiché en rouge), par
  exemple via une région `aria-live`.

---

### US-02 — Soumettre un prélèvement manuel et obtenir une prédiction

**En tant que** Client, **je veux** saisir les 9 mesures physico-chimiques d'un prélèvement,
**afin de** savoir immédiatement si l'eau est potable.

**Contexte** : la prédiction utilise le modèle XGBoost `Production` chargé depuis MLflow, avec
un seuil de décision fixe (`0.37`, pas le seuil par défaut de 0.5) appliqué à `predict_proba`.

**Scénario d'utilisation**
1. Sur "Panel de Test", le Client saisit ph, hardness, solids, chloramines, sulfate,
   conductivity, organic_carbon, trihalomethanes, turbidity (ou charge un échantillon du jeu
   de test).
2. Il clique sur "Lancer la prédiction API" → `POST /api/measurements`.
3. L'API calcule `probabilité potable = predict_proba(features)`, compare à 0.37, enregistre
   le prélèvement (`source = "manuel"`) et renvoie le verdict.
4. Le résultat ("Potable (Safe)" / "Non Potable (Unsafe)") et la probabilité s'affichent.

**Critères de validation**
- Requête avec 9 features valides + clé API valide → `201`, réponse contient `prediction`
  (0 ou 1), `probability_potable`, `water_status`, `client_id`.
- `probability_potable >= 0.37` ⟹ `prediction = 1` ; sinon `prediction = 0`.
- Sans header `X-API-Key` → `401`.
- Payload avec un nombre de features ≠ 9 → `422` (validation Pydantic).
- Si le modèle MLflow n'a pas pu être chargé au démarrage → `503` ("Modèle ML indisponible").
- Le prélèvement est bien rattaché à `current_user.id`, jamais à un ID fourni par le client.
- Couvert par `test_measurements_predict_potable`, `test_measurements_predict_non_potable`,
  `test_measurements_bad_request`, `test_measurements_requires_api_key`.
- **Accessibilité (WCAG 3.3.2 Étiquettes ou instructions)** : chacun des 9 champs numériques a
  un label explicite (nom + unité), pas seulement un placeholder qui disparaît à la saisie.
- **Accessibilité (WCAG 1.4.1 Utilisation de la couleur)** : le verdict "Potable" / "Non
  Potable" reste toujours accompagné du texte correspondant, jamais signalé par la seule
  couleur verte/rouge du message.
- **Accessibilité (WCAG 2.1.1 Clavier)** : la saisie des 9 valeurs et le déclenchement de
  "Lancer la prédiction API" sont réalisables sans souris.

---

### US-03 — Importer une fiche labo par OCR

**En tant que** Client, **je veux** importer une photo ou un PDF de fiche labo, **afin de**
ne pas ressaisir manuellement les 9 mesures.

**Contexte** : l'image/PDF est envoyée à OCR.space, le texte retourné est parsé par regex pour
extraire les 9 features (+ quelques champs informatifs comme les nitrates). Le `client_id` de
la prédiction vient **toujours** de la clé API authentifiée, jamais du fichier ni du formulaire
(choix RGPD délibéré pour empêcher qu'un client attribue un prélèvement à un tiers).

**Scénario d'utilisation**
1. Le Client dépose une image/PDF dans le champ d'upload et clique sur "Analyser via l'OCR".
2. `POST /api/ocr/lab-report` (multipart) est appelé avec le fichier + `X-API-Key`.
3. Si les 9 champs sont extraits avec succès, la prédiction est calculée et enregistrée
   (`source = "ocr"`), les champs du formulaire sont pré-remplis avec les valeurs lues.
4. Si certains champs sont introuvables, un avertissement liste les champs manquants à
   compléter manuellement ; aucune prédiction n'est calculée dans ce cas.

**Critères de validation**
- Extension non supportée (hors png/jpg/jpeg/gif/pdf/bmp/tiff) → `415`.
- Fichier > 10 Mo → `413`.
- Extraction complète (9/9 champs) → `200`, `status: "success"`, `prediction` renseigné,
  `missing_features: []`.
- Extraction partielle → `202`, `status: "partial_match"`, `prediction: null`,
  `missing_features` liste les clés absentes.
- OCR.space injoignable / timeout / erreur HTTP → `502` / `504` avec un `incident` explicite.
- Sans clé API → `401`.
- Couvert par `test_ocr_lab_report_requires_api_key`,
  `test_ocr_lab_report_rejects_unsupported_extension`, `test_ocr_lab_report_success`.
- **Accessibilité (WCAG 1.1.1 Contenu non textuel)** : le contrôle de dépôt de fichier a un
  intitulé texte explicite ("Importer une fiche laboratoire"), pas seulement une icône.
- **Accessibilité (WCAG 3.3.1 Identification des erreurs)** : les erreurs OCR (extension
  refusée, timeout, service injoignable) sont annoncées en texte clair et associées au champ
  concerné, pas uniquement par une couleur ou une icône d'alerte.
- **Accessibilité (WCAG 4.1.3 Messages de statut)** : le message de succès/avertissement après
  analyse ("Fiche analysée avec succès", champs manquants) doit pouvoir être perçu par un
  lecteur d'écran sans déplacer le focus depuis le formulaire.

---

### US-04 — Consulter l'historique de ses prélèvements

**En tant que** Client, **je veux** voir la liste de tous mes prélèvements passés,
**afin de** suivre l'évolution de la qualité de l'eau dans le temps.

**Contexte** : chaque Client ne voit que ses propres prélèvements (filtrés par `user_id`,
jamais ceux des autres clients).

**Scénario d'utilisation**
1. Le Client ouvre la page "Historique des Analyses".
2. `GET /api/measurements` est appelé avec sa clé API.
3. Un tableau s'affiche (mesures + potabilité, coloré vert/rouge), avec un bouton d'export CSV.

**Critères de validation**
- Sans clé API → `401`.
- Avec clé valide → `200`, `total_records` = nombre de prélèvements de **cet** utilisateur
  uniquement, `history` liste les mesures + `potability_result` pour chacun.
- Historique vide → l'UI affiche un message informatif plutôt qu'un tableau vide.
- Couvert par `test_get_measurements_requires_api_key`, `test_get_measurements_history`.
- **Accessibilité (WCAG 1.3.1 Information et relations)** : le tableau des prélèvements
  utilise de véritables en-têtes de colonnes associés à leurs cellules (pas une image ou une
  mise en forme purement visuelle), lisible par un lecteur d'écran.
- **Accessibilité (WCAG 1.4.1 Utilisation de la couleur)** : la colonne "Potabilité" combine
  toujours couleur ET texte ("Potable (Safe)" / "Non Potable (Unsafe)").
- **Accessibilité (WCAG 2.1.1 Clavier)** : le bouton "Rafraîchir l'historique" et le lien
  d'export CSV sont activables au clavier.

---

### US-05 — Consulter et supprimer mes données personnelles (RGPD)

**En tant que** Client, **je veux** consulter mes données stockées et pouvoir supprimer mon
compte, **afin de** exercer mon droit d'accès et mon droit à l'oubli RGPD.

**Contexte** : la suppression est une anonymisation partielle : les `audit_logs` sont conservés
mais `user_id` y devient `NULL` (traçabilité de sécurité conservée), alors que les
`prediction` de l'utilisateur sont réellement supprimées.

**Scénario d'utilisation**
1. Sur "Mes Données (RGPD)" (`views/mes_donnees.py`), le Client voit ses informations
   d'identification et la règle de conservation, chargées via `GET /api/me`.
2. Il coche la case de confirmation explicite, puis clique sur "Supprimer mon compte"
   (bouton désactivé tant que la case n'est pas cochée) → `DELETE /api/me`.
3. Sa clé API ne fonctionne plus pour aucune requête ultérieure ; il est redirigé vers l'écran
   de connexion.

**Critères de validation**
- `GET /api/me` sans clé → `401` ; avec clé valide → `200` + `donnees_personnelles.id_client`.
- `DELETE /api/me` → `200` + message de confirmation.
- Après suppression, toute requête avec l'ancienne clé (ex. `POST /api/login`) → `401`.
- Les lignes `audit_logs` préexistantes de cet utilisateur restent présentes mais avec
  `user_id = NULL`, jamais supprimées.
- Couvert côté API par `test_rgpd_me_get`, `test_rgpd_me_delete` ; côté UI par
  `test_ui_mes_donnees_shows_real_data`, `test_ui_mes_donnees_delete_requires_confirmation`,
  `test_ui_mes_donnees_delete_with_confirmation` (`tests/test_ui_integration.py`).
- **Accessibilité (WCAG 3.3.4 Prévention des erreurs - données)** : la suppression du compte
  étant irréversible, l'interface doit exiger une confirmation explicite avant d'appeler
  `DELETE /api/me` (pas un simple clic isolé sur un bouton).
- **Accessibilité (WCAG 2.4.6 En-têtes et étiquettes)** : le bouton de suppression est libellé
  en texte clair ("Supprimer mon compte"), jamais une icône seule (ex. corbeille).

---

## Rôle : Quality_Analyst

### US-06 — Consulter tous les prélèvements avec filtres

**En tant que** Quality_Analyst, **je veux** voir les prélèvements de tous les clients avec
des filtres (client, provenance, période), **afin de** analyser la qualité de l'eau à l'échelle
du réseau et non client par client.

**Scénario d'utilisation**
1. Sur "Dashboard Qualité" → onglet "Prélèvements", il choisit des filtres (`client_id`,
   `source: manuel|ocr`, `date_from`, `date_to`).
2. `GET /api/dashboard/measurements` renvoie les prélèvements correspondants, jointure avec
   `users` incluse (nom du client, rôle).

**Critères de validation**
- Rôle `Client` sur cette route → `403`.
- Rôles `Quality_Analyst` et `Admin` → `200`, chaque ligne inclut `client.id`,
  `client.username`, `client.role`, les mesures, `potability_result`, `source`, `created_at`.
- Sans filtre → tous les prélèvements sont renvoyés, triés du plus récent au plus ancien.
- Couvert par `test_dashboard_measurements_forbidden_for_client`,
  `test_dashboard_measurements_as_analyst`.
- **Accessibilité (WCAG 2.4.6 En-têtes et étiquettes)** : chaque filtre (client, provenance,
  dates) a un label explicite et visible en permanence, pas seulement un texte d'exemple.
- **Accessibilité (WCAG 1.4.10 Redimensionnement / Reflow)** : le tableau de résultats, large
  (9 mesures + métadonnées), reste consultable à un zoom de 400% sans perte d'information ni
  défilement bidirectionnel obligatoire.

---

### US-07 — Consulter les métriques du modèle en Production

**En tant que** Quality_Analyst, **je veux** voir les métriques (F1, accuracy, etc.) et
paramètres du modèle actuellement en Production, **afin de** vérifier sa fiabilité avant de
faire confiance à ses prédictions.

**Scénario d'utilisation**
1. Onglet "Métriques du modèle" → `GET /api/dashboard/metrics`.
2. Les métriques loggées dans MLflow pour la version `Production` s'affichent (une carte par
   métrique), ainsi que les hyperparamètres dans un menu déroulant.

**Critères de validation**
- Rôle `Client` → `403`.
- Aucune version `Production` trouvée sur MLflow → `404`.
- Version trouvée → `200` avec `version`, `run_id`, `stage`, `metrics`, `params`.
- Couvert par `test_dashboard_metrics`.
- **Accessibilité (WCAG 1.3.1 Information et relations)** : chaque carte de métrique expose son
  libellé et sa valeur comme une paire associée pour un lecteur d'écran, pas juste deux blocs de
  texte juxtaposés visuellement.
- **Accessibilité (WCAG 1.4.3 Contraste minimum)** : le texte des métriques et des paramètres
  respecte un ratio de contraste ≥ 4.5:1 sur son fond.

---

### US-08 — Comparer les versions du modèle et rejouer une prédiction

**En tant que** Quality_Analyst, **je veux** lister toutes les versions du modèle et rejouer
une prédiction avec une version précise, **afin de** comparer le comportement de plusieurs
versions sur le même prélèvement (audit / debug de dérive du modèle).

**Scénario d'utilisation**
1. Onglet "Comparaison des versions" → `GET /api/dashboard/model-versions` liste toutes les
   versions enregistrées (pas seulement `Production`) avec leurs métriques.
2. L'analyste choisit un `run_id` et saisit 9 mesures.
3. `POST /api/dashboard/replay` charge le modèle de **cette** version précise (`runs:/<run_id>/model`)
   et renvoie sa prédiction — indépendamment du seuil ou du modèle actuellement en Production.

**Critères de validation**
- Rôle `Client` → `403` sur les deux routes.
- `GET /api/dashboard/model-versions` → `200`, `versions` triées version décroissante.
- `POST /api/dashboard/replay` avec un `run_id` existant + 9 features → `200`,
  `prediction`, `probability_potable`, `water_status` calculés avec le modèle de cette version
  et le seuil de décision courant (`app.state.best_threshold`).
- Couvert par `test_dashboard_model_versions`, `test_dashboard_replay`.
- **Accessibilité (WCAG 2.4.3 Ordre de focus)** : l'ordre de tabulation entre le sélecteur de
  version, les 9 champs de mesure et le bouton "Rejouer la prédiction" suit l'ordre visuel
  logique de gauche à droite, haut en bas.
- **Accessibilité (WCAG 2.1.1 Clavier)** : la sélection d'une version dans la liste déroulante
  et le déclenchement du rejeu sont réalisables sans souris.

---

## Rôle : Admin

### US-09 — Créer un nouveau compte (Client ou Quality_Analyst)

**En tant que** Admin, **je veux** créer un compte pour un nouveau laboratoire ou analyste,
**afin de** lui donner accès à la plateforme sans qu'il puisse s'auto-inscrire.

**Contexte** : la clé API générée (`secrets.token_hex(32)`) n'est **jamais** stockée en clair —
seul son hash SHA-256 est persisté. Elle n'est visible qu'une seule fois, au moment de la
création.

**Scénario d'utilisation**
1. Sur "Sécurité & Gestion des Accès", l'Admin remplit le formulaire (nom, rôle
   `Client`/`Quality_Analyst`/`Admin`) et valide.
2. `POST /api/clients` crée l'utilisateur et renvoie `api_key_plain`.
3. L'UI affiche la clé dans un encart persistant jusqu'à ce que l'Admin clique sur "Effacer
   l'affichage" — le temps de la copier en lieu sûr.

**Critères de validation**
- Rôle `Client` ou `Quality_Analyst` appelant cette route → `403`.
- Rôle `Admin` + payload valide → `201`, réponse contient `client.id`, `client.username`,
  `client.role`, `client.api_key_plain`.
- La clé en clair n'apparaît dans aucune autre réponse API ni log après cet appel.
- Couvert par `test_create_client_forbidden_for_non_admin`, `test_create_client_as_admin`.
- **Accessibilité (WCAG 2.2.1 Réglage du délai)** : la clé API affichée reste visible jusqu'à
  une action explicite de l'Admin ("Effacer l'affichage"), jamais masquée automatiquement après
  un délai fixe.
- **Accessibilité (WCAG 4.1.2 Nom, rôle et valeur)** : le champ affichant la clé en lecture
  seule expose son état (lecture seule, information sensible) aux technologies d'assistance,
  pas seulement par une mise en forme visuelle (gras/encadré).
- **Accessibilité (WCAG 3.3.2 Étiquettes ou instructions)** : le formulaire de création (nom,
  rôle) a des labels explicites et permanents, pas de simple texte d'exemple.

---

### US-10 — Régénérer (rotation) la clé API d'un compte

**En tant que** Admin, **je veux** révoquer l'ancienne clé d'un compte et lui en attribuer une
nouvelle, **afin de** réagir à une fuite de clé suspectée sans supprimer le compte.

**Scénario d'utilisation**
1. Sur "Sécurité & Gestion des Accès", l'Admin choisit un compte dans la liste déroulante
   (alimentée par `GET /api/clients`) et clique sur "Régénérer la clé".
2. `POST /api/clients/{cid}/rotate-key` remplace le hash de clé en base et renvoie la nouvelle
   clé en clair, affichée une seule fois.
3. L'ancienne clé cesse immédiatement de fonctionner sur toute route protégée.

**Critères de validation**
- Rôle non-Admin → `403`.
- `cid` inexistant → `404` ("Client introuvable").
- `cid` valide → `200`, `client_id`, `api_key_plain` (nouvelle clé).
- Après rotation : l'ancienne clé → `401` sur `POST /api/login` (ou toute route protégée) ;
  la nouvelle clé → `200`.
- Couvert par `test_rotate_key_forbidden_for_non_admin`, `test_rotate_key_nonexistent_client`,
  `test_rotate_key_admin`.
- **Accessibilité (WCAG 3.3.4 Prévention des erreurs - données)** : la rotation étant
  irréversible (l'ancienne clé cesse aussitôt de fonctionner), l'UI doit demander une
  confirmation explicite avant d'appeler `POST /api/clients/{cid}/rotate-key`.
- **Accessibilité (WCAG 2.2.1 Réglage du délai)** : comme pour la création de compte, la
  nouvelle clé reste affichée jusqu'à l'action "Masquer la clé", sans disparition automatique.

---

### US-11 — Consulter le registre des comptes et le journal d'audit

**En tant que** Admin, **je veux** voir la liste de tous les comptes et l'historique complet
des appels API, **afin de** surveiller les accès et détecter une activité anormale.

**Scénario d'utilisation**
1. Sur "Registre des comptes", `GET /api/clients` liste tous les utilisateurs (id, username,
   rôle, hash de clé — jamais la clé en clair).
2. `GET /api/audit-logs` liste chaque appel API tracé par le middleware `access_log`
   (endpoint, méthode, statut HTTP, durée, IP, utilisateur résolu ou `NULL` si anonymisé/inconnu).

**Critères de validation**
- Rôle non-Admin sur l'une ou l'autre route → `403`.
- `GET /api/clients` → `200`, jamais de champ `api_key_plain` dans la liste.
- `GET /api/audit-logs` → `200`, triés du plus récent au plus ancien (`ORDER BY id DESC`),
  chaque entrée authentifiée génère bien une ligne (vérifiable en rejouant un appel juste avant).
- Les routes `/health` et `/api/ocr/health` ne génèrent **pas** d'entrée d'audit (bruit de
  monitoring exclu volontairement).
- Couvert par `test_admin_can_list_clients`, `test_audit_logs_forbidden_for_non_admin`,
  `test_audit_logs_admin`.
- **Accessibilité (WCAG 1.3.1 Information et relations)** : les deux tableaux (comptes, logs)
  exposent des en-têtes de colonnes correctement associés à leurs cellules pour un lecteur
  d'écran.
- **Accessibilité (WCAG 1.4.10 Redimensionnement / Reflow)** : le journal d'audit, riche en
  colonnes, reste consultable à 400% de zoom sans double défilement (horizontal et vertical
  simultané).

---

## Transverse

### US-12 — Contrôle d'accès basé sur les rôles

**En tant que** plateforme, **je veux** qu'une route réservée à un rôle refuse tout appel d'un
rôle non autorisé, **afin de** garantir l'étanchéité entre espaces Client / Analyste / Admin.

**Contexte** : implémenté une seule fois via la dépendance FastAPI `require_role(*roles)`
(`api/auth.py`), réutilisée par toutes les routes sensibles — pas de vérification de rôle
dupliquée dans chaque endpoint.

**Critères de validation**
- Toute route `Admin`-only appelée par `Client` ou `Quality_Analyst` → `403`
  ("Accès refusé. Rôles autorisés : ...").
- Toute route `Quality_Analyst`/`Admin`-only appelée par `Client` → `403`.
- Une clé API absente → `401` avant même l'évaluation du rôle.
- Une clé révoquée (`is_active = 0`) → `403` ("Cette clé API a été révoquée."), y compris pour
  un rôle qui aurait normalement les droits.
- **Accessibilité (WCAG 4.1.3 Messages de statut)** : tout message d'erreur/succès affiché côté
  UI (`st.error`, `st.success`, `st.toast`, quel que soit le rôle) doit pouvoir être annoncé par
  un lecteur d'écran sans déplacer le focus de l'utilisateur — critère transverse à toutes les
  stories ci-dessus.
- **Accessibilité (WCAG 1.4.3 Contraste minimum)** : le thème visuel de l'application (texte,
  boutons, badges de statut) respecte un ratio de contraste ≥ 4.5:1 pour le texte normal et
  ≥ 3:1 pour les éléments d'interface, sur l'ensemble des trois espaces (Client, Analyste, Admin).