import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Je bent een gecertificeerd Nederlandse energie-adviseur met 20 jaar praktijkervaring.
Je schrijft beknopte, eerlijke verduurzamingsrapporten die huiseigenaren direct helpen beslissen.

Schrijfprincipes:
- Schrijf als een expert die praat met de eigenaar, niet als een ambtenaar die een formulier invult
- Elke zin moet een nut hebben — geen opvulling, geen herhaling
- Concrete euro-bedragen en jaren, geen vage termen als "aanzienlijk" of "significant"
- Eerlijk: als een maatregel weinig oplevert voor dit specifieke huis, zeg dat
- Gebruik Markdown: ## voor hoofdstukken, ### voor maatregelen, ** voor vetgedrukt, tabellen
- Gebruik GEEN emoji's in kopjes — die horen niet in een professioneel rapport
"""


def _bouwjaar_context(bouwjaar) -> str:
    try:
        jaar = int(bouwjaar)
    except (ValueError, TypeError):
        return "Bouwjaar onbekend — geef algemeen advies maar vermeld de onzekerheid."

    if jaar < 1945:
        return (
            "Vooroorlogse woning (voor 1945): massieve muren zonder spouw, geen isolatie, "
            "hoge plafonds, enkelglas waarschijnlijk. Gasverbruik typisch 3.000–5.000 m³/jaar. "
            "Prioriteit: vloerisolatie, dakisolatie, HR++ glas. "
            "Spouwmuurisolatie is NIET mogelijk — er is geen spouw."
        )
    elif jaar < 1965:
        return (
            "Vroeg-naoorlogse woning (1945–1964): spouwmuren aanwezig maar leeg, "
            "weinig tot geen isolatie, grotendeels enkelglas. Gasverbruik typisch 2.500–4.000 m³/jaar. "
            "Spouwmuurisolatie is de goedkoopste en snelste eerste stap."
        )
    elif jaar < 1975:
        return (
            "Naoorlogse woning (1965–1974): spouwmuren aanwezig maar leeg, "
            "beperkte isolatie, veel enkel- of oud dubbelglas. Gasverbruik typisch 2.000–3.500 m³/jaar. "
            "Spouwmuurisolatie en HR++ glas zijn de meest rendabele stappen. "
            "Warmtepomp is haalbaar na isolatieverbetering."
        )
    elif jaar < 1992:
        return (
            "Pre-EPBD woning (1975–1991): eerste isolatienormen aanwezig maar ruim onder huidige standaard. "
            "Gasverbruik typisch 1.800–2.800 m³/jaar. Dakisolatie en HR++ glas lonen goed. "
            "Hybride warmtepomp is een logische volgende stap zonder groot risico."
        )
    elif jaar < 2012:
        return (
            "Post-EPBD woning (1992–2011): redelijk geïsoleerd maar haalt geen label A. "
            "Gasverbruik typisch 1.200–2.000 m³/jaar. "
            "Focus op zonnepanelen, hybride warmtepomp ter vervanging van de HR-ketel."
        )
    else:
        return (
            "Moderne woning (2012 of later): goed geïsoleerd, voldoet aan nieuwbouwnormen. "
            "Gasverbruik typisch 500–1.200 m³/jaar. "
            "Focus op zonnepanelen en volledige warmtepomp. Gasvrij worden is realistisch."
        )


def _oppervlakte_context(oppervlakte) -> str:
    try:
        m2 = int(oppervlakte)
    except (ValueError, TypeError):
        return ""

    if m2 < 60:
        return f"Kleine woning ({m2} m²): absolute besparingen zijn lager, maar ratio kan hoog zijn."
    elif m2 < 100:
        return f"Compacte woning ({m2} m²): gemiddelde verwarmingsbehoefte."
    elif m2 < 150:
        return f"Gemiddelde woning ({m2} m²): typisch Nederlandse gezinswoning."
    elif m2 < 250:
        return f"Grote woning ({m2} m²): hogere energierekening, maar ook hogere absolute besparingen."
    else:
        return f"Zeer grote woning ({m2} m²): fors energieverbruik en fors besparingspotentieel."


def genereer_energie_advies(bouwjaar, oppervlakte, woningtype="Woning") -> str:
    """
    Genereert een beknopt, goed gestructureerd verduurzamingsrapport.

    Args:
        bouwjaar:    Bouwjaar van het pand (int of str)
        oppervlakte: Gebruiksoppervlakte in m² (int, float of str)
        woningtype:  Beschrijving van het type woning

    Returns:
        Markdown-string met het volledige rapport.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "**Fout:** Geen `ANTHROPIC_API_KEY` gevonden. Controleer je `.env` of Streamlit Secrets."

    bouwjaar_ctx    = _bouwjaar_context(bouwjaar)
    oppervlakte_ctx = _oppervlakte_context(oppervlakte)

    prompt = f"""Schrijf een professioneel verduurzamingsrapport voor deze woning.

## Woningdata (officieel uit Kadaster BAG)
- Bouwjaar: {bouwjaar}
- Gebruiksoppervlakte: {oppervlakte} m²
- Woningtype: {woningtype}

## Technische context voor jouw advies
{bouwjaar_ctx}
{oppervlakte_ctx}

## Structuur van het rapport

Gebruik EXACT deze volgorde en kopjes. Geen emoji's in kopjes.

---

## Woningprofiel

2-3 zinnen. Beschrijf de woning op basis van bouwjaar en oppervlakte: typische bouwkenmerken,
geschat huidig energieverbruik (m³ gas/jaar én €/jaar op basis van €1,10/m³),
en het geschatte huidige energielabel. Wees specifiek.

---

## Wat kunt u besparen?

Één krachtige zin: maximale jaarlijkse besparing in euro's als alle maatregelen worden genomen.
Tweede zin: hoeveel CO₂ dat scheelt (in kg/jaar).
Derde zin: hoe dit zich verhoudt tot de gemiddelde Nederlandse woning van dit type.

---

## Overzicht van aanbevolen maatregelen

Geef hier direct de overzichtstabel — vóór de details. Dit geeft de eigenaar meteen een totaalplaatje.

| Maatregel | Investering | Netto na subsidie | Besparing/jaar | Terugverdientijd |
|-----------|------------|------------------|----------------|-----------------|
| ...       | € ...      | € ...            | € ...          | ... jaar        |

Voeg onder de tabel één zin toe over de Energiebespaarlening (SVn.nl) als optie voor wie
niet alles zelf wil voorfinancieren.

---

## Aanbevelingen in detail

Geef 5 tot 8 maatregelen, gesorteerd van hoogste naar laagste rendement.
Alleen maatregelen die realistisch zijn voor dit specifieke huis en bouwjaar.

Voor elke maatregel:

### [Naam maatregel]

- **Wat:** Één zin uitleg voor een leek
- **Waarom voor dit huis:** Specifiek voor dit bouwjaar en deze situatie
- **Investering:** € X.XXX – € X.XXX
- **Besparing per jaar:** € XXX – € XXX
- **Terugverdientijd:** X – Y jaar
- **Subsidie:** [Naam regeling, bedrag/percentage, en of je dit vóór of na de installatie aanvraagt via welke website] of "Geen subsidie beschikbaar"

Houd de subsidie-informatie compact: één regel, niet meer. De eigenaar zoekt zelf de details op.

---

## Aanpak in de tijd

Verdeel de maatregelen over een praktische tijdlijn:

**Dit jaar — quick wins:** Maatregelen met de beste prijs/kwaliteit verhouding of laagste investering

**Over 1-3 jaar:** Grotere investeringen die logisch volgen na de quick wins

**Op lange termijn:** Grote renovaties of vervanging van installaties op het einde van hun levensduur

---

## Eerste stap deze week

Één concrete actie. Geen vage aanrading — een specifieke website, telefoonnummer of handeling.
Maximaal 2 zinnen.

---

## Disclaimer

Dit rapport is indicatief op basis van Kadaster BAG-gegevens en AI-analyse en vervangt geen
officieel EPA-maatwerkadvies. Subsidieregelingen wijzigen regelmatig — controleer de actuele
voorwaarden altijd op rvo.nl vóór u een aanvraag indient.

---

Schrijf alsof je dit persoonlijk uitlegt aan de eigenaar. Gebruik geen opvulzinnen.
Gebruik realistische Nederlandse prijzen en subsidiebedragen van 2024-2025.
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    except Exception as e:
        return f"**AI-fout:** {str(e)}\n\nControleer je API-sleutel en probeer opnieuw."


if __name__ == "__main__":
    print(genereer_energie_advies(bouwjaar=1968, oppervlakte=112, woningtype="Tussenwoning"))