import os
import sys
import feedparser
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

def fetch_feed_entries(url, limit=10):
    """Helper function to fetch and clean RSS feed entries."""
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:limit]:
        articles.append({
            "title": entry.title,
            "summary": entry.summary if 'summary' in entry else "",
            "link": entry.link
        })
    return articles

# 1. Fetching raw news from various sources (10 articles each to allow AI filtering)
print("Fetching RSS feeds...")
raw_denmark = fetch_feed_entries("https://www.dr.dk/nyheder/service/feeds/senestenyt")
raw_greece = fetch_feed_entries("https://www.ertnews.gr/feed/")
raw_world = fetch_feed_entries("http://feeds.bbci.co.uk/news/world/rss.xml")
raw_tech = fetch_feed_entries("https://techcrunch.com/feed/")
raw_sports = fetch_feed_entries("https://www.gazzetta.gr/rss")

# 2. Construct the prompt with strict filtering instructions
prompt = f"""
You are an elite news editor. Analyze the provided lists of recent news articles across 5 categories.
Your task is to filter, select, and translate the top 3-4 MOST IMPORTANT and impactful stories for each category. Skip minor or repetitive news.

For each selected article, generate a detailed 3-4 sentence summary in English explaining what happened, why it matters, and any critical figures/consequences.

Return a strict JSON object with exactly these 5 keys: 'world', 'tech', 'sports', 'denmark', 'greece'. Each key must contain a list of your top selected articles.

Raw Data to Analyze:
- World News: {json.dumps(raw_world, ensure_ascii=False)}
- Tech News: {json.dumps(raw_tech, ensure_ascii=False)}
- Sports News (Greek & International Football/Basketball): {json.dumps(raw_sports, ensure_ascii=False)}
- Denmark News: {json.dumps(raw_denmark, ensure_ascii=False)}
- Greece News: {json.dumps(raw_greece, ensure_ascii=False)}
"""

print("Analyzing and filtering news via AI Agent...")
# Call the Groq API using JSON mode
completion = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.2 # Slightly higher for better editorial judgment
)

output_text = completion.choices[0].message.content.strip()

try:
    # Validate and save JSON output
    json_data = json.loads(output_text)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    print("Dashboard data curated successfully!")
except json.JSONDecodeError:
    print("Error: The model did not return a valid JSON format. Raw output:")
    print(output_text)
    sys.exit(1)