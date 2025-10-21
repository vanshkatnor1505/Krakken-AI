import re
import os
from dotenv import dotenv_values

# --- Settings ---
CATEGORIES = [
    "general", "realtime", "open", "close", "play", "generate image",
    "system", "content", "google search", "youtube search", "reminder", "exit"
]
EXIT_PHRASES = {"bye", "exit", "quit", "goodbye", "end"}
REALTIME_KEYWORDS = [
    "news", "weather", "update", "current", "latest", "recent",
    "headline", "now", "live", "score", "trending", "breaking",
    "forecast", "stock", "price", "exchange rate", "covid", "coronavirus",
    "today's news", "todays news", "today's headline", "todays headline",
    "today's weather", "todays weather", "result", "results", "match",
    "game", "event", "happening", "going on"
]
DATE_TIME_KEYWORDS = ["date", "time", "day", "month", "year"]

# --- Main rule-based classifier ---
def classify_query(query: str) -> str:
    q = query.lower().strip()
    q_nopunct = re.sub(r"[^\w\s]", "", q)

    # Exit phrases
    if any(phrase in q_nopunct.split() for phrase in EXIT_PHRASES):
        return "exit"

    # Google/Youtube searches
    if q_nopunct.startswith("google "):
        return f'google search {query[7:].strip()}'
    if q_nopunct.startswith("search google for "):
        return f'google search {query[17:].strip()}'
    if q_nopunct.startswith("youtube "):
        return f'youtube search {query[8:].strip()}'
    if q_nopunct.startswith("search youtube for "):
        return f'youtube search {query[18:].strip()}'

    # Multi-action open, close, play, system
    for act in ["open", "close", "play", "system"]:
        if q_nopunct.startswith(act + " "):
            items = re.split(r"\s*,\s*|\s+and\s+", query[len(act):].strip())
            actions = [f"{act} {item.strip()}" for item in items if item.strip()]
            return ", ".join(actions)

    # Reminders
    if "remind" in q_nopunct or "reminder" in q_nopunct:
        m = re.search(r'remind(?:er)?(?: me)?(?: on| at)?\s*(.*)', query, re.IGNORECASE)
        arg = m.group(1).strip() if m and m.group(1).strip() else query
        return f'reminder {arg}'


    # Realtime for certain keywords/entities
    if any(word in q_nopunct for word in REALTIME_KEYWORDS):
        return f'realtime {query}'
    entity_patterns = [r"^(who|what) is ([^?]+)\??$", r"^(tell me about|information about) ([^?]+)\??$"]
    for pat in entity_patterns:
        m = re.match(pat, q_nopunct)
        if m:
            subject = m.group(2).strip()
            if len(subject.split()) > 1 or any(w[0].isupper() for w in subject.split() if w):
                return f'realtime {query}'
            return f'general {query}'
    # Date/Time questions
    if any(word in q_nopunct for word in DATE_TIME_KEYWORDS):
        return f'general {query}'
    # Fallback
    return f'general {query}'

def FirstLayerDMM(query):
    """Returns a list of decisions for the given query using classify_query."""
    result = classify_query(query)
    return [r.strip() for r in result.split(',')] if isinstance(result, str) else list(result)

if __name__ == "__main__":
    print("Type your query. Type 'exit' to quit.")
    while True:
        user_input = input(">>> ").strip()
        decisions = FirstLayerDMM(user_input)
        print(decisions)
        if decisions[0] == "exit":
            break
