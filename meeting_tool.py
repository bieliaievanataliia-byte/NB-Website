#!/usr/bin/env python3
"""
Notizen-Tool
Verarbeitet Notizen aller Art mit Claude und erstellt strukturierte PDFs.
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

import requests as http_requests

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import Flowable


# ── Farben & Design ──────────────────────────────────────────────────────────

BRAND_DARK   = colors.HexColor("#1A2742")
BRAND_MID    = colors.HexColor("#2E6DA4")
BRAND_LIGHT  = colors.HexColor("#E8F1FA")
ACCENT       = colors.HexColor("#F0A500")
TEXT_DARK    = colors.HexColor("#1C1C1E")
TEXT_MUTED   = colors.HexColor("#6B7280")


# ── Notiztypen ───────────────────────────────────────────────────────────────

NOTIZTYPEN = {
    "meeting": {
        "label": "Meeting-Protokoll",
        "icon": "📋",
        "prompt": """Du bist ein professioneller Meeting-Assistent.
Extrahiere aus den Meeting-Notizen folgende Informationen als JSON.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Kurzer Meeting-Titel",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": ["Ort falls vorhanden", "Teilnehmer: Name1, Name2"],
  "zusammenfassung": "2-3 Sätze Kernzusammenfassung",
  "sektionen": [
    {"titel": "Beschlüsse", "icon": "📋", "punkte": ["Beschluss 1"]},
    {"titel": "Nächste Schritte", "icon": "→", "punkte": ["Schritt 1"]},
    {"titel": "Offene Punkte", "icon": "?", "punkte": ["Offener Punkt 1"]}
  ],
  "aktionspunkte": [
    {"aufgabe": "Aufgabe", "verantwortlich": "Name oder TBD", "frist": "Datum oder TBD"}
  ]
}"""
    },
    "brainstorming": {
        "label": "Brainstorming",
        "icon": "💡",
        "prompt": """Du bist ein kreativer Ideenassistent.
Strukturiere die Brainstorming-Notizen als JSON.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Kurzer Titel des Brainstormings",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": ["Kontext falls erkennbar"],
  "zusammenfassung": "Kern-Idee oder Fragestellung in 1-2 Sätzen",
  "sektionen": [
    {"titel": "Hauptideen", "icon": "💡", "punkte": ["Idee 1", "Idee 2"]},
    {"titel": "Chancen", "icon": "✅", "punkte": ["Chance 1"]},
    {"titel": "Risiken & Fragen", "icon": "⚠️", "punkte": ["Risiko 1"]}
  ],
  "aktionspunkte": [
    {"aufgabe": "Nächster Schritt", "verantwortlich": "TBD", "frist": "TBD"}
  ]
}"""
    },
    "journal": {
        "label": "Tagebuch / Reflexion",
        "icon": "📓",
        "prompt": """Du bist ein einfühlsamer Reflexionsassistent.
Strukturiere den Tagebucheintrag oder die persönliche Notiz als JSON.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Thema oder Datum des Eintrags",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": [],
  "zusammenfassung": "Kerngedanke oder Stimmung des Eintrags",
  "sektionen": [
    {"titel": "Was ist passiert", "icon": "📅", "punkte": ["Ereignis 1"]},
    {"titel": "Gedanken & Gefühle", "icon": "💭", "punkte": ["Gedanke 1"]},
    {"titel": "Erkenntnisse", "icon": "✨", "punkte": ["Erkenntnis 1"]}
  ],
  "aktionspunkte": []
}"""
    },
    "aufgaben": {
        "label": "Aufgabenliste / To-Do",
        "icon": "✅",
        "prompt": """Du bist ein effizienter Aufgaben-Assistent.
Strukturiere die Aufgaben und To-Dos als JSON.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Aufgabenliste oder Projektname",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": ["Kontext falls erkennbar"],
  "zusammenfassung": "Überblick: was muss erledigt werden und warum",
  "sektionen": [
    {"titel": "Dringend", "icon": "🔴", "punkte": ["Aufgabe 1"]},
    {"titel": "Wichtig", "icon": "🟡", "punkte": ["Aufgabe 1"]},
    {"titel": "Irgendwann", "icon": "🟢", "punkte": ["Aufgabe 1"]}
  ],
  "aktionspunkte": [
    {"aufgabe": "Aufgabe", "verantwortlich": "Name oder Ich", "frist": "Datum oder TBD"}
  ]
}"""
    },
    "recherche": {
        "label": "Recherche & Notizen",
        "icon": "🔍",
        "prompt": """Du bist ein strukturierter Wissensassistent.
Strukturiere die Recherche-Notizen als JSON.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Thema der Recherche",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": ["Quellen falls erkennbar"],
  "zusammenfassung": "Kernaussage oder Fragestellung der Recherche",
  "sektionen": [
    {"titel": "Wichtigste Erkenntnisse", "icon": "🔑", "punkte": ["Erkenntnis 1"]},
    {"titel": "Details & Fakten", "icon": "📊", "punkte": ["Fakt 1"]},
    {"titel": "Offene Fragen", "icon": "❓", "punkte": ["Frage 1"]}
  ],
  "aktionspunkte": [
    {"aufgabe": "Weitere Recherche zu", "verantwortlich": "TBD", "frist": "TBD"}
  ]
}"""
    },
    "allgemein": {
        "label": "Allgemeine Notizen",
        "icon": "📝",
        "prompt": """Du bist ein intelligenter Notizassistent.
Strukturiere die Notizen sinnvoll als JSON.
Erkenne selbst, welche Abschnitte am meisten Sinn machen.
Antworte NUR mit gültigem JSON, kein weiterer Text.

Schema:
{
  "titel": "Kurzer Titel",
  "datum": "Datum (TT.MM.JJJJ) falls vorhanden, sonst heute",
  "meta": ["Kontext falls erkennbar"],
  "zusammenfassung": "Kernaussage in 1-2 Sätzen",
  "sektionen": [
    {"titel": "Abschnittsname", "icon": "●", "punkte": ["Punkt 1", "Punkt 2"]}
  ],
  "aktionspunkte": [
    {"aufgabe": "Aufgabe falls vorhanden", "verantwortlich": "TBD", "frist": "TBD"}
  ]
}"""
    }
}


# ── Ollama-Integration ───────────────────────────────────────────────────────

OLLAMA_URL    = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


def ki_aufbereiten(notizen: str, notiz_typ: str = "allgemein", model: str = DEFAULT_MODEL) -> dict:
    """Sendet Notizen an Ollama und gibt strukturiertes JSON zurück."""
    typ_config    = NOTIZTYPEN.get(notiz_typ, NOTIZTYPEN["allgemein"])
    system_prompt = typ_config["prompt"]

    payload = {
        "model": model,
        "prompt": f"{system_prompt}\n\nNotizen:\n{notizen}",
        "stream": False,
        "format": "json"
    }
    try:
        resp = http_requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        return json.loads(raw)
    except http_requests.exceptions.ConnectionError:
        print("⚠️  Ollama nicht erreichbar. Starte Ollama mit: ollama serve")
        return _fallback_parse(notizen, notiz_typ)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️  Antwort konnte nicht geparst werden: {e}")
        return _fallback_parse(notizen, notiz_typ)


def _fallback_parse(notizen: str, notiz_typ: str = "allgemein") -> dict:
    """Einfacher Fallback ohne KI."""
    zeilen = [z.strip() for z in notizen.splitlines() if z.strip()]
    typ_config = NOTIZTYPEN.get(notiz_typ, NOTIZTYPEN["allgemein"])
    return {
        "titel": zeilen[0] if zeilen else typ_config["label"],
        "datum": datetime.now().strftime("%d.%m.%Y"),
        "meta": [],
        "zusammenfassung": notizen[:500] + ("..." if len(notizen) > 500 else ""),
        "sektionen": [],
        "aktionspunkte": []
    }


# ── PDF-Bausteine ────────────────────────────────────────────────────────────

class ColorBar(Flowable):
    def __init__(self, width, height, color):
        super().__init__()
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


def make_styles():
    return {
        "title": ParagraphStyle(
            "Title", fontName="Helvetica-Bold", fontSize=22,
            textColor=colors.white, leading=28, spaceAfter=4
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontName="Helvetica", fontSize=11,
            textColor=colors.HexColor("#BDD4EC"), leading=16
        ),
        "section": ParagraphStyle(
            "Section", fontName="Helvetica-Bold", fontSize=12,
            textColor=BRAND_DARK, spaceBefore=14, spaceAfter=6, leading=16
        ),
        "body": ParagraphStyle(
            "Body", fontName="Helvetica", fontSize=10,
            textColor=TEXT_DARK, leading=15, spaceAfter=4
        ),
        "bullet": ParagraphStyle(
            "Bullet", fontName="Helvetica", fontSize=10,
            textColor=TEXT_DARK, leading=15, leftIndent=12,
            spaceAfter=3, bulletIndent=0
        ),
        "muted": ParagraphStyle(
            "Muted", fontName="Helvetica-Oblique", fontSize=9,
            textColor=TEXT_MUTED, leading=13
        ),
        "footer": ParagraphStyle(
            "Footer", fontName="Helvetica", fontSize=8,
            textColor=TEXT_MUTED, alignment=TA_CENTER
        ),
        "table_header": ParagraphStyle(
            "TableHeader", fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.white, leading=12
        ),
        "table_body": ParagraphStyle(
            "TableBody", fontName="Helvetica", fontSize=9,
            textColor=TEXT_DARK, leading=13
        ),
    }


def header_block(daten: dict, notiz_typ: str, styles: dict, page_width: float) -> list:
    content = []
    inner_w = page_width - 40*mm
    typ_config = NOTIZTYPEN.get(notiz_typ, NOTIZTYPEN["allgemein"])

    content.append(ColorBar(inner_w, 70*mm, BRAND_DARK))
    content.append(Spacer(1, -70*mm))
    content.append(Spacer(1, 8*mm))

    content.append(Paragraph(
        f"{typ_config['icon']}  {daten.get('titel', typ_config['label'])}",
        styles["title"]
    ))

    meta_parts = []
    if daten.get("datum"):
        meta_parts.append(f"<b>Datum:</b> {daten['datum']}")
    for m in (daten.get("meta") or []):
        if m:
            meta_parts.append(m)

    if meta_parts:
        content.append(Spacer(1, 2*mm))
        content.append(Paragraph("  ·  ".join(meta_parts), styles["subtitle"]))

    content.append(Spacer(1, 10*mm))
    content.append(ColorBar(inner_w, 2*mm, ACCENT))
    content.append(Spacer(1, 6*mm))
    return content


def zusammenfassung_box(text: str, styles: dict, page_width: float) -> list:
    if not text:
        return []
    inner_w = page_width - 40*mm
    content = [ColorBar(inner_w, 1*mm, ACCENT), Spacer(1, 0)]
    data = [[Paragraph(text, ParagraphStyle(
        "BoxBody", fontName="Helvetica-Oblique", fontSize=10,
        textColor=BRAND_DARK, leading=16
    ))]]
    box = Table(data, colWidths=[inner_w])
    box.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    content.append(box)
    content.append(ColorBar(inner_w, 1*mm, ACCENT))
    content.append(Spacer(1, 6*mm))
    return content


def section_block(titel: str, punkte: list, icon: str, styles: dict, page_width: float) -> list:
    if not punkte:
        return []
    content = []
    content.append(KeepTogether([
        Paragraph(f"{icon}  {titel}", styles["section"]),
        HRFlowable(width=page_width - 40*mm, thickness=0.5,
                   color=BRAND_MID, spaceAfter=6)
    ]))
    for item in punkte:
        if isinstance(item, str) and item.strip():
            content.append(
                Paragraph(f"<bullet>&bull;</bullet> {item}", styles["bullet"])
            )
    content.append(Spacer(1, 4*mm))
    return content


def aktionspunkte_tabelle(punkte: list, styles: dict, page_width: float) -> list:
    if not punkte:
        return []
    content = []
    content.append(Paragraph("✓  Aktionspunkte", styles["section"]))
    content.append(HRFlowable(width=page_width - 40*mm, thickness=0.5,
                               color=BRAND_MID, spaceAfter=8))

    header = [
        Paragraph("Aufgabe", styles["table_header"]),
        Paragraph("Verantwortlich", styles["table_header"]),
        Paragraph("Frist", styles["table_header"]),
    ]
    rows = [header]
    for p in punkte:
        if isinstance(p, dict):
            rows.append([
                Paragraph(p.get("aufgabe", ""), styles["table_body"]),
                Paragraph(p.get("verantwortlich", "TBD"), styles["table_body"]),
                Paragraph(p.get("frist", "TBD"), styles["table_body"]),
            ])

    col_w = page_width - 40*mm
    table = Table(rows, colWidths=[col_w * 0.5, col_w * 0.25, col_w * 0.25])
    table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  BRAND_MID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E0")),
        ("LINEBELOW",      (0, 0), (-1, 0),  1.5, BRAND_DARK),
        ("TOPPADDING",     (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 6),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    content.append(table)
    content.append(Spacer(1, 4*mm))
    return content


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(
        20*mm, 12*mm,
        f"Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')}  ·  Claude AI"
    )
    canvas.drawRightString(A4[0] - 20*mm, 12*mm, f"Seite {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
    canvas.setLineWidth(0.5)
    canvas.line(20*mm, 18*mm, A4[0] - 20*mm, 18*mm)
    canvas.restoreState()


# ── PDF erstellen ────────────────────────────────────────────────────────────

def pdf_erstellen(daten: dict, ausgabe_pfad: str, notiz_typ: str = "allgemein"):
    typ_config = NOTIZTYPEN.get(notiz_typ, NOTIZTYPEN["allgemein"])
    doc = SimpleDocTemplate(
        ausgabe_pfad,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=15*mm, bottomMargin=22*mm,
        title=daten.get("titel", typ_config["label"]),
        author="Notizen Tool · Claude AI"
    )

    styles = make_styles()
    page_w = A4[0]
    story = []

    story.extend(header_block(daten, notiz_typ, styles, page_w))

    if daten.get("zusammenfassung"):
        story.extend(zusammenfassung_box(daten["zusammenfassung"], styles, page_w))

    for sektion in (daten.get("sektionen") or []):
        story.extend(section_block(
            sektion.get("titel", ""),
            sektion.get("punkte", []),
            sektion.get("icon", "●"),
            styles, page_w
        ))

    story.extend(aktionspunkte_tabelle(
        daten.get("aktionspunkte", []), styles, page_w
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"✅  PDF erstellt: {ausgabe_pfad}")


# ── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nVerwendung:")
        print("  python3 meeting_tool.py notizen.txt [ausgabe.pdf] [typ]")
        print("\nNotiztypen:", ", ".join(NOTIZTYPEN.keys()))
        sys.exit(0)

    eingabe  = sys.argv[1]
    ausgabe  = sys.argv[2] if len(sys.argv) > 2 else eingabe.replace(".txt", "") + "_notiz.pdf"
    typ      = sys.argv[3] if len(sys.argv) > 3 else "allgemein"

    try:
        notizen = Path(eingabe).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"❌  Datei nicht gefunden: {eingabe}")
        sys.exit(1)

    print(f"📄  Lese Notizen aus: {eingabe}")
    print(f"🤖  Verarbeite mit Claude ({typ}) ...")

    daten = ki_aufbereiten(notizen, typ)
    if not daten.get("datum"):
        daten["datum"] = datetime.now().strftime("%d.%m.%Y")

    print("📑  Erstelle PDF ...")
    pdf_erstellen(daten, ausgabe, typ)


if __name__ == "__main__":
    main()
