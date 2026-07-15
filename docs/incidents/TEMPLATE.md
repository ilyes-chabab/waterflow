# Incident #NNN — Titre court de l'incident

**Date** : AAAA-MM-JJ HH:MM → HH:MM (durée)
**Sévérité** : Mineure / Majeure / Critique
**Auteur** :

## Détection

Comment l'incident a été détecté (alerte Grafana/Prometheus, requête PromQL déclenchée,
signalement utilisateur, etc.).

## Diagnostic

Ce que les métriques (`/metrics`) et les logs structurés JSON ont montré pour identifier
la cause.

## Correction

Ce qui a été fait pour résoudre l'incident. Lien vers le commit / la PR correspondante.

## Prévention

Ce qui a été mis en place pour éviter que ça se reproduise (nouvelle alerte, seuil ajusté,
fallback ajouté, documentation mise à jour...).

---

*Copier ce fichier en `docs/incidents/NNN-titre-court.md` pour chaque incident réel
(numéro incrémental, ex. `001-ocr-timeout.md`). Ne pas modifier ce template directement.*
