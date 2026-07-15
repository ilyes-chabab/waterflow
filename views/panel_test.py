import os
import json
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Waterflow - Demo CSV & OCR", layout="centered")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error(" Accès refusé. Vous devez d'abord vous connecter sur la page d'accueil.")
    st.markdown("[Aller à la page de connexion](/)")
    st.stop()
        
st.title("Projet Waterflow - Panel de Test")
st.caption(f"Session active pour le laboratoire : {st.session_state.username}")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
URL_PREDICT = f"{API_BASE_URL}/api/measurements"
URL_OCR = f"{API_BASE_URL}/api/ocr/lab-report"

X_TEST_PATH = "data/processed/X_test.csv"
Y_TEST_PATH = "data/processed/y_test.csv"
MEAN_FEATURES_PATH = "mean_features.json"


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


def load_mean_features():
    if os.path.exists(MEAN_FEATURES_PATH):
        with open(MEAN_FEATURES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


df_test = load_real_test_data()
mean_features = load_mean_features()

if "current_features" not in st.session_state:
    st.session_state.current_features = [0.0] * 9

st.subheader("Génération des données")

uploaded_file = st.file_uploader(
    "Importer une fiche laboratoire (Image ou PDF)",
    type=["png", "jpg", "jpeg", "pdf"],
)

if uploaded_file is not None:
    if st.button("Analyser le document via l'OCR", use_container_width=True):
        try:
            with st.spinner("Analyse du document en cours par l'API..."):
                files = {
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type,
                    )
                }
                headers = {"X-API-Key": st.session_state.api_key}

                response = requests.post(URL_OCR, headers=headers, files=files)

            if response.status_code in [200, 202, 206]:
                ocr_result = response.json()
                
                # S'adapter aux légères variantes de structures imbriquées (measurement ou measurement_payload)
                payload_key = "measurement" if "measurement" in ocr_result else "measurement_payload"
                features_ocr = ocr_result[payload_key]["features"]

                st.session_state.current_features = [
                    float(features_ocr.get("ph") or 0.0),
                    float(features_ocr.get("hardness") or 0.0),
                    float(features_ocr.get("solids") or 0.0),
                    float(features_ocr.get("chloramines") or 0.0),
                    float(features_ocr.get("sulfate") or 0.0),
                    float(features_ocr.get("conductivity") or 0.0),
                    float(features_ocr.get("organic_carbon") or 0.0),
                    float(features_ocr.get("trihalomethanes") or 0.0),
                    float(features_ocr.get("turbidity") or 0.0),
                ]

                if response.status_code in [202, 206]:
                    st.warning(
                        " Document lu partiellement ! Certains champs requis n'ont pas été trouvés sur la fiche."
                    )
                    for warning in ocr_result.get("warnings", []):
                        st.caption(f"{warning}")
                else:
                    st.success(" Fiche analysée avec succès !")
                st.rerun()

            else:
                st.error(
                    f"Erreur lors de l'analyse OCR ({response.status_code}) : {response.text}"
                )

        except requests.exceptions.ConnectionError:
            st.error(
                "Impossible de joindre l'API . Vérifiez qu'elle tourne sur le port 8000."
            )

st.caption("Ou utilisez les échantillons du jeu de test :")
col_btn1, col_btn2 = st.columns(2)

if df_test is not None:
    with col_btn1:
        if st.button("Échantillon Aléatoire", use_container_width=True):
            sample = df_test.sample(n=1).iloc[0]
            st.session_state.current_features = sample.drop(
                "Potability"
            ).tolist()
            st.toast(
                f"Échantillon aléatoire chargé. Vraie Potabilité : {int(sample['Potability'])}"
            )
            st.rerun()

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
                st.rerun()
            else:
                st.warning(
                    "Aucune ligne avec Potability = 1 présente dans le fichier."
                )

st.divider()

st.subheader("Valeurs des caractéristiques (scalées)")

if mean_features is not None:
    if st.button("Imputer les valeurs manquantes via le JSON", use_container_width=True):
        ordered_keys = [
            "ph", "hardness", "solids", "chloramines", "sulfate",
            "conductivity", "organic_carbon", "trihalomethanes", "turbidity"
        ]
        
        new_features = []
        imputed_count = 0
        for idx, key in enumerate(ordered_keys):
            current_val = st.session_state.current_features[idx]
            if current_val == 0.0:
                new_features.append(float(mean_features.get(key, 0.0)))
                imputed_count += 1
            else:
                new_features.append(current_val)
        
        st.session_state.current_features = new_features
        if imputed_count > 0:
            st.toast(f"✅ {imputed_count} caractéristique(s) manquante(s) imputée(s) avec succès !")
            st.rerun()
        else:
            st.toast("Aucune valeur à 0.0 n'a eu besoin d'être imputée.")
else:
    st.error("Fichier 'mean_features.json' introuvable. Impossible d'utiliser le bouton d'imputation.")

cf = st.session_state.current_features

col1, col2, col3 = st.columns(3)
with col1:
    ph = st.number_input("ph", value=float(cf[0]), step=0.1, format="%.4f")
    hardness = st.number_input("Hardness", value=float(cf[1]), step=1.0, format="%.4f")
    solids = st.number_input("Solids", value=float(cf[2]), step=100.0, format="%.4f")

with col2:
    chloramines = st.number_input("Chloramines", value=float(cf[3]), step=0.1, format="%.4f")
    sulfate = st.number_input("Sulfate", value=float(cf[4]), step=1.0, format="%.4f")
    conductivity = st.number_input("Conductivity", value=float(cf[5]), step=10.0, format="%.4f")

with col3:
    organic_carbon = st.number_input("Organic_carbon", value=float(cf[6]), step=0.1, format="%.4f")
    trihalomethanes = st.number_input("Trihalomethanes", value=float(cf[7]), step=1.0, format="%.4f")
    turbidity = st.number_input("Turbidity", value=float(cf[8]), step=0.1, format="%.4f")

st.session_state.current_features = [
    ph, hardness, solids, chloramines, sulfate,
    conductivity, organic_carbon, trihalomethanes, turbidity
]

st.divider()

if st.button(
    "Lancer la prédiction API", type="primary", use_container_width=True
):
    features_list = st.session_state.current_features

    if any(val == 0.0 for val in features_list):
        st.error(
            "Impossible de lancer la prédiction : au moins une des caractéristiques est non rempli. \n"
            "Veuillez remplir toutes les cases manuellement ou utiliser le bouton d'imputation ci-dessus."
        )
    else:
        payload = {
            "features": features_list
        }
        # Transmission de la clé API dans le header requis pour la sécurité de la route
        headers = {
            "X-API-Key": st.session_state.api_key,
            "Content-Type": "application/json"
        }

        try:
            with st.spinner("Requête en cours vers l'API ..."):
                response = requests.post(URL_PREDICT, json=payload, headers=headers)

            if response.status_code in [200, 201]:
                result = response.json()
                status = result["water_status"]
                prediction = result["prediction"]
                prob = result.get("probability_potable", 0.0)
                
                if prediction == 1:
                    st.success(f"⚖️ Résultat de l'API : {status}")
                else:
                    st.error(f"⚖️ Résultat de l'API : {status}")

                st.info(
                    f"Probabilité calculée : {prob:.4%} (Le prélèvement a été enregistré dans votre historique)."
                )
                if "msg" in result:
                    st.caption(f" {result['msg']}")
            else:
                st.error(f"Erreur API ({response.status_code}) : {response.text}")

        except requests.exceptions.ConnectionError:
            st.error(
                "Erreur de connexion. L'API ne répond pas sur le port 8000."
            )