# Checklist d'audit — RNCP 37827 Développeur.se en IA
## Compétences C9 à C14 (épreuves E3 et E4)

> **Usage prévu** : ce fichier sert de grille d'audit pour Claude Code (ou tout autre agent) sur le dépôt `waterflow2`. Pour chaque critère, l'agent doit chercher une preuve concrète dans le code/dépôt (fichier, ligne, test qui passe, doc présente...) avant de cocher. Ne jamais cocher une case sur la seule base d'une intention déclarée — il faut une preuve exécutable ou documentaire.
>
> Source : Grille d'évaluation individuelle RNCP 37827 (Simplon.co).

---

## E3 — Mise en situation (C9, C10, C11, C12, C13)

Contexte de l'épreuve : réalisation d'un service IA à partir d'un modèle fourni — mise en service (packaging, monitorage, test) et intégration dans une application existante.
Livrable attendu : rapport professionnel individuel + soutenance orale avec démonstration.

### C9 — Développer une API exposant un modèle IA (REST)

- [x] L'API restreint l'accès au modèle IA avec un moyen d'authentification.
- [x] L'API permet l'accès aux fonctions du modèle, comme attendu selon les spécifications.
- [ ] Les recommandations de sécurisation d'une API du Top 10 OWASP sont intégrées quand nécessaire.
- [x] Les sources sont versionnées et accessibles depuis un dépôt Git distant.
- [x] Les tests couvrent tous les points de terminaison dans le respect des spécifications.
- [x] Les tests s'exécutent sans bug.
- [x] Les résultats des tests sont correctement interprétés.
- [x] La documentation couvre l'architecture et tous les points de terminaison de l'API.
- [x] La documentation couvre les règles d'authentification et/ou d'autorisation d'accès à l'API.
- [x] La documentation et l'API respectent les standards d'un modèle choisi (ex. OpenAPI).
- [ ] La documentation est communiquée dans un format qui respecte les recommandations d'accessibilité (ex. association Valentin Haüy ou Microsoft).

### C10 — Intégrer l'API d'un modèle/service IA dans une application

- [ ] L'application de départ est installée et fonctionnelle en environnement de développement.
- [ ] La communication avec l'API depuis l'application fonctionne.
- [ ] Les éventuelles étapes d'authentification et de renouvellement de l'authentification (expiration des jetons, etc.) sont intégrées correctement en suivant la documentation de l'API.
- [ ] Tous les points de terminaison de l'API concernés par le projet sont intégrés à l'application selon les spécifications fonctionnelles et techniques.
- [ ] Les adaptations d'interface nécessaires et en accord avec les spécifications sont intégrées à l'application.
- [ ] Les tests d'intégration couvrent tous les points de terminaison exploités.
- [ ] Les tests s'exécutent en totalité, sans bug dans les programmes de test eux-mêmes.
- [ ] Les résultats des tests sont correctement interprétés.
- [x] Les sources sont versionnées et accessibles depuis le dépôt Git de l'application.

### C11 — Monitorer un modèle IA (métriques, alertes, restitution)

- [ ] Les métriques faisant l'objet du monitorage du modèle sont expliquées sans erreur d'interprétation.
- [x] Le ou les outils pour l'intégration du monitorage du modèle sont adaptés au contexte et aux contraintes techniques du projet.
- [x] Au moins un vecteur de restitution des métriques évaluées, en temps réel, est proposé (dashboard, feuille de calcul, etc.).
- [ ] Les enjeux d'accessibilité, pour toutes les parties prenantes du projet, sont pris en compte lors de la sélection de l'outil de restitution.
- [x] La chaîne de monitorage est d'abord testée dans un bac à sable ou environnement de test dédié.
- [ ] La chaîne de monitorage est en état de marche : les métriques visées sont effectivement évaluées et restituées.
- [x] Les sources sont versionnées et accessibles depuis un dépôt Git distant.
- [ ] La documentation technique de la chaîne de monitorage couvre la procédure d'installation, de configuration, et d'utilisation à destination des équipes techniques.
- [ ] La documentation est communiquée dans un format qui respecte les recommandations d'accessibilité.

### C12 — Programmer les tests automatisés d'un modèle IA

- [x] L'ensemble des cas à tester sont listés et définis : partie du modèle visée, périmètre du test, stratégie de test.
- [x] Les outils de test (framework, bibliothèque, etc.) choisis sont cohérents avec l'environnement technique du projet.
- [ ] Les tests sont intégrés et respectent la couverture souhaitée établie.
- [x] **Les tests s'exécutent sans problème technique en environnement de test** (critère bloquant — vérifier que `pytest` se termine avec un exit code 0, sans erreur d'import ni d'exécution).
- [x] Les sources sont versionnées et accessibles depuis un dépôt Git distant (DVC, GitLab, etc.).
- [x] La documentation couvre la procédure d'installation de l'environnement de test, les dépendances installées, la procédure d'exécution des tests et de calcul de la couverture.
- [ ] La documentation est communiquée dans un format qui respecte les recommandations d'accessibilité.

### C13 — Créer une chaîne de livraison continue d'un modèle IA (CI/CD, MLOps)

- [ ] La documentation pour l'utilisation de la chaîne couvre toutes les étapes, les tâches et tous les déclencheurs disponibles.
- [x] Les déclencheurs sont intégrés comme préalablement définis.
- [x] Le ou les fichiers de configuration de la chaîne sont correctement reconnus et exécutés par le système selon les déclencheurs configurés.
- [x] L'étape de test des données est intégrée à la chaîne et s'exécute sans erreur.
- [x] La ou les étapes de test, d'entraînement et de validation du modèle sont intégrées à la chaîne et s'exécutent sans erreur.
- [x] Les sources de la chaîne sont versionnées et accessibles depuis le dépôt Git distant du projet.
- [ ] La documentation de la chaîne de livraison continue couvre la procédure d'installation, de configuration et de test de la chaîne.
- [ ] La documentation est communiquée dans un format qui respecte les recommandations d'accessibilité.

---

## E4 — Mise en situation (C14 uniquement pour ce périmètre)

> Note : dans la grille officielle, E4 couvre C14 à C19. Ce fichier ne détaille que **C14**, à la demande explicite du candidat, le reste du projet ne portant que sur C9-C14.

Contexte de l'épreuve : développement d'une application intégrant un service IA — analyse du besoin, conception, développement, tests, livraison.
Livrable attendu : rapport professionnel individuel + soutenance orale avec démonstration.

### C14 — Analyser le besoin, rédiger les spécifications fonctionnelles et modéliser

- [x] La modélisation des données respecte un formalisme reconnu : Merise, entités-relations, etc. (MCD + MPD).
- [x] La modélisation des parcours utilisateurs respecte un formalisme : schéma fonctionnel, wireframes, etc.
- [x] Chaque spécification fonctionnelle couvre le contexte, les scénarios d'utilisation et les critères de validation.
- [x] Les objectifs d'accessibilité sont directement intégrés aux critères d'acceptation des user stories.
- [x] Les objectifs d'accessibilité sont formulés en s'appuyant sur un standard d'accessibilité reconnu (WCAG, RGAA, etc.).

---

## Instructions pour l'agent d'audit (Claude Code)

Pour chaque case ci-dessus :

1. **Chercher une preuve dans le dépôt** : fichier de code, test, fichier de config CI/CD, fichier de documentation, script.
2. **Vérifier que la preuve fonctionne réellement**, pas seulement qu'elle existe :
   - Un test doit être exécuté (`pytest`) et passer, pas seulement présent dans le code.
   - Un pipeline CI doit être un fichier de config valide et cohérent avec les étapes attendues, idéalement avec un historique d'exécution réussi sur le dépôt distant.
   - Une doc doit couvrir tous les sous-points listés dans le critère, pas juste le sujet en général.
3. **Ne pas cocher une case sur la base d'une déclaration d'intention** (ex. un commentaire "TODO: ajouter les tests" ne compte pas).
4. Pour chaque case non cochée, indiquer précisément **quel fichier créer ou modifier** pour la satisfaire.
5. Produire en sortie un tableau récapitulatif par compétence (C9 à C14) avec le statut global : **Acquis / Non acquis / Partiellement acquis**, en listant les cases encore ouvertes pour chaque compétence partiellement acquise.
