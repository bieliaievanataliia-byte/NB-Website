# NB-Website – Notizen-Web-App

Eine lokale Web-App zum Aufbereiten von Notizen mit KI (Ollama) und PDF-Export.

## Funktionen

- Notizen per Browser eingeben und von einem lokalen KI-Modell strukturieren lassen
- Verschiedene Notiztypen (Protokoll, Zusammenfassung, Aufgabenliste u.a.)
- PDF-Export der aufbereiteten Notizen

## Voraussetzungen

- Python 3.10+
- [Ollama](https://ollama.com) läuft lokal auf Port 11434

## Installation

```bash
pip install flask requests reportlab
```

## Starten

```bash
python app.py
```

App läuft unter: http://localhost:5050
