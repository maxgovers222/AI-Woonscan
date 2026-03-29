import streamlit as st
import datetime
import os
import urllib.parse
from adres_bag_gegevens import get_bag_data
from ai_architect import genereer_energie_advies
from database import sla_scan_op, zoek_bestaand_rapport, haal_recente_scans_op, is_supabase_actief
from fpdf import FPDF

# ─────────────────────────────────────────────────────────────
#  PAGINA CONFIGURATIE
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WoningCheckAI – Gratis Energiescan",
    page_icon="🏡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
#  STRIPE
#  Hoe het werkt:
#  1. Gebruiker scant een adres → ziet gratis preview
#  2. Klikt op betaalknop → adres wordt opgeslagen in sessie
#  3. Stripe stuurt hem terug naar ?betaald=ja
#  4. App leest adres uit sessie → toont volledig rapport + PDF
# ─────────────────────────────────────────────────────────────

STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK", "")
APP_URL             = os.getenv("APP_URL", "https://ai-woonscan-qdkwobbescefekt7zxo6j6.streamlit.app")


def maak_stripe_url(adres: str = "") -> str:
    """Geeft de Stripe betaallink terug met het adres in de success URL."""
    if not STRIPE_PAYMENT_LINK:
        return ""
    # Adres veilig encoderen voor gebruik in URL
    adres_encoded = urllib.parse.quote(adres, safe="")
    success_url = f"{APP_URL}?betaald=ja&adres={adres_encoded}"
    # Success URL encoderen voor meegeven aan Stripe
    return f"{STRIPE_PAYMENT_LINK}?success_url={urllib.parse.quote(success_url, safe=':/?=&')}"


def controleer_betaling() -> tuple[bool, str]:
    """Geeft (True, adres) terug als Stripe de gebruiker heeft teruggestuurd."""
    params = st.query_params
    betaald = params.get("betaald", "") == "ja"
    adres   = urllib.parse.unquote(params.get("adres", ""))
    return betaald, adres


# ─────────────────────────────────────────────────────────────
#  RAPPORT SPLITTER
#  Knipt het AI-rapport op in een gratis preview en een betaald deel.
#  De gratis preview bevat alles t/m het eerste kopje na het
#  besparingspotentieel. De rest is verborgen achter de betaalmuur.
# ─────────────────────────────────────────────────────────────

def splits_rapport(rapport: str) -> tuple[str, str]:
    """
    Geeft (preview, rest) terug.
    Preview = eerste twee secties (Woningprofiel + Besparingspotentieel).
    Rest    = alles daarna (maatregelen, tabel, tijdlijn, subsidies).
    """
    lijnen    = rapport.split("\n")
    kopjes    = 0
    splitpunt = len(lijnen)

    for i, lijn in enumerate(lijnen):
        if lijn.startswith("## ") or lijn.startswith("# "):
            kopjes += 1
            # Na het 3e kopje (Aanbevelingen) knippen we
            if kopjes == 3:
                splitpunt = i
                break

    preview = "\n".join(lijnen[:splitpunt]).strip()
    rest    = "\n".join(lijnen[splitpunt:]).strip()
    return preview, rest


# ─────────────────────────────────────────────────────────────
#  PDF HELPER
# ─────────────────────────────────────────────────────────────
def create_pdf(rapport_tekst: str, adres: str, bouwjaar, oppervlakte) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_fill_color(15, 40, 80)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 20)
    pdf.set_xy(0, 9)
    pdf.cell(210, 12, "WoningCheckAI.nl", align="C", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(210, 6, "Persoonlijk Verduurzamingsrapport", align="C", ln=True)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(180, 210, 255)
    pdf.cell(210, 6, f"Gegenereerd op {datetime.date.today().strftime('%d %B %Y')}", align="C", ln=True)
    pdf.ln(12)

    pdf.set_text_color(15, 40, 80)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, f"Adres: {adres}", ln=True)
    pdf.set_draw_color(15, 40, 80)
    pdf.set_line_width(0.4)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(60, 7, f"Bouwjaar: {bouwjaar}", ln=False)
    pdf.cell(0, 7, f"Gebruiksoppervlakte: {oppervlakte} m2", ln=True)
    pdf.ln(5)

    pdf.set_text_color(25, 25, 25)
    pdf.set_font("Arial", "", 11)
    safe_text = rapport_tekst.encode("latin-1", "replace").decode("latin-1")
    for sym in ["##", "**", "__", "---", "```", "# "]:
        safe_text = safe_text.replace(sym, "")
    pdf.multi_cell(0, 7, safe_text)

    pdf.set_y(-18)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 8,
             "WoningCheckAI.nl  |  AI-gegenereerd rapport  |  Alleen indicatief - geen officieel energielabel",
             align="C")

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────
#  GECACHEDE DATA-FUNCTIES
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def cached_bag_data(adres: str):
    return get_bag_data(adres)

@st.cache_data(ttl=3600, show_spinner=False)
def cached_advies(bouwjaar, oppervlakte, woningtype: str) -> str:
    return genereer_energie_advies(bouwjaar, oppervlakte, woningtype)


def schat_energielabel(bouwjaar) -> str:
    try:
        jaar = int(bouwjaar)
    except (ValueError, TypeError):
        return "?"
    if jaar >= 2015: return "A"
    if jaar >= 2000: return "B"
    if jaar >= 1990: return "C"
    if jaar >= 1975: return "D"
    if jaar >= 1960: return "E"
    return "F"


# ─────────────────────────────────────────────────────────────
#  SESSION STATE INITIALISATIE
#  We slaan het adres op in de sessie zodat we het nog weten
#  nadat Stripe de gebruiker heeft teruggestuurd.
# ─────────────────────────────────────────────────────────────
if "huidig_adres" not in st.session_state:
    st.session_state.huidig_adres = ""
if "huidig_rapport" not in st.session_state:
    st.session_state.huidig_rapport = ""
if "huidig_bouwjaar" not in st.session_state:
    st.session_state.huidig_bouwjaar = ""
if "huidig_oppervlakte" not in st.session_state:
    st.session_state.huidig_oppervlakte = ""


# ─────────────────────────────────────────────────────────────
#  CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

  :root {
    --navy:     #0F2850;
    --navy-mid: #1A3A6B;
    --teal:     #0EA87E;
    --teal-lt:  #12C991;
    --bg:       #F4F6FA;
    --surface:  #FFFFFF;
    --text:     #1C2333;
    --muted:    #6B7A99;
    --border:   #DDE3EF;
    --r:        14px;
    --sh:       0 4px 24px rgba(15,40,80,.09);
    --sh-lg:    0 12px 48px rgba(15,40,80,.14);
  }

  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
  }
  [data-testid="stHeader"] { background: transparent !important; }
  footer, #MainMenu { display: none !important; }

  .hero {
    background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 55%, #1E4D8C 100%);
    border-radius: var(--r); padding: 52px 40px 46px;
    margin-bottom: 28px; text-align: center;
    position: relative; overflow: hidden; box-shadow: var(--sh-lg);
  }
  .hero::before {
    content:''; position:absolute; top:-70px; right:-70px;
    width:260px; height:260px; border-radius:50%;
    background:rgba(14,168,126,.11);
  }
  .hero::after {
    content:''; position:absolute; bottom:-90px; left:-50px;
    width:220px; height:220px; border-radius:50%;
    background:rgba(255,255,255,.04);
  }
  .hero-badge {
    display:inline-block;
    background:rgba(14,168,126,.18); border:1px solid rgba(14,168,126,.40);
    color:var(--teal-lt); font-size:.71rem; font-weight:500;
    letter-spacing:1.3px; text-transform:uppercase;
    padding:4px 14px; border-radius:999px; margin-bottom:18px;
  }
  .hero-logo { font-family:'Syne',sans-serif; font-weight:800;
               font-size:2.3rem; color:#fff; letter-spacing:-.5px; line-height:1; }
  .hero-logo span { color:var(--teal-lt); }
  .hero-sub { font-weight:300; font-size:1.05rem; color:rgba(255,255,255,.70); margin-top:10px; }

  .card {
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--r); padding:30px 32px;
    box-shadow:var(--sh); margin-bottom:22px;
  }
  .card-title {
    font-family:'Syne',sans-serif; font-weight:700; font-size:1.1rem;
    color:var(--navy); border-bottom:2px solid var(--border);
    padding-bottom:14px; margin-bottom:20px;
  }

  .pills { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
  .pill { flex:1; min-width:110px; background:var(--bg);
          border:1px solid var(--border); border-radius:10px;
          padding:14px 16px; text-align:center; }
  .pill-lbl { font-size:.68rem; font-weight:500; letter-spacing:.9px;
              text-transform:uppercase; color:var(--muted); margin-bottom:6px; }
  .pill-val { font-family:'Syne',sans-serif; font-weight:700;
              font-size:1.45rem; color:var(--navy); line-height:1; }
  .pill-unit { font-size:.78rem; color:var(--muted); margin-top:3px; }

  .accent { height:4px; border-radius:4px; margin-bottom:22px;
            background:linear-gradient(90deg,var(--teal),var(--teal-lt)); }

  .report-body { font-size:.97rem; line-height:1.78; color:var(--text); }
  .report-body h2,.report-body h3 { font-family:'Syne',sans-serif; color:var(--navy); margin-top:1.3em; }
  .report-body table { width:100%; border-collapse:collapse; font-size:.88rem; margin:1em 0; }
  .report-body th { background:var(--navy); color:#fff; padding:8px 12px; text-align:left; }
  .report-body td { padding:7px 12px; border-bottom:1px solid var(--border); }
  .report-body tr:nth-child(even) td { background:#F8FAFD; }

  /* Vervaag-effect onderaan de preview */
  .preview-fade {
    position:relative; overflow:hidden; max-height:320px;
  }
  .preview-fade::after {
    content:''; position:absolute; bottom:0; left:0; right:0;
    height:140px;
    background:linear-gradient(transparent, var(--surface));
    pointer-events:none;
  }

  /* Betaalmuur */
  .paywall {
    background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%);
    border: 2px solid #F59E0B; border-radius: var(--r);
    padding: 28px 32px; text-align: center; margin-bottom: 22px;
    box-shadow: 0 4px 20px rgba(245,158,11,.15);
  }
  .paywall-title { font-family:'Syne',sans-serif; font-weight:800;
                   font-size:1.25rem; color:var(--navy); margin-bottom:8px; }
  .paywall-sub { font-size:.92rem; color:#92400E; margin-bottom:18px; line-height:1.6; }
  .paywall-price { font-family:'Syne',sans-serif; font-weight:800;
                   font-size:2rem; color:var(--navy); margin-bottom:4px; }
  .paywall-price span { font-size:1rem; font-weight:400; color:var(--muted); }
  .paywall-features { display:flex; justify-content:center; gap:16px;
                      flex-wrap:wrap; margin:14px 0 20px; font-size:.82rem; color:#78350F; }

  .stripe-btn {
    display:block; width:100%;
    background:linear-gradient(135deg,#F59E0B 0%,#D97706 100%);
    color:#fff !important; text-decoration:none !important;
    font-family:'Syne',sans-serif; font-weight:800; font-size:1.05rem;
    padding:15px 24px; border-radius:10px; text-align:center;
    box-shadow:0 4px 16px rgba(245,158,11,.40);
    transition:transform .15s,box-shadow .15s; cursor:pointer;
  }
  .stripe-btn:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(245,158,11,.50); }

  /* Succes banner */
  .succes-banner {
    background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
    border: 2px solid var(--teal); border-radius: var(--r);
    padding: 22px 28px; text-align: center; margin-bottom: 22px;
  }
  .succes-banner h3 { font-family:'Syne',sans-serif; color:#065F46; margin:0 0 6px; }
  .succes-banner p { color:#047857; margin:0; font-size:.9rem; }

  .trust { display:flex; align-items:center; justify-content:center;
           gap:26px; padding:16px 0 2px; flex-wrap:wrap; }
  .ti { display:flex; align-items:center; gap:7px; font-size:.80rem; color:var(--muted); }
  .td { width:7px; height:7px; background:var(--teal); border-radius:50%; flex-shrink:0; }

  .features { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }
  .feat { flex:1; min-width:140px; background:var(--surface);
          border:1px solid var(--border); border-radius:12px;
          padding:22px 20px; box-shadow:var(--sh); }
  .feat-icon { font-size:1.5rem; margin-bottom:10px; }
  .feat-title { font-family:'Syne',sans-serif; font-weight:700;
                font-size:.95rem; color:var(--navy); margin-bottom:6px; }
  .feat-desc { font-size:.83rem; color:var(--muted); line-height:1.5; }

  div[data-testid="stTextInput"] input {
    border:2px solid var(--border) !important; border-radius:10px !important;
    padding:14px 18px !important; font-size:1rem !important;
    font-family:'DM Sans',sans-serif !important; background:#FAFBFE !important;
    color:var(--text) !important; transition:border-color .2s,box-shadow .2s;
  }
  div[data-testid="stTextInput"] input:focus {
    border-color:var(--teal) !important;
    box-shadow:0 0 0 3px rgba(14,168,126,.14) !important;
  }
  div[data-testid="stTextInput"] input::placeholder { color:var(--muted) !important; }

  div[data-testid="stButton"]>button {
    width:100%;
    background:linear-gradient(135deg,var(--teal) 0%,#0C9A70 100%) !important;
    border:none !important; border-radius:10px !important; color:#fff !important;
    font-family:'Syne',sans-serif !important; font-weight:700 !important;
    font-size:1rem !important; padding:14px 24px !important;
    box-shadow:0 4px 16px rgba(14,168,126,.33) !important; margin-top:4px;
    transition:transform .15s,box-shadow .15s !important;
  }
  div[data-testid="stButton"]>button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 24px rgba(14,168,126,.44) !important;
  }
  div[data-testid="stDownloadButton"]>button {
    width:100%;
    background:linear-gradient(135deg,var(--navy) 0%,var(--navy-mid) 100%) !important;
    border:none !important; border-radius:10px !important; color:#fff !important;
    font-family:'Syne',sans-serif !important; font-weight:700 !important;
    font-size:1.05rem !important; padding:16px 24px !important;
    box-shadow:0 4px 16px rgba(15,40,80,.28) !important;
    transition:transform .15s,box-shadow .15s !important;
  }
  div[data-testid="stDownloadButton"]>button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 24px rgba(15,40,80,.38) !important;
  }
  [data-testid="stAlert"] { border-radius:10px !important; }

  /* Stripe betaalknop via st.link_button */
  div[data-testid="stLinkButton"] a {
    display:block; width:100%;
    background:linear-gradient(135deg,#F59E0B 0%,#D97706 100%) !important;
    color:#fff !important; text-decoration:none !important;
    font-family:'Syne',sans-serif !important; font-weight:800 !important;
    font-size:1.05rem !important; padding:15px 24px !important;
    border-radius:10px !important; text-align:center;
    box-shadow:0 4px 16px rgba(245,158,11,.40) !important;
    transition:transform .15s,box-shadow .15s !important;
  }
  div[data-testid="stLinkButton"] a:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 24px rgba(245,158,11,.50) !important;
  }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  HERO
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-badge">✦ Preview gratis &nbsp;·&nbsp; AI-gedreven &nbsp;·&nbsp; Officiële Kadaster BAG-data</div>
  <div class="hero-logo">Woning<span>Check</span>AI</div>
  <div class="hero-sub">Vul een adres in — ontvang binnen seconden een persoonlijk verduurzamingsrapport</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  BETALING TERUGKEER
#  Stripe stuurt de gebruiker terug met ?betaald=ja in de URL.
#  We lezen het adres uit de sessie (daar hebben we het opgeslagen
#  voordat de gebruiker naar Stripe ging).
# ─────────────────────────────────────────────────────────────
betaald, url_adres = controleer_betaling()

if betaald:
    # Adres uit sessie of uit URL
    adres_betaald     = st.session_state.huidig_adres or url_adres
    rapport_betaald   = st.session_state.huidig_rapport
    bouwjaar_betaald  = st.session_state.huidig_bouwjaar
    oppervlak_betaald = st.session_state.huidig_oppervlakte

    # Sessie verlopen? Haal meest recente scan op uit database
    if not rapport_betaald:
        with st.spinner("Rapport ophalen uit database..."):
            recente_scans = haal_recente_scans_op(limiet=1)
            if recente_scans:
                laatste = recente_scans[0]
                adres_betaald     = laatste.get("adres", adres_betaald)
                bouwjaar_betaald  = laatste.get("bouwjaar", "Onbekend")
                oppervlak_betaald = laatste.get("oppervlakte", "Onbekend")
                rapport_betaald   = zoek_bestaand_rapport(adres_betaald)
            if not rapport_betaald and adres_betaald:
                bag_tijdelijk = cached_bag_data(adres_betaald)
                if bag_tijdelijk:
                    rapport_betaald = cached_advies(
                        bag_tijdelijk.get("bouwjaar", "Onbekend"),
                        bag_tijdelijk.get("oppervlakte", "Onbekend"),
                        bag_tijdelijk.get("woningtype", "Woning")
                    )

    st.markdown("""
    <div class="succes-banner">
      <h3>✅ Betaling geslaagd!</h3>
      <p>Bedankt! Uw volledige rapport staat hieronder klaar om te downloaden.</p>
    </div>
    """, unsafe_allow_html=True)

    if rapport_betaald:
        # Volledig rapport tonen
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📄 &nbsp;Uw Volledige Verduurzamingsplan</div>', unsafe_allow_html=True)
        st.markdown('<div class="accent"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="report-body">{rapport_betaald}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # PDF download
        pdf_bytes = create_pdf(rapport_betaald, adres_betaald, bouwjaar_betaald, oppervlak_betaald)
        safe_name = adres_betaald.replace(" ", "_").replace(",", "").replace("/", "-")
        st.download_button(
            label="📄  Download uw PDF Rapport",
            data=pdf_bytes,
            file_name=f"WoningCheckAI_{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.warning("Rapport kon niet worden opgehaald. Voer uw adres opnieuw in.")

    st.query_params.clear()
    st.markdown("---")


# ─────────────────────────────────────────────────────────────
#  ZOEKFORMULIER
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
adres_input = st.text_input(
    label="adres",
    label_visibility="collapsed",
    placeholder="Bijv. Keizersgracht 123, Amsterdam",
)
scan_clicked = st.button("⚡  Genereer Gratis Preview", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="trust">
  <span class="ti"><span class="td"></span>Preview gratis</span>
  <span class="ti"><span class="td"></span>Officiële BAG-data</span>
  <span class="ti"><span class="td"></span>Claude AI analyse</span>
  <span class="ti"><span class="td"></span>Volledig rapport €4,95</span>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  VERWERKING
# ─────────────────────────────────────────────────────────────
if scan_clicked:
    if not adres_input.strip():
        st.warning("Vul een adres in om door te gaan.")
    else:
        # Stap 1: BAG data
        with st.spinner("Woningdata ophalen via Kadaster BAG…"):
            data = cached_bag_data(adres_input)

        if not data:
            st.error(
                "❌ Adres niet gevonden. Controleer de schrijfwijze of gebruik een volledig adres "
                "*(bijv. Hoofdstraat 1, Utrecht)*."
            )
            st.stop()

        bouwjaar    = data.get("bouwjaar", "Onbekend")
        oppervlakte = data.get("oppervlakte", "Onbekend")
        woningtype  = data.get("woningtype", "Woning")
        label       = schat_energielabel(bouwjaar)

        # Stap 2: Kaart + metrics
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="card-title">📍 &nbsp;{adres_input}</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="pills">
          <div class="pill">
            <div class="pill-lbl">Bouwjaar</div>
            <div class="pill-val">{bouwjaar}</div>
          </div>
          <div class="pill">
            <div class="pill-lbl">Oppervlak</div>
            <div class="pill-val">{oppervlakte}</div>
            <div class="pill-unit">m²</div>
          </div>
          <div class="pill">
            <div class="pill-lbl">Gesch. label</div>
            <div class="pill-val">{label}</div>
            <div class="pill-unit">indicatief</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.map([{"lat": data["lat"], "lon": data["lon"]}], zoom=16)
        st.markdown('</div>', unsafe_allow_html=True)

        # Stap 3: Rapport genereren
        bestaand = zoek_bestaand_rapport(adres_input)
        if bestaand:
            rapport = bestaand
        else:
            with st.spinner("AI schrijft uw persoonlijk verduurzamingsplan…"):
                rapport = cached_advies(bouwjaar, oppervlakte, woningtype)

        # Stap 4: Opslaan in sessie (voor na Stripe terugkeer)
        st.session_state.huidig_adres      = adres_input
        st.session_state.huidig_rapport    = rapport
        st.session_state.huidig_bouwjaar   = bouwjaar
        st.session_state.huidig_oppervlakte = oppervlakte

        # Stap 5: Opslaan in Supabase (alleen als nog niet bestaat)
        if not bestaand:
            sla_scan_op(
                adres=adres_input,
                bag_data=data,
                rapport=rapport,
                energielabel=label,
            )

        # Stap 6: Gratis PREVIEW tonen (eerste 2 secties)
        preview, rest = splits_rapport(rapport)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🤖 &nbsp;Uw Verduurzamingsplan — Preview</div>', unsafe_allow_html=True)
        st.markdown('<div class="accent"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="report-body preview-fade">{preview}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Stap 7: BETAALMUUR
        stripe_url = maak_stripe_url(adres_input)

        if stripe_url:
            st.markdown(f"""
            <div class="paywall">
              <div class="paywall-title">🔒 Ontgrendel uw volledige rapport</div>
              <div class="paywall-sub">
                Bekijk alle aanbevelingen, het volledige kostenoverzicht,<br>
                stap-voor-stap subsidie-aanvraaginstructies en download uw PDF.
              </div>
              <div class="paywall-price">€4,95 <span>eenmalig &nbsp;·&nbsp; direct beschikbaar</span></div>
              <div class="paywall-features">
                <span>✓ Alle verduurzamingsmaatregelen</span>
                <span>✓ Subsidie-aanvraaginstructies</span>
                <span>✓ Kostenoverzicht tabel</span>
                <span>✓ PDF rapport</span>
                <span>✓ Veilig via Stripe</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button(
                "🔒  Volledig rapport voor €4,95",
                stripe_url,
                use_container_width=True,
            )
        else:
            # Testmodus: geen Stripe geconfigureerd
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<div class="report-body">{rest}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            pdf_bytes = create_pdf(rapport, adres_input, bouwjaar, oppervlakte)
            safe_name = adres_input.replace(" ", "_").replace(",", "").replace("/", "-")
            st.download_button(
                label="📄  Download rapport (testmodus)",
                data=pdf_bytes,
                file_name=f"WoningCheckAI_{safe_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        st.caption(
            "ℹ️ Dit rapport is indicatief op basis van officiële BAG-data en AI-analyse. "
            "Het vervangt geen officieel energielabel."
        )


# ─────────────────────────────────────────────────────────────
#  FEATURE STRIP
# ─────────────────────────────────────────────────────────────
if not scan_clicked and not betaald:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="features">
      <div class="feat">
        <div class="feat-icon">⚡</div>
        <div class="feat-title">Preview gratis</div>
        <div class="feat-desc">Zie direct uw woningprofiel en besparingspotentieel — geen account nodig.</div>
      </div>
      <div class="feat">
        <div class="feat-icon">📊</div>
        <div class="feat-title">Kadaster BAG-data</div>
        <div class="feat-desc">Officiële bouwdata van de Nederlandse overheid als basis.</div>
      </div>
      <div class="feat">
        <div class="feat-icon">🏦</div>
        <div class="feat-title">Subsidiegids</div>
        <div class="feat-desc">Stap-voor-stap uitleg hoe u ISDE, SEEH en andere subsidies aanvraagt.</div>
      </div>
      <div class="feat">
        <div class="feat-icon">📄</div>
        <div class="feat-title">Volledig rapport €4,95</div>
        <div class="feat-desc">Alle maatregelen, kostentabel en PDF — eenmalig en direct beschikbaar.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; padding:24px 0 8px; font-size:.78rem; color:#9CA3AF;">
  © 2026 WoningCheckAI.nl &nbsp;·&nbsp; Alle rechten voorbehouden<br>
  <span style="opacity:.6;">Niet gelieerd aan de Nederlandse overheid · Indicatief advies</span>
</div>
""", unsafe_allow_html=True)