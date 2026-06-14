import os
import sys
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from groq import Groq
import json
from dotenv import load_dotenv

# Load environment variables from .env file (local development)
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("ERROR: GROQ_API_KEY not found in environment variables!")

# Initialize the Groq client
client = Groq(api_key=API_KEY)

def fetch_feed_entries(url, limit=5):
    """Fetch RSS entries and truncate summaries to dramatically save tokens."""
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:limit]:
        raw_summary = entry.summary if 'summary' in entry else ""
        clean_summary = raw_summary[:200] if raw_summary else ""
        articles.append({
            "title": entry.title,
            "summary": clean_summary,
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
            return "Could not fetch TV program details directly."
        
        soup = BeautifulSoup(res.text, "html.parser")
        lines = []
        
        # Look for text structures that contain a timestamp (e.g., 18:30 or 21:45)
        for element in soup.find_all(['p', 'div', 'span', 'li']):
            text = element.get_text().strip()
            if re.search(r'\b\d{2}:\d{2}\b', text) and len(text) < 150:
                if text not in lines:
                    lines.append(text)
                    
        # Fallback text parser if layout structural markers miss
        if not lines:
            for line in soup.get_text(separator="\n").split("\n"):
                line = line.strip()
                if re.search(r'\b\d{2}:\d{2}\b', line) and len(line) < 150:
                    if line not in lines:
                        lines.append(line)
                        
        return "\n".join(lines[:30]) # Pass the top 30 filtered items to prevent token overflow
    except Exception as e:
        return f"Error gathering TV data: {str(e)}"

# 1. Gathering data sources
print("Fetching RSS feeds...")
raw_denmark = fetch_feed_entries("https://www.dr.dk/nyheder/service/feeds/senestenyt")
raw_greece = fetch_feed_entries("https://www.ertnews.gr/feed/")
raw_world = fetch_feed_entries("http://feeds.bbci.co.uk/news/world/rss.xml")
raw_tech = fetch_feed_entries("https://techcrunch.com/feed/")
raw_sports = fetch_feed_entries("https://www.gazzetta.gr/rss")

print("Fetching Sports TV program text...")
raw_tv = fetch_sports_tv()

# 2. Construct the localized routing prompt
prompt = f"""
You are an expert news editor. Analyze the provided recent news articles and live TV schedule text data.
Your job is to select the top 3-4 items per category and strictly apply language rules.

Language Rules:
1. For 'world', 'tech', and 'denmark' keys: BOTH the 'title' and 'summary' fields MUST be entirely in ENGLISH. Translate Danish titles/content completely.
2. For 'greece' and 'sports' keys: BOTH the 'title' and 'summary' fields MUST be entirely in GREEK.
3. For the 'tv_program' key: Parse the raw live TV schedule text provided. Extract the top 8-10 major sports broadcasts for today and format them into a clean array of objects, where each object contains "time", "event", and "channel" written entirely in GREEK.

Return a strict JSON object with exactly these 6 keys: 'world', 'tech', 'sports', 'denmark', 'greece', 'tv_program'.

Raw Data:
- World (English): {json.dumps(raw_world, ensure_ascii=False)}
- Tech (English): {json.dumps(raw_tech, ensure_ascii=False)}
- Sports (Greek): {json.dumps(raw_sports, ensure_ascii=False)}
- Denmark (Danish): {json.dumps(raw_denmark, ensure_ascii=False)}
- Greece (Greek): {json.dumps(raw_greece, ensure_ascii=False)}
- Live TV Text: {json.dumps(raw_tv, ensure_ascii=False)}
"""

print("Curating, translating and localizing via AI Agent...")
completion = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.1
)

output_text = completion.choices[0].message.content.strip()

try:
    json_data = json.loads(output_text)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    print("Dashboard JSON package compiled successfully!")
except json.JSONDecodeError:
    print("Error: Invalid JSON compiled by model. Raw text dump:")
    print(output_text)
    sys.exit(1)