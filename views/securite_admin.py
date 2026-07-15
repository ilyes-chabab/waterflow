import os

import streamlit as st
import requests

st.title("Sécurité & Gestion des Accès")
st.caption("Attention : Les actions effectuées ici modifient instantanément les droits et accès des clients.")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
URL_CLIENTS = f"{API_BASE_URL}/api/clients"

headers = {
    "X-API-Key": st.session_state.get("api_key", ""),
    "Content-Type": "application/json"
}

# --- ZONE D'AFFICHAGE DES CLÉS COMPROMISES OU CRÉÉES (FLASH) ---
if "last_created_client" in st.session_state and st.session_state.last_created_client:
    client_info = st.session_state.last_created_client
    st.success(" Nouveau compte créé avec succès !")
    st.info(" Notez bien la clé ci-dessous. Elle ne sera plus jamais visible en clair.")
    st.text_input("Clé API du nouveau client", value=client_info.get("api_key_plain"), key="new_key_page")
    if st.button("Effacer l'affichage", key="clear_new_key_page"):
        st.session_state.last_created_client = None
        st.rerun()
    st.divider()

if "last_rotated_key" in st.session_state and st.session_state.last_rotated_key:
    rot = st.session_state.last_rotated_key
    st.warning(f"Clé renouvelée pour le client ID {rot['id']} !")
    st.info("Copiez la nouvelle clé immédiatement. Elle ne réapparaîtra plus jamais.")
    st.text_input("Nouvelle clé API générée", value=rot["key"], key="rot_key_page")
    if st.button("Masquer la clé", key="clear_rot_key_page"):
        st.session_state.last_rotated_key = None
        st.rerun()
    st.divider()


# --- SOUS-SECTION A : CRÉATION ---
st.write("###Générer un nouveau compte client ou analyste")
with st.form("create_user_form_page", clear_on_submit=True):
    new_username = st.text_input("Nom de l'entreprise ou de l'utilisateur")
    new_role = st.selectbox("Attribuer un rôle système", options=["Client", "Quality_Analyst", "Admin"])
    submit_btn = st.form_submit_button("Créer le compte et la clé", type="primary")

    if submit_btn:
        if not new_username.strip():
            st.error("Nom invalide.")
        else:
            try:
                res = requests.post(URL_CLIENTS, json={"username": new_username.strip(), "role": new_role}, headers=headers)
                if res.status_code == 201:
                    st.session_state.last_created_client = res.json().get("client")
                    st.rerun()
                else:
                    st.error(f"Erreur ({res.status_code})")
            except Exception:
                st.error("API injoignable.")

st.divider()


# --- SOUS-SECTION B : ROTATION ---
st.write("### Renouveler une clé API existante (Rotation)")
try:
    res_list = requests.get(URL_CLIENTS, headers=headers)
    if res_list.status_code == 200:
        current_clients = res_list.json().get("clients", [])
        user_options = {f"ID {u['id']} - {u['username']} ({u['role']})": u['id'] for u in current_clients}
        
        if user_options:
            col_sel, col_act = st.columns([2, 1])
            with col_sel:
                selected_user_str = st.selectbox("Sélectionner le compte cible", options=list(user_options.keys()))
                target_id = user_options[selected_user_str]
            with col_act:
                st.write("###")
                if st.button("Régénérer la clé", type="secondary", use_container_width=True):
                    try:
                        rot_res = requests.post(f"{API_BASE_URL}/api/clients/{target_id}/rotate-key", headers=headers)
                        if rot_res.status_code == 200:
                            st.session_state.last_rotated_key = {"id": target_id, "key": rot_res.json().get("api_key_plain")}
                            st.rerun()
                        else:
                            st.error(f"Erreur de rotation : {rot_res.text}")
                    except Exception as e:
                        st.error(f"Erreur API : {e}")
        else:
            st.info("Aucun client disponible.")
except Exception:
    st.error("Impossible de charger les comptes.")