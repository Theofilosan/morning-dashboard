import os
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

# 1. Fetch Danish News (DR RSS feed)
dr_url = "https://www.dr.dk/nyheder/service/feeds/senestenyt"
dr_feed = feedparser.parse(dr_url)
denmark_articles = []
for entry in dr_feed.entries[:5]: # Fetch top 5 articles
    denmark_articles.append({
        "title": entry.title,
        "summary": entry.summary if 'summary' in entry else "",
        "link": entry.link
    })

# 2. Fetch Greek News (ERT RSS feed)
ert_url = "https://www.ertnews.gr/feed/"
ert_feed = feedparser.parse(ert_url)
greece_articles = []
for entry in ert_feed.entries[:5]: # Fetch top 5 articles
    greece_articles.append({
        "title": entry.title,
        "summary": entry.summary if 'summary' in entry else "",
        "link": entry.link
    })

# 3. Construct the prompt for the AI Agent
prompt = f"""
You are an expert news analyst. Translate the following Danish and Greek news articles into English.

For each article, provide a detailed summary (3-4 sentences) highlighting the main event, why it matters, and any key figures or locations.

Return ONLY a raw JSON object with two keys: 'denmark' and 'greece'. Each key must contain a list of the translated articles.
Do not include any markdown formatting, do not include ```json or any conversational text.

Danish Articles:
{json.dumps(denmark_articles, ensure_ascii=False)}

Greek Articles:
{json.dumps(greece_articles, ensure_ascii=False)}
"""

# Call the Groq API using Llama 3.1
completion = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1 # Low temperature for structural consistency
)

output_text = completion.choices[0].message.content.strip()

try:
    # Validate and save JSON output
    json_data = json.loads(output_text)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    print("News from Denmark and Greece updated successfully!")
except json.JSONDecodeError:
    print("Error: The model did not return a valid JSON format. Raw output:")
    print(output_text)