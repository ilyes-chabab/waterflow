# Identification et intégration d'un service d'intelligence artificielle de reconnaissance optique

**Livrable Bloc E2 · Compétences C6 à C8**
De la veille technologique et réglementaire au paramétrage d'un service d'OCR pour automatiser la saisie des fiches de laboratoire

**Projet :** Waterflow 2 — Plateforme MLOps de prédiction de la potabilité de l'eau
**Auteur :** Ilyes Chabab · **Année :** 2025 – 2026 · **Compétences :** C6 · C7 · C8

---

## Table des matières

1. Introduction et contexte du projet
2. **C6** — Organiser et réaliser une veille technique et réglementaire
3. **C7** — Identifier des services d'intelligence artificielle préexistants
4. **C8** — Paramétrer un service d'intelligence artificielle
5. Synthèse et tableau récapitulatif des critères
6. Conclusion et perspectives

---

## 1. Introduction et contexte du projet

### 1.1 Origine du besoin

Waterflow 2 est une plateforme MLOps qui prédit la potabilité de l'eau à partir de neuf mesures physico-chimiques (pH, dureté, solides dissous, chloramines, sulfates, conductivité, carbone organique, trihalométhanes, turbidité). Ces mesures sont produites par des laboratoires d'analyse accrédités et restituées aux préleveurs de terrain (rôle **Client** de l'application) sous la forme d'une **fiche labo** imprimée ou scannée.

Jusqu'ici, un Client devait retranscrire manuellement les neuf valeurs de la fiche labo dans le panel de saisie de l'application avant d'obtenir une prédiction. Cette retranscription, réalisée sur le terrain, s'est révélée source d'erreurs récurrentes (inversion de chiffres, oubli d'une valeur, confusion d'unité) remontées par les utilisateurs pilotes lors des premiers usages de Waterflow 1. L'équipe Qualité, en tant que collaboratrice data scientist sollicitant une fonctionnalité d'intelligence artificielle, a formulé le besoin suivant :

> **Expression de besoin**
> Équiper Waterflow 2 d'une fonctionnalité d'extraction automatique des neuf mesures à partir d'une photo ou d'un scan de la fiche labo, en s'appuyant sur un service d'intelligence artificielle de reconnaissance optique de caractères (OCR), le résultat de l'extraction restant systématiquement soumis à relecture et validation du Client avant tout enregistrement en base.

Cette expression de besoin correspond au cas pratique du bloc E2 : elle porte sur l'installation et la configuration d'un service d'intelligence artificielle préconisé, en amont de son exposition via l'API (compétence C9, traitée dans le rapport du bloc E3) et de son intégration dans le parcours utilisateur (compétence C14, US-03, traitée dans le rapport du bloc E4).

### 1.2 Cadrage du besoin

| Contrainte | Détail |
|---|---|
| Format des documents | Photo (JPEG/PNG) prise au smartphone sur le terrain, ou scan PDF pour les fiches transmises par e-mail par le laboratoire |
| Volumétrie | Usage ponctuel : quelques dizaines de fiches importées par jour sur l'ensemble des Clients, pas de pic prévisible |
| Budget | Aucun budget dédié alloué à ce jour — nécessité d'un service gratuit ou à coût quasi nul pour ce volume |
| Latence | Réponse en quelques secondes pour ne pas bloquer le parcours de saisie du Client sur le terrain |
| Langue | Fiches rédigées en français, avec un vocabulaire technique de chimie de l'eau |
| Intégration | Doit être appelable par requête HTTP depuis un backend Python/FastAPI existant, sans dépendance lourde à installer |
| Données | Le document peut porter des mentions identifiantes indirectes (nom du laborantin, cachet du laboratoire) — traitement à encadrer |

### 1.3 Démarche suivie

Ce rapport suit la structure attendue par le référentiel pour le bloc E2 : une veille technique et réglementaire (C6) pour cadrer les solutions disponibles et les obligations applicables, un benchmark formel de services d'intelligence artificielle existants (C7) débouchant sur une recommandation motivée, puis le paramétrage effectif du service retenu au sein de Waterflow 2 (C8).

---

## C6 — Organiser et réaliser une veille technique et réglementaire

### 2.1 Objectif de la compétence

Il s'agissait d'organiser une veille technique et réglementaire portant sur l'outil et/ou la réglementation mobilisée par la mise en situation, avec une planification récurrente, des sources fiables et une synthèse communiquée dans un format accessible aux parties prenantes.

### 2.2 Thématique de veille retenue

Deux axes complémentaires, directement mobilisés par le besoin exprimé en §1.1, ont structuré la veille :

- **Axe technique** — les solutions d'OCR et d'extraction documentaire assistée par IA, leurs évolutions (nouveaux moteurs, capacités de reconnaissance de tableaux, tarification), afin d'alimenter le benchmark du §C7.
- **Axe réglementaire** — le traitement d'un document susceptible de porter des données à caractère personnel indirectes, transmis à un service tiers potentiellement hébergé hors Union européenne : cadre RGPD, et positionnement d'un système d'extraction documentaire au regard du règlement européen sur l'intelligence artificielle (*AI Act*, règlement UE 2024/1689).

### 2.3 Planification et récurrence

| Activité | Fréquence | Durée |
|---|---|---|
| Lecture et tri des flux agrégés (RSS, newsletters) | Continue, en tâche de fond | 10-15 min / jour |
| Créneau de veille active dédié | Hebdomadaire (chaque mardi matin) | 1 heure |
| Rédaction de la synthèse | Bimensuelle | 30 min |

Le créneau hebdomadaire dédié respecte la récurrence minimale d'une heure par semaine attendue par le référentiel, en complément d'une veille passive continue portée par les outils d'agrégation présentés ci-dessous.

### 2.4 Sources et outils d'agrégation

Le choix des outils d'agrégation a été guidé par la contrainte de budget nul posée en §1.2 : seules des solutions gratuites ont été retenues, un agrégateur de flux RSS suffisant largement au nombre de sources suivies pour ce périmètre.

| Type de source | Source | Vecteur |
|---|---|---|
| Blog éditeur cloud | Google Cloud AI Blog, AWS Machine Learning Blog, Microsoft Azure AI Blog | Flux RSS natif, agrégé dans Feedly (plan gratuit) |
| Communauté / recherche | Hugging Face Blog | Flux RSS natif |
| Newsletter spécialisée IA | The Batch (DeepLearning.AI) | Abonnement e-mail gratuit, hebdomadaire |
| Autorité de régulation | CNIL — actualités et fiches pratiques | Flux RSS natif du site cnil.fr |
| Texte réglementaire officiel | EUR-Lex — règlement (UE) 2024/1689 (AI Act) et ses actes délégués | Suivi direct de la page officielle, consultation ponctuelle |

Feedly (plan gratuit, limité à 100 flux suivis) est largement suffisant pour les cinq sources retenues et évite tout coût d'abonnement, cohérent avec l'absence de budget alloué à cette activité.

### 2.5 Critères de fiabilité appliqués aux sources

Chaque source a été retenue après vérification des critères de fiabilité attendus par le référentiel. Le tableau ci-dessous illustre cette grille sur trois sources représentatives.

| Critère | CNIL (cnil.fr) | AWS Machine Learning Blog | The Batch |
|---|---|---|---|
| Auteur identifié | Autorité administrative française identifiée | Ingénieurs/équipes produit AWS signés | Andrew Ng et l'équipe éditoriale DeepLearning.AI |
| Notoriété / absence d'intérêt personnel | Institution publique indépendante | Éditeur du service décrit — biais commercial identifié et pris en compte | Organisme de formation IA reconnu, ligne éditoriale indépendante des éditeurs cloud |
| Contenu daté et sourcé | Articles horodatés, réglementation citée | Articles horodatés, liens vers documentation technique | Édition hebdomadaire datée, sources citées |
| Structuration | Site structuré, navigation par thématique | Blog structuré par catégorie de service | Format newsletter structuré (sections fixes) |
| Accessibilité | Site conforme RGAA (secteur public) | HTML sémantique standard | E-mail texte structuré, alternative web accessible |
| Recoupement | Positions confirmées par les publications de la CNCTR et de la CNIL elle-même | Informations recoupées avec la documentation officielle du produit | Analyses recoupées avec les publications sources qu'elle synthétise |

### 2.6 Synthèse de veille

**Volet technique.** Trois constats structurants ressortent de la veille technique menée sur la période :

- les offres d'OCR cloud managées proposent presque toutes un palier gratuit (de l'ordre de quelques centaines à plusieurs milliers de requêtes par mois), largement suffisant pour un usage ponctuel comme celui de Waterflow 2 ;
- la tendance de fond est le passage d'un OCR « brut » (texte non structuré) vers une extraction structurée capable de restituer des paires clé/valeur ou des cellules de tableau, particulièrement pertinente pour une fiche labo tabulaire ;
- plusieurs fournisseurs mettent désormais en avant une option d'hébergement des traitements au sein de l'Union européenne, argument commercial directement lié aux obligations RGPD identifiées ci-dessous.

**Volet réglementaire.**

- **RGPD** — une fiche labo scannée peut comporter des données à caractère personnel indirectes (nom d'un laborantin, signature, cachet). Le traitement doit reposer sur une base légale (l'exécution du contrat de service liant le Client à l'exploitant du réseau d'eau constitue la base la plus directe), respecter un principe de minimisation (ne pas conserver l'image brute au-delà du temps nécessaire à l'extraction) et faire l'objet d'une information des personnes concernées.
- **AI Act** — au sens de la classification par niveau de risque du règlement (UE) 2024/1689, un système qui se limite à extraire des valeurs numériques d'un formulaire ne relève d'aucune des catégories à haut risque de l'annexe III (il n'opère ni évaluation, ni notation, ni décision affectant une personne) : il relève d'un risque minimal, sans obligation de conformité renforcée à ce stade. Ce classement devra être réexaminé si l'usage du service évoluait vers une analyse portant sur des personnes plutôt que sur des mesures physico-chimiques.

### 2.7 Communication de la synthèse

La synthèse de veille est rédigée en Markdown texte brut (`docs/veille/SYNTHESE_OCR_IA.md`), choix délibéré cohérent avec le reste de la documentation du projet (voir `docs/ACCESSIBILITE_DOCUMENTATION.md`) : un fichier Markdown produit du HTML sémantique une fois rendu (vrais titres, vraies listes), nativement compatible avec les lecteurs d'écran, contrairement à une capture d'écran ou un PDF scanné. Elle est diffusée aux rôles Quality_Analyst et Admin du projet, qui sont les parties prenantes concernées par une évolution du périmètre fonctionnel de l'application.

### 2.8 Bilan des critères d'évaluation — C6

| Critère | Statut |
|---|---|
| Thématique de veille portant sur un outil et/ou une réglementation de la mise en situation | Acquis |
| Temps de veille planifiés régulièrement (récurrence hebdomadaire minimale) | Acquis |
| Outils d'agrégation cohérents avec les sources et le budget disponible | Acquis |
| Synthèses communiquées dans un format respectant les recommandations d'accessibilité | Acquis |
| Informations partagées répondant à la thématique de veille choisie | Acquis |
| Sources et flux répondant aux critères de fiabilité attendus | Acquis |

---

## C7 — Identifier des services d'intelligence artificielle préexistants

### 3.1 Objectif de la compétence

Il s'agissait, à partir de l'expression de besoin formulée en §1.1, de réaliser un benchmark de services d'intelligence artificielle existants, d'analyser leurs caractéristiques et de formaliser une recommandation motivée.

### 3.2 Reformulation du besoin

Le besoin peut être reformulé ainsi : disposer d'un service d'extraction de texte structuré (OCR) capable de lire une fiche labo photographiée ou scannée en français, de restituer un texte exploitable par un traitement applicatif ultérieur, appelable depuis un backend Python sans infrastructure supplémentaire à opérer, pour un volume de quelques dizaines de documents par jour et sans budget dédié.

### 3.3 Services étudiés et services écartés en amont

| Service | Statut | Raison |
|---|---|---|
| OCR.space | Étudié | API REST simple, palier gratuit sans engagement de facturation |
| Google Cloud Vision AI | Étudié | Référence du marché en reconnaissance de texte |
| AWS Textract | Étudié | Spécialisé dans l'extraction de formulaires et de tableaux |
| Azure AI Document Intelligence | Étudié | Offre équivalente dans l'écosystème Microsoft |
| Tesseract OCR (open source) | Étudié | Alternative auto-hébergée, sans dépendance à un tiers |
| Mindee | Non étudié | Spécialisé sur des documents à structure fixe préentraînée (factures, pièces d'identité), non adapté à une fiche labo dont la mise en page varie selon le laboratoire émetteur |
| ABBYY FineReader Engine | Non étudié | Licence commerciale par poste, hors du budget nul fixé en §1.2 |

### 3.4 Grille d'adéquation fonctionnelle

| Critère | OCR.space | Google Vision | AWS Textract | Azure Doc. Intel. | Tesseract |
|---|---|---|---|---|---|
| Extraction de texte libre | Oui | Oui | Oui | Oui | Oui |
| Image + PDF en entrée | Oui | Oui | Oui | Oui | Image uniquement (conversion préalable requise) |
| Support du français | Oui | Oui | Oui (anglais prioritaire) | Oui | Oui (paquet de langue à installer) |
| Détection de structure tabulaire | Oui (option `isTable`) | Partielle | Oui (spécialité du service) | Oui | Non nativement |
| Latence typique constatée | 1 à 3 s | < 1 s | 1 à 2 s | 1 à 2 s | Variable, dépend du matériel hôte |
| Intégration REST simple sans SDK cloud | Oui (requête HTTP unique) | Nécessite SDK/compte GCP | Nécessite SDK/compte AWS | Nécessite SDK/compte Azure | Bibliothèque locale, aucun réseau |

### 3.5 Démarche éco-responsable des services étudiés

| Service | Informations disponibles |
|---|---|
| OCR.space | Éditeur de taille modeste, peu de communication publique sur l'empreinte environnementale de son infrastructure |
| Google Cloud Vision AI | Google communique sur la neutralité carbone de son cloud depuis 2007 et vise un fonctionnement 24/7 sur énergie sans carbone d'ici 2030 (objectif public documenté) |
| AWS Textract | AWS publie un objectif de neutralité carbone 2040 et des rapports de durabilité annuels ; granularité par service individuel (Textract) non détaillée |
| Azure AI Document Intelligence | Microsoft communique un objectif « carbone négatif » d'ici 2030 à l'échelle du groupe, non détaillé par service |
| Tesseract | Empreinte dépendante entièrement de l'infrastructure d'hébergement choisie par le projet, donc maîtrisable mais à la charge du projet |

Les trois éditeurs cloud majeurs communiquent des engagements globaux de décarbonation, mais aucun ne détaille l'empreinte du service d'OCR pris isolément : cette information, demandée par le référentiel, n'est disponible qu'à l'échelle de l'infrastructure globale de l'éditeur, limite documentée plutôt que passée sous silence.

### 3.6 Contraintes techniques et pré-requis

| Service | Pré-requis |
|---|---|
| OCR.space | Une adresse e-mail pour obtenir une clé API gratuite ; aucun moyen de paiement à renseigner |
| Google Cloud Vision AI | Compte Google Cloud Platform, activation de la facturation (carte bancaire requise même pour le palier gratuit), gestion IAM |
| AWS Textract | Compte AWS, carte bancaire, gestion IAM et des rôles d'accès au service |
| Azure AI Document Intelligence | Compte Azure, carte bancaire, création d'une ressource cognitive dédiée |
| Tesseract | Serveur ou conteneur additionnel à provisionner et maintenir, installation des paquets de langue, absence de service managé |

### 3.7 Coût pour le volume visé

| Service | Palier gratuit | Suffisant pour le volume visé ? |
|---|---|---|
| OCR.space | 25 000 requêtes / mois (clé gratuite) | Oui, très largement |
| Google Cloud Vision AI | 1 000 unités / mois | Oui, mais nécessite une facturation active dès le dépassement |
| AWS Textract | 1 000 pages / mois pendant 3 mois seulement | Oui à court terme, non pérenne |
| Azure AI Document Intelligence | 500 pages / mois | Oui |
| Tesseract | Gratuit (open source), coût reporté sur l'hébergement | Oui, mais coût d'infrastructure et de maintenance à porter par le projet |

### 3.8 Conclusions du benchmark

Les services cloud managés (Google Vision, AWS Textract, Azure Document Intelligence) sont écartés pour ce cas d'usage : chacun impose la création d'un compte cloud complet avec facturation active, une gestion IAM et une intégration disproportionnées par rapport au volume visé de quelques dizaines de requêtes par jour — une architecture surdimensionnée au regard du besoin. Tesseract est également écarté : il exigerait de provisionner et maintenir une infrastructure dédiée, sans offrir nativement la détection de structure tabulaire recherchée pour une fiche labo, ce qui aurait nécessité un travail de tuning disproportionné par rapport au gain attendu.

> **Service retenu**
> **OCR.space** est recommandé : palier gratuit de 25 000 requêtes/mois très largement suffisant, clé API unique sans carte bancaire à renseigner, intégration par une simple requête HTTP multipart sans SDK propriétaire, moteur « OCR Engine 2 » avec support explicite des tableaux (`isTable=true`), cohérent avec la contrainte de budget nul et de simplicité d'intégration fixée en §1.2.

**Limite assumée :** l'entreprise éditrice d'OCR.space communique peu sur sa démarche environnementale (§3.5) et son hébergement n'est pas garanti au sein de l'Union européenne — un point de vigilance RGPD traité au §4.6, à réévaluer si le volume ou la sensibilité des documents traités venait à augmenter.

### 3.9 Bilan des critères d'évaluation — C7

| Critère | Statut |
|---|---|
| Expression de besoin reformulée avec objectifs et contraintes | Acquis |
| Benchmark listant les services étudiés et non étudiés | Acquis |
| Raisons d'écarter un service explicitées | Acquis |
| Niveau d'adéquation détaillé par ensemble fonctionnel | Acquis |
| Niveau de démarche éco-responsable détaillé selon les informations disponibles | Acquis |
| Contraintes techniques et pré-requis détaillés par solution | Acquis |
| Conclusions délimitant clairement services adaptés et non adaptés | Acquis |

---

## C8 — Paramétrer un service d'intelligence artificielle

### 4.1 Objectif de la compétence

Il s'agissait de paramétrer le service retenu à l'issue du benchmark (C7) en suivant sa documentation technique et en respectant les spécifications du besoin (C6), afin de permettre l'intégration de ses connecteurs dans le système d'information de Waterflow 2.

### 4.2 Accès et authentification au service

Un compte a été créé sur ocr.space avec une adresse e-mail dédiée au projet, générant une clé API gratuite. Cette clé est injectée en variable d'environnement (`OCR_API_KEY`) au démarrage du conteneur `api` via `docker-compose.yml`, jamais codée en dur ni versionnée dans le dépôt Git (fichier `.env` listé dans `.gitignore`), conformément à la pratique déjà appliquée pour les autres secrets du projet (voir bloc E3, C9 §2.3).

### 4.3 Configuration retenue

| Paramètre | Valeur | Justification |
|---|---|---|
| Point de terminaison | `https://api.ocr.space/parse/image` | Point d'entrée REST unique du service |
| `OCREngine` | `2` | Moteur le plus récent d'OCR.space, meilleure gestion des tableaux et du français |
| `language` | `fre` | Fiches rédigées en français (§1.2) |
| `isTable` | `true` | Restitution de la structure ligne/colonne de la fiche labo |
| `scale` | `true` | Mise à l'échelle automatique des photos basse résolution prises au smartphone |
| `detectOrientation` | `true` | Compense les photos prises en orientation portrait/paysage variable sur le terrain |
| Délai d'attente (timeout) | 8 secondes | Compatible avec la contrainte de latence perçue fixée en §1.2, avec marge avant d'échouer explicitement |

### 4.4 Intégration dans Waterflow 2

Le service est intégré à l'API via un routeur dédié (`api/ocr_router.py`), exposant deux points de terminaison déjà présentés dans le rapport du bloc E3 (C9 §2.2) : `POST /api/ocr/lab-report` pour le traitement d'une fiche, et `GET /api/ocr/health` pour vérifier la disponibilité du service tiers indépendamment d'une soumission réelle.

```python
async def call_ocr_space(file_bytes: bytes, filename: str) -> dict:
    payload = {
        "apikey": settings.OCR_API_KEY,
        "language": "fre",
        "OCREngine": "2",
        "isTable": "true",
        "scale": "true",
        "detectOrientation": "true",
    }
    files = {"file": (filename, file_bytes)}
    try:
        response = httpx.post(OCR_ENDPOINT, data=payload, files=files, timeout=8.0)
        response.raise_for_status()
    except httpx.TimeoutException:
        ocr_failures_total.labels(reason="timeout").inc()
        raise HTTPException(status_code=502, detail="Service OCR indisponible (délai dépassé)")
    except httpx.HTTPStatusError:
        ocr_failures_total.labels(reason="http_error").inc()
        raise HTTPException(status_code=502, detail="Service OCR indisponible")

    result = response.json()
    if not result.get("ParsedResults"):
        ocr_failures_total.labels(reason="empty_result").inc()
        raise HTTPException(status_code=422, detail="Aucun texte détecté sur le document")
    return parse_lab_report(result["ParsedResults"][0]["ParsedText"])
```

Le texte brut renvoyé par OCR.space est ensuite passé à une fonction d'analyse (`parse_lab_report`) qui applique des expressions régulières et des heuristiques de libellé (« pH », « Dureté », « Chloramines », etc.) pour reconstituer les neuf champs attendus par le modèle. Les valeurs extraites pré-remplissent le panel de saisie du Client, qui reste seul responsable de la validation finale avant l'appel à `POST /api/measurements` : aucune prédiction n'est déclenchée sans relecture humaine explicite des valeurs extraites.

### 4.5 Monitorage du service

Conformément au critère du référentiel demandant que « le monitorage disponible du service soit opérationnel », l'intégration expose la métrique Prometheus `ocr_failures_total{reason=...}` (déjà détaillée dans le rapport du bloc E3, C11 §4.3), qui distingue les causes d'échec de l'appel au service externe (délai dépassé, service injoignable, réponse en erreur, résultat vide), et le point de terminaison `GET /api/ocr/health` qui vérifie la disponibilité du service indépendamment d'une soumission de document.

### 4.6 Sécurisation et gestion des données

- Le fichier image transmis par le Client est traité en mémoire et transmis directement à OCR.space sans être écrit sur disque, ce qui limite la persistance de données potentiellement identifiantes indirectes évoquée au §2.6.
- Seul le texte extrait, puis les neuf valeurs numériques validées par le Client, sont conservés en base — jamais l'image source elle-même.
- La consommation d'un service tiers est traitée en respectant la recommandation API10 du Top 10 OWASP API Security (« Unsafe Consumption of APIs »), déjà documentée dans le rapport du bloc E3 (C9 §2.4) : tous les cas d'erreur possibles côté OCR.space sont interceptés explicitement, sans confiance aveugle dans la réponse du service externe.

### 4.7 Documentation

La documentation technique du paramétrage (`docs/OCR_INTEGRATION.md`) couvre la gestion des accès (obtention et rotation de la clé API), la procédure d'installation et de test en local, les dépendances (bibliothèque `httpx`), l'interconnexion avec le service externe OCR.space et la nature des données impliquées. Rédigée en Markdown, elle respecte les mêmes standards d'accessibilité que le reste de la documentation du projet (voir `docs/ACCESSIBILITE_DOCUMENTATION.md`).

### 4.8 Bilan des critères d'évaluation — C8

| Critère | Statut |
|---|---|
| Service installé accessible, avec authentification | Acquis |
| Service configuré correctement, répondant aux besoins fonctionnels et contraintes techniques | Acquis |
| Monitorage disponible du service opérationnel | Acquis |
| Documentation couvrant gestion des accès, installation, test, interconnexions, données impliquées | Acquis |
| Documentation communiquée dans un format respectant les recommandations d'accessibilité | Acquis |

---

## 5. Synthèse et tableau récapitulatif

| Comp. | Intitulé | Statut global |
|---|---|---|
| C6 | Organiser et réaliser une veille technique et réglementaire | Acquis |
| C7 | Identifier des services d'intelligence artificielle préexistants | Acquis |
| C8 | Paramétrer un service d'intelligence artificielle | Acquis |

Les trois compétences du bloc E2 forment une chaîne continue et traçable : une veille technique et réglementaire cadrant précisément le besoin et ses contraintes (C6), un benchmark documenté distinguant explicitement les services retenus des services écartés et pourquoi (C7), et un paramétrage effectif, sécurisé et monitoré du service recommandé au sein de l'application (C8). Cette même intégration est ensuite exposée via une API authentifiée (bloc E3, C9) puis intégrée au parcours utilisateur du rôle Client sous la forme de l'US-03 (bloc E4, C14).

## 6. Conclusion et perspectives

Ce travail a permis de documenter, du besoin à la mise en service, l'intégration d'un premier service d'intelligence artificielle tiers dans Waterflow 2 : une veille ciblée a cadré les contraintes techniques et réglementaires, un benchmark structuré a justifié le choix d'OCR.space parmi sept services considérés, et son paramétrage a été réalisé dans le respect de ces contraintes, avec un monitorage et une documentation opérationnels dès la mise en service.

Deux axes de vigilance restent identifiés pour une évolution future du projet : réévaluer le choix d'OCR.space si le volume de documents dépassait significativement le palier gratuit actuel (25 000 requêtes/mois), et objectiver plus précisément la localisation d'hébergement des traitements du service avant tout usage portant sur des documents plus sensibles que la fiche labo actuelle.

---
*Ilyes Chabab — Waterflow 2 — 2025-2026*
