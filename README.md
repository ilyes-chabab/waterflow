# waterflow

## Définition du MLOps :

Le Machine Learning Operations (MLOps) est un ensemble de pratiques qui combine le Machine Learning, le DevOps et l’industrialisation des données afin de faciliter le développement, le déploiement, le suivi et la maintenance des modèles d’intelligence artificielle en production.

Le MLOps vise à rendre les projets de Machine Learning :

reproductibles ;
automatisés ;
scalables ;
fiables ;
et maintenables tout au long du cycle de vie des modèles.

Il couvre notamment :

la gestion des données et des versions de modèles ;
l’entraînement et le déploiement automatisés ;
l’intégration et le déploiement continus (CI/CD) ;
la surveillance des performances des modèles ;
ainsi que la détection de dérive des données (data drift) et des prédictions.

Les outils fréquemment utilisés en MLOps incluent notamment MLflow, Kubeflow, Apache Airflow, Docker et Kubernetes.


## Veille technologique — MLflow

### Présentation de MLflow

MLflow est une plateforme open source dédiée à la gestion du cycle de vie des projets de Machine Learning. Développé initialement par Databricks, MLflow permet aux équipes Data Science et MLOps de centraliser et automatiser les différentes étapes de création et de déploiement des modèles d’intelligence artificielle.

L’outil est aujourd’hui largement utilisé dans les environnements professionnels et académiques grâce à sa simplicité d’intégration avec les principaux frameworks de Machine Learning comme :

- TensorFlow 
- PyTorch 
- Scikit-learn 
- XGBoost
- Fonctionnalités principales

MLflow se compose de plusieurs modules essentiels :

MLflow Tracking

Permet d’enregistrer les expériences de Machine Learning :

- paramètres 
- métriques 
- résultats 
- artefacts 
- historiques d’entraînement

Cela facilite la comparaison et la reproductibilité des expériences.

MLflow Projects

Standardise l’exécution des projets ML afin de garantir leur portabilité entre différents environnements.

MLflow Models

Permet de sauvegarder, versionner et déployer les modèles dans différents formats compatibles avec plusieurs plateformes.

MLflow Model Registry

Offre un système de gestion des versions des modèles avec :

- validation 
- transition entre environnements (staging, production) 
- archivage 
- collaboration entre équipes
- Étendue de l’utilisation de MLflow

MLflow est largement adopté dans :

- les projets de Data Science 
- les pipelines MLOps industriels 
- les plateformes cloud 
- les environnements Kubernetes 
- les workflows CI/CD

Il est notamment compatible avec :

- Docker 
- Kubernetes 
- Apache Spark 
- Amazon SageMaker 
- Azure Machine Learning

De nombreuses entreprises utilisent MLflow pour :

industrialiser leurs modèles ;
assurer la traçabilité des expérimentations ;
automatiser les déploiements ;
superviser les performances des modèles en production.

c'est une librairie python qui s'installe 

```bash
pip install mlflow 
```

ensuite il faut taper la commande 

```bash 
mlflow ui
```

l'interface sera disponible par défaut à l'adresse : http://127.0.0.1:5000


Pour lancer le projet d'abord lancer MLFLOW avec :
python -m mlflow server --host 127.0.0.1 --port 5000

ensuite l'api avec : python3 app.py


test api :
curl -X POST http://localhost:8000/api/ocr/lab-report -H "X-API-Key: votre_cle_client" -F "file=@test_OCR.png"

lancer Streamlit :
python -m streamlit run ui.py

## Conclusion

MLflow est aujourd’hui une référence dans le domaine du MLOps grâce à ses capacités de suivi des expériences, de gestion des modèles et d’automatisation des workflows de Machine Learning. Son intégration avec de nombreux outils et frameworks en fait une solution flexible et adaptée aux projets de Data Science modernes.