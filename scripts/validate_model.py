"""
validate_model.py - Entraînement + validation du modèle (étape CI, gate qualité).

Rejoue la même logique que experiment.py (SMOTE + XGBoost + recherche du meilleur seuil)
mais sans dépendance à un serveur MLflow : rien n'est loggé ni promu en Production ici,
c'est juste un contrôle de non-régression avant merge.

Le seuil minimal (MIN_F1_SCORE) est le même que celui de
tests/test_pipeline.py::test_model_non_regression_f1_score.
"""

import pickle
import sys

import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

PROCESSED_DATA_PATH = "data/processed/processed_data.pkl"
MIN_F1_SCORE = 0.50

PARAMS_XGB = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma": 0.2,
    "reg_alpha": 0.1,
    "reg_lambda": 1.5,
    "eval_metric": "logloss",
    "random_state": 42,
}


def main() -> int:
    with open(PROCESSED_DATA_PATH, "rb") as f:
        data = pickle.load(f)

    X_train, X_val = data["X_train"], data["X_val"]
    y_train, y_val = data["y_train"], data["y_val"]

    X_train_resampled, y_train_resampled = SMOTE(random_state=42).fit_resample(X_train, y_train)

    model = XGBClassifier(**PARAMS_XGB)
    model.fit(X_train_resampled, y_train_resampled, eval_set=[(X_val, y_val)], verbose=False)

    y_proba = model.predict_proba(X_val)[:, 1]

    best_threshold, best_f1 = 0.5, 0.0
    for threshold in np.arange(0.30, 0.70, 0.01):
        f1 = f1_score(y_val, (y_proba >= threshold).astype(int), zero_division=0)
        if f1 > best_f1:
            best_threshold, best_f1 = threshold, f1

    y_pred = (y_proba >= best_threshold).astype(int)
    metrics = {
        "accuracy": accuracy_score(y_val, y_pred),
        "f1_score": best_f1,
        "precision": precision_score(y_val, y_pred, zero_division=0),
        "recall": recall_score(y_val, y_pred, zero_division=0),
        "best_threshold": best_threshold,
    }

    print("Validation du modèle (SMOTE + XGBoost) :")
    for name, val in metrics.items():
        print(f"  {name:15s} : {val:.4f}")

    if best_f1 < MIN_F1_SCORE:
        print(f"\nÉchec : F1-score {best_f1:.4f} < seuil minimal {MIN_F1_SCORE}.")
        return 1

    print(f"\nOK : F1-score {best_f1:.4f} >= seuil minimal {MIN_F1_SCORE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())