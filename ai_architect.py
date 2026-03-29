import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Je bent een gecertificeerd Nederlandse energie-adviseur (BRL 9500 equivalent).
Je geeft technisch onderbouwd, eerlijk en praktisch verduurzamingsadvies op basis van officiële BAG-woningdata.

Schrijfstijl:
- Professioneel maar toegankelijk voor een huiseigenaar zonder technische achtergrond
- Concreet: noem altijd een geschatte besparing in €/jaar en terugverdientijd
- Eerlijk: als een maatregel weinig oplevert voor dit specifieke huis, zeg dat dan
- Gebruik Markdown met duidelijke kopjes (##) en eventueel een tabel voor overzicht

Structuur van elk rapport:
1. Korte samenvatting (2 zinnen, krachtig)
2. Woningprofiel & startsituatie
3. Top aanbevelingen (geprioriteerd op rendement)
4. Kostenoverzicht-tabel (maatregel | investering | besparing/jaar | terugverdientijd | subsidie beschikbaar?)
5. Volgende stap voor de eigenaar
"""

def _bouwjaar_context(bouwjaar) -> str:
    """Geeft extra context mee aan het model op basis van bouwjaar."""
    try:
        jaar = int(bouwjaar)
    except (ValueError, TypeError):
        return ""

    if jaar < 1945:
        return "Vooroorlogse woning: dikke muren (spouwloos), hoge plafonds, geen isolatie. Hoge prioriteit voor vloer- en dakisolatie."
    elif jaar < 1975:
        return "Naoorlogse bouw: spouwmuren maar niet gevuld, enkel glas waarschijnlijk. HR++ glas en spouwmuurisolatie zijn de meest rendabele stappen."
    elif jaar < 1992:
        return "Pre-EPBD woning: basis isolatie aanwezig maar ruim onder moderne norm. Warmtepomp combinatie met dakisolatie is kansrijk."
    elif jaar < 2012:
        return "Woning van vóór 2012: voldoet aan toenmalige normen maar haalt geen energielabel A. Na-isolatie dak en HR++ ketel-vervanging loont."
    else:
        return "Relatief nieuwbouw: al behoorlijk goed geïsoleerd. Focus op zonnepanelen, thuisbatterij en eventueel hybride warmtepomp."

def genereer_energie_advies(bouwjaar, oppervlakte, woningtype="Woning") -> str:
    """
    Genereert een gestructureerd verduurzamingsrapport via Claude.

    Args:
        bouwjaar:    Bouwjaar van het pand (int of str)
        oppervlakte: Gebruiksoppervlakte in m² (int, float of str)
        woningtype:  Beschrijving van het type woning

    Returns:
        Markdown-string met het volledige rapport, of een foutmelding.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "**Fout:** Geen `ANTHROPIC_API_KEY` gevonden. Controleer je `.env` of Streamlit Secrets."

    extra_context = _bouwjaar_context(bouwjaar)

    prompt = f"""Analyseer de volgende woning en schrijf een volledig verduurzamingsrapport:

**Woningdata (officieel uit Kadaster BAG):**
- Bouwjaar: {bouwjaar}
- Gebruiksoppervlakte: {oppervlakte} m²
- Woningtype: {woningtype}

**Aanvullende context:**
{extra_context if extra_context else "Geen aanvullende context beschikbaar."}

**Opdracht:**
Schrijf een gepersonaliseerd verduurzamingsrapport met de structuur uit je instructies.
Prioriteer maatregelen op rendement (hoogste €-besparing per geïnvesteerde euro eerst).
Vermeld bij elke maatregel of er ISDE-, SEEH- of salderingssubsidie van toepassing is.
Sluit af met één concrete actie die de eigenaar deze week kan zetten.
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    except Exception as e:
        return f"**AI-fout:** {str(e)}\n\nControleer je API-sleutel en probeer opnieuw."


if __name__ == "__main__":
    # Lokale test
    print(genereer_energie_advies(bouwjaar=1968, oppervlakte=112, woningtype="Tussenwoning"))
