import os
import sys
import re
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from groq import Groq
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("ERROR: GROQ_API_KEY not found!")

client = Groq(api_key=API_KEY)

def clean_html(text):
    if not text: return ""
    soup = BeautifulSoup(text, "html.parser")
    return " ".join(soup.get_text(separator=" ").split())

def fetch_feed_entries(url, limit=5):
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:limit]:
        articles.append({
            "title": clean_html(entry.title),
            "summary": clean_html(entry.summary if 'summary' in entry else "")[:200],
            "link": entry.link
        })
    return articles

def fetch_sports_tv():
    url = "https://www.sport24.gr/tvprogram/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return "Could not fetch TV program details."
        soup = BeautifulSoup(res.text, "html.parser")
        lines = []
        for element in soup.find_all(['p', 'div', 'span', 'li']):
            text = clean_html(element.get_text())
            if re.search(r'\b\d{2}:\d{2}\b', text) and len(text) < 150:
                if text not in lines: lines.append(text)
        return "\n".join(lines[:35])
    except Exception as e:
        return f"Error gathering TV data: {str(e)}"

def get_detailed_weather():
    """Fetches weather and calculates specific rain timeframes (e.g., Athens)."""
    # Συντεταγμένες για Αθήνα (Άλλαξέ τις αν θες άλλη πόλη, π.χ. Latitude=55.67 για Κοπεγχάγη)
    lat, lon = 37.9838, 23.7275 
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability,weather_code&current_weather=true&timezone=auto"
    
    # Weather codes mapping to Greek descriptions
    weather_desc = {0: "Ηλιοφάνεια", 1: "Σχεδόν αίθριος", 2: "Μερική συννεφιά", 3: "Συννεφιά", 45: "Ομίχλη", 51: "Ψιχάλες", 61: "Ασθενής βροχή", 63: "Βροχή", 80: "Καταιγίδα"}

    try:
        res = requests.get(url, timeout=10).json()
        current = res.get("current_weather", {})
        code = current.get("weathercode", 0)
        condition = weather_desc.get(code, "Συννεφιά" if code > 3 else "Καλή")
        
        # Ανάλυση ωριαίας βροχής
        hourly = res.get("hourly", {})
        times = hourly.get("time", [])
        probs = hourly.get("precipitation_probability", [])
        
        rain_hours = []
        # Ελέγχουμε τις επόμενες 18 ώρες
        for i in range(min(18, len(times))):
            if probs[i] >= 30: # Πιθανότητα βροχής πάνω από 30%
                hour_str = times[i].split("T")[1][:5] # Παίρνουμε το HH:MM
                rain_hours.append(hour_str)
        
        if rain_hours:
            rain_info = f"Πιθανή βροχή κατά τις ώρες: {', '.join(rain_hours)}"
        else:
            rain_info = "Δεν αναμένεται βροχή σήμερα."

        return {
            "temp": f"{current.get('temperature', 'N/A')}°C",
            "condition": condition,
            "rain_alert": rain_info
        }
    except Exception:
        return {"temp": "N/A", "condition": "Άγνωστος", "rain_alert": "Δεν υπάρχουν δεδομένα βροχής."}

# Execution
print("Fetching clean data...")
raw_data = {
    "world": fetch_feed_entries("http://feeds.bbci.co.uk/news/world/rss.xml"),
    "tech": fetch_feed_entries("https://techcrunch.com/feed/"),
    "denmark": fetch_feed_entries("https://www.dr.dk/nyheder/service/feeds/senestenyt"),
    "greece": fetch_feed_entries("https://www.ertnews.gr/feed/"),
    "sports": fetch_feed_entries("https://www.gazzetta.gr/rss"),
    "tv_program": fetch_sports_tv()
}

weather_info = get_detailed_weather()

final_dashboard = {
    "weather": weather_info,
    "world": [], "tech": [], "denmark": [], "greece": [], "sports": [], "tv_program": []
}

def ask_groq_chunk(prompt_content):
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt_content}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(completion.choices[0].message.content.strip())

print("Processing and organizing sections through Groq...")

# --- NEWS SECTIONS (English & Greek) ---
for cat in ["world", "tech"]:
    p = f"Select the top 3-4 items. BOTH title and summary MUST be in ENGLISH. Format: {{'{cat}': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data[cat])}"
    final_dashboard.update(ask_groq_chunk(p))
    time.sleep(2)

p_dk = f"Select top 3-4 items. Translate completely to ENGLISH. Format: {{'denmark': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['denmark'])}"
final_dashboard.update(ask_groq_chunk(p_dk))
time.sleep(2)

for cat in ["greece", "sports"]:
    p = f"Select the top 3-4 items. BOTH title and summary MUST be in GREEK. Format: {{'{cat}': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data[cat])}"
    final_dashboard.update(ask_groq_chunk(p))
    time.sleep(2)

# --- TV PROGRAM SECTION (Strictly Organized) ---
print("-> Structuring Sports TV Schedule...")
p_tv = f"""
Extract the top 10 major live sports broadcasts for today from the text. 
Sort them chronologically by time.
Format them into a strict JSON array of objects with keys 'time', 'event', and 'channel' written entirely in GREEK.
Example format: {{'tv_program': [{{'time': '16:00', 'event': 'Φόρμουλα 1: Γκραν Πρι Βαρκελώνης', 'channel': 'ANT1+'}}]}}
Text: {json.dumps(raw_data['tv_program'], ensure_ascii=False)}
"""
final_dashboard.update(ask_groq_chunk(p_tv))

# Save output
with open("news.json", "w", encoding="utf-8") as f:
    json.dump(final_dashboard, f, ensure_ascii=False, indent=4)

print("Process finished! All sections organized.")