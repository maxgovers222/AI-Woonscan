import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# .strip() haalt onzichtbare spaties aan het begin of eind weg
api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() 

client = Anthropic(api_key=api_key)

try:
    print("Sleutel laden...")
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print("✅ EINDELIJK! De verbinding is live.")
    print("Antwoord:", message.content[0].text)
except Exception as e:
    print(f"❌ Fout: {e}")