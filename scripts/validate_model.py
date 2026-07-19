"""
validate_model.py - Entraînement + validation du modèle (étape CI, gate qualité).

Rejoue la même logique que experiment.py (SMOTE + XGBoost + recherche du meilleur seuil)
mais sans dépendance à un serveur MLflow : rien n'est loggé ni promu en Production ici,
c'est juste un contrôle de non-régression avant merge.

Le seuil minimal (MIN_F1_SCORE) est le même que celui de
tests/test_pipeline.py::test_model_non_regression_f1_score.

Données et hyperparamètres alignés sur scripts/prepare_data.py et
scripts/model_selection.py :
- `data/processed/processed_data.pkl` est désormais produit par un split train/val/test
  fait AVANT toute imputation/normalisation (voir prepare_data.py), pour éviter la fuite
  de données qui existait auparavant (statistiques de prétraitement calculées sur
  l'ensemble du dataset avant le split).
- PARAMS_XGB reprend les meilleurs hyperparamètres trouvés par recherche en validation
  croisée (StratifiedKFold à 5 plis, RandomizedSearchCV) dans model_selection.py, plutôt
  que des valeurs choisies à la main.
"""

import pickle
import sys

import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

PROCESSED_DATA_PATH = "data/processed/processed_data.pkl"
MIN_F1_SCORE = 0.50

# Issus de la recherche par validation croisée (scripts/model_selection.py) sur les
# 9 features brutes : ajouter les 4 features dérivées testées en parallèle n'améliorait
# pas le F1 en CV, elles ont donc été écartées plutôt que gardées par défaut.
PARAMS_XGB = {
    "n_estimators": 150,
    "max_depth": 5,
    "learning_rate": 0.08,
    "subsample": 0.7,
    "colsample_bytree": 0.6,
    "min_child_weight": 3,
    "gamma": 0.1,
    "reg_alpha": 1,
    "reg_lambda": 1.5,
    "eval_metric": "logloss",
    "random_state": 42,
}


def train_and_evaluate(data_path: str = PROCESSED_DATA_PATH) -> dict:
    """Entraîne le modèle et retourne ses métriques de validation.

    Réutilisé par `main()` (gate CI) et par
    `tests/test_pipeline.py::test_model_non_regression_f1_score`, pour que le
    test de non-régression recalcule réellement le F1-score plutôt que de
    comparer une valeur codée en dur.
    """
    with open(data_path, "rb") as f:
        data = pickle.load(f)

    X_train, X_val = data["X_train"], data["X_val"]
    y_train, y_val = data["y_train"], data["y_val"]

    X_train_resampled, y_train_resampled = SMOTE(random_state=42).fit_resample(X_train, y_train)

    model = XGBClassifier(**PARAMS_XGB)
    model.fit(X_train_resampled, y_train_resampled, eval_set=[(X_val, y_val)], verbose=False)

    y_proba = model.predict_proba(X_val)[:, 1]

    best_threshold, best_f1 = 0.5, 0.0
    for threshold in np.arange(0.20, 0.71, 0.01):
        f1 = f1_score(y_val, (y_proba >= threshold).astype(int), zero_division=0)
        if f1 > best_f1:
            best_threshold, best_f1 = threshold, f1

    y_pred = (y_proba >= best_threshold).astype(int)
    return {
        "accuracy": accuracy_score(y_val, y_pred),
        "f1_score": best_f1,
        "precision": precision_score(y_val, y_pred, zero_division=0),
        "recall": recall_score(y_val, y_pred, zero_division=0),
        "best_threshold": best_threshold,
    }


def main() -> int:
    metrics = train_and_evaluate()

    print("Validation du modèle (SMOTE + XGBoost) :")
    for name, val in metrics.items():
        print(f"  {name:15s} : {val:.4f}")

    if metrics["f1_score"] < MIN_F1_SCORE:
        print(f"\nÉchec : F1-score {metrics['f1_score']:.4f} < seuil minimal {MIN_F1_SCORE}.")
        return 1

    print(f"\nOK : F1-score {metrics['f1_score']:.4f} >= seuil minimal {MIN_F1_SCORE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())