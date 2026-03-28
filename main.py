import sys
from adres_bag_gegevens import get_bag_data # Zorg dat je functie in dat bestand zo heet
from ai_architect import genereer_energie_advies

def start_woonscan(adres_tekst):
    print(f"🚀 Start scan voor: {adres_tekst}...")
    
    # STAP 1: Haal data op uit de overheidskranen
    # We gaan ervan uit dat je adres_bag_gegevens functie de data als dictionary teruggeeft
    data = get_bag_data(adres_tekst)
    
    if not data:
        print("❌ Kon geen data vinden voor dit adres.")
        return

    print(f"✅ Data gevonden: Bouwjaar {data['bouwjaar']}, Oppervlakte {data['oppervlakte']}m2")

    # STAP 2: Stuur data naar het AI Brein
    print("🤖 AI is een rapport aan het schrijven...")
    rapport = genereer_energie_advies(
        bouwjaar=data['bouwjaar'], 
        oppervlakte=data['oppervlakte'], 
        woningtype=data.get('woningtype', 'onbekend')
    )

    # STAP 3: Resultaat tonen (of opslaan als PDF)
    print("\n" + "="*30)
    print("UW GEPERSONALISEERDE WOONSCAN")
    print("="*30 + "\n")
    print(rapport)

    # Bestand opslaan
    bestandsnaam = f"Woonscan_{adres_tekst.replace(' ', '_').replace(',', '')}.md"
    with open(bestandsnaam, "w", encoding="utf-8") as f:
        f.write(f"# Energie-advies: {adres_tekst}\n\n")
        f.write(rapport)
    print(f"💾 Rapport opgeslagen als: {bestandsnaam}")

if __name__ == "__main__":
    # Pak het adres uit de opdrachtregel (bijv: python main.py "Hoofdstraat 1, Utrecht")
    adres = sys.argv[1] if len(sys.argv) > 1 else "Abel Eppensstraat 1, Delfzijl"
    start_woonscan(adres)


