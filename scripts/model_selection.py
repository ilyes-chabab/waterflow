"""
model_selection.py - Comparaison de modeles avec validation croisee, en gardant un
oeil explicite sur le sur-apprentissage a chaque etape.

Methodologie (pensee pour eviter l'overfitting a chaque niveau) :

  1. Le TRAIN sert a la recherche d'hyperparametres, via RandomizedSearchCV en
     StratifiedKFold(5). SMOTE est place A L'INTERIEUR du pipeline scikit-learn/imblearn,
     pas applique une fois pour toutes avant la CV : sans ca, des echantillons synthetiques
     generes a partir de points qui finissent dans le pli de validation "fuiteraient" dans
     le pli d'entrainement de ce pli, et gonfleraient artificiellement le score CV.
  2. Le VAL (jamais vu pendant la recherche d'hyperparametres) sert a deux choses
     seulement : choisir le seuil de decision, et departager les 3 candidats entre eux.
  3. Le TEST n'est utilise qu'UNE SEULE FOIS, a la toute fin, sur le candidat final deja
     fige (modele + hyperparametres + seuil) - jamais pour choisir quoi que ce soit.
  4. A chaque etape, le F1 d'entrainement est aussi rapporte : un ecart important entre
     F1(train) et F1(CV)/F1(val)/F1(test) est le signal explicite de sur-apprentissage
     a surveiller, plutot qu'un simple totalise de metriques.

Trois familles de modeles sont comparees pour verifier que la limite de performance
observee vient des donnees (features faiblement previsibles - un fait documente sur ce
jeu de donnees) et non d'un choix de modele sous-optimal :
  - XGBoost (le modele en Production actuel)
  - RandomForest (autre modele a base d'arbres, moins sujet au sur-apprentissage sur
    de petits volumes de par le bagging)
  - Regression logistique (baseline lineaire simple, sert de garde-fou : si un modele
    complexe ne fait pas mieux qu'une regression logistique, la complexite ne se justifie
    pas)

Aucun des runs generes ici n'est promu automatiquement en Production : ce script logue
les candidats dans MLflow et affiche une recommandation, la promotion reste une decision
humaine explicite (voir la fin du script).
"""

import pickle
import sys
import warnings

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

warnings.filterwarnings("ignore", category=FutureWarning)

PROCESSED_DATA_PATH = "data/processed/processed_data.pkl"
RANDOM_STATE = 42
N_SPLITS = 5
N_ITER_SEARCH = 25
THRESHOLD_GRID = np.arange(0.20, 0.71, 0.01)

mlflow.set_tracking_uri("http://127.0.0.1:5000")
EXPERIMENT_NAME = "experiment_water_quality"


# ──────────────────────────────────────────────
# Feature engineering (deterministe, sans .fit -> aucun risque de fuite)
# ──────────────────────────────────────────────
def add_engineered_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    X["ph_dist_neutral"] = (X["ph"] - 7.0).abs()
    X["hardness_solids_ratio"] = X["Hardness"] / (X["Solids"] + 1e-6)
    X["chloramines_x_thm"] = X["Chloramines"] * X["Trihalomethanes"]
    X["carbon_x_turbidity"] = X["Organic_carbon"] * X["Turbidity"]
    return X


def best_threshold_for(y_true, y_proba, grid=THRESHOLD_GRID) -> tuple[float, float]:
    best_t, best_f1 = 0.5, -1.0
    for t in grid:
        f1 = f1_score(y_true, (y_proba >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_t, best_f1 = t, f1
    return best_t, best_f1


def metrics_at(y_true, y_proba, threshold) -> dict:
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
    }


# ──────────────────────────────────────────────
# Espaces de recherche - volontairement bornes vers plus de regularisation,
# le dataset ne fait que ~2300 lignes d'entrainement.
# ──────────────────────────────────────────────
CANDIDATES = {
    "XGBoost": {
        "estimator": XGBClassifier(eval_metric="logloss", random_state=RANDOM_STATE),
        "needs_scaling": False,
        "param_distributions": {
            "clf__n_estimators": [150, 200, 300, 400],
            "clf__max_depth": [3, 4, 5, 6],
            "clf__learning_rate": [0.01, 0.03, 0.05, 0.08, 0.1],
            "clf__subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
            "clf__colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
            "clf__min_child_weight": [1, 3, 5, 7],
            "clf__gamma": [0, 0.1, 0.2, 0.3],
            "clf__reg_alpha": [0, 0.05, 0.1, 0.5, 1],
            "clf__reg_lambda": [1, 1.5, 2, 3],
        },
    },
    "RandomForest": {
        "estimator": RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
        "needs_scaling": False,
        "param_distributions": {
            "clf__n_estimators": [200, 300, 400, 500],
            "clf__max_depth": [4, 6, 8, 10, None],
            "clf__min_samples_leaf": [1, 2, 4, 8],
            "clf__min_samples_split": [2, 5, 10],
            "clf__max_features": ["sqrt", "log2", 0.5],
        },
    },
    "LogisticRegression": {
        "estimator": LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
        "needs_scaling": True,
        "param_distributions": {
            "clf__C": [0.01, 0.03, 0.1, 0.3, 1, 3, 10],
            "clf__penalty": ["l2"],
        },
    },
}


def build_pipeline(spec) -> ImbPipeline:
    steps = [("smote", SMOTE(random_state=RANDOM_STATE))]
    if spec["needs_scaling"]:
        steps.append(("scaler", StandardScaler()))
    steps.append(("clf", spec["estimator"]))
    return ImbPipeline(steps)


def run():
    with open(PROCESSED_DATA_PATH, "rb") as f:
        data = pickle.load(f)

    X_train, y_train = data["X_train"], data["y_train"]
    X_val, y_val = data["X_val"], data["y_val"]
    X_test, y_test = data["X_test"], data["y_test"]

    # Feature engineering evaluee, pas supposee utile : on compare avec/sans plus bas
    # via le meme protocole CV, pour ne garder les features ajoutees que si elles
    # ameliorent reellement le score de validation croisee.
    X_train_fe = add_engineered_features(X_train)
    X_val_fe = add_engineered_features(X_val)
    X_test_fe = add_engineered_features(X_test)

    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()

    results = []

    for feature_set_name, (Xtr, Xva, Xte) in [
        ("features_brutes", (X_train, X_val, X_test)),
        ("features_augmentees", (X_train_fe, X_val_fe, X_test_fe)),
    ]:
        print(f"\n{'=' * 90}\nJeu de features : {feature_set_name} ({Xtr.shape[1]} colonnes)\n{'=' * 90}")

        for name, spec in CANDIDATES.items():
            pipe = build_pipeline(spec)
            search = RandomizedSearchCV(
                pipe,
                param_distributions=spec["param_distributions"],
                n_iter=N_ITER_SEARCH,
                scoring="f1",
                cv=skf,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                refit=True,
            )
            search.fit(Xtr, y_train)

            best_pipe = search.best_estimator_
            cv_f1_mean = search.best_score_
            cv_f1_std = search.cv_results_["std_test_score"][search.best_index_]

            # F1 d'entrainement (sur les donnees d'origine, sans SMOTE) : sert de
            # signal de sur-apprentissage si tres superieur au F1 de validation/test.
            train_proba = best_pipe.predict_proba(Xtr)[:, 1]
            train_f1_at_05 = f1_score(y_train, (train_proba >= 0.5).astype(int), zero_division=0)

            # Seuil choisi sur VAL uniquement (jamais vu par la recherche d'hyperparametres)
            val_proba = best_pipe.predict_proba(Xva)[:, 1]
            threshold, _ = best_threshold_for(y_val, val_proba)
            val_metrics = metrics_at(y_val, val_proba, threshold)

            gap_train_val = train_f1_at_05 - val_metrics["f1_score"]

            row = {
                "feature_set": feature_set_name,
                "model": name,
                "cv_f1_mean": cv_f1_mean,
                "cv_f1_std": cv_f1_std,
                "train_f1": train_f1_at_05,
                "val_f1": val_metrics["f1_score"],
                "val_accuracy": val_metrics["accuracy"],
                "val_precision": val_metrics["precision"],
                "val_recall": val_metrics["recall"],
                "threshold": threshold,
                "gap_train_val": gap_train_val,
                "best_params": search.best_params_,
                "pipeline": best_pipe,
                "Xte": Xte,
            }
            results.append(row)

            print(
                f"{name:20s} | CV F1 {cv_f1_mean:.3f} (+/-{cv_f1_std:.3f}) "
                f"| train F1 {train_f1_at_05:.3f} | val F1 {val_metrics['f1_score']:.3f} "
                f"| ecart train-val {gap_train_val:+.3f} | seuil {threshold:.2f}"
            )
            print(f"    best_params: {search.best_params_}")

    # ──────────────────────────────────────────────
    # Selection du champion sur le VAL uniquement
    # ──────────────────────────────────────────────
    champion = max(results, key=lambda r: r["val_f1"])
    print(f"\n{'=' * 90}\nCHAMPION (meilleur F1 sur VAL, jamais vu pendant la recherche) : "
          f"{champion['model']} / {champion['feature_set']}\n{'=' * 90}")

    # ──────────────────────────────────────────────
    # Evaluation finale sur TEST - une seule fois, sans retoucher le seuil
    # ──────────────────────────────────────────────
    test_proba = champion["pipeline"].predict_proba(champion["Xte"])[:, 1]
    test_metrics = metrics_at(y_test, test_proba, champion["threshold"])

    print("\nComparaison train / CV / val / test du champion (diagnostic de sur-apprentissage) :")
    print(f"  train F1 : {champion['train_f1']:.4f}")
    print(f"  CV F1    : {champion['cv_f1_mean']:.4f} (+/- {champion['cv_f1_std']:.4f})")
    print(f"  val F1   : {champion['val_f1']:.4f}")
    print(f"  test F1  : {test_metrics['f1_score']:.4f}  <- jamais vu avant cette ligne")
    print(f"  ecart train -> test : {champion['train_f1'] - test_metrics['f1_score']:+.4f}")
    for k, v in test_metrics.items():
        print(f"  test {k:10s}: {v:.4f}")

    # ──────────────────────────────────────────────
    # Importance des features (permutation, sans dependance supplementaire)
    # ──────────────────────────────────────────────
    perm = permutation_importance(
        champion["pipeline"], champion["Xte"], y_test,
        n_repeats=30, random_state=RANDOM_STATE, scoring="f1", n_jobs=-1,
    )
    importances = sorted(
        zip(champion["Xte"].columns, perm.importances_mean, perm.importances_std),
        key=lambda t: t[1], reverse=True,
    )
    print("\nImportance des features (permutation, mesuree sur TEST, impact sur le F1) :")
    for feat, mean_imp, std_imp in importances:
        print(f"  {feat:24s} : {mean_imp:+.4f} (+/- {std_imp:.4f})")

    # ──────────────────────────────────────────────
    # Logging MLflow - candidats + champion, SANS promotion automatique
    # ──────────────────────────────────────────────
    for row in results:
        run_name = f"{row['model']}_{row['feature_set']}_v2"
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({f"best__{k.replace('clf__', '')}": v for k, v in row["best_params"].items()})
            mlflow.log_params({
                "feature_set": row["feature_set"],
                "cv_folds": N_SPLITS,
                "smote": True,
                "leak_free_split": True,
            })
            mlflow.log_metrics({
                "cv_f1_mean": row["cv_f1_mean"],
                "cv_f1_std": row["cv_f1_std"],
                "train_f1": row["train_f1"],
                "val_f1": row["val_f1"],
                "val_accuracy": row["val_accuracy"],
                "val_precision": row["val_precision"],
                "val_recall": row["val_recall"],
                "best_threshold": row["threshold"],
                "gap_train_val": row["gap_train_val"],
            })
            if row is champion:
                mlflow.log_metrics({f"test_{k}": v for k, v in test_metrics.items()})
                for feat, mean_imp, _ in importances:
                    mlflow.log_metric(f"perm_importance_{feat}", mean_imp)
                # On ne logue jamais SMOTE : c'est un outil d'entrainement (rééchantillonnage
                # du train), il n'a aucun role a l'inference et n'a pas de .predict/.transform
                # utile sur une nouvelle donnee. Seules les etapes utiles a l'inference (le
                # scaler eventuel, puis le classifieur) sont conservees dans l'artefact loggue.
                inference_steps = [
                    (name, step) for name, step in row["pipeline"].steps if name != "smote"
                ]
                if row["model"] == "XGBoost" and len(inference_steps) == 1:
                    mlflow.xgboost.log_model(
                        xgb_model=inference_steps[0][1],
                        artifact_path="model",
                        registered_model_name="water_quality_model",
                    )
                else:
                    # Pipeline scikit-learn "pure" (pas imblearn) : aucune classe imblearn
                    # dans l'objet loggue, uniquement des types scikit-learn standards.
                    inference_pipeline = SkPipeline(inference_steps)
                    mlflow.sklearn.log_model(
                        sk_model=inference_pipeline,
                        artifact_path="model",
                        registered_model_name="water_quality_model",
                    )

    print(f"\n{'=' * 90}")
    print("Tous les candidats sont logues dans MLflow (experience 'experiment_water_quality').")
    print("Aucun n'a ete promu en Production automatiquement.")
    print(f"Pour promouvoir le champion ({champion['model']} / {champion['feature_set']}) apres revue :")
    print('  client.transition_model_version_stage(name="water_quality_model", version=<derniere version>, stage="Production")')
    print(f"{'=' * 90}")


if __name__ == "__main__":
    run()
