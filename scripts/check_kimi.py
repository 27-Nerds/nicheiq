"""Quick check: verify Kimi K2.5 API connectivity and model name."""

import sys
from openai import OpenAI

from nicheiq.config.settings import settings


def main():
    if not settings.moonshot_api_key:
        print("FAIL: MOONSHOT_API_KEY not set in .env")
        sys.exit(1)

    model = settings.landing_page_execution_llm
    print(f"Model:    {model}")
    print(f"Base URL: https://api.moonshot.ai/v1")
    print(f"API key:  {settings.moonshot_api_key[:8]}...{settings.moonshot_api_key[-4:]}")
    print()

    if not model.lower().startswith("kimi"):
        print(f"SKIP: LANDING_PAGE_EXECUTION_LLM={model} is not a Kimi model")
        sys.exit(0)

    client = OpenAI(
        api_key=settings.moonshot_api_key,
        base_url="https://api.moonshot.ai/v1",
    )

    # List available models to verify the name exists
    print("Available Kimi models:")
    try:
        for m in client.models.list().data:
            if "kimi" in m.id:
                marker = " <-- selected" if m.id == model else ""
                print(f"  {m.id}{marker}")
    except Exception as e:
        print(f"  (could not list models: {e})")
    print()

    # Test instant mode (thinking disabled, temp=0.6)
    print("Testing instant mode (thinking disabled)...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=16,
            temperature=0.6,
            extra_body={"thinking": {"type": "disabled"}},
        )
        reply = response.choices[0].message.content.strip()
        tokens = response.usage
        print(f"Response: {reply}")
        print(f"Tokens:   {tokens.prompt_tokens} in / {tokens.completion_tokens} out")
        print()
        print("OK: Kimi API connection works")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
