import os
import feedparser
from groq import Groq
import json
from dotenv import load_dotenv

# load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("ERROR: Δεν βρέθηκε το GROQ_API_KEY στο αρχείο .env!")

client = Groq(api_key=API_KEY)

# latest news from DR
DR_RSS_URL = "https://www.dr.dk/nyheder/service/feeds/senestenyt"
feed = feedparser.parse(DR_RSS_URL)

articles = []
for entry in feed.entries[:7]: # will add more articles later
    articles.append({
        "title": entry.title,
        "summary": entry.summary if 'summary' in entry else "",
        "link": entry.link
    })

# agency prompt
prompt = f"""
You are an expert news analyst. Translate the following Danish news articles into English. 

For each article, provide a detailed summary (3-4 sentences) that highlights:
1. What the main event/news is.
2. Why it is important or what the consequences are.
3. Any key figures, locations, or dates mentioned.

Return ONLY a raw JSON list of objects, where each object has 'title', 'summary', and 'link'. 
Do not include any markdown formatting, do not include ```json or any conversational text.

Articles:
{json.dumps(articles, ensure_ascii=False)}
"""
# call the model
completion = client.chat.completions.create(
    model="llama-3.1-8b-instant",  
    messages=[
        {"role": "user", "content": prompt}
    ],
    temperature=0.1
)
# get the output text
output_text = completion.choices[0].message.content.strip()

try:
    # parse the output as JSON
    json_data = json.loads(output_text)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    print("news updated!")
except json.JSONDecodeError:
    print("ERROR: Failed to parse model output as JSON.")
    print(output_text)