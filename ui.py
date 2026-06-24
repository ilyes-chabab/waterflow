import os
import json
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Waterflow - Demo CSV & OCR", page_icon=None, layout="centered"
)

API_BASE_URL = "http://127.0.0.1:8000"
URL_LOGIN = f"{API_BASE_URL}/api/login"
URL_PREDICT = f"{API_BASE_URL}/predict"
URL_OCR = f"{API_BASE_URL}/api/ocr/lab-report"

# ──────────────────────────────────────────────────────────────────────────────
# GESTION DE LA SESSION DE CONNEXION
# ──────────────────────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.api_key = None

if not st.session_state.logged_in:
    st.title("🔐 Connexion au Portail Waterflow")
    st.write("Veuillez vous authentifier pour accéder au panel de test environnemental.")

    with st.form("login_form"):
        user_id_input = st.number_input("ID Utilisateur (Client)", min_value=1, step=1, value=1)
        api_key_input = st.text_input("Clé API Secrète", type="password")
        submit_login = st.form_submit_button("Se connecter", type="primary")

        if submit_login:
            if not api_key_input:
                st.error("Veuillez saisir votre clé API.")
            else:
                try:
                    # Appel de la nouvelle route Flask
                    response = requests.post(URL_LOGIN, json={
                        "user_id": user_id_input,
                        "api_key": api_key_input
                    })

                    if response.status_code == 200:
                        res_data = response.json()
                        st.session_state.logged_in = True
                        st.session_state.user_id = res_data["user_id"]
                        st.session_state.username = res_data["username"]
                        st.session_state.api_key = api_key_input  # Stockée pour les appels OCR
                        st.rerun()  # Recharge la page pour afficher le panel
                    else:
                        st.error("❌ ID ou Clé API incorrecte.")
                except requests.exceptions.ConnectionError:
                    st.error("L'API Flask ne répond pas sur le port 8000. Lancez app.py d'abord.")
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# ACCÈS AUTORISÉ : LE PANEL DE TEST COMMENCE ICI
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.write(f"👤 **Utilisateur :** {st.session_state.username}")
    st.write(f"🆔 **ID Client :** {st.session_state.user_id}")
    
    if st.button("📊 Historique des prédictions", use_container_width=True):
        st.session_state.page = "history"
        st.rerun()
    
    if st.button("Se déconnecter", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.api_key = None
        st.session_state.page = "main"
        st.rerun()

if "page" not in st.session_state:
    st.session_state.page = "main"
    
st.title("Projet Waterflow - Panel de Test")
st.caption(f"Session active pour le laboratoire : {st.session_state.username}")

X_TEST_PATH = "data/processed/X_test.csv"
Y_TEST_PATH = "data/processed/y_test.csv"
MEAN_FEATURES_PATH = "mean_features.json"


@st.cache_data
def show_history_page():
    st.title("📊 Historique des prédictions")
    if st.button("← Retour"):
        st.session_state.page = "main"
        st.rerun()

    # GET sur ton endpoint Flask /api/predictions/history (à créer côté app.py)
    resp = requests.get(
        f"{API_BASE_URL}/api/predictions/history",
        params={"user_id": st.session_state.user_id}
    )
    if resp.status_code != 200:
        st.error("Impossible de charger l'historique.")
        return

    predictions = resp.json()["predictions"]

    for pred in predictions:
        proba = pred["probability_potable"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.progress(proba, text=f"#{pred['id']} — {pred['created_at']} — Proba potable : {proba:.2f}")
        with col2:
            if st.button("Détails", key=f"pred_{pred['id']}"):
                st.session_state.page = "dashboard"
                st.session_state.selected_prediction_id = pred["id"]
                st.rerun()

def show_dashboard_page():
    st.title("📈 Tableau de bord du modèle")
    if st.button("← Retour à l'historique"):
        st.session_state.page = "history"
        st.rerun()

    pred_id = st.session_state.selected_prediction_id
    # détail de la prédiction sélectionnée
    pred_detail = requests.get(f"{API_BASE_URL}/api/predictions/{pred_id}").json()
    st.subheader(f"Prédiction #{pred_id}")
    st.json(pred_detail)

    st.divider()
    st.subheader("Performance globale du modèle en production")

    metrics = requests.get(f"{API_BASE_URL}/api/model/metrics").json()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accuracy", f"{metrics['accuracy']:.2%}")
    c2.metric("Recall", f"{metrics['recall']:.2%}")
    c3.metric("F1-score", f"{metrics['f1_score']:.2%}")
    c4.metric("ROC AUC", f"{metrics['roc_auc']:.2%}")

if st.session_state.page == "history":
    show_history_page()
    st.stop()
elif st.session_state.page == "dashboard":
    show_dashboard_page()
    st.stop()
    
    # Graphiques MLflow
    roc_img = requests.get(f"{API_BASE_URL}/api/model/artifact/roc_curve.png")
    st.image(roc_img.content, caption="Courbe ROC")

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

            if response.status_code in [200, 206]:
                ocr_result = response.json()
                features_ocr = ocr_result["measurement"]["features"]

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

                if response.status_code == 206:
                    st.warning(
                        "Document lu partiellement ! Certains champs requis n'ont pas été trouvés sur la fiche."
                    )
                    for warning in ocr_result.get("warnings", []):
                        st.caption(f"{warning}")
                else:
                    st.success("Fiche analysée avec succès !")

            else:
                st.error(
                    f"Erreur lors de l'analyse OCR ({response.status_code}) : {response.text}"
                )

        except requests.exceptions.ConnectionError:
            st.error(
                "Impossible de joindre l'API Flask. Vérifiez qu'elle tourne sur le port 8000."
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

if mean_features is not None:
    if st.button("Imputer les valeurs manquantes.", use_container_width=True):
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
            st.toast(f"{imputed_count} caractéristique(s) imputée(s) avec succès !")
        else:
            st.toast("Aucune valeur à 0.0 n'a eu besoin d'être imputée.")
else:
    st.error("Fichier 'mean_features.json' introuvable. Impossible d'utiliser le bouton d'imputation.")

cf = st.session_state.current_features

col1, col2, col3 = st.columns(3)
with col1:
    ph = st.number_input("ph", value=float(cf[0]))
    hardness = st.number_input("Hardness", value=float(cf[1]))
    solids = st.number_input("Solids", value=float(cf[2]))

with col2:
    chloramines = st.number_input(
        "Chloramines", value=float(cf[3])
    )
    sulfate = st.number_input("Sulfate", value=float(cf[4]))
    conductivity = st.number_input(
        "Conductivity", value=float(cf[5])
    )

with col3:
    organic_carbon = st.number_input(
        "Organic_carbon", value=float(cf[6])
    )
    trihalomethanes = st.number_input(
        "Trihalomethanes", value=float(cf[7])
    )
    turbidity = st.number_input("Turbidity", value=float(cf[8]))

st.divider()

if st.button(
    "Lancer la prédiction API", type="primary", use_container_width=True
):
    features_list = [
        ph, hardness, solids, chloramines, sulfate,
        conductivity, organic_carbon, trihalomethanes, turbidity
    ]

    if any(val == 0.0 for val in features_list):
        st.error(
            "Impossible de lancer la prédiction : au moins une des caractéristiques est à 0.0.  \n"
            "Veuillez remplir toutes les cases ou utiliser le bouton d'imputation ci-dessus."
        )
    else:
        payload = {
            "features": features_list
        }

        try:
            with st.spinner("Requête en cours vers l'API Flask..."):
                response = requests.post(URL_PREDICT, json=payload)

            if response.status_code == 200:
                result = response.json()
                status = result["water_status"]
                prediction = result["prediction"]

                prob = result.get("probability_potable", 0.0)
                threshold = result.get("decision_threshold_used", 0.5)

                if prediction == 1:
                    st.success(f"Résultat de l'API : {status}")
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