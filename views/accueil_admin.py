import os

import streamlit as st
import requests
import pandas as pd

st.title("Registre des Utilisateurs & Audit")
st.write("Consultez la liste des comptes actifs et l'historique des actions sur la plateforme.")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
URL_CLIENTS = f"{API_BASE_URL}/api/clients"
URL_LOGS = f"{API_BASE_URL}/api/audit-logs"

headers = {
    "X-API-Key": st.session_state.get("api_key", ""),
    "Content-Type": "application/json"
}

# ─── SECTION 1 : REGISTRE DES COMPTES ─────────────────────────────────
st.write("### Utilisateurs enregistrés")

try:
    response = requests.get(URL_CLIENTS, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        clients_list = data.get("clients", [])
        total_clients = data.get("total_clients", 0)
        
        st.metric(label="Nombre total de comptes enregistrés", value=total_clients)
        
        if total_clients == 0:
            st.info("Aucun utilisateur enregistré pour le moment.")
        else:
            rows = []
            for c in clients_list:
                rows.append({
                    "ID": c.get("id"),
                    "Nom d'utilisateur": c.get("username"),
                    "Rôle": c.get("role"),
                    "Empreinte de la clé (SHA-256)": c.get("api_key_hash")
                })
            
            df = pd.DataFrame(rows).set_index("ID")
            st.dataframe(df, use_container_width=True)
                
    elif response.status_code == 403:
        st.error("Droits insuffisants pour lister les utilisateurs.")
    else:
        st.error(f"Erreur de récupération des utilisateurs ({response.status_code})")

except requests.exceptions.ConnectionError:
    st.error("L'API FastAPI ne répond pas. Impossible de charger la liste des utilisateurs.")

st.divider()

# ─── SECTION 2 : LOGS D'AUDIT SYSTEME ─────────────────────────────────
st.write("### Journal d'audit de l'API (Activity Logs)")

try:
    response_logs = requests.get(URL_LOGS, headers=headers)
    
    if response_logs.status_code == 200:
        logs_data = response_logs.json()
        logs_list = logs_data.get("logs", [])
        total_logs = logs_data.get("total_logs", len(logs_list))
        
        if total_logs == 0:
            st.info("Aucun log d'audit enregistré pour le moment.")
        else:
            log_rows = []
            for log in logs_list:
                # Structure basée sur les colonnes de ta table audit_logs
                log_rows.append({
                    "ID Log": log.get("id"),
                    "User ID": log.get("user_id") if log.get("user_id") is not None else "Anonyme/Supprimé",
                    "Endpoint": log.get("endpoint"),
                    "Méthode": log.get("method"),
                    "Statut HTTP": log.get("status"),
                    "Durée (s)": log.get("duration"),
                    "Adresse IP": log.get("ip"),
                    "Date de l'action": log.get("created_at")
                })
            
            df_logs = pd.DataFrame(log_rows).set_index("ID Log")
            
            # Affichage du tableau des logs
            st.dataframe(df_logs, use_container_width=True)
            
    elif response_logs.status_code == 403:
        st.error("Droits insuffisants pour consulter le journal d'audit.")
    else:
        st.error(f"Erreur de récupération des logs ({response_logs.status_code})")

except requests.exceptions.ConnectionError:
    st.error("L'API FastAPI ne répond pas. Impossible de charger le journal d'audit.")

st.write("")
if st.button("Actualiser toute la page"):
    st.rerun()