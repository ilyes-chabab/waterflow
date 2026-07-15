"""
validate_data.py - Contrôle qualité de data/raw/water_potability.csv (étape CI).

Vérifie le schéma (colonnes, types) et l'absence de dérive grossière sur les valeurs
manquantes, avant que le pipeline d'entraînement ne consomme ce fichier.
Sort avec un code non nul (et un message explicite) si une vérification échoue.
"""

import sys

import pandas as pd

CSV_PATH = "data/raw/water_potability.csv"

FEATURE_COLUMNS = [
    "ph", "Hardness", "Solids", "Chloramines", "Sulfate",
    "Conductivity", "Organic_carbon", "Trihalomethanes", "Turbidity",
]
TARGET_COLUMN = "Potability"
MIN_ROWS = 100
MAX_MISSING_RATIO = 0.30  # au-delà, on suspecte un export corrompu plutôt que le NaN habituel


def main() -> int:
    errors = []

    df = pd.read_csv(CSV_PATH)

    if len(df) < MIN_ROWS:
        errors.append(f"Seulement {len(df)} lignes (minimum attendu : {MIN_ROWS}).")

    expected_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = expected_columns - set(df.columns)
    if missing_columns:
        errors.append(f"Colonnes manquantes : {sorted(missing_columns)}.")

    for col in FEATURE_COLUMNS:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"Colonne '{col}' non numérique (dtype={df[col].dtype}).")

    if TARGET_COLUMN in df.columns:
        unexpected_labels = set(df[TARGET_COLUMN].dropna().unique()) - {0, 1}
        if unexpected_labels:
            errors.append(f"Valeurs inattendues dans '{TARGET_COLUMN}' : {unexpected_labels}.")

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            continue
        missing_ratio = df[col].isna().mean()
        print(f"{col:20s} : {missing_ratio:.1%} de valeurs manquantes")
        if missing_ratio > MAX_MISSING_RATIO:
            errors.append(
                f"Colonne '{col}' : {missing_ratio:.1%} de valeurs manquantes "
                f"(seuil max : {MAX_MISSING_RATIO:.0%})."
            )

    if errors:
        print("\nÉchec de la validation des données :")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"\nOK : {len(df)} lignes, schéma conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())