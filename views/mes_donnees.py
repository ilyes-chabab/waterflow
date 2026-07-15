import os

import streamlit as st
import requests

st.set_page_config(page_title="Waterflow - Mes Données (RGPD)", layout="centered")

# ── 1. VÉRIFICATION DE LA SÉCURITÉ/CONNEXION ──────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("Accès refusé. Vous devez d'abord vous connecter sur la page d'accueil.")
    st.markdown("[Aller à la page de connexion](/)")
    st.stop()

# ── 2. CONSTANTES & APPEL API ─────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
URL_ME = f"{API_BASE_URL}/api/me"

st.title("Mes données personnelles")
st.caption("Droit d'accès et droit à l'oubli RGPD.")

headers = {"X-API-Key": st.session_state.api_key}

# ─── SECTION 1 : DROIT D'ACCÈS (GET /api/me) ───────────────────────────
try:
    response = requests.get(URL_ME, headers=headers)

    if response.status_code == 200:
        data = response.json()
        infos = data.get("donnees_personnelles", {})

        st.write("### Données stockées vous concernant")
        st.write(f"**Identifiant client :** {infos.get('id_client')}")
        st.write(f"**Nom d'utilisateur :** {infos.get('nom_utilisateur')}")
        st.write(f"**Rôle :** {infos.get('role')}")

        st.info(data.get("regle_conservation", ""))
    else:
        st.error(f"Impossible de charger vos données ({response.status_code}).")

except requests.exceptions.ConnectionError:
    st.error("Erreur de connexion. L'API ne répond pas sur le port 8000.")

st.divider()

# ─── SECTION 2 : DROIT À L'OUBLI (DELETE /api/me) ──────────────────────
st.write("### Supprimer mon compte")
st.warning(
    "Cette action est irréversible : votre compte et vos prélèvements seront "
    "définitivement supprimés. Vos logs d'audit sont conservés mais anonymisés."
)

confirm = st.checkbox(
    "Je comprends que cette action est irréversible et je souhaite supprimer mon compte."
)

if st.button("Supprimer mon compte", type="primary", disabled=not confirm):
    try:
        del_response = requests.delete(URL_ME, headers=headers)
        if del_response.status_code == 200:
            st.success("Compte et données supprimés.")
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.api_key = None
            st.session_state.role = None
            st.rerun()
        else:
            st.error(f"Erreur lors de la suppression ({del_response.status_code}).")
    except requests.exceptions.ConnectionError:
        st.error("Erreur de connexion. L'API ne répond pas sur le port 8000.")
