import os

import streamlit as st
import requests
import pandas as pd

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
headers = {"X-API-Key": st.session_state.api_key}

st.title("Dashboard Qualite")
st.caption(f"Connecte en tant que : {st.session_state.username} ({st.session_state.role})")

tab_releves, tab_metriques, tab_versions = st.tabs(
    ["Prelevements", "Metriques du modele", "Comparaison des versions"]
)

# ──────────────────────────────────────────────
# TAB 1 : Tous les prélèvements + filtres
# ──────────────────────────────────────────────
with tab_releves:
    st.subheader("Filtres")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        client_id_filter = st.text_input("ID Client", value="")
    with col2:
        source_filter = st.selectbox("Provenance", ["Toutes", "manuel", "ocr"])
    with col3:
        date_from = st.date_input("Du", value=None)
    with col4:
        date_to = st.date_input("Au", value=None)

    params = {}
    if client_id_filter:
        params["client_id"] = client_id_filter
    if source_filter != "Toutes":
        params["source"] = source_filter
    if date_from:
        params["date_from"] = str(date_from)
    if date_to:
        params["date_to"] = str(date_to)

    if st.button("Actualiser les prelevements", type="primary"):
        st.session_state["_refresh_releves"] = True

    try:
        response = requests.get(
            f"{API_BASE_URL}/api/dashboard/measurements",
            headers=headers, params=params
        )
        if response.status_code == 200:
            data = response.json()
            st.write(f"**Total :** {data['total_records']} prelevement(s)")

            rows = []
            for item in data["data"]:
                rows.append({
                    "Prediction ID": item["id_prediction"],
                    "Client ID": item["client"]["id"],
                    "Client": item["client"]["username"],
                    "Role": item["client"]["role"],
                    "Provenance": item["source"],
                    "Date": item["created_at"],
                    "Potabilite": "Potable" if item["potability_result"] == 1 else "Non potable",
                    "Measures": item["measures"]
                })

            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Aucun prelevement ne correspond aux filtres.")

        elif response.status_code == 403:
            st.error("Acces refuse : role insuffisant.")
        else:
            st.error(f"Erreur serveur ({response.status_code}).")

    except requests.exceptions.ConnectionError:
        st.error("L'API Flask ne repond pas sur le port 8000.")

# ──────────────────────────────────────────────
# TAB 2 : Métriques du modèle en Production (MLflow)
# ──────────────────────────────────────────────
with tab_metriques:
    st.subheader("Modele en Production")
    try:
        response = requests.get(f"{API_BASE_URL}/api/dashboard/metrics", headers=headers)
        if response.status_code == 200:
            data = response.json()
            st.write(f"**Version :** {data['version']}  |  **Run ID :** `{data['run_id']}`")

            metrics = data.get("metrics", {})
            if metrics:
                cols = st.columns(len(metrics))
                for col, (name, value) in zip(cols, metrics.items()):
                    col.metric(name, f"{value:.4f}" if isinstance(value, float) else value)
            else:
                st.info("Aucune metrique trouvee pour cette version.")

            with st.expander("Parametres du modele"):
                st.json(data.get("params", {}))

        elif response.status_code == 404:
            st.warning("Aucune version 'Production' trouvee sur MLflow.")
        else:
            st.error(f"Erreur serveur ({response.status_code}).")

    except requests.exceptions.ConnectionError:
        st.error("L'API Flask ne repond pas sur le port 8000.")

# ──────────────────────────────────────────────
# TAB 3 : Comparaison des versions + rejeu de prédiction
# ──────────────────────────────────────────────
with tab_versions:
    st.subheader("Toutes les versions enregistrees")
    try:
        response = requests.get(f"{API_BASE_URL}/api/dashboard/model-versions", headers=headers)
        if response.status_code == 200:
            versions_data = response.json()["versions"]

            if versions_data:
                rows = []
                for v in versions_data:
                    row = {"Version": v["version"], "Stage": v["stage"], "Run ID": v["run_id"]}
                    row.update(v.get("metrics", {}))
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

                st.divider()
                st.subheader("Rejouer une prediction sur une version")

                run_id_choisi = st.selectbox(
                    "Choisir une version (run_id)",
                    options=[v["run_id"] for v in versions_data],
                    format_func=lambda rid: next(
                        f"v{v['version']} ({v['stage']}) - {rid[:8]}..."
                        for v in versions_data if v["run_id"] == rid
                    )
                )

                st.write("Entrer les 9 mesures du prelevement a rejouer :")
                noms_features = [
                    "ph", "hardness", "solids", "chloramines", "sulfate",
                    "conductivity", "organic_carbon", "trihalomethanes", "turbidity"
                ]
                cols = st.columns(3)
                valeurs = []
                for i, nom in enumerate(noms_features):
                    with cols[i % 3]:
                        valeurs.append(st.number_input(nom, value=0.0, key=f"replay_{nom}"))

                if st.button("Rejouer la prediction"):
                    try:
                        replay_resp = requests.post(
                            f"{API_BASE_URL}/api/dashboard/replay",
                            headers=headers,
                            json={"run_id": run_id_choisi, "features": valeurs}
                        )
                        if replay_resp.status_code == 200:
                            result = replay_resp.json()
                            st.success(
                                f"Resultat : {result['water_status']} "
                                f"(probabilite potable : {result['probability_potable']:.4f})"
                            )
                        else:
                            st.error(f"Erreur ({replay_resp.status_code}) : {replay_resp.json().get('error')}")
                    except requests.exceptions.ConnectionError:
                        st.error("L'API Flask ne repond pas sur le port 8000.")
            else:
                st.info("Aucune version de modele trouvee sur MLflow.")

        else:
            st.error(f"Erreur serveur ({response.status_code}).")

    except requests.exceptions.ConnectionError:
        st.error("L'API Flask ne repond pas sur le port 8000.")
