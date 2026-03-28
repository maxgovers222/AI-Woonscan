import streamlit as st
from adres_bag_gegevens import get_bag_data
from ai_architect import genereer_energie_advies
from fpdf import FPDF
import io

# Functie om de PDF te maken
def create_pdf(rapport_tekst, adres):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Energie-advies: {adres}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", "", 12)
    # De AI tekst kan speciale tekens bevatten, we maken het simpel voor de PDF
    pdf.multi_cell(0, 10, rapport_tekst.encode('latin-1', 'ignore').decode('latin-1'))
    
    # Sla de PDF op in het geheugen
    return pdf.output()

# --- Website Layout ---
st.set_page_config(page_title="AI Woonscan", page_icon="🏠")
st.title("🏠 Mijn AI Woonscan")

adres_input = st.text_input("Vul hier het adres in:", placeholder="Bijv. Rode Schouw 40, Halsteren")

if st.button("Genereer Woonscan"):
    if adres_input:
        with st.spinner("Rapport maken..."):
            data = get_bag_data(adres_input)
            
            if data:
                st.success(f"Pand gevonden! Bouwjaar: {data['bouwjaar']}")
                
                # Toon de kaart
                map_data = [{"lat": data['lat'], "lon": data['lon']}]
                st.map(map_data)
                
                # AI Rapport maken
                rapport = genereer_energie_advies(data['bouwjaar'], data['oppervlakte'])
                st.markdown("---")
                st.markdown(rapport)
                
                # --- NIEUW: DE DOWNLOAD KNOP ---
                pdf_output = create_pdf(rapport, adres_input)
                
                st.download_button(
                    label="📥 Download rapport als PDF",
                    data=bytes(pdf_output),
                    file_name=f"Woonscan_{adres_input}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("Adres niet gevonden.")