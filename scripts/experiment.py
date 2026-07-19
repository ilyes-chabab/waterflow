import pickle
import mlflow
import mlflow.xgboost
import numpy as np
from xgboost import XGBClassifier
from mlflow.tracking import MlflowClient
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from imblearn.over_sampling import SMOTE

# ──────────────────────────────────────────────
# Setup MLflow
# ──────────────────────────────────────────────
mlflow.set_tracking_uri("http://127.0.0.1:5000")
EXPERIMENT_NAME = "experiment_water_quality"
client = MlflowClient()

experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
if experiment is None:
    experiment_id = client.create_experiment(EXPERIMENT_NAME)
else:
    experiment_id = experiment.experiment_id

mlflow.set_experiment(EXPERIMENT_NAME)

# ──────────────────────────────────────────────
# Chargement des données
#
# processed_data.pkl est produit par scripts/prepare_data.py : le split
# train / val / test est fait AVANT toute imputation, écrêtage des outliers ou
# normalisation, pour que ces statistiques de prétraitement ne soient jamais calculées
# avec des lignes de validation/test (fuite de données corrigée - voir prepare_data.py).
# X_train/y_train ne contiennent QUE le train ; X_val/y_val servent au choix du seuil.
# X_test/y_test existent aussi dans le pickle mais ne sont volontairement pas chargés
# ici : le test ne doit être évalué qu'une seule fois, dans scripts/model_selection.py,
# jamais réutilisé pour ajuster un seuil ou un hyperparamètre.
# ──────────────────────────────────────────────
with open("data/processed/processed_data.pkl", "rb") as f:
    data = pickle.load(f)

X_train = data["X_train"]
X_val   = data["X_val"]
y_train = data["y_train"]
y_val   = data["y_val"]

print(f"Distribution train — 0: {(y_train==0).sum()} | 1: {(y_train==1).sum()}")

# ──────────────────────────────────────────────
# 
# ──────────────────────────────────────────────
smote = SMOTE(random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

print(f"Après SMOTE      — 0: {(y_train_resampled==0).sum()} | 1: {(y_train_resampled==1).sum()}")

# ──────────────────────────────────────────────
# Paramètres XGBoost optimisés
#
# Issus de scripts/model_selection.py : recherche par validation croisée
# (StratifiedKFold 5 plis, RandomizedSearchCV, SMOTE appliqué à l'intérieur de chaque
# pli pour éviter toute fuite entre plis) sur les 9 features brutes. RandomForest et une
# régression logistique ont aussi été comparés dans les mêmes conditions ; l'écart avec
# XGBoost est resté dans le bruit de la validation croisée (± 0.02-0.03 de F1), ce qui ne
# justifiait pas de changer de famille de modèle pour un gain non significatif.
# ──────────────────────────────────────────────
params_xgb = {
    "n_estimators":     150,
    "max_depth":        5,
    "learning_rate":    0.08,
    "subsample":        0.7,
    "colsample_bytree": 0.6,
    "min_child_weight": 3,
    "gamma":            0.1,
    "reg_alpha":        1,
    "reg_lambda":       1.5,
    "eval_metric":      "logloss",
    "random_state":     42,
}

# ──────────────────────────────────────────────
# Run MLflow
# ──────────────────────────────────────────────
with mlflow.start_run(run_name="XGBoost_SMOTE_Optimise") as run:

    model = XGBClassifier(**params_xgb)
    model.fit(
        X_train_resampled, y_train_resampled,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

 
    y_proba = model.predict_proba(X_val)[:, 1]

    best_threshold = 0.5
    best_f1 = 0
    for threshold in np.arange(0.3, 0.7, 0.01):
        y_pred_t = (y_proba >= threshold).astype(int)
        f1 = f1_score(y_val, y_pred_t, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    print(f"\n   Meilleur seuil trouvé : {best_threshold:.2f}")

    y_pred = (y_proba >= best_threshold).astype(int)

    metrics = {
        "accuracy":       accuracy_score(y_val, y_pred),
        "f1_score":       f1_score(y_val, y_pred, zero_division=0),
        "precision":      precision_score(y_val, y_pred, zero_division=0),
        "recall":         recall_score(y_val, y_pred, zero_division=0),
        "best_threshold": best_threshold,
    }

    mlflow.log_params(params_xgb)
    mlflow.log_params({"smote": True, "threshold_tuning": True})
    mlflow.log_metrics(metrics)

    mlflow.xgboost.log_model(
        xgb_model=model,
        artifact_path="model",
        registered_model_name="water_quality_model",
    )

    print(f"\nRun ID : {run.info.run_id}")
    for name, val in metrics.items():
        print(f"   {name:15s} : {val:.4f}")

# ──────────────────────────────────────────────
#          Transition vers Production
# ──────────────────────────────────────────────
latest = client.get_latest_versions("water_quality_model")
latest_version = latest[-1].version

client.transition_model_version_stage(
    name="water_quality_model",
    version=latest_version,
    stage="Production",
)
print(f"\n Modèle v{latest_version} → Production")