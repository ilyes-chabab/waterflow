import pickle
import json

DATA_PATH = "data/processed/processed_data.pkl"

with open(DATA_PATH, "rb") as f:
    data = pickle.load(f)

# Si 'data' est un dictionnaire, on regarde ce qu'il y a dedans
print("Structure du fichier pickle :", type(data))
if isinstance(data, dict):
    print("Clés disponibles :", list(data.keys()))
    
    # On cherche l'objet imputer. Adaptez la clé (ex: "imputer" ou "preprocessor") 
    # si elle porte un autre nom dans vos clés affichées.
    imputer_key = "imputer" if "imputer" in data else None
    
    if imputer_key and hasattr(data[imputer_key], "statistics_"):
        imputer = data[imputer_key]
        # Dans scikit-learn, les moyennes calculées sont stockées dans .statistics_
        means = imputer.statistics_
        print("\nImputer trouvé ! Statistiques récupérées.")
    else:
        # Si l'imputer est imbriqué dans un autre objet ou si vous n'avez pas de clés
        raise ValueError("Impossible de localiser l'imputer dans le dictionnaire. Vérifiez les clés affichées ci-dessus.")
else:
    # Si 'data' est directement l'objet imputer ou le pipeline
    if hasattr(data, "statistics_"):
        means = data.statistics_
    elif hasattr(data, "named_steps") and "imputer" in data.named_steps:
        means = data.named_steps["imputer"].statistics_
    else:
        raise ValueError("L'objet pickle n'est pas un dictionnaire connu ni un imputer direct.")

# L'ordre exact des 9 features requises par votre modèle
ordered_keys = [
    "ph", "hardness", "solids", "chloramines", "sulfate",
    "conductivity", "organic_carbon", "trihalomethanes", "turbidity"
]

# Associer les moyennes de scikit-learn à vos clés
mean_values = {key: float(val) for key, val in zip(ordered_keys, means)}

print("\nMoyennes extraites de votre imputer existant :")
for feature, val in mean_values.items():
    print(f"  - {feature}: {val:.6f}")

# Sauvegarde dans le JSON pour l'API
OUTPUT_JSON = "mean_features.json"
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(mean_values, f, indent=4)

print(f"\nFichier des moyennes sauvegardé avec succès : {OUTPUT_JSON}")