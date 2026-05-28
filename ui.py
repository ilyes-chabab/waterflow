import os
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Waterflow - Demo CSV", page_icon=None, layout="centered"
)

st.title("Projet Waterflow - Panel de Test")


X_TEST_PATH = "data/processed/X_test.csv"
Y_TEST_PATH = "data/processed/y_test.csv"


@st.cache_data
def load_real_test_data():
    if not os.path.exists(X_TEST_PATH) or not os.path.exists(Y_TEST_PATH):
        st.error(
            f"Fichiers introuvables. Vérifiez les chemins : {X_TEST_PATH} et {Y_TEST_PATH}"
        )
        return None

    X_df = pd.read_csv(X_TEST_PATH)
    y_df = pd.read_csv(Y_TEST_PATH)

    y_df.columns = ["Potability"]

    combined_df = pd.concat([X_df, y_df], axis=1)
    return combined_df


df_test = load_real_test_data()

if "current_features" not in st.session_state:
    st.session_state.current_features = [0.0] * 9

if df_test is not None:
    st.subheader("Génération des données")
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("Échantillon Aléatoire", use_container_width=True):
            sample = df_test.sample(n=1).iloc[0]
            st.session_state.current_features = sample.drop(
                "Potability"
            ).tolist()
            st.toast(
                f"Échantillon aléatoire chargé. Vraie Potabilité : {int(sample['Potability'])}"
            )

    with col_btn2:
        if st.button(
            "Échantillon Potable Garanti (Y=1)",
            use_container_width=True,
            type="secondary",
        ):
            potable_samples = df_test[df_test["Potability"] == 1]
            if not potable_samples.empty:
                sample = potable_samples.sample(n=1).iloc[0]
                st.session_state.current_features = sample.drop(
                    "Potability"
                ).tolist()
                st.toast("Échantillon Potable chargé.")
            else:
                st.warning(
                    "Aucune ligne avec Potability = 1 présente dans le fichier."
                )

    st.divider()

st.subheader("Valeurs des caractéristiques (scalées)")

cf = st.session_state.current_features

col1, col2, col3 = st.columns(3)
with col1:
    ph = st.number_input("ph", value=float(cf[0]), format="%.6f")
    hardness = st.number_input("Hardness", value=float(cf[1]), format="%.6f")
    solids = st.number_input("Solids", value=float(cf[2]), format="%.6f")

with col2:
    chloramines = st.number_input(
        "Chloramines", value=float(cf[3]), format="%.6f"
    )
    sulfate = st.number_input("Sulfate", value=float(cf[4]), format="%.6f")
    conductivity = st.number_input(
        "Conductivity", value=float(cf[5]), format="%.6f"
    )

with col3:
    organic_carbon = st.number_input(
        "Organic_carbon", value=float(cf[6]), format="%.6f"
    )
    trihalomethanes = st.number_input(
        "Trihalomethanes", value=float(cf[7]), format="%.6f"
    )
    turbidity = st.number_input("Turbidity", value=float(cf[8]), format="%.6f")

st.divider()

if st.button(
    "Lancer la prédiction API", type="primary", use_container_width=True
):

    payload = {
        "features": [
            ph,
            hardness,
            solids,
            chloramines,
            sulfate,
            conductivity,
            organic_carbon,
            trihalomethanes,
            turbidity,
        ]
    }

    URL_API = "http://127.0.0.1:8000/predict"

    try:
        with st.spinner("Requête en cours vers l'API Flask..."):
            response = requests.post(URL_API, json=payload)

        if response.status_code == 200:
            result = response.json()
            status = result["water_status"]
            prediction = result["prediction"]

            prob = result.get("probability_potable", 0.0)
            threshold = result.get("decision_threshold_used", 0.5)

            if prediction == 1:
                st.success(f"Présultat de l'API : {status}")
            else:
                st.error(f"Résultat de l'API : {status}")

            st.info(
                f"Probabilité calculée : {prob:.4f} (Seuil de décision appliqué : {threshold:.2f})"
            )
            st.caption(f"Modèle : {result['model_version_used']}")
        else:
            st.error(f"Erreur API : {response.text}")

    except requests.exceptions.ConnectionError:
        st.error(
            "Erreur de connexion. L'API Flask ne répond pas sur le port 8000."
        )