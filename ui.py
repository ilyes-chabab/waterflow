import streamlit as st
import requests

# Initialisation des variables de session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.api_key = None
    st.session_state.role = None  # Stocke "Admin" , "Data_Quality" ou "Client"

API_BASE_URL = "http://127.0.0.1:8000"
URL_LOGIN = f"{API_BASE_URL}/api/login"

# ── 1. GESTION DES PAGES VIA ST.NAVIGATION ───────────────────────────

page_connexion = st.Page(lambda: login_screen(), title="Connexion", icon=None)
page_panel = st.Page("views/panel_test.py", title="Panel de Test", icon=None)
page_historique = st.Page("views/historique.py", title="Historique des Analyses", icon=None)
page_admin = st.Page("views/accueil_admin.py", title="Accueil Admin", icon=None)
page_dashboard_qualite = st.Page("dashboard_qualite.py", title="Dashboard Qualite", icon=None)

# Définition du routage dynamique selon le rôle
if not st.session_state.logged_in:
    # Si non connecté, seule la page de connexion existe
    nav = st.navigation([page_connexion])
else:
    if st.session_state.role == "Admin":
        nav = st.navigation([page_admin])
    elif st.session_state.role == "Quality_Analyst":
        nav = st.navigation([page_dashboard_qualite])
    else:
        # Par défaut, rôle "Client" ou autre
        nav = st.navigation([page_panel, page_historique])

# ── 2. ÉCRAN DE CONNEXION (FONCTION) ──────────────────────────────────

def login_screen():
    st.title("Connexion au Portail Waterflow")
    st.write("Veuillez saisir votre cle API pour debloquer vos outils.")

    with st.form("login_form"):
        api_key_input = st.text_input("Cle API Secrete", type="password")
        submit_login = st.form_submit_button("Se connecter", type="primary")

        if submit_login:
            if not api_key_input:
                st.error("Veuillez saisir votre cle API.")
            else:
                try:
                    headers = {"X-API-Key": api_key_input}
                    response = requests.post(URL_LOGIN, headers=headers)

                    if response.status_code == 200:
                        res_data = response.json()
                        
                        # Stockage des informations critiques en session
                        st.session_state.logged_in = True
                        st.session_state.user_id = res_data["user_id"]
                        st.session_state.username = res_data["username"]
                        st.session_state.api_key = api_key_input
                        
                        # ATTENTION : On recupere la valeur du champ "role" ou "right" renvoye par l'API
                        st.session_state.role = res_data.get("role") 
                        
                        st.success("Connexion reussie.")
                        st.rerun()
                    elif response.status_code == 401:
                        st.error("Cle API incorrecte ou invalide.")
                    else:
                        st.error(f"Erreur serveur ({response.status_code}).")
                except requests.exceptions.ConnectionError:
                    st.error("L'API Flask ne repond pas sur le port 8000. Lancez app.py d'abord.")

# ── 3. EXÉCUTION DE LA NAVIGATION ────────────────────────────────────

# Ajout d'éléments communs dans la sidebar si l'utilisateur est connecté
if st.session_state.logged_in:
    with st.sidebar:
        st.write(f"**Utilisateur :** {st.session_state.username}")
        st.write(f"**Role :** {st.session_state.role}")
        st.write(f"**ID Client :** {st.session_state.user_id}")
        st.divider()
        if st.button("Se deconnecter", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.api_key = None
            st.session_state.role = None
            st.rerun()

# Affiche la page active sélectionnée dans le menu latéral
nav.run()