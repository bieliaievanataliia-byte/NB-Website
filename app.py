#!/usr/bin/env python3
"""
Notizen-Web-App – Flask-Server
"""

import os
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify
import requests as req

from meeting_tool import ki_aufbereiten, pdf_erstellen, NOTIZTYPEN

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/notiztypen")
def notiztypen():
    return jsonify({
        k: {"label": v["label"], "icon": v["icon"]}
        for k, v in NOTIZTYPEN.items()
    })


@app.route("/verarbeiten", methods=["POST"])
def verarbeiten():
    data = request.get_json(silent=True) or {}
    notizen   = data.get("notizen", "").strip()
    notiz_typ = data.get("notiz_typ", "allgemein")
    model     = data.get("model", "llama3")

    if not notizen:
        return jsonify({"fehler": "Keine Notizen angegeben."}), 400

    try:
        ergebnis = ki_aufbereiten(notizen, notiz_typ, model)
        if not ergebnis.get("datum"):
            ergebnis["datum"] = datetime.now().strftime("%d.%m.%Y")
        ergebnis["_typ"] = notiz_typ
        return jsonify(ergebnis)
    except Exception as e:
        return jsonify({"fehler": str(e)}), 500


@app.route("/ollama-status")
def ollama_status():
    try:
        r = req.get("http://localhost:11434/api/tags", timeout=2)
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"online": True, "modelle": models})
    except Exception:
        return jsonify({"online": False, "modelle": []})


@app.route("/pdf", methods=["POST"])
def pdf():
    data = request.get_json(silent=True) or {}
    notizen   = data.get("notizen", "").strip()
    notiz_typ = data.get("notiz_typ", "allgemein")
    model     = data.get("model", "llama3")

    if not notizen:
        return jsonify({"fehler": "Keine Notizen angegeben."}), 400

    try:
        daten = ki_aufbereiten(notizen, notiz_typ, model)
        if not daten.get("datum"):
            daten["datum"] = datetime.now().strftime("%d.%m.%Y")

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        pdf_erstellen(daten, tmp.name, notiz_typ)

        titel = daten.get("titel", "Notiz").replace(" ", "_")
        datum = daten.get("datum", "").replace(".", "-")
        filename = f"{datum}_{titel}.pdf"

        return send_file(
            tmp.name,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"fehler": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, port=5050)
