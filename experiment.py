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
# ──────────────────────────────────────────────
params_xgb = {
    "n_estimators":     300,
    "max_depth":        5,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma":            0.2,
    "reg_alpha":        0.1,
    "reg_lambda":       1.5,
    "use_label_encoder": False,
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