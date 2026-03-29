import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Je bent een gecertificeerd Nederlandse energie-adviseur (BRL 9500 equivalent) 
met 20 jaar ervaring. Je schrijft professionele verduurzamingsrapporten die huiseigenaren 
écht helpen — met concrete cijfers, eerlijk advies en een duidelijk actieplan.

Schrijfstijl:
- Professioneel maar begrijpelijk voor iemand zonder technische kennis
- Altijd concreet: geen vage termen maar exacte bedragen, tijdlijnen en weblinks
- Eerlijk: als iets weinig oplevert voor dit specifieke huis, zeg dat gewoon
- Gebruik Markdown: kopjes (##), vetgedrukte tekst (**), tabellen en lijsten

Toon: alsof je een persoonlijk gesprek hebt met de huiseigenaar aan de keukentafel.

Subsidiekennis (gebruik altijd de meest actuele Nederlandse regelingen):
- ISDE (Investeringssubsidie Duurzame Energie): voor warmtepompen, zonneboilers. 
  Aanvragen via RVO.nl, doe dit VOOR de installatie.
- SEEH (Subsidie Energiebesparing Eigen Huis): voor isolatiemaatregelen zoals 
  spouwmuur, dak, vloer, glas. Aanvragen via RVO.nl, doe dit VOOR de werkzaamheden.
- Salderingsregeling: voor zonnepanelen, teruglevering aan net. 
  Geen aparte aanvraag nodig — automatisch via energieleverancier.
- Energiebespaarlening: lening via SVn (Stimuleringsfonds Volkshuisvesting) 
  voor verduurzaming, lage rente. Aanvragen via SVn.nl.
- BTW-verlaging zonnepanelen: 0% BTW op aankoop en installatie zonnepanelen op woningen.
  Geen aanvraag nodig — installateur rekent automatisch 0% BTW.
- Gemeentelijke subsidies: veel gemeenten hebben eigen regelingen bovenop de nationale. 
  Altijd checken op de website van de eigen gemeente.
"""

# ─────────────────────────────────────────────────────────────
#  CONTEXT HELPERS
# ─────────────────────────────────────────────────────────────

def _bouwjaar_context(bouwjaar) -> str:
    try:
        jaar = int(bouwjaar)
    except (ValueError, TypeError):
        return "Bouwjaar onbekend — geef algemeen advies maar vermeld de onzekerheid."

    if jaar < 1945:
        return (
            "Vooroorlogse woning (voor 1945): massieve muren zonder spouw, geen isolatie, "
            "hoge plafonds, enkelglas waarschijnlijk. Energieverbruik ligt typisch op "
            "3.000–5.000 m³ gas per jaar. Hoogste prioriteit: vloerisolatie, dakisolatie "
            "en HR++ glas. Spouwmuurisolatie is hier NIET mogelijk (geen spouw)."
        )
    elif jaar < 1965:
        return (
            "Vroeg-naoorlogse woning (1945–1964): spouwmuren aanwezig maar niet gevuld, "
            "geen of minimale isolatie, grotendeels enkelglas. Gasverbruik typisch "
            "2.500–4.000 m³/jaar. Spouwmuurisolatie is de goedkoopste en snelste maatregel. "
            "Daarna HR++ glas en dakisolatie."
        )
    elif jaar < 1975:
        return (
            "Naoorlogse woning (1965–1974): spouwmuren aanwezig maar niet gevuld, "
            "beperkte isolatie, veel enkelglas of oud dubbelglas. Gasverbruik typisch "
            "2.000–3.500 m³/jaar. Spouwmuurisolatie en HR++ glas zijn de meest rendabele stappen. "
            "Warmtepomp is haalbaar na isolatie-verbeteringen."
        )
    elif jaar < 1992:
        return (
            "Pre-EPBD woning (1975–1991): eerste isolatienormen aanwezig maar ruim onder "
            "huidige standaard. Gasverbruik typisch 1.800–2.800 m³/jaar. Dakisolatie en "
            "HR++ glas lonen goed. Hybride warmtepomp is een logische volgende stap "
            "zonder groot risico."
        )
    elif jaar < 2012:
        return (
            "Post-EPBD woning (1992–2011): redelijk geïsoleerd maar haalt geen label A. "
            "Gasverbruik typisch 1.200–2.000 m³/jaar. Focus op zonnepanelen, "
            "HR-ketel vervangen door hybride warmtepomp en eventueel dakisolatie verbeteren."
        )
    else:
        return (
            "Moderne woning (2012 of later): goed geïsoleerd, voldoet aan nieuwbouwnormen. "
            "Gasverbruik typisch 500–1.200 m³/jaar. Focus op zonnepanelen, thuisbatterij "
            "en volledige warmtepomp als de isolatie het toelaat. Mogelijkheid om gasvrij te worden."
        )


def _oppervlakte_context(oppervlakte) -> str:
    try:
        m2 = int(oppervlakte)
    except (ValueError, TypeError):
        return ""

    if m2 < 60:
        return f"Kleine woning ({m2} m²): lagere absolute besparingen maar hoge besparingsratio mogelijk."
    elif m2 < 100:
        return f"Compacte woning ({m2} m²): gemiddelde verwarmingsbehoefte."
    elif m2 < 150:
        return f"Gemiddelde woning ({m2} m²): typisch Nederlandse gezinswoning."
    elif m2 < 250:
        return f"Grote woning ({m2} m²): hogere energierekening maar ook hogere absolute besparingen."
    else:
        return f"Zeer grote woning ({m2} m²): energieverbruik en besparingspotentieel zijn fors."


# ─────────────────────────────────────────────────────────────
#  HOOFD FUNCTIE
# ─────────────────────────────────────────────────────────────

def genereer_energie_advies(bouwjaar, oppervlakte, woningtype="Woning") -> str:
    """
    Genereert een uitgebreid verduurzamingsrapport inclusief subsidie-aanvraaginstructies.

    Args:
        bouwjaar:    Bouwjaar van het pand (int of str)
        oppervlakte: Gebruiksoppervlakte in m² (int, float of str)
        woningtype:  Beschrijving van het type woning

    Returns:
        Uitgebreide Markdown-string met het volledige rapport.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "**Fout:** Geen `ANTHROPIC_API_KEY` gevonden. Controleer je `.env` of Streamlit Secrets."

    bouwjaar_ctx    = _bouwjaar_context(bouwjaar)
    oppervlakte_ctx = _oppervlakte_context(oppervlakte)

    prompt = f"""Schrijf een volledig, professioneel verduurzamingsrapport voor deze woning.

## Woningdata (officieel uit Kadaster BAG)
- Bouwjaar: {bouwjaar}
- Gebruiksoppervlakte: {oppervlakte} m²
- Woningtype: {woningtype}

## Technische context
{bouwjaar_ctx}
{oppervlakte_ctx}

## Opdracht

Schrijf een uitgebreid rapport met EXACT deze structuur en volgorde:

---

## 🏠 Woningprofiel

Schrijf 3-4 zinnen over de huidige staat van deze specifieke woning op basis van het bouwjaar 
en de oppervlakte. Wat zijn de typische kenmerken? Wat is het geschatte huidige gasverbruik 
in m³/jaar en de energierekening in €/jaar (gebruik realistische Nederlandse gemiddelden)?
Wat is het geschatte huidige energielabel?

---

## ⚡ Uw Besparingspotentieel

Eén krachtige zin: hoeveel kan deze eigenaar maximaal besparen per jaar als hij alles doet?
Vermeld ook hoeveel CO₂ dat scheelt (in kg/jaar).

---

## 📋 Aanbevelingen (van meest naar minst rendabel)

Geef voor ELKE maatregel die relevant is voor dit huis een apart blok.
Geef minimaal 5 en maximaal 8 maatregelen. Alleen maatregelen die realistisch zijn voor dit huis.

### [Naam maatregel]
- **Wat het is:** Leg in één zin uit wat dit is voor iemand zonder technische kennis
- **Waarom nu:** Waarom is dit specifiek voor dit huis en bouwjaar de juiste keuze?
- **Investering:** € [bedrag] – € [bedrag]
- **Jaarlijkse besparing:** € [bedrag] – € [bedrag] per jaar
- **Terugverdientijd:** [X] – [Y] jaar
- **Prioriteit:** [Hoog / Middel / Laag]
- **Subsidie beschikbaar:** [Ja — [naam regeling] / Nee]
- **Subsidiebedrag:** [€ bedrag of percentage, of "n.v.t."]
- **Zo vraagt u het aan:**
  1. [Stap 1 — concrete handeling, bijv. "Ga naar rvo.nl/isde"]
  2. [Stap 2 — bijv. "Klik op 'Aanvragen' en log in met DigiD"]
  3. [Stap 3 — bijv. "Vraag aan VÓÓR de installatie — achteraf aanvragen werkt niet"]
  4. [Eventuele stap 4 — bijv. "Upload de offerte van de installateur"]
  - **Let op:** [Eventuele valkuil of deadline, bijv. "Aanvragen moet vóór de werkzaamheden starten"]

---

## 💰 Kostenoverzicht

| Maatregel | Investering | Subsidie | Netto investering | Besparing/jaar | Terugverdientijd |
|-----------|------------|---------|------------------|----------------|-----------------|
| ...       | € ...      | € ...   | € ...            | € ...          | ... jaar        |

---

## 🏦 Financiering zonder eigen geld

Schrijf een korte paragraaf (3-4 zinnen) over de Energiebespaarlening via SVn.nl. 
Leg uit dat mensen ook kunnen verduurzamen zonder eigen spaargeld, wat de rente 
ongeveer is, en hoe ze meer informatie kunnen vinden op svn.nl/energiebespaarlening.

---

## 📅 Aanbevolen Aanpak

Verdeel de maatregelen over een tijdlijn:

**Dit jaar (quick wins):** [2-3 maatregelen — hoogste rendement of laagste investering]

**Over 1-3 jaar:** [Grotere investeringen die logisch volgen na de quick wins]

**Op lange termijn (3-10 jaar):** [Grote renovaties of vervanging van installaties]

---

## 🎯 Uw Eerste Stap Deze Week

Één concrete, praktische actie die de eigenaar deze week kan zetten.
Geen vaag advies maar een specifieke handeling met een echte website of telefoonnummer.
Bijvoorbeeld: "Ga naar subsidiewijzer.rvo.nl en vul uw situatie in om te zien welke 
subsidies u kunt aanvragen — dit duurt 5 minuten."

---

## ℹ️ Disclaimer

Sluit af met twee zinnen dat dit rapport indicatief is op basis van BAG-data en dat een 
erkend energieadviseur een officieel EPA-maatwerkadvies kan opstellen voor een nauwkeurigere analyse.
Vermeld dat subsidieregelingen kunnen wijzigen en de eigenaar dit altijd even checkt op rvo.nl.

---

Gebruik realistische Nederlandse prijzen en subsidiebedragen van 2024-2025.
Wees specifiek en concreet. De subsidie-aanvraaginstructies moeten zo duidelijk zijn 
dat iemand ze direct kan volgen zonder verdere hulp.
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    except Exception as e:
        return f"**AI-fout:** {str(e)}\n\nControleer je API-sleutel en probeer opnieuw."


if __name__ == "__main__":
    print(genereer_energie_advies(bouwjaar=1968, oppervlakte=112, woningtype="Tussenwoning"))