from groq import Groq
from json import load, dump
import os
import datetime
from dotenv import dotenv_values
import requests
from bs4 import BeautifulSoup
import urllib.parse
import pytz

# --- Load .env variables ---
env_path = os.path.join(os.path.dirname(__file__), ".env")
env_vars = dotenv_values(env_path)
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Assistant")
GroqAPIKey = env_vars.get("GroqAPIKey")

if not GroqAPIKey:
    print("Error: GroqAPIKey not found in .env file")
    exit(1)

# --- Groq client ---
client = Groq(api_key=GroqAPIKey)
MODEL = "llama-3.1-8b-instant"

# --- System prompt ---
System = f"""You are {Assistantname}, an AI assistant with real-time information access.
- Provide professional, well-formatted answers.
- Use proper grammar and punctuation.
- Prefer the latest information available.
"""

# --- Chat history helpers ---
def load_chat_history():
    os.makedirs("Data", exist_ok=True)
    path = "Data/ChatLog.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            dump([], f)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return load(f)

def save_chat_history(messages):
    with open("Data/ChatLog.json", "w", encoding="utf-8") as f:
        dump(messages, f, indent=4)

# --- Google search scraper (top 3 results) ---
def GoogleSearch(query):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        results = []
        for g in soup.find_all('div', class_='g'):
            title_elem = g.find('h3')
            link_elem = g.find('a')
            desc_elem = g.find('div', class_=['VwiC3b', 'yDYNvb'])
            if title_elem and link_elem:
                title = title_elem.get_text()
                link = link_elem.get('href', '')
                desc = desc_elem.get_text() if desc_elem else ''
                results.append({'title': title, 'link': link, 'description': desc[:200] + '...' if len(desc) > 200 else desc})
            if len(results) >= 3:
                break
        if results:
            formatted = "Latest Search Results:\n\n"
            for idx, r in enumerate(results, 1):
                formatted += f"{idx}. {r['title']}\n   {r['description']}\n"
            return formatted
        return "No recent search results found. Using general knowledge."
    except Exception:
        return "No search results are available at this time."

# --- Date/time info (IST) ---
def get_realtime_info():
    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    return f"{now.strftime('%d %B %Y')}\n{now.strftime('%H:%M:%S IST')}"

# --- Remove empty and debug lines from LLM output ---
def clean_response(answer):
    lines = [
        line for line in answer.split('\n')
        if line.strip() and not any(
            line.lower().startswith(x) for x in (
                'err:', '[', 'warning:', 'api request failed', 'image not found',
                'successfully generated', 'no images', 'failed to generate',
                'error:'
            )
        )
    ]
    return '\n'.join(lines)

# --- End-to-end real-time answering ---
def RealtimeSearchEngine(prompt):
    messages = load_chat_history()
    messages.append({"role": "user", "content": prompt})
    search_results = GoogleSearch(prompt)
    realtime_info = get_realtime_info()
    all_messages = [
        {"role": "system", "content": System},
        {"role": "system", "content": realtime_info},
        {"role": "system", "content": search_results},
        *messages
    ]
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=all_messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False
        )
        answer = completion.choices[0].message.content or "I apologize, but I couldn't generate a response. Please try again."
        messages.append({"role": "assistant", "content": answer})
        save_chat_history(messages)
        return clean_response(answer)
    except Exception as e:
        return "I'm experiencing technical difficulties. Please try again later."

if __name__ == "__main__":
    while True:
        try:
            prompt = input("You: ").strip()
            if prompt.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye! 👋")
                break
            if not prompt:
                continue
            response = RealtimeSearchEngine(prompt)
            print(f"\n{Assistantname}: {response}\n{'=' * 60}")
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\nError: {e}")
