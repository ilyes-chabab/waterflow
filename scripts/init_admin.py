import hashlib
import secrets
from data.db.WaterFlowDB import WaterFlowDB

def init_first_admin():
    # 1. Génération de la clé en clair (64 caractères hex)
    plain_key = secrets.token_hex(32)
    
    # 2. Calcul du hash SHA-256
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()
    
    # 3. Insertion directe dans la BDD
    try:
        db = WaterFlowDB()
        # On crée un utilisateur nommé 'SuperAdmin' avec le rôle 'Admin'
        db.add_user(username="SuperAdmin", api_key=hashed_key, right="Admin")
        db.close()
        
        print("================================================================")
        print(" COMPTE ADMINISTRATEUR INITIALISÉ AVEC SUCCÈS")
        print("================================================================")
        print(f"Nom d'utilisateur : SuperAdmin")
        print(f"Voici votre clé API en clair (Copiez-la, elle ne réapparaîtra plus) :")
        print(f"\n{plain_key}\n")
        print("================================================================")
        
    except Exception as e:
        print(f"Erreur lors de l'initialisation : {str(e)}")

if __name__ == "__main__":
    init_first_admin()