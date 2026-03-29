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
#  CSS — Professionele, strakke layout
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('[https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap](https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap)');

:root {
  --navy:      #0B1D3A;
  --navy-mid:  #132E5B;
  --navy-lt:   #1E4D8C;
  --accent:    #0EA56F;
  --accent-dk: #0A8A5C;
  --accent-lt: #E7F9F1;
  --warm:      #F5A623;
  --warm-lt:   #FFF8EC;
  --bg:        #F6F8FB;
  --surface:   #FFFFFF;
  --text:      #1A1F2E;
  --text-2:    #3D4663;
  --muted:     #6B7896;
  --border:    #E4E9F2;
  --border-h:  #CDD5E3;
  --radius:    12px;
  --radius-lg: 20px;
  --shadow-s:  0 1px 2px rgba(11,29,58,.04), 0 2px 8px rgba(11,29,58,.06);
  --shadow-m:  0 2px 4px rgba(11,29,58,.04), 0 8px 24px rgba(11,29,58,.08);
  --shadow-l:  0 4px 8px rgba(11,29,58,.04), 0 16px 40px rgba(11,29,58,.10);
}

/* ── Reset & base ─────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
.stApp {
  background: var(--bg) !important;
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--text) !important;
}

/* Verberg Streamlit chrome */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
footer, #MainMenu,
.stDeployButton { display: none !important; }

/* ── KERNFIX: beperk breedte ──────────────────────── */
[data-testid="stMain"] {
  background: var(--bg) !important;
}

.block-container,
[data-testid="stMainBlockContainer"] {
  max-width: 680px !important;
  margin: 0 auto !important;
  padding: 0 20px 60px !important;
}

/* Verwijder lege ruimtes */
[data-testid="stVerticalBlock"] {
  gap: 0.35rem !important;
}
[data-testid="stElementContainer"]:has(> div:empty),
[data-testid="stVerticalBlock"] > div:empty,
.element-container:empty {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 0 !important;
}

/* ── Navigatiebalk ────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 0 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}
.nav-logo {
  font-family: 'Playfair Display', serif;
  font-weight: 800;
  font-size: 1.25rem;
  color: var(--navy);
  letter-spacing: -0.3px;
  line-height: 1;
}
.nav-logo em {
  font-style: italic;
  color: var(--accent);
}
.nav-pills {
  display: flex;
  align-items: center;
  gap: 6px;
}
.nav-badge {
  background: var(--accent-lt);
  color: var(--accent);
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(14,165,111,.15);
}
.nav-secure {
  background: var(--warm-lt);
  color: var(--warm);
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(245,166,35,.15);
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 20px 0 45px; /* Diepere spacing voor ademruimte */
}
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: .68rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: .7px;
  text-transform: uppercase;
  margin-bottom: 14px;
  background: var(--accent-lt);
  padding: 5px 14px;
  border-radius: 999px;
  border: 1px solid rgba(14,165,111,.12);
}
.hero-eyebrow-dot {
  width: 5px; height: 5px;
  background: var(--accent);
  border-radius: 50%;
  animation: pulse 2.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .4; transform: scale(1.4); }
}
.hero-title {
  font-family: 'Playfair Display', serif;
  font-weight: 800;
  font-size: clamp(1.7rem, 4.5vw, 2.4rem);
  color: var(--navy);
  line-height: 1.15;
  letter-spacing: -0.5px;
  margin-bottom: 14px;
}
.hero-title em {
  font-style: italic;
  color: var(--accent);
}
.hero-sub {
  font-size: .95rem;
  color: var(--muted);
  font-weight: 400;
  line-height: 1.6;
  max-width: 460px;
  margin: 0 auto;
}

/* ── Trust strip ──────────────────────────────────── */
.trust {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 18px; /* Meer ruimte tussen vinkjes */
  margin-top: 10px;
  margin-bottom: 60px; /* Meer ruimte richting 'Hoe het werkt' */
  padding: 0 4px;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: .72rem;
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
}
.trust-check {
  color: var(--accent);
  font-size: .8rem;
  font-weight: 700;
}

/* ── Resultaat card ───────────────────────────────── */
.result-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-s);
  margin-bottom: 14px;
}
.result-card-header {
  background: var(--navy);
  padding: 13px 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.result-card-header-title {
  font-weight: 600;
  font-size: .86rem;
  color: #fff;
}
.result-card-body { padding: 18px; }

/* ── Metric pills ─────────────────────────────────── */
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
@media (max-width: 480px) {
  .metrics { grid-template-columns: 1fr; }
}
.metric {
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  text-align: center;
}
.metric-label {
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 3px;
}
.metric-value {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.4rem;
  color: var(--navy);
  line-height: 1.1;
}
.metric-unit {
  font-size: .68rem;
  color: var(--muted);
  margin-top: 2px;
}

/* ── Rapport ──────────────────────────────────────── */
.rapport-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-s);
  margin-bottom: 14px;
}
.rapport-header {
  padding: 14px 18px;
  border-bottom: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rapport-header-title {
  font-weight: 700;
  font-size: .9rem;
  color: var(--text);
}
.rapport-badge {
  background: var(--accent-lt);
  color: var(--accent);
  font-size: .62rem;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  letter-spacing: .3px;
}
.rapport-body {
  padding: 20px 22px 18px;
  font-size: .9rem;
  line-height: 1.72;
  color: var(--text-2);
}
.rapport-body h1, .rapport-body h2 {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  color: var(--navy);
  font-size: 1.1rem;
  margin: 1.3em 0 .45em;
  padding-bottom: 5px;
  border-bottom: 2px solid var(--border);
}
.rapport-body h3 {
  font-weight: 700;
  color: var(--text);
  font-size: .92rem;
  margin: 1.1em 0 .3em;
}
.rapport-body strong { color: var(--text); font-weight: 700; }
.rapport-body ul { padding-left: 18px; margin: .4em 0; }
.rapport-body li { margin-bottom: 3px; }
.rapport-body table {
  width: 100%; border-collapse: collapse;
  font-size: .8rem; margin: 1em 0;
  border-radius: 8px; overflow: hidden;
}
.rapport-body th {
  background: var(--navy); color: #fff;
  padding: 8px 10px; text-align: left;
  font-weight: 600; font-size: .74rem;
  letter-spacing: .2px;
}
.rapport-body td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-2);
}
.rapport-body tr:nth-child(even) td { background: var(--bg); }

/* Preview fade */
.preview-wrap {
  position: relative;
  overflow: hidden;
  max-height: 300px;
}
.preview-wrap::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 120px;
  background: linear-gradient(transparent, var(--surface));
  pointer-events: none;
}

/* ── Betaalmuur ───────────────────────────────────── */
.paywall {
  background: linear-gradient(145deg, #F0F6FF 0%, #E0ECFA 100%);
  border: 1.5px solid #B8D0F0;
  border-radius: var(--radius);
  padding: 26px 22px;
  text-align: center;
  margin-bottom: 10px;
}
.paywall-icon { font-size: 1.5rem; margin-bottom: 8px; }
.paywall-title {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.2rem;
  color: var(--navy);
  margin-bottom: 8px;
}
.paywall-sub {
  font-size: .84rem;
  color: var(--text-2);
  line-height: 1.55;
  margin-bottom: 14px;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}
.paywall-price {
  font-family: 'Playfair Display', serif;
  font-weight: 800;
  font-size: 1.9rem;
  color: var(--navy);
  margin-bottom: 12px;
  line-height: 1;
}
.paywall-price small {
  font-family: 'DM Sans', sans-serif;
  font-size: .78rem;
  font-weight: 400;
  color: var(--muted);
}
.paywall-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 5px 14px;
  margin-bottom: 18px;
  font-size: .76rem;
  color: var(--text-2);
}
.paywall-list span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.paywall-list .chk { color: var(--accent); font-weight: 700; }

/* ── Succes banner ────────────────────────────────── */
.succes {
  background: linear-gradient(145deg, #ECFDF5 0%, #D1FAE5 100%);
  border: 1.5px solid #86EFAC;
  border-radius: var(--radius);
  padding: 18px 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}
.succes-icon { font-size: 1.4rem; flex-shrink: 0; }
.succes-title { font-weight: 700; color: #065F46; font-size: .88rem; margin-bottom: 2px; }
.succes-sub { font-size: .8rem; color: #047857; line-height: 1.5; }

/* ── Features ─────────────────────────────────────── */
.features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 32px;
}
@media (max-width: 480px) {
  .features { grid-template-columns: 1fr; }
}
.feature {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--shadow-s);
  transition: box-shadow .2s, transform .2s;
}
.feature:hover {
  box-shadow: var(--shadow-m);
  transform: translateY(-2px);
}
.feature-icon {
  width: 34px; height: 34px;
  background: var(--accent-lt);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: .95rem;
  margin-bottom: 10px;
}
.feature-title {
  font-weight: 700;
  font-size: .84rem;
  color: var(--text);
  margin-bottom: 4px;
}
.feature-desc {
  font-size: .78rem;
  color: var(--muted);
  line-height: 1.5;
}

/* ── Hoe het werkt ────────────────────────────────── */
.how-section {
  margin-bottom: 32px;
}
.how-title {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.2rem;
  color: var(--navy);
  text-align: center;
  margin-bottom: 18px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
}
.step-num {
  width: 28px; height: 28px;
  min-width: 28px;
  background: var(--navy);
  color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .74rem;
  font-weight: 700;
}
.step-text { flex: 1; }
.step-title {
  font-weight: 700;
  font-size: .84rem;
  color: var(--text);
  margin-bottom: 2px;
}
.step-desc {
  font-size: .78rem;
  color: var(--muted);
  line-height: 1.45;
}

/* ── Social proof ─────────────────────────────────── */
.social-proof {
  text-align: center;
  padding: 24px 0;
  margin-bottom: 32px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.social-proof-stats {
  display: flex;
  justify-content: center;
  gap: 28px;
  flex-wrap: wrap;
}
.sp-stat { text-align: center; }
.sp-number {
  font-family: 'Playfair Display', serif;
  font-weight: 800;
  font-size: 1.45rem;
  color: var(--navy);
  line-height: 1;
}
.sp-label {
  font-size: .68rem;
  color: var(--muted);
  font-weight: 500;
  margin-top: 3px;
}

/* ── Footer ───────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 24px 0 8px;
  border-top: 1px solid var(--border);
  font-size: .7rem;
  color: var(--muted);
  line-height: 1.7;
}

/* ═════════════════════════════════════════════════════
   STREAMLIT WIDGET OVERRIDES
   ═════════════════════════════════════════════════════ */

/* Text input */
div[data-testid="stTextInput"] > div > div {
  border: 1.5px solid var(--border-h) !important;
  border-radius: 10px !important;
  background: var(--surface) !important; /* Witte balk achtergrond voor zoekveld */
  box-shadow: var(--shadow-m) !important; /* Mooie schaduw eromheen */
  transition: border-color .2s, box-shadow .2s !important;
  margin-bottom: 14px !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
  border-color: var(--navy-lt) !important;
  box-shadow: 0 0 0 3px rgba(30,77,140,.10) !important;
}
div[data-testid="stTextInput"] input {
  font-family: 'DM Sans', sans-serif !important;
  font-size: 1.05rem !important; /* Groter lettertype voor input */
  color: var(--text) !important;
  padding: 14px 14px !important; /* Meer ademruimte */
  background: transparent !important;
  text-align: center !important; /* Forceert de tekst naar het midden */
}
div[data-testid="stTextInput"] input::placeholder {
  color: var(--muted) !important;
  font-size: 1rem !important;
}

/* ── KNOPPEN — beperkte breedte, gecentreerd ──────── */
div[data-testid="stButton"],
div[data-testid="stDownloadButton"],
div[data-testid="stLinkButton"] {
  display: flex !important;
  justify-content: center !important;
}

div[data-testid="stButton"] > button {
  max-width: 340px !important;
  width: 100% !important;
  margin: 15px auto 40px auto !important; /* Zorgt dat de knop in het midden blijft en ademruimte heeft */
  background: var(--navy) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: .88rem !important;
  padding: 11px 20px !important;
  letter-spacing: .2px !important;
  box-shadow: 0 2px 8px rgba(11,29,58,.18) !important;
  transition: all .15s !important;
  cursor: pointer !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--navy-mid) !important;
  box-shadow: 0 4px 14px rgba(11,29,58,.24) !important;
  transform: translateY(-1px) !important;
}

div[data-testid="stDownloadButton"] > button {
  max-width: 340px !important;
  width: 100% !important;
  background: var(--navy) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: .88rem !important;
  padding: 11px 20px !important;
  box-shadow: 0 2px 8px rgba(11,29,58,.18) !important;
  transition: all .15s !important;
  cursor: pointer !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: var(--navy-mid) !important;
  transform: translateY(-1px) !important;
}

div[data-testid="stLinkButton"] > a {
  display: block !important;
  max-width: 340px !important;
  width: 100% !important;
  background: var(--accent) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 700 !important;
  font-size: .9rem !important;
  padding: 11px 20px !important;
  text-align: center !important;
  text-decoration: none !important;
  box-shadow: 0 2px 8px rgba(14,165,111,.22) !important;
  transition: all .15s !important;
  cursor: pointer !important;
}
div[data-testid="stLinkButton"] > a:hover {
  background: var(--accent-dk) !important;
  box-shadow: 0 4px 14px rgba(14,165,111,.30) !important;
  transform: translateY(-1px) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: .84rem !important;
}

/* Map */
[data-testid="stDeckGlJsonChart"],
[data-testid="stDeckGlJsonChart"] > div {
  border-radius: 10px !important;
  overflow: hidden !important;
  max-height: 200px !important;
}

/* Spinner */
[data-testid="stSpinner"] p {
  font-family: 'DM Sans', sans-serif !important;
  color: var(--navy) !important;
  font-size: .84rem !important;
}

/* Caption */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: .72rem !important;
  text-align: center !important;
}

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 560px) {
  .block-container,
  [data-testid="stMainBlockContainer"] {
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
  .navbar { padding: 12px 0 14px; margin-bottom: 20px; }
  .hero { padding: 2px 0 20px; }
  .paywall { padding: 20px 16px; }
  .trust { gap: 3px 10px; }
  .trust-item { font-size: .66rem; }
  .nav-secure { display: none; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  NAVIGATIEBALK
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="navbar">
  <div class="nav-logo">Woning<em>Check</em>AI</div>
  <div class="nav-pills">
    <div class="nav-secure">🔒 SSL</div>
    <div class="nav-badge">✦ Beta</div>
  </div>
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
        )
    else:
        st.warning("Rapport kon niet worden opgehaald. Voer uw adres hieronder opnieuw in.")

    st.query_params.clear()


# ─────────────────────────────────────────────────────────────
#  HERO + ZOEKFORMULIER
# ─────────────────────────────────────────────────────────────
if not betaald:
    st.markdown("""
    <div class="hero">
      <div class="hero-eyebrow">
        <span class="hero-eyebrow-dot"></span>
        Kadaster BAG-data · Claude AI analyse
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

# LET OP: De "<div class='search-wrap'>" wrapper is verwijderd om de spookbalk te fixen.
# We hebben de styling nu verplaatst naar de CSS voor "stTextInput" zelf.
st.markdown('<div class="search-label" style="text-align: center; margin-bottom: 12px; font-size: 0.75rem; color: #6B7896; font-weight: 700; text-transform: uppercase; letter-spacing: 0.7px;">🔍 Voer een Nederlands adres in</div>', unsafe_allow_html=True)
adres_input = st.text_input(
    label="adres",
    label_visibility="collapsed",
    placeholder="Bijv. Keizersgracht 123, Amsterdam",
)
scan_clicked = st.button("Analyseer dit adres →")

st.markdown("""
<div class="trust">
  <span class="trust-item"><span class="trust-check">✓</span> Preview gratis</span>
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
            st.error("Adres niet gevonden. Controleer de schrijfwijze of gebruik een volledig adres *(bijv. Hoofdstraat 1, Utrecht)*.")
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
                Alle aanbevelingen, besparingen, kostenoverzicht,
                subsidie-instructies en PDF download.
              </div>
              <div class="paywall-price">€4,95 <small>· eenmalig</small></div>
              <div class="paywall-list">
                <span><span class="chk">✓</span> Alle maatregelen</span>
                <span><span class="chk">✓</span> Subsidiegids</span>
                <span><span class="chk">✓</span> Kostentabel</span>
                <span><span class="chk">✓</span> PDF download</span>
                <span><span class="chk">✓</span> Veilig via Stripe</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button(
                "Volledig rapport ontgrendelen voor €4,95 →",
                stripe_url,
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
            )

        st.caption("Dit rapport is indicatief op basis van officiële BAG-data en AI-analyse. Het vervangt geen officieel energielabel.")


# ─────────────────────────────────────────────────────────────
#  HOE HET WERKT + FEATURES
# ─────────────────────────────────────────────────────────────
if not scan_clicked and not betaald:

    st.markdown("""
    <div class="how-section">
      <div class="how-title">Hoe het werkt</div>
      <div class="steps">
        <div class="step">
          <div class="step-num">1</div>
          <div class="step-text">
            <div class="step-title">Vul uw adres in</div>
            <div class="step-desc">Wij zoeken uw woning op in het Kadaster en halen bouwjaar en oppervlakte op.</div>
          </div>
        </div>
        <div class="step">
          <div class="step-num">2</div>
          <div class="step-text">
            <div class="step-title">AI analyseert uw woning</div>
            <div class="step-desc">Claude AI genereert een persoonlijk verduurzamingsadvies op basis van uw woningkenmerken.</div>
          </div>
        </div>
        <div class="step">
          <div class="step-num">3</div>
          <div class="step-text">
            <div class="step-title">Ontvang uw rapport</div>
            <div class="step-desc">Gratis preview, of het volledige rapport met subsidiegids en PDF voor €4,95.</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="features">
      <div class="feature">
        <div class="feature-icon">⚡</div>
        <div class="feature-title">Klaar in 30 seconden</div>
        <div class="feature-desc">Direct een volledig besparingsplan — geen wachttijd, geen account nodig.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">🏛️</div>
        <div class="feature-title">Officiële overheidsdata</div>
        <div class="feature-desc">Bouwjaar en oppervlakte direct uit het Kadaster BAG-register.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">🏦</div>
        <div class="feature-title">Subsidiegids inbegrepen</div>
        <div class="feature-desc">Stap-voor-stap ISDE, SEEH en meer — inclusief directe links naar aanvragen.</div>
      </div>
      <div class="feature">
        <div class="feature-icon">📄</div>
        <div class="feature-title">Professionele PDF</div>
        <div class="feature-desc">Download uw rapport — klaar om te delen met uw aannemer of adviseur.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="social-proof">
      <div class="social-proof-stats">
        <div class="sp-stat">
          <div class="sp-number">2.400+</div>
          <div class="sp-label">Woningen gescand</div>
        </div>
        <div class="sp-stat">
          <div class="sp-number">€847</div>
          <div class="sp-label">Gem. besparing/jaar</div>
        </div>
        <div class="sp-stat">
          <div class="sp-number">30 sec</div>
          <div class="sp-label">Gemiddelde levertijd</div>
        </div>
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