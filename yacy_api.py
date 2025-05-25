#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
YACY_URL = "http://localhost:8090/yacysearch.json?maximumRecords=5&query="

# 1. Nur Suche (Links zurückgeben)
@app.route("/suche", methods=["GET"])
def suche():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        res = requests.get(YACY_URL + query.replace(" ", "+"))
        items = res.json()["channels"][0]["items"]
        links = [{"title": i["title"], "link": i["link"]} for i in items]
        return jsonify(links)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Einzelne Seite extrahieren
@app.route("/inhalt", methods=["GET"])
def inhalt():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400

    try:
        page = requests.get(url, timeout=10)
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text()
        return jsonify({"url": url, "text": text[:5000]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. Suche + Top-Seite extrahieren
@app.route("/suche-und-text", methods=["GET"])
def suche_und_text():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        res = requests.get(YACY_URL + query.replace(" ", "+"))
        items = res.json()["channels"][0]["items"]
        if not items:
            return jsonify({"error": "No results found"}), 404

        url = items[0]["link"]
        page = requests.get(url, timeout=10)
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text()
        return jsonify({
            "query": query,
            "source_url": url,
            "text": text[:5000]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Suche + Text + LLM-Zusammenfassung + Markdown-Speicherung
@app.route("/suche-und-zusammenfassung", methods=["GET"])
def suche_und_zusammenfassung():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        # YaCy-Suche
        res = requests.get(YACY_URL + query.replace(" ", "+"))
        items = res.json()["channels"][0]["items"]
        if not items:
            return jsonify({"error": "No results found"}), 404

        # Wikipedia bevorzugen
        wiki_items = [i for i in items if "wikipedia.org" in i["link"]]
        url = (wiki_items[0] if wiki_items else items[0])["link"]

        # Text holen und kürzen
        page = requests.get(url, timeout=10)
        soup = BeautifulSoup(page.text, "html.parser")
        text = soup.get_text()[:3000]

        # LLM anfragen
        prompt = f"Fasse den folgenden Text sachlich und informativ zusammen:\n\n{text}"
        ollama_res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma:7b",
                "prompt": prompt,
                "stream": False
            }
        )
        antwort = ollama_res.json().get("response", "").strip()

        # Markdown speichern
        md_filename = f"{query.replace(' ', '_')}.md"
        with open(md_filename, "w") as f:
            f.write(f"# Zusammenfassung: {query}\n\n")
            f.write(f"🔗 Quelle: {url}\n\n")
            f.write("## Inhalt:\n\n")
            f.write(antwort)

        return jsonify({
            "query": query,
            "source_url": url,
            "summary": antwort,
            "markdown_file": md_filename
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. OpenAPI JSON ausliefern
@app.route("/openapi.json", methods=["GET"])
def openapi():
    return send_file("openapi.json")

# Server starten
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055)
