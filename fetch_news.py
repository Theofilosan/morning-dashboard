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

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("ERROR: GROQ_API_KEY not found in environment variables!")

client = Groq(api_key=API_KEY)

def clean_html(text):
    """Strip all HTML elements, images, and broken tags completely."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    clean_text = soup.get_text(separator=" ")
    return " ".join(clean_text.split())

def fetch_feed_entries(url, limit=5):
    """Fetch RSS entries, clean HTML junk, and truncate safely."""
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:limit]:
        title = clean_html(entry.title)
        raw_summary = entry.summary if 'summary' in entry else ""
        summary = clean_html(raw_summary)[:200]
        
        articles.append({
            "title": title,
            "summary": summary,
            "link": entry.link
        })
    return articles

def fetch_sports_tv():
    """Scrape raw sports TV schedule text from Sport24."""
    url = "https://www.sport24.gr/tvprogram/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "Could not fetch TV program details."
        
        soup = BeautifulSoup(res.text, "html.parser")
        lines = []
        
        for element in soup.find_all(['p', 'div', 'span', 'li']):
            text = clean_html(element.get_text())
            if re.search(r'\b\d{2}:\d{2}\b', text) and len(text) < 150:
                if text not in lines:
                    lines.append(text)
        return "\n".join(lines[:25])
    except Exception as e:
        return f"Error gathering TV data: {str(e)}"

# 1. Gather Raw Data
print("Fetching raw data sources...")
raw_data = {
    "world": fetch_feed_entries("http://feeds.bbci.co.uk/news/world/rss.xml"),
    "tech": fetch_feed_entries("https://techcrunch.com/feed/"),
    "denmark": fetch_feed_entries("https://www.dr.dk/nyheder/service/feeds/senestenyt"),
    "greece": fetch_feed_entries("https://www.ertnews.gr/feed/"),
    "sports": fetch_feed_entries("https://www.gazzetta.gr/rss"),
    "tv_program": fetch_sports_tv()
}

# Final dictionary that will hold the combined results
final_dashboard = {
    "world": [], "tech": [], "denmark": [], "greece": [], "sports": [], "tv_program": []
}

# 2. Sequential Processing with Time Pauses (To completely avoid TPM limits)
def ask_groq_chunk(prompt_content):
    """Helper to send small chunks to Groq safely."""
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt_content}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(completion.choices[0].message.content.strip())

print("Analyzing categories sequentially with safety pauses...")

# --- WORLD NEWS (English) ---
print("-> Processing World News...")
prompt_world = f"Select the top 3-4 articles. BOTH 'title' and 'summary' (3-4 sentences) MUST be in ENGLISH. Return JSON format: {{'world': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['world'])}"
final_dashboard.update(ask_groq_chunk(prompt_world))
time.sleep(3) # Safety pause

# --- TECH NEWS (English) ---
print("-> Processing Tech News...")
prompt_tech = f"Select the top 3-4 articles. BOTH 'title' and 'summary' (3-4 sentences) MUST be in ENGLISH. Return JSON format: {{'tech': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['tech'])}"
final_dashboard.update(ask_groq_chunk(prompt_tech))
time.sleep(3) # Safety pause

# --- DENMARK NEWS (Translate to English) ---
print("-> Processing Denmark News (Translating)...")
prompt_dk = f"Select the top 3-4 articles. Translate everything completely. BOTH 'title' and 'summary' (3-4 sentences) MUST be in ENGLISH. Return JSON format: {{'denmark': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['denmark'])}"
final_dashboard.update(ask_groq_chunk(prompt_dk))
time.sleep(3) # Safety pause

# --- GREECE NEWS (Greek) ---
print("-> Processing Greece News...")
prompt_gr = f"Select the top 3-4 articles. BOTH 'title' and 'summary' (3-4 sentences) MUST be in GREEK. Return JSON format: {{'greece': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['greece'])}"
final_dashboard.update(ask_groq_chunk(prompt_gr))
time.sleep(3) # Safety pause

# --- SPORTS NEWS (Greek) ---
print("-> Processing Sports News...")
prompt_sports = f"Select the top 3-4 articles. BOTH 'title' and 'summary' (3-4 sentences) MUST be in GREEK. Return JSON format: {{'sports': [{{'title': '...', 'summary': '...', 'link': '...'}}]}}. Data: {json.dumps(raw_data['sports'])}"
final_dashboard.update(ask_groq_chunk(prompt_sports))
time.sleep(3) # Safety pause

# --- TV PROGRAM (Greek) ---
print("-> Processing Sports TV Schedule...")
prompt_tv = f"Extract the top 8-10 major live sports broadcasts for today from the text. Format them as an array of objects with keys 'time', 'event', 'channel' written entirely in GREEK. Return JSON format: {{'tv_program': [{{'time': '...', 'event': '...', 'channel': '...'}}]}}. Text: {json.dumps(raw_data['tv_program'], ensure_ascii=False)}"
final_dashboard.update(ask_groq_chunk(prompt_tv))

# 3. Save the master JSON file
with open("news.json", "w", encoding="utf-8") as f:
    json.dump(final_dashboard, f, ensure_ascii=False, indent=4)

print("Dashboard compiled successfully without hitting rate limits!")