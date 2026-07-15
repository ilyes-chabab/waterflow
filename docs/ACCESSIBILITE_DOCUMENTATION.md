# Accessibilité du format de la documentation — Waterflow 2

Ce document couvre l'accessibilité du **format** des livrables documentaires du projet
(`README.md`, `CLAUDE.md`, `tests/test_README.md`, `tests/bugTrouvé_README.md`,
`docs/user_stories.md`, `docs/parcours_utilisateurs.md`, `docs/CI_CD.md`, `docs/MONITORING.md`),
et sert de preuve pour les critères d'audit associés (C9, C11, C12, C13, C17, C18, C19). Pour
l'accessibilité de l'**application** elle-même (UI Streamlit), voir les critères WCAG intégrés
dans `docs/user_stories.md`.

Référentiels suivis : recommandations de l'association [Valentin Haüy](https://www.avh.asso.fr/)
pour la production de documents numériques accessibles, et WCAG 2.1 (même référentiel que les
user stories du projet).

## Choix de format

Toute la documentation est écrite en **Markdown texte brut**, versionné avec le code. Ce choix
est délibéré du point de vue accessibilité : contrairement à un PDF scanné ou une capture d'écran,
un fichier Markdown est nativement lisible par un lecteur d'écran (texte brut) et, une fois rendu
par GitHub/VSCode, produit du **HTML sémantique** (vrais titres, vraies listes, vrais blocs de
code, vrais tableaux) plutôt qu'une mise en forme purement visuelle.

## Points vérifiés

- **Hiérarchie des titres respectée, sans saut de niveau** (toujours H1 → H2 → H3) : vérifié sur
  les 8 fichiers ci-dessus. Une hiérarchie cohérente permet une navigation par titres au clavier
  ou au lecteur d'écran (ex. touche `H` sous NVDA/JAWS).
- **Aucune information transmise uniquement par une image ou une couleur** : la documentation ne
  contient aucune image sans texte équivalent. Les diagrammes de parcours utilisateurs
  (`docs/parcours_utilisateurs.md`) sont écrits en Mermaid, donc **du texte brut lisible tel
  quel** par un lecteur d'écran (`flowchart TD`, nœuds et flèches nommés explicitement) ; le rendu
  graphique via [mermaid.live](https://mermaid.live) est une restitution optionnelle, pas le seul
  moyen d'accéder à l'information. Le schéma d'architecture ASCII de `docs/MONITORING.md` est lui
  aussi du texte brut, lisible sans rendu graphique.
- **Liens avec un intitulé explicite** : aucun lien du type "cliquez ici" ou URL nue sans contexte
  (ex. `[mermaid.live](https://mermaid.live)`, jamais un lien qui ne se comprend pas hors contexte).
- **Tableaux avec en-tête** : les tableaux Markdown de `docs/CI_CD.md` (étapes de la chaîne) et
  `docs/MONITORING.md` (métriques RED) ont chacun une ligne d'en-tête correctement déclarée
  (`| Col1 | Col2 |` suivi de `|---|---|`), condition nécessaire pour qu'un lecteur d'écran
  associe chaque cellule à son en-tête de colonne.
- **Langage clair, sections courtes** : chaque document est découpé en sections numérotées ou
  thématiques plutôt qu'en un bloc de texte continu, pour faciliter le survol au lecteur d'écran.

## Limite assumée

Cette vérification porte sur la **structure** du format (titres, liens, tableaux, alternatives
textuelles), pas sur un contrôle outillé complet (contraste, navigation clavier de bout en bout)
— comme précisé dans `docs/user_stories.md`, aucun audit accessibilité outillé n'a été mené sur
le rendu final dans un lecteur d'écran réel.
