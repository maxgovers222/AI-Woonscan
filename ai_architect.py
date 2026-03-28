import os
from anthropic import Anthropic
from dotenv import load_dotenv

# Laad de kluis
load_dotenv()

# Maak de AI-cliënt aan
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def genereer_energie_advies(bouwjaar, oppervlakte, woningtype="Woning"):
    """
    Stuurt de BAG-data naar Claude 3.5 Sonnet voor een professioneel advies.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Fout: Geen ANTHROPIC_API_KEY gevonden in .env"

    prompt = (
        f"Je bent een energie-adviseur. Gegevens woning:\n"
        f"- Bouwjaar: {bouwjaar}\n"
        f"- Oppervlakte: {oppervlakte} m2\n"
        f"- Woningtype: {woningtype}\n\n"
        f"Schrijf een concreet verduurzamingsadvies in Markdown met kopjes voor: "
        f"Isolatie, Warmtepomp en Thuisbatterij."
    )

    try:
        # We gebruiken 'latest' zonder datum om de meest actuele versie te dwingen
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system="Je bent een Nederlandse energie-adviseur. Geef technisch en eerlijk advies.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        # Dit print de exacte reden waarom Anthropic nee zegt
        return f"AI-fout details: {str(e)}"

if __name__ == "__main__":
    # Testje
    print(genereer_energie_advies(1980, 251))