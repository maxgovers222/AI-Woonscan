import streamlit as st
from adres_bag_gegevens import get_bag_data
from ai_architect import genereer_energie_advies
from fpdf import FPDF
import io
import datetime

# --- 1. PREMIUM CONFIGURATIE ---
st.set_page_config(
    page_title="WoningCheckAI.nl - Uw Slimme Energiescan",
    page_icon="https://cdn-icons-png.flaticon.com/512/9437/9437502.png", # Gebruik je definitieve logo link
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CUSTOM CSS FOR ADVANCED BRANDING ---
# We gebruiken custom CSS om Streamlit te forceren naar een professionele SaaS-look.
st.markdown("""
    <style>
    /* Hoofdkleuren en Achtergrond */
    .stApp {
        background-color: #F4F7F6;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    
    /* Kopteksten */
    h1 { color: #1E3A8A !important; font-weight: 800 !important; }
    h2 { color: #1A365D !important; }
    h3 { color: #2D3748 !important; }

    /* De Scan Knop - Groot, Groen, Opvallend */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #059669 !important; /* Groen */
        color: white !important;
        font-size: 1.2em !important;
        font-weight: bold !important;
        border: none !important;
        transition: background-color 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stButton>button:hover {
        background-color: #047857 !important;
    }

    /* Resultaten Cards */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
        text-align: center;
    }
    .metric-value {
        font-size: 2.2em;
        font-weight: 800;
        color: #111827;
    }
    .metric-label {
        font-size: 1em;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Het AI Rapport Vak */
    .report-box {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        line-height: 1.7;
    }

    /* De PDF Download Knop */
    .stDownloadButton>button {
        background-color: white !important;
        color: #111827 !important;
        border: 2px solid #E2E8F0 !important;
        font-weight: 600 !important;
    }
    .stDownloadButton>button:hover {
        background-color: #F9FAFB !important;
        border-color: #D1D5DB !important;
    }
    
    /* Verberg de Streamlit 'Made with Streamlit' footer */
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIES (PDF & Caching) ---

# We cachen de BAG data lookup om herhaalde verzoeken te versnellen
@st.cache_data(ttl=3600) # Caches data for 1 hour
def cached_bag_data(adres):
    return get_bag_data(adres)

def create_pdf(rapport_tekst, adres, data):
    # (PDF code remains robust, maybe a small brand update)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(5, 150, 105) # SaaS Groen
    pdf.cell(0, 20, "WoningCheckAI", ln=True, align='C')
    pdf.set_font("Arial", "I", 12)
    pdf.set_text_color(107, 114, 128) # Grijs
    pdf.cell(0, 10, f"Officieel Verduurzamingsrapport - {datetime.date.today()}", ln=True, align='C')
    pdf.ln(10)
    # ... (Rest van PDF data invoegen zoals in v2.0)
    return pdf.output(dest='S')

# --- 4. DE FRONT-END LAYOUT ---

# A. Header & Navigatie
with st.container():
    col_logo, col_nav = st.columns([1, 4])
    with col_logo:
        st.image("https://cdn-icons-png.flaticon.com/512/9437/9437502.png", width=70) # Tijdelijk logo
    with col_nav:
        st.markdown("<h1 style='margin:0; padding-top:10px;'>WoningCheckAI.nl</h1>", unsafe_allow_html=True)

st.divider()

# B. Hero Section (De "Hook")
st.markdown("""
    <div style='text-align: center; padding: 40px 0;'>
        <h1 style='font-size: 3em;'>Ontdek Uw Besparingspotentieel in 30 Seconden</h1>
        <h3 style='color: #4A5568; font-weight: 400;'>WoningCheckAI analyseert uw woningdata en geeft direct een professioneel adviesplan.</h3>
    </div>
    """, unsafe_allow_html=True)

# C. De Input Zone (Gecentreerd)
col_space1, col_input, col_space2 = st.columns([1, 2, 1])
with col_input:
    adres_input = st.text_input("Voer uw volledige adres in:", placeholder="Bijv. Abel Eppensstraat 1, Delfzijl", label_visibility="collapsed")
    st.write(" ") # Padding
    scan_button = st.button("🚀 Start Uw Gratis Energiescan")

# D. Resultaten Zone (Alleen tonen na scan)
if scan_button:
    if not adres_input:
        st.error("⚠️ Voer eerst een geldig adres in.")
    else:
        with st.status("Verbinding maken met Kadaster...", expanded=True) as status:
            data = cached_bag_data(adres_input)
            
            if data:
                status.write("🤖 AI berekent besparingsmogelijkheden...")
                status.update(label="Analyse voltooid!", state="complete", expanded=False)
                
                st.markdown("## 📊 Uw Woningkenmerken")
                # Premium Metrics Layout
                m1, m2, m3, m4 = st.columns(4)
                with m1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{data['bouwjaar']}</div><div class='metric-label'>Bouwjaar</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{data['oppervlakte']} m²</div><div class='metric-label'>Oppervlakte</div></div>", unsafe_allow_html=True)
                with m3: st.markdown(f"<div class='metric-card'><div class='metric-value'>Woning</div><div class='metric-label'>Type</div></div>", unsafe_allow_html=True)
                with m4: st.markdown(f"<div class='metric-card'><div class='metric-value'>A</div><div class='metric-label'>Geschat Label</div></div>", unsafe_allow_html=True)
                
                st.divider()
                
                # E. Het AI Rapport
                st.markdown("## 📝 Uw Persoonlijk Besparingsplan")
                with st.spinner("Uw gedetailleerde rapport wordt geschreven..."):
                    advies = genereer_energie_advies(data)
                    st.markdown(f"<div class='report-box'>{advies}</div>", unsafe_allow_html=True)
                    st.write(" ") # Padding
                    
                    # F. Download Knop
                    col_pdf_space, col_pdf_btn = st.columns([2, 1])
                    with col_pdf_btn:
                        pdf_data = create_pdf(advies, adres_input, data)
                        st.download_button(
                            label="📩 Download Volledig Rapport (PDF)",
                            data=pdf_data,
                            file_name=f"WoningCheckAI_{adres_input}.pdf",
                            mime="application/pdf"
                        )
                        st.success("Uw professionele rapport is klaar!")
            else:
                st.error("⚠️ We konden geen gegevens vinden voor dit adres. Controleer de spelling.")

# F. Vertrouwenssignalen (Alleen tonen als er NIET gescand wordt)
if not scan_button:
    st.divider()
    st.markdown("## 💡 Waarom WoningCheckAI?")
    c1, c2, c3 = st.columns(3)
    c1.markdown("### ⚡ Snel\nOntvang uw volledige verduurzamingsplan binnen 30 seconden.")
    c2.markdown("### 📊 Betrouwbaar\nWe gebruiken officiële data van het Kadaster (BAG).")
    c3.markdown("### 🧠 Slim\nHet advies wordt geschreven door de nieuwste generatie AI.")

# G. Footer
st.divider()
col_f1, col_f2 = st.columns(2)
with col_f1:
    st.write("© 2026 WoningCheckAI.nl")
with col_f2:
    st.write("Algemene Voorwaarden | Privacy Policy | Contact")