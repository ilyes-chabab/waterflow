"""
prepare_data.py - Prepare le jeu de donnees Waterflow (potabilite) sans fuite de donnees.

Corrige un probleme identifie dans le notebook d'origine (notebooks/water_quality_analysis.ipynb) :
l'imputation, le clipping des outliers et la standardisation y etaient calcules sur
l'ensemble du dataset AVANT le split train/validation. Les statistiques utilisees pour
nettoyer le train (mediane d'imputation, bornes de clipping, moyenne/ecart-type de la
standardisation) integraient donc des lignes du jeu de validation : une fuite de donnees
qui rend les metriques de validation optimistes par rapport a ce que le modele voit
reellement en production.

Deuxieme probleme corrige : le notebook ne produisait que 2 sous-ensembles (train 80% /
validation 20%), et `X_test.csv` etait en realite une copie de `X_val.csv`. Le seuil de
decision et les choix de modele/hyperparametres etaient donc toujours values sur les
memes 656 lignes qui servaient aussi de "test" - aucune donnee n'etait jamais totalement
tenue a l'ecart des decisions de modelisation.

Ce script cree un vrai split a trois blocs (train 70% / val 15% / test 15%, stratifie),
et n'ajuste (`.fit`) l'imputer et les bornes de clipping que sur le train. Le val et le
test ne sont que transformes (`.transform`) avec les statistiques apprises sur le train.

Choix delibere : aucune standardisation (StandardScaler) n'est appliquee aux jeux exportes.
XGBoost et RandomForest (les modeles compares dans scripts/model_selection.py) sont
invariants a l'echelle des features - ils n'en ont pas besoin. Plus important : l'API de
production (`api/main.py::add_measurement`) envoie au modele les 9 valeurs brutes du
Client, sans jamais les standardiser. Entrainer un modele sur des donnees standardisees
puis le servir en production avec des donnees brutes est une fuite de type train/serve
skew - le modele recoit alors des entrees hors de la distribution qu'il a apprise. En
gardant les jeux d'entrainement a l'echelle brute (juste imputes + ecretes), le modele
entraine ici est directement compatible avec ce que l'API envoie reellement, sans qu'il
soit necessaire de modifier l'API pour appliquer un scaler a chaque requete.
"""

import pickle

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split

RAW_PATH = "data/raw/water_potability.csv"
OUT_PKL = "data/processed/processed_data.pkl"
RANDOM_STATE = 42


def clip_bounds_from(df: pd.DataFrame, cols) -> dict:
    return {col: (df[col].quantile(0.01), df[col].quantile(0.99)) for col in cols}


def apply_clip(df: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    df = df.copy()
    for col, (lo, hi) in bounds.items():
        df[col] = df[col].clip(lower=lo, upper=hi)
    return df


def main():
    df = pd.read_csv(RAW_PATH)
    feature_cols = list(df.columns[:-1])
    X = df[feature_cols]
    y = df["Potability"]

    # 1) Split D'ABORD, stratifie sur la cible : 70% train / 15% val / 15% test.
    #    Le test n'est plus jamais touche avant l'evaluation finale dans model_selection.py.
    X_train, X_tmp, y_train, y_tmp = train_test_split(
        X, y, test_size=0.30, random_state=RANDOM_STATE, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_tmp, y_tmp, test_size=0.50, random_state=RANDOM_STATE, stratify=y_tmp
    )

    # 2) Imputation - ajustee sur le train uniquement.
    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=feature_cols, index=X_train.index)
    X_val_imp = pd.DataFrame(imputer.transform(X_val), columns=feature_cols, index=X_val.index)
    X_test_imp = pd.DataFrame(imputer.transform(X_test), columns=feature_cols, index=X_test.index)

    # 3) Ecretage des outliers (1er/99e percentile) - bornes calculees sur le train uniquement.
    bounds = clip_bounds_from(X_train_imp, feature_cols)
    X_train_c = apply_clip(X_train_imp, bounds)
    X_val_c = apply_clip(X_val_imp, bounds)
    X_test_c = apply_clip(X_test_imp, bounds)

    print(f"Train : {X_train_c.shape[0]} lignes | Val : {X_val_c.shape[0]} lignes | Test : {X_test_c.shape[0]} lignes")
    for split_name, yy in [("train", y_train), ("val", y_val), ("test", y_test)]:
        pct = yy.value_counts(normalize=True).sort_index()
        print(f"  {split_name:5s} - Potability 0: {pct.get(0, 0):.3f} | 1: {pct.get(1, 0):.3f}")

    processed_data = {
        "X_train": X_train_c.reset_index(drop=True),
        "X_val": X_val_c.reset_index(drop=True),
        "X_test": X_test_c.reset_index(drop=True),
        "y_train": y_train.reset_index(drop=True),
        "y_val": y_val.reset_index(drop=True),
        "y_test": y_test.reset_index(drop=True),
        "feature_cols": pd.Index(feature_cols),
        "imputer": imputer,
        "clip_bounds": bounds,
    }

    with open(OUT_PKL, "wb") as f:
        pickle.dump(processed_data, f)
    print(f"\nOK : {OUT_PKL} regenere (train/val/test disjoints, pretraitement sans fuite).")

    # CSV de reference, alignes sur le pickle (auparavant X_test.csv etait une copie de X_val.csv)
    X_train_c.to_csv("data/processed/X_train.csv", index=False)
    X_val_c.to_csv("data/processed/X_val.csv", index=False)
    X_test_c.to_csv("data/processed/X_test.csv", index=False)
    y_train.to_csv("data/processed/y_train.csv", index=False, header=["Potability"])
    y_val.to_csv("data/processed/y_val.csv", index=False, header=["Potability"])
    y_test.to_csv("data/processed/y_test.csv", index=False, header=["Potability"])
    print("OK : CSV de reference regeneres (X_train/X_val/X_test/y_train/y_val/y_test).")


if __name__ == "__main__":
    main()
