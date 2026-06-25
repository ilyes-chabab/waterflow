import streamlit as st
import requests

st.set_page_config(page_title="Waterflow - Connexion", layout="centered")

API_BASE_URL = "http://127.0.0.1:8000"
URL_LOGIN = f"{API_BASE_URL}/api/login"

# Initialisation des variables de session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.api_key = None

if st.session_state.logged_in:
    st.title("🎉 Vous êtes déjà connecté !")
    st.subheader(f"Bienvenue, {st.session_state.username}")
    st.info("👈 Utilisez le menu de gauche pour accéder au **Panel de Test**.")
    
    if st.button("Se déconnecter", type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.api_key = None
        st.rerun()
    st.stop()

st.title("Connexion au Portail Waterflow")
st.write("Veuillez saisir votre clé API pour débloquer les outils de prédiction.")

with st.form("login_form"):
    api_key_input = st.text_input("Clé API Secrète", type="password", help="Saisissez la clé API fournie par votre administrateur.")
    submit_login = st.form_submit_button("Se connecter", type="primary")

    if submit_login:
        if not api_key_input:
            st.error("Veuillez saisir votre clé API.")
        else:
            try:
                # Appel à l'API Flask en passant la clé dans les headers
                headers = {"X-API-Key": api_key_input}
                response = requests.post(URL_LOGIN, headers=headers)

                if response.status_code == 200:
                    res_data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.user_id = res_data["user_id"]
                    st.session_state.username = res_data["username"]
                    st.session_state.api_key = api_key_input
                    
                    st.success("Connexion réussie ! Redirection...")
                    st.rerun() # Recharge pour appliquer le statut connecté
                elif response.status_code == 401:
                    st.error("Clé API incorrecte ou invalide.")
                else:
                    st.error(f"Erreur serveur ({response.status_code}).")
            except requests.exceptions.ConnectionError:
                st.error("L'API Flask ne répond pas sur le port 8000. Lancez app.py d'abord.")