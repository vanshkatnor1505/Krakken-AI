from groq import Groq
from groq.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam
)
from json import load, dump
from dotenv import dotenv_values
import os


# Load environment variables with multiple fallback options
def load_environment():
    """Load API key and names from multiple sources"""
    # Try .env file first
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_vars = dotenv_values(env_path)
    # Check for API key in .env with different possible variable names
    GroqAPIKey = (
        env_vars.get("GroqAPIKey") or
        env_vars.get("GROQ_API_KEY") or
        env_vars.get("API_KEY") or
        os.getenv("GROQ_API_KEY") or
        os.getenv("GroqAPIKey")
    )

    Username = env_vars.get("Username") or os.getenv("USERNAME", "User")
    Assistantname = env_vars.get("Assistantname") or os.getenv("ASSISTANTNAME", "Jarvis")

    if not GroqAPIKey:
        print("❌ GROQ_API_KEY not found! Please set it in your .env file.")
        exit(1)

    return GroqAPIKey, Username, Assistantname


def create_env_template():
    """Create a template .env file if it doesn't exist"""
    env_content = """# Groq API Configuration
GroqAPIKey=your_actual_groq_api_key_here


# Chatbot Configuration  
Username=YourName
Assistantname=Jarvis


# Get your free API key from: [https://console.groq.com/keys](https://console.groq.com/keys)
"""


# Load environment variables
try:
    GroqAPIKey, Username, Assistantname = load_environment()
    print("✅ Environment variables loaded successfully")
except Exception as e:
    print(f"❌ Error loading environment: {e}")
    exit(1)


# Initialize Groq client
try:
    client = Groq(api_key=GroqAPIKey)
    print("✅ Groq client initialized successfully")
except Exception as e:
    print(f"❌ Error initializing Groq client: {e}")
    exit(1)


# Model and system prompt
MODEL = "llama-3.1-8b-instant"
SystemChatBot = [{
    "role": "system",
    "content": f"""Hello, I am {Username}. You are {Assistantname}, an accurate AI assistant with real-time information.
- Answer questions concisely
- Reply only in English
- No unnecessary notes or training data mentions"""
}]


# Initialize chat history
messages = []


def load_chat_history():
    """Load chat history from JSON file"""
    try:
        os.makedirs("Data", exist_ok=True)
        file_path = "Data/ChatLog.json"

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            with open(file_path, "w", encoding='utf-8') as f:
                dump([], f, indent=4)
            return []

        with open(file_path, "r", encoding='utf-8') as f:
            return load(f)

    except Exception as e:
        print(f"⚠️ Error loading chat history: {e}")
        return []


def save_chat_history(messages):
    """Save chat history to JSON file"""
    try:
        with open("Data/ChatLog.json", "w", encoding='utf-8') as f:
            dump(messages, f, indent=4)
    except Exception as e:
        print(f"⚠️ Error saving chat history: {e}")


def clean_response(answer):
    """Remove empty lines from response"""
    lines = [line for line in answer.split('\n') if line.strip()]
    return '\n'.join(lines)


def create_message_objects(messages_list):
    """Convert message dictionaries to Groq message objects"""
    message_objects = []
    for msg in messages_list:
        if msg["role"] == "system":
            message_objects.append(ChatCompletionSystemMessageParam(role="system", content=msg["content"]))
        elif msg["role"] == "user":
            message_objects.append(ChatCompletionUserMessageParam(role="user", content=msg["content"]))
        elif msg["role"] == "assistant":
            message_objects.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg["content"]))
    return message_objects


def ChatBot(query):
    """Process user query and return AI response"""
    global messages

    # Load current chat history
    messages = load_chat_history()

    # Add user message
    messages.append({"role": "user", "content": query})

    # Prepare all messages for AI
    all_messages = SystemChatBot + messages

    # Convert to Groq format
    groq_messages = create_message_objects(all_messages)

    try:
        # Get AI response
        completion = client.chat.completions.create(
            model=MODEL,
            messages=groq_messages,
            max_tokens=1024,
            temperature=0.7,
            top_p=1,
            stream=True,
            stop=None
        )

        # Stream response
        answer = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                answer += chunk.choices[0].delta.content

        # Clean and store response
        answer = answer.replace("</s>", "").strip()
        if not answer:
            answer = "Sorry, I couldn't generate a response. Please try again."

        messages.append({"role": "assistant", "content": answer})
        save_chat_history(messages)

        return clean_response(answer)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return "I'm experiencing technical difficulties. Please try again."


# Initialize chat history
messages = load_chat_history()


if __name__ == "__main__":

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye! 👋")
                break
            if not user_input:
                continue

            response = ChatBot(user_input)
            print(f"\n{Assistantname}: {response}\n")
            print("-" * 50)

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\nError: {e}")
