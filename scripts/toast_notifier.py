"""Petit serveur local qui recoit les webhooks Alertmanager et affiche une
notification Windows (toast) pour chaque alerte qui se declenche ou se resout.

A lancer sur la machine hote (pas dans Docker) :
    pip install winotify
    python scripts/toast_notifier.py

Alertmanager (dans le conteneur) appelle ensuite ce serveur via
http://host.docker.internal:5001/webhook (voir alertmanager.yml).
"""
from flask import Flask, request
from winotify import Notification

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)

    for a in payload.get("alerts", []):
        status = a.get("status", "unknown")
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})

        alertname = labels.get("alertname", "Alerte Waterflow")
        summary = annotations.get("summary", "")

        if status == "firing":
            title = f"Waterflow2 - {alertname}"
            msg = summary or "Une alerte s'est declenchee."
        else:
            title = f"Waterflow2 - {alertname} resolue"
            msg = "L'alerte est revenue a la normale."

        Notification(
            app_id="Waterflow2",
            title=title,
            msg=msg,
            duration="long",
        ).show()

    return "", 200


if __name__ == "__main__":
    print("Toast notifier en ecoute sur http://0.0.0.0:5001/webhook")
    app.run(host="0.0.0.0", port=5001)
