import os

import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Waterflow - Historique des Analyses", layout="wide")

# ── 1. VÉRIFICATION DE LA SÉCURITÉ/CONNEXION ──────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("Accès refusé. Vous devez d'abord vous connecter sur la page d'accueil.")
    st.markdown("[Aller à la page de connexion](/)")
    st.stop()

# ── 2. CONSTANTES & APPEL API ─────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
URL_HISTORY = f"{API_BASE_URL}/api/measurements"

st.title("Historique de vos Prélèvements & Prédictions")
st.caption(f"Consultation sécurisée (RGPD) des données du laboratoire : **{st.session_state.username}**")

@st.fragment
def load_and_display_history():
    """Fonction isolée pour charger et rafraîchir l'historique sans recharger toute la page."""
    headers = {
        "X-API-Key": st.session_state.api_key,
        "Content-Type": "application/json"
    }

    try:
        with st.spinner("Récupération de votre historique depuis la base SQLite..."):
            response = requests.get(URL_HISTORY, headers=headers)

        if response.status_code == 200:
            data = response.json()
            history_list = data.get("history", [])
            total_records = data.get("total_records", 0)

            # --- CAS OU L'HISTORIQUE EST VIDE ---
            if total_records == 0 or not history_list:
                st.info("Vous n'avez aucun prélèvement enregistré pour le moment. Utilisez le panel de test ou l'OCR pour ajouter des mesures.")
                return

            st.metric(label="Nombre total d'analyses enregistrées", value=total_records)

            # --- APPLATISSAGE ET FORMATAGE DU JSON EN DATAFRAME ---
            rows = []
            for item in history_list:
                row = {
                    "ID Prédiction": item["id_prediction"],
                    "Potabilité": "Potable (Safe)" if item["potability_result"] == 1 else "Non Potable (Unsafe)",
                    "pH": item["measures"]["ph"],
                    "Hardness": item["measures"]["hardness"],
                    "Solids": item["measures"]["solids"],
                    "Chloramines": item["measures"]["chloramines"],
                    "Sulfate": item["measures"]["sulfate"],
                    "Conductivity": item["measures"]["conductivity"],
                    "Organic Carbon": item["measures"]["organic_carbon"],
                    "Trihalomethanes": item["measures"]["trihalomethanes"],
                    "Turbidity": item["measures"]["turbidity"]
                }
                rows.append(row)

            df = pd.DataFrame(rows).set_index("ID Prédiction")

            # --- AFFICHAGE AVEC REHAUSSEMENT DE COULEUR (STYLING) ---
            st.write("### Tableau récapitulatif")
            
            # Fonction pour colorer la colonne Potabilité en vert/rouge
            def color_potability(val):
                if val == "Potable (Safe)":
                    return 'background-color: #d4edda; color: #155724; font-weight: bold;'
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'

            styled_df = df.style.map(color_potability, subset=["Potabilité"]).format(
                precision=4, 
                subset=["pH", "Hardness", "Solids", "Chloramines", "Sulfate", "Conductivity", "Organic Carbon", "Trihalomethanes", "Turbidity"]
            )

            st.dataframe(styled_df, use_container_width=True, height=450)

            # Option de téléchargement CSV pour le client
            st.divider()
            csv = df.to_csv().encode('utf-8')
            st.download_button(
                label=" Exporter l'historique en CSV",
                data=csv,
                file_name=f"historique_waterflow_client_{st.session_state.user_id}.csv",
                mime='text/csv',
            )

        else:
            st.error(f"Impossible de charger l'historique ({response.status_code}) : {response.text}")

    except requests.exceptions.ConnectionError:
        st.error("Erreur de connexion. L'API ne répond pas sur le port 8000. Lancez app.py d'abord.")

if st.button("Rafraîchir l'historique", type="secondary"):
    st.rerun()

load_and_display_history()