FROM python:3.10-slim

WORKDIR /app

# CA locale optionnelle (proxy/antivirus faisant de l'inspection TLS sur la machine
# de build, ex. Norton) : docker/certs/ est vide sauf ajout local (gitignored), donc
# ces deux lignes sont un no-op inoffensif sur une machine/CI sans interception TLS.
COPY docker/certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui.py .
COPY scripts/dashboard_qualite.py ./scripts/dashboard_qualite.py
COPY views/ ./views/
COPY data/processed/mean_features.json ./data/processed/mean_features.json
COPY data/processed/X_test.csv data/processed/y_test.csv ./data/processed/

EXPOSE 8501

CMD ["streamlit", "run", "ui.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
