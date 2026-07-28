# Synthèse de veille — Services d'extraction documentaire (OCR) et cadre réglementaire

Preuve documentaire pour **C6** (Bloc de compétences 2, E2). Rédigée en Markdown texte brut,
cohérent avec le choix d'accessibilité déjà appliqué au reste de la documentation du projet
(voir `docs/ACCESSIBILITE_DOCUMENTATION.md`) : hiérarchie de titres réelle, pas d'information
portée uniquement par une couleur ou une image.

## Thématique de veille

Deux axes liés au besoin projet (extraire automatiquement les 9 mesures d'une fiche labo
photographiée/scannée) :

- **Axe technique** : solutions d'OCR / extraction documentaire, évolution des moteurs,
  reconnaissance de structure tabulaire, modèles de tarification.
- **Axe réglementaire** : RGPD (la fiche labo peut porter des mentions identifiantes indirectes)
  et positionnement au regard de l'AI Act (règlement UE 2024/1689).

C'est l'intersection des deux — un service technique traitant un document potentiellement
personnel — qui définit la zone de risque à surveiller.

## Organisation du temps de veille

| Activité | Fréquence |
|---|---|
| Lecture / tri des flux | Continue, 10-15 min/jour |
| Créneau actif dédié | 1h/semaine (respecte la récurrence minimale d'1h hebdomadaire) |
| Rédaction de synthèse | Bimensuelle, 30 min |

## Sources suivies et critères de fiabilité

| Source | Nature |
|---|---|
| Blogs éditeurs cloud (Google, AWS, Azure AI) | Offre commerciale — flux RSS |
| Hugging Face Blog | Recherche / communauté — flux RSS |
| The Batch (DeepLearning.AI) | Newsletter indépendante |
| CNIL | Autorité de régulation — flux RSS |
| EUR-Lex | Texte réglementaire officiel (AI Act) |

Ces 5 sources couvrent offre commerciale, recherche et autorité réglementaire — pas d'angle
mort sur un seul point de vue.

### Application des 6 critères de fiabilité par source

| Source | Auteur identifié | Compétence / notoriété / absence d'intérêt personnel | Contenu valable (date, sources citées, langue) | Structurée | Normes d'accessibilité | Recoupée par une autre source |
|---|---|---|---|---|---|---|
| Blogs éditeurs cloud (Google, AWS, Azure) | Équipe produit signée (nom/rôle) sur chaque article | Notoriété du groupe confirmée ; intérêt commercial explicite (éditeur du produit décrit) — biais identifié et assumé, pas dissimulé | Articles datés, changelogs produit sourcés, langue soignée | Blog structuré par catégories et dates | Accessibilité standard des plateformes, non spécifiquement documentée — limite notée | Recoupée par Hugging Face Blog / The Batch sur les annonces techniques |
| Hugging Face Blog | Auteurs identifiés (chercheurs, ingénieurs de la communauté) | Notoriété reconnue dans la communauté ML/NLP, publication non commerciale | Articles datés, liens vers papiers/dépôts sources | Structuré par tags et dates | Site conforme aux standards web courants | Recoupée par les blogs éditeurs (annonces convergentes) |
| The Batch (DeepLearning.AI) | Newsletter signée (équipe éditoriale Andrew Ng) | Notoriété académique/industrielle établie, indépendante des éditeurs cloud | Publication hebdomadaire datée, sources citées | Format newsletter structuré (rubriques fixes) | Format texte/e-mail, accessible nativement | Recoupée par Hugging Face Blog sur les tendances techniques |
| CNIL | Autorité administrative française identifiée (institution, pas un auteur individuel) | Mission légale de régulation, aucun intérêt commercial | Articles datés, textes réglementaires cités en référence | Site institutionnel à rubriques claires | Site public soumis au RGAA | Recoupée par EUR-Lex sur les questions réglementaires |
| EUR-Lex | Institution européenne (Office des publications de l'UE) | Source primaire officielle du texte réglementaire | Texte de référence daté, version consolidée disponible | Structuré par articles/considérants numérotés | Site institutionnel multilingue | Recoupée par CNIL (interprétation française du texte) |

**Point de méthode** : le biais commercial d'un blog éditeur (AWS, Google) n'est pas
éliminatoire — c'est une source de première main sur leurs propres produits. La bonne pratique
est de l'identifier explicitement (colonne 2 du tableau) et de recouper chaque affirmation
commerciale avec une source indépendante (Hugging Face, The Batch) avant de la retenir.

## Synthèse — axe technique

- La plupart des services d'OCR cloud proposent un palier gratuit suffisant pour un usage
  ponctuel de quelques dizaines de documents par jour.
- Tendance de fond : passage de l'OCR « brut » (texte non structuré) vers l'extraction
  structurée (paires clé/valeur, tableaux) — directement pertinent pour une fiche labo tabulaire.
- Montée des options d'hébergement en Union Européenne chez plusieurs fournisseurs.

## Synthèse — axe réglementaire

**RGPD** : base légale envisageable = exécution du contrat (fournir le service de prédiction
au Client) ; principe de minimisation (ne conserver que les valeurs extraites, pas l'image
source) ; obligation d'information des personnes concernées.

**AI Act** : le règlement définit 4 niveaux de risque (inacceptable / haut / limité / minimal).
Un service qui se limite à extraire des valeurs numériques d'un document, sans évaluer ni noter
une personne, relève du risque **minimal** — hors annexe III (systèmes à haut risque). À
réexaminer si l'usage du service évoluait vers une décision automatisée sur une personne.

## Diffusion

Synthèse communiquée aux rôles **Quality_Analyst** et **Admin**, parties prenantes du périmètre
fonctionnel concerné par ce service.

## Limite assumée

Cette veille couvre le champ d'application initial du projet (extraction de mesures
physico-chimiques). Elle devra être réévaluée si le périmètre de documents traités s'élargit
(ex. documents à caractère plus personnel).
