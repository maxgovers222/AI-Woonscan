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
    layout="wide",
    initial_sidebar_state="collapsed",
)

STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK", "")
APP_URL             = os.getenv("APP_URL", "https://ai-woonscan-qdkwobbescefekt7zxo6j6.streamlit.app")


def maak_stripe_url(adres: str = "") -> str:
    if not STRIPE_PAYMENT_LINK:
        return ""
    adres_encoded = urllib.parse.quote(adres, safe="")
    success_url = f"{APP_URL}?betaald=ja&adres={adres_encoded}"
    return f"{STRIPE_PAYMENT_LINK}?success_url={urllib.parse.quote(success_url, safe=':/?=&')}"


def controleer_betaling() -> tuple[bool, str]:
    params = st.query_params
    betaald = params.get("betaald", "") == "ja"
    adres   = urllib.parse.unquote(params.get("adres", ""))
    return betaald, adres


def splits_rapport(rapport: str) -> tuple[str, str]:
    lijnen    = rapport.split("\n")
    kopjes    = 0
    splitpunt = len(lijnen)
    for i, lijn in enumerate(lijnen):
        if lijn.startswith("## ") or lijn.startswith("# "):
            kopjes += 1
            if kopjes == 3:
                splitpunt = i
                break
    preview = "\n".join(lijnen[:splitpunt]).strip()
    rest    = "\n".join(lijnen[splitpunt:]).strip()
    return preview, rest


def create_pdf(rapport_tekst: str, adres: str, bouwjaar, oppervlakte) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_fill_color(10, 36, 99)
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
    pdf.set_text_color(10, 36, 99)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, f"Adres: {adres}", ln=True)
    pdf.set_draw_color(10, 36, 99)
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
    pdf.cell(0, 8, "WoningCheckAI.nl  |  AI-gegenereerd rapport  |  Alleen indicatief", align="C")
    return bytes(pdf.output())


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


if "huidig_adres" not in st.session_state:
    st.session_state.huidig_adres = ""
if "huidig_rapport" not in st.session_state:
    st.session_state.huidig_rapport = ""
if "huidig_bouwjaar" not in st.session_state:
    st.session_state.huidig_bouwjaar = ""
if "huidig_oppervlakte" not in st.session_state:
    st.session_state.huidig_oppervlakte = ""


# ─────────────────────────────────────────────────────────────
#  CSS — Volledige revamp
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Fraunces:ital,wght@0,700;0,900;1,700&display=swap');

:root {
  --blue:      #0A2463;
  --blue-mid:  #1B3F8B;
  --blue-lt:   #2D5BE3;
  --green:     #059669;
  --green-lt:  #10B981;
  --green-xlt: #D1FAE5;
  --amber:     #D97706;
  --amber-lt:  #FEF3C7;
  --bg:        #F8FAFF;
  --surface:   #FFFFFF;
  --text:      #0F172A;
  --text-2:    #334155;
  --muted:     #64748B;
  --border:    #E2E8F0;
  --border-2:  #CBD5E1;
  --r-sm:      8px;
  --r:         16px;
  --r-lg:      24px;
  --sh:        0 1px 3px rgba(0,0,0,.06), 0 4px 16px rgba(10,36,99,.07);
  --sh-lg:     0 4px 6px rgba(0,0,0,.04), 0 20px 48px rgba(10,36,99,.12);
}

/* ── Reset & base ─────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {
  background: var(--bg) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  color: var(--text) !important;
}

/* Verberg Streamlit chrome */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
footer, #MainMenu { display: none !important; }

/* Centreer alles met max-breedte */
[data-testid="stAppViewBlockContainer"] {
  max-width: 860px !important;
  margin: 0 auto !important;
  padding: 0 24px 48px !important;
}

/* ── Navigatiebalk ────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0 28px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 48px;
}
.nav-logo {
  font-family: 'Fraunces', serif;
  font-weight: 900;
  font-size: 1.4rem;
  color: var(--blue);
  letter-spacing: -0.5px;
  line-height: 1;
}
.nav-logo em {
  font-style: normal;
  color: var(--green);
}
.nav-badge {
  background: var(--green-xlt);
  color: var(--green);
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .8px;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(5,150,105,.2);
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 16px 0 48px;
}
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: .78rem;
  font-weight: 600;
  color: var(--green);
  letter-spacing: .6px;
  text-transform: uppercase;
  margin-bottom: 20px;
}
.hero-eyebrow-dot {
  width: 6px; height: 6px;
  background: var(--green);
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .5; transform: scale(1.3); }
}
.hero-title {
  font-family: 'Fraunces', serif;
  font-weight: 900;
  font-size: clamp(2.2rem, 5vw, 3.2rem);
  color: var(--blue);
  line-height: 1.1;
  letter-spacing: -1px;
  margin-bottom: 18px;
}
.hero-title em {
  font-style: italic;
  color: var(--green);
}
.hero-sub {
  font-size: 1.1rem;
  color: var(--muted);
  font-weight: 400;
  line-height: 1.6;
  max-width: 540px;
  margin: 0 auto 36px;
}

/* ── Zoekbox ──────────────────────────────────────── */
.search-wrap {
  background: var(--surface);
  border: 1.5px solid var(--border-2);
  border-radius: var(--r-lg);
  padding: 24px 28px 20px;
  box-shadow: var(--sh-lg);
  margin-bottom: 20px;
}
.search-label {
  font-size: .78rem;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: .6px;
  text-transform: uppercase;
  margin-bottom: 10px;
}

/* ── Trust pills ──────────────────────────────────── */
.trust {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px 20px;
  margin-bottom: 52px;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: .8rem;
  color: var(--muted);
  font-weight: 500;
}
.trust-check {
  color: var(--green);
  font-size: .9rem;
}

/* ── Section label ────────────────────────────────── */
.section-label {
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 16px;
}

/* ── Resultaat card ───────────────────────────────── */
.result-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--r);
  overflow: hidden;
  box-shadow: var(--sh);
  margin-bottom: 20px;
}
.result-card-header {
  background: var(--blue);
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-card-header-title {
  font-weight: 700;
  font-size: .95rem;
  color: #fff;
  letter-spacing: -.2px;
}
.result-card-body { padding: 24px; }

/* ── Metric pills ─────────────────────────────────── */
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.metric {
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: var(--r-sm);
  padding: 14px 16px;
  text-align: center;
}
.metric-label {
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .7px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}
.metric-value {
  font-family: 'Fraunces', serif;
  font-weight: 700;
  font-size: 1.6rem;
  color: var(--blue);
  line-height: 1;
}
.metric-unit {
  font-size: .75rem;
  color: var(--muted);
  margin-top: 3px;
}

/* ── Rapport ──────────────────────────────────────── */
.rapport-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--r);
  overflow: hidden;
  box-shadow: var(--sh);
  margin-bottom: 20px;
}
.rapport-header {
  padding: 18px 24px;
  border-bottom: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rapport-header-title {
  font-weight: 700;
  font-size: 1rem;
  color: var(--text);
}
.rapport-badge {
  background: var(--green-xlt);
  color: var(--green);
  font-size: .7rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.rapport-body {
  padding: 28px 28px 24px;
  font-size: .96rem;
  line-height: 1.8;
  color: var(--text-2);
}
.rapport-body h1, .rapport-body h2 {
  font-family: 'Fraunces', serif;
  font-weight: 700;
  color: var(--blue);
  font-size: 1.25rem;
  margin: 1.6em 0 .6em;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border);
}
.rapport-body h3 {
  font-weight: 700;
  color: var(--text);
  font-size: 1rem;
  margin: 1.3em 0 .4em;
}
.rapport-body strong { color: var(--text); font-weight: 700; }
.rapport-body ul { padding-left: 20px; margin: .5em 0; }
.rapport-body li { margin-bottom: 4px; }
.rapport-body table {
  width: 100%; border-collapse: collapse;
  font-size: .88rem; margin: 1.2em 0;
  border-radius: var(--r-sm); overflow: hidden;
}
.rapport-body th {
  background: var(--blue); color: #fff;
  padding: 10px 14px; text-align: left;
  font-weight: 600; font-size: .82rem;
}
.rapport-body td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-2);
}
.rapport-body tr:nth-child(even) td { background: var(--bg); }

/* Preview fade */
.preview-wrap { position: relative; overflow: hidden; max-height: 340px; }
.preview-wrap::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 160px;
  background: linear-gradient(transparent, var(--surface));
  pointer-events: none;
}

/* ── Betaalmuur ───────────────────────────────────── */
.paywall {
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  border: 2px solid #93C5FD;
  border-radius: var(--r);
  padding: 32px 28px;
  text-align: center;
  margin-bottom: 16px;
}
.paywall-icon { font-size: 2rem; margin-bottom: 12px; }
.paywall-title {
  font-family: 'Fraunces', serif;
  font-weight: 700;
  font-size: 1.4rem;
  color: var(--blue);
  margin-bottom: 10px;
}
.paywall-sub {
  font-size: .92rem;
  color: var(--text-2);
  line-height: 1.6;
  margin-bottom: 20px;
  max-width: 440px;
  margin-left: auto;
  margin-right: auto;
}
.paywall-price {
  font-family: 'Fraunces', serif;
  font-weight: 900;
  font-size: 2.4rem;
  color: var(--blue);
  margin-bottom: 16px;
  line-height: 1;
}
.paywall-price small {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: .85rem;
  font-weight: 400;
  color: var(--muted);
}
.paywall-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 20px;
  margin-bottom: 24px;
  font-size: .83rem;
  color: var(--text-2);
}
.paywall-list span { display: flex; align-items: center; gap: 5px; }
.paywall-list .chk { color: var(--green); font-weight: 700; }

/* ── Succes banner ────────────────────────────────── */
.succes {
  background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
  border: 2px solid var(--green-lt);
  border-radius: var(--r);
  padding: 24px 28px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}
.succes-icon { font-size: 1.8rem; flex-shrink: 0; }
.succes-title { font-weight: 700; color: #065F46; font-size: 1rem; margin-bottom: 4px; }
.succes-sub { font-size: .88rem; color: #047857; }

/* ── Features ─────────────────────────────────────── */
.features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 48px;
}
.feature {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--r);
  padding: 24px;
  box-shadow: var(--sh);
  transition: box-shadow .2s, transform .2s;
}
.feature:hover { box-shadow: var(--sh-lg); transform: translateY(-2px); }
.feature-icon {
  width: 40px; height: 40px;
  background: var(--green-xlt);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  margin-bottom: 14px;
}
.feature-title {
  font-weight: 700;
  font-size: .95rem;
  color: var(--text);
  margin-bottom: 6px;
}
.feature-desc { font-size: .84rem; color: var(--muted); line-height: 1.55; }

/* ── Footer ───────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 32px 0 8px;
  border-top: 1px solid var(--border);
  font-size: .78rem;
  color: var(--muted);
  line-height: 1.8;
}

/* ── Streamlit widget overrides ───────────────────── */

/* Text input */
div[data-testid="stTextInput"] > div > div {
  border: 1.5px solid var(--border-2) !important;
  border-radius: var(--r-sm) !important;
  background: var(--bg) !important;
  box-shadow: none !important;
  transition: border-color .2s, box-shadow .2s !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
  border-color: var(--blue-lt) !important;
  box-shadow: 0 0 0 3px rgba(45,91,227,.12) !important;
}
div[data-testid="stTextInput"] input {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-size: .97rem !important;
  color: var(--text) !important;
  padding: 12px 16px !important;
  background: transparent !important;
}
div[data-testid="stTextInput"] input::placeholder {
  color: var(--muted) !important;
}

/* Primaire knop (scan) */
div[data-testid="stButton"] > button {
  width: 100% !important;
  background: var(--blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: .97rem !important;
  padding: 13px 24px !important;
  letter-spacing: .2px !important;
  box-shadow: 0 4px 14px rgba(10,36,99,.25) !important;
  transition: background .15s, box-shadow .15s, transform .15s !important;
  margin-top: 8px !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--blue-mid) !important;
  box-shadow: 0 6px 20px rgba(10,36,99,.32) !important;
  transform: translateY(-1px) !important;
}

/* Download knop */
div[data-testid="stDownloadButton"] > button {
  width: 100% !important;
  background: var(--blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: .97rem !important;
  padding: 13px 24px !important;
  box-shadow: 0 4px 14px rgba(10,36,99,.25) !important;
  transition: background .15s, box-shadow .15s, transform .15s !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: var(--blue-mid) !important;
  transform: translateY(-1px) !important;
}

/* Link knop (Stripe betaalknop) */
div[data-testid="stLinkButton"] > a {
  display: block !important;
  width: 100% !important;
  background: var(--green) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: 1rem !important;
  padding: 13px 24px !important;
  text-align: center !important;
  text-decoration: none !important;
  box-shadow: 0 4px 14px rgba(5,150,105,.30) !important;
  transition: background .15s, box-shadow .15s, transform .15s !important;
}
div[data-testid="stLinkButton"] > a:hover {
  background: #047857 !important;
  box-shadow: 0 6px 20px rgba(5,150,105,.38) !important;
  transform: translateY(-1px) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  border-radius: var(--r-sm) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Map */
[data-testid="stDeckGlJsonChart"],
iframe { border-radius: var(--r-sm) !important; overflow: hidden; }

/* Spinner */
[data-testid="stSpinner"] p {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  color: var(--blue) !important;
  font-size: .9rem !important;
}

/* Caption */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: .78rem !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  NAVIGATIEBALK
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="navbar">
  <div class="nav-logo">Woning<em>Check</em>AI</div>
  <div class="nav-badge">✦ Beta</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  BETALING TERUGKEER
# ─────────────────────────────────────────────────────────────
betaald, url_adres = controleer_betaling()

if betaald:
    adres_betaald     = st.session_state.huidig_adres or url_adres
    rapport_betaald   = st.session_state.huidig_rapport
    bouwjaar_betaald  = st.session_state.huidig_bouwjaar
    oppervlak_betaald = st.session_state.huidig_oppervlakte

    if not rapport_betaald:
        with st.spinner("Rapport ophalen..."):
            recente_scans = haal_recente_scans_op(limiet=1)
            if recente_scans:
                laatste       = recente_scans[0]
                adres_betaald = laatste.get("adres", adres_betaald)
                bouwjaar_betaald  = laatste.get("bouwjaar", "Onbekend")
                oppervlak_betaald = laatste.get("oppervlakte", "Onbekend")
                rapport_betaald   = zoek_bestaand_rapport(adres_betaald)
            if not rapport_betaald and adres_betaald:
                bag_t = cached_bag_data(adres_betaald)
                if bag_t:
                    rapport_betaald = cached_advies(
                        bag_t.get("bouwjaar", "Onbekend"),
                        bag_t.get("oppervlakte", "Onbekend"),
                        bag_t.get("woningtype", "Woning"),
                    )

    st.markdown("""
    <div class="succes">
      <div class="succes-icon">✅</div>
      <div>
        <div class="succes-title">Betaling geslaagd — bedankt!</div>
        <div class="succes-sub">Uw volledige verduurzamingsrapport en PDF staan hieronder klaar.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if rapport_betaald:
        st.markdown("""
        <div class="rapport-card">
          <div class="rapport-header">
            <span class="rapport-header-title">📄 Uw Volledige Verduurzamingsplan</span>
            <span class="rapport-badge">Volledig</span>
          </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="rapport-body">{rapport_betaald}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        pdf_bytes = create_pdf(rapport_betaald, adres_betaald, bouwjaar_betaald, oppervlak_betaald)
        safe_name = adres_betaald.replace(" ", "_").replace(",", "").replace("/", "-")
        st.download_button(
            label="⬇️  Download PDF Rapport",
            data=pdf_bytes,
            file_name=f"WoningCheckAI_{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.warning("Rapport kon niet worden opgehaald. Voer uw adres hieronder opnieuw in.")

    st.query_params.clear()
    st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  HERO + ZOEKFORMULIER
# ─────────────────────────────────────────────────────────────
if not betaald:
    st.markdown("""
    <div class="hero">
      <div class="hero-eyebrow">
        <span class="hero-eyebrow-dot"></span>
        Officiële Kadaster BAG-data · Claude AI analyse
      </div>
      <h1 class="hero-title">
        Uw woning verduurzamen?<br>
        <em>Wij regelen het advies.</em>
      </h1>
      <p class="hero-sub">
        Vul een adres in en ontvang binnen 30 seconden een persoonlijk
        energiebesparingsplan — gratis, zonder account.
      </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="search-wrap">', unsafe_allow_html=True)
st.markdown('<div class="search-label">🔍 Voer een Nederlands adres in</div>', unsafe_allow_html=True)
adres_input = st.text_input(
    label="adres",
    label_visibility="collapsed",
    placeholder="Bijv. Keizersgracht 123, Amsterdam",
)
scan_clicked = st.button("Analyseer dit adres →", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="trust">
  <span class="trust-item"><span class="trust-check">✓</span> Preview altijd gratis</span>
  <span class="trust-item"><span class="trust-check">✓</span> Officiële BAG-data</span>
  <span class="trust-item"><span class="trust-check">✓</span> Geen account nodig</span>
  <span class="trust-item"><span class="trust-check">✓</span> Volledig rapport €4,95</span>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  VERWERKING
# ─────────────────────────────────────────────────────────────
if scan_clicked:
    if not adres_input.strip():
        st.warning("Vul een adres in om door te gaan.")
    else:
        with st.spinner("Woningdata ophalen via Kadaster..."):
            data = cached_bag_data(adres_input)

        if not data:
            st.error("❌ Adres niet gevonden. Controleer de schrijfwijze of gebruik een volledig adres *(bijv. Hoofdstraat 1, Utrecht)*.")
            st.stop()

        bouwjaar    = data.get("bouwjaar", "Onbekend")
        oppervlakte = data.get("oppervlakte", "Onbekend")
        woningtype  = data.get("woningtype", "Woning")
        label       = schat_energielabel(bouwjaar)

        # Woningkaart
        st.markdown(f"""
        <div class="result-card">
          <div class="result-card-header">
            <span>📍</span>
            <span class="result-card-header-title">{adres_input}</span>
          </div>
          <div class="result-card-body">
            <div class="metrics">
              <div class="metric">
                <div class="metric-label">Bouwjaar</div>
                <div class="metric-value">{bouwjaar}</div>
              </div>
              <div class="metric">
                <div class="metric-label">Oppervlak</div>
                <div class="metric-value">{oppervlakte}</div>
                <div class="metric-unit">m²</div>
              </div>
              <div class="metric">
                <div class="metric-label">Gesch. label</div>
                <div class="metric-value">{label}</div>
                <div class="metric-unit">indicatief</div>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.map([{"lat": data["lat"], "lon": data["lon"]}], zoom=16)

        # Rapport genereren
        bestaand = zoek_bestaand_rapport(adres_input)
        if bestaand:
            rapport = bestaand
        else:
            with st.spinner("AI schrijft uw persoonlijk verduurzamingsplan..."):
                rapport = cached_advies(bouwjaar, oppervlakte, woningtype)

        # Sessie opslaan
        st.session_state.huidig_adres       = adres_input
        st.session_state.huidig_rapport     = rapport
        st.session_state.huidig_bouwjaar    = bouwjaar
        st.session_state.huidig_oppervlakte = oppervlakte

        # Supabase opslaan
        if not bestaand:
            sla_scan_op(adres=adres_input, bag_data=data, rapport=rapport, energielabel=label)

        # Preview tonen
        preview, rest = splits_rapport(rapport)

        st.markdown("""
        <div class="rapport-card">
          <div class="rapport-header">
            <span class="rapport-header-title">🤖 Uw Verduurzamingsplan</span>
            <span class="rapport-badge">Preview</span>
          </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="rapport-body"><div class="preview-wrap">{preview}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Betaalmuur
        stripe_url = maak_stripe_url(adres_input)

        if stripe_url:
            st.markdown(f"""
            <div class="paywall">
              <div class="paywall-icon">🔒</div>
              <div class="paywall-title">Ontgrendel uw volledige rapport</div>
              <div class="paywall-sub">
                Bekijk alle aanbevelingen met geschatte besparingen, het complete
                kostenoverzicht, stap-voor-stap subsidie-aanvraaginstructies en download uw PDF.
              </div>
              <div class="paywall-price">€4,95 <small>· eenmalig</small></div>
              <div class="paywall-list">
                <span><span class="chk">✓</span> Alle verduurzamingsmaatregelen</span>
                <span><span class="chk">✓</span> Subsidie-aanvraag stap voor stap</span>
                <span><span class="chk">✓</span> Kostenoverzicht tabel</span>
                <span><span class="chk">✓</span> PDF rapport download</span>
                <span><span class="chk">✓</span> Veilig betalen via Stripe</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button(
                "Volledig rapport ontgrendelen voor €4,95 →",
                stripe_url,
                use_container_width=True,
            )
        else:
            st.markdown(f'<div class="rapport-body">{rest}</div>', unsafe_allow_html=True)
            pdf_bytes = create_pdf(rapport, adres_input, bouwjaar, oppervlakte)
            safe_name = adres_input.replace(" ", "_").replace(",", "").replace("/", "-")
            st.download_button(
                label="⬇️  Download rapport (testmodus)",
                data=pdf_bytes,
                file_name=f"WoningCheckAI_{safe_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        st.caption("Dit rapport is indicatief op basis van officiële BAG-data en AI-analyse. Het vervangt geen officieel energielabel.")


# ─────────────────────────────────────────────────────────────
#  FEATURE GRID
# ─────────────────────────────────────────────────────────────
if not scan_clicked and not betaald:
    st.markdown("""
    <div class="features">
      <div class="feature">
        <div class="feature-icon">⚡</div>
        <div class="feature-title">Resultaat in 30 seconden</div>
        <div class="feature-desc">Vul een adres in en ontvang direct een volledig besparingsplan — geen wachttijd, geen account.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">🏛️</div>
        <div class="feature-title">Officiële overheidsdata</div>
        <div class="feature-desc">We halen bouwjaar en oppervlakte rechtstreeks op via de Kadaster BAG API van de Nederlandse overheid.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">🏦</div>
        <div class="feature-title">Subsidiegids inbegrepen</div>
        <div class="feature-desc">Stap-voor-stap uitleg hoe u ISDE, SEEH en andere subsidies aanvraagt — inclusief directe links.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">📄</div>
        <div class="feature-title">PDF voor €4,95</div>
        <div class="feature-desc">Download het volledige rapport als professionele PDF — klaar om te delen met uw aannemer of adviseur.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  © 2026 WoningCheckAI.nl · Alle rechten voorbehouden<br>
  Niet gelieerd aan de Nederlandse overheid · Indicatief advies · Geen officieel energielabel
</div>
""", unsafe_allow_html=True)