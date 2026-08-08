
"""
Basic Groq provider test.

Run:

    python -m tests.test_groq
"""

from app.config import config
from core.ai.models import ChatMessage
from core.ai.provider import GroqProvider


def main() -> None:

    if not config.groq_api_key:

        print(
            "ERROR: GROQ_API_KEY is not configured."
        )

        return

    print(
        f"Using model: {config.groq_model}"
    )

    provider = GroqProvider(
        api_key=config.groq_api_key,
        model=config.groq_model,
    )

    messages = [
        ChatMessage(
            role="user",
            content="Say hello to Krakken AI in one short sentence.",
        )
    ]

    print()
    print("Requesting response...")
    print()

    response = provider.chat(
        messages
    )

    print("Response:")
    print(response.content)

    print()
    print("Model:")
    print(response.model)

    print()
    print("Usage:")
    print(response.usage)


if __name__ == "__main__":
    main()

