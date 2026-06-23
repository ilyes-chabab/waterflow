import csv
import os
import re
from PIL import Image
import pytesseract

# Nom du fichier CSV cible
FICHIER_CSV = "resultats_analyses_complets.csv"

def extraire_texte_depuis_png(chemin_image):
    """Effectue l'OCR sur l'image PNG pour en extraire le texte brut."""
    # Conseil : lang='fra' permet de bien interpréter les caractères accentués français (é, è, °)
    img = Image.open(chemin_image)
    return pytesseract.image_to_string(img, lang='fra')

def parser_rapport_aquatest(texte_brut):
    """Analyse le texte du laboratoire AquaTest et extrait toutes les variables clés."""
    
    # Initialisation de notre dictionnaire de données avec des valeurs par défaut (None)
    donnees = {
        "client_id": None,
        "date_prelevement": None,
        "ph": None,
        "conductivite": None,
        "temperature": None,
        "turbidite": None,
        "durete": None,
        "nitrates": None,
        "nitrites": None,
        "ammonium": None,
        "chlorures": None,
        "sulfates": None,
        "fer": None,
        "manganese": None
    }
    
    # --- 1. Extraction des métadonnées (Client et Date) ---
    # Cherche "Client :" suivi de caractères jusqu'au tiret ou la fin de ligne
    match_client = re.search(r"Client\s*:\s*([A-Z0-9-]+)", texte_brut)
    if match_client:
        donnees["client_id"] = match_client.group(1).strip()
        
    # Cherche "Date de prélèvement :" suivi d'une date au format JJ/MM/AAAA (et l'heure optionnelle)
    match_date = re.search(r"Date de prélèvement\s*:\s*([\d/]+\s*[\d:]*)", texte_brut, re.IGNORECASE)
    if match_date:
        donnees["date_prelevement"] = match_date.group(1).strip()

    # --- 2. Extraction des mesures physico-chimiques ---
    # Liste des patterns Regex pour chaque élément métrique. 
    # Le pattern `([\d,.]+)` capture un nombre entier ou décimal contenant une virgule ou un point.
    patterns = {
        "ph": r"pH\s*:\s*([\d,.]+)",
        "conductivite": r"Conductivité\s*:\s*([\d,.]+)",
        "temperature": r"Température\s*:\s*([\d,.]+)",
        "turbidite": r"Turbidité\s*:\s*([\d,.]+)",
        "durete": r"Dureté\s*:\s*([\d,.]+)",
        "nitrates": r"Nitrates.*:\s*([\d,.]+)",
        "nitrites": r"Nitrites.*:\s*([\d,.]+)",
        "ammonium": r"Ammonium.*:\s*([\d,.]+)",
        "chlorures": r"Chlorures.*:\s*([\d,.]+)",
        "sulfates": r"Sulfates.*:\s*([\d,.]+)",
        "fer": r"Fer total\s*:\s*([\d,.]+)",
        "manganese": r"Manganèse\s*:\s*([\d,.]+)"
    }
    
    # Application de chaque regex sur le texte brut
    for cle, pattern in patterns.items():
        match = re.search(pattern, texte_brut, re.IGNORECASE)
        if match:
            # On récupère le texte du nombre, on remplace la virgule française par un point, 
            # puis on le convertit en float (nombre décimal) pour Python.
            valeur_str = match.group(1).replace(",", ".")
            donnees[cle] = float(valeur_str)
            
    return donnees

def enregistrer_dans_csv(donnees, nom_fichier):
    """Enregistre le dictionnaire complet dans le fichier CSV."""
    # Définition des colonnes du fichier CSV basées sur les clés du dictionnaire
    colonnes = list(donnees.keys())
    
    fichier_existe = os.path.exists(nom_fichier)
    
    with open(nom_fichier, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=colonnes)
        
        # Si c'est la première fois qu'on écrit, on met les entêtes de colonnes
        if not fichier_existe:
            writer.writeheader()
            
        writer.writerow(donnees)
    print(f"🎉 Données de {donnees['client_id']} sauvegardées dans '{nom_fichier}' !")

# --- ZONE DE TEST / EXÉCUTION ---
fichier_png = "rapport_aquatest.png"

try:
    print("--- Étape 1 : Lecture OCR du rapport de laboratoire ---")
    texte_extrait = extraire_texte_depuis_png(fichier_png)
    
    print("--- Étape 2 : Analyse et structuration des données via Regex ---")
    donnees_finales = parser_rapport_aquatest(texte_extrait)
    
    print("\nDonnées extraites en direct :")
    for cle, val in donnees_finales.items():
        print(f"  {cle} -> {val}")
        
    print("\n--- Étape 3 : Sauvegarde dans le fichier CSV ---")
    enregistrer_dans_csv(donnees_finales, FICHIER_CSV)

except FileNotFoundError:
    print(f"\n❌ Erreur : Impossible de trouver le fichier '{fichier_png}'.")
    print("Pour tester, assurez-vous d'avoir une image contenant le texte de votre exemple à cet emplacement.")