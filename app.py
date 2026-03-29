import streamlit as st
import datetime
import os
import urllib.parse
from adres_bag_gegevens import get_bag_data
from ai_architect import genereer_energie_advies
from database import sla_scan_op, zoek_bestaand_rapport, haal_recente_scans_op, is_supabase_actief
from fpdf import FPDF

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WoningCheckAI – Gratis Energiescan",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK", "")
APP_URL = os.getenv("APP_URL", "https://ai-woonscan-qdkwobbescefekt7zxo6j6.streamlit.app")


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def maak_stripe_url(adres: str = "") -> str:
    if not STRIPE_PAYMENT_LINK:
        return ""
    adres_encoded = urllib.parse.quote(adres, safe="")
    success_url = f"{APP_URL}?betaald=ja&adres={adres_encoded}"
    return f"{STRIPE_PAYMENT_LINK}?success_url={urllib.parse.quote(success_url, safe=':/?=&')}"


def controleer_betaling() -> tuple[bool, str]:
    params = st.query_params
    betaald = params.get("betaald", "") == "ja"
    adres = urllib.parse.unquote(params.get("adres", ""))
    return betaald, adres


def splits_rapport(rapport: str) -> tuple[str, str]:
    lijnen = rapport.split("\n")
    kopjes = 0
    splitpunt = len(lijnen)
    for i, lijn in enumerate(lijnen):
        if lijn.startswith("## ") or lijn.startswith("# "):
            kopjes += 1
            if kopjes == 3:
                splitpunt = i
                break
    return "\n".join(lijnen[:splitpunt]).strip(), "\n".join(lijnen[splitpunt:]).strip()


def create_pdf(rapport_tekst: str, adres: str, bouwjaar, oppervlakte) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_fill_color(11, 29, 58)
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
    pdf.set_text_color(11, 29, 58)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, f"Adres: {adres}", ln=True)
    pdf.set_draw_color(11, 29, 58)
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
    safe = rapport_tekst.encode("latin-1", "replace").decode("latin-1")
    for s in ["##", "**", "__", "---", "```", "# "]:
        safe = safe.replace(s, "")
    pdf.multi_cell(0, 7, safe)
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


for k, v in [("huidig_adres", ""), ("huidig_rapport", ""), ("huidig_bouwjaar", ""), ("huidig_oppervlakte", "")]:
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,900;1,600;1,700&family=Outfit:wght@300;400;500;600;700&display=swap');

/* ── Tokens ───────────────────────────────────────── */
:root {
  --ink:       #0B1D3A;
  --ink-2:     #2C3E5D;
  --muted:     #7A8BA8;
  --green:     #0C9B6A;
  --green-dk:  #097A53;
  --green-lt:  #E6F7F1;
  --amber:     #D97706;
  --amber-lt:  #FEF3C7;
  --bg:        #F7F9FC;
  --white:     #FFFFFF;
  --border:    #DDE4EF;
  --border-2:  #C8D3E6;
  --sh-1:      0 1px 4px rgba(11,29,58,.06), 0 6px 20px rgba(11,29,58,.07);
  --sh-2:      0 2px 8px rgba(11,29,58,.05), 0 16px 40px rgba(11,29,58,.10);
  --r:         12px;
  --r-lg:      20px;
}

/* ── Base ─────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp,
[data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'Outfit', sans-serif !important;
  color: var(--ink) !important;
}

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
.stDeployButton, footer, #MainMenu { display: none !important; }

/* Max-width container */
[data-testid="stMainBlockContainer"],
.block-container {
  max-width: 820px !important;
  margin: 0 auto !important;
  padding: 0 32px 80px !important;
}

/* Tighten vertical spacing between Streamlit blocks */
[data-testid="stVerticalBlock"] { gap: 0 !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── Navbar ───────────────────────────────────────── */
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28px 0 24px;
  margin-bottom: 0;
  border-bottom: 1px solid var(--border);
}
.nav-logo {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.25rem;
  color: var(--ink);
  letter-spacing: -0.3px;
}
.nav-logo span { color: var(--green); }
.nav-tag {
  font-family: 'Outfit', sans-serif;
  font-size: .65rem;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--green);
  background: var(--green-lt);
  border: 1px solid rgba(12,155,106,.18);
  padding: 5px 13px;
  border-radius: 999px;
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 64px 0 52px;
}
.hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .9px;
  text-transform: uppercase;
  color: var(--green);
  background: var(--green-lt);
  border: 1px solid rgba(12,155,106,.2);
  padding: 6px 16px 6px 12px;
  border-radius: 999px;
  margin-bottom: 28px;
}
.pill-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--green);
  animation: blink 2.5s ease-in-out infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: .3; }
}
.hero-h1 {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: clamp(2.4rem, 5vw, 3.4rem);
  color: var(--ink);
  line-height: 1.1;
  letter-spacing: -1px;
  margin-bottom: 0;
}
.hero-h1 em {
  font-style: italic;
  color: var(--green);
}
.hero-sub {
  font-family: 'Outfit', sans-serif;
  font-size: 1.08rem;
  color: var(--muted);
  font-weight: 400;
  line-height: 1.7;
  margin: 20px auto 0;
  max-width: 500px;
  text-align: center;
}

/* ── Search box ───────────────────────────────────── */
.search-area {
  margin: 40px auto 0;
  max-width: 560px;
  text-align: center;
}
.search-hint {
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}

/* ── Trust strip ──────────────────────────────────── */
.trust {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 18px 0 64px;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: .75rem;
  color: var(--muted);
  font-weight: 500;
}
.tck { color: var(--green); font-weight: 700; }

/* ── Section divider ──────────────────────────────── */
.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 0 0 48px;
}

/* ── Woningkaart ──────────────────────────────────── */
.wcard {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  box-shadow: var(--sh-1);
  margin-bottom: 16px;
}
.wcard-top {
  background: var(--ink);
  padding: 14px 22px;
}
.wcard-top-label {
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .6px;
  text-transform: uppercase;
  color: rgba(255,255,255,.5);
  margin-bottom: 2px;
}
.wcard-top-adres {
  font-family: 'Outfit', sans-serif;
  font-weight: 600;
  font-size: .97rem;
  color: #fff;
}
.wcard-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  padding: 22px 22px 18px;
  gap: 12px;
}
.metric {
  text-align: center;
  padding: 16px 8px;
  background: var(--bg);
  border-radius: 10px;
  border: 1px solid var(--border);
}
.metric-lbl {
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: .9px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 8px;
}
.metric-val {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 2rem;
  color: var(--ink);
  line-height: 1;
}
.metric-unit {
  font-size: .65rem;
  color: var(--muted);
  margin-top: 4px;
}

/* ── Rapport card ─────────────────────────────────── */
.rcard {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  box-shadow: var(--sh-1);
  margin-bottom: 16px;
}
.rcard-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
}
.rcard-title {
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: .9rem;
  color: var(--ink);
}
.rcard-badge {
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: .7px;
  text-transform: uppercase;
  color: var(--green);
  background: var(--green-lt);
  border: 1px solid rgba(12,155,106,.2);
  padding: 3px 11px;
  border-radius: 999px;
}
.rcard-badge.full { color: var(--amber); background: var(--amber-lt); border-color: rgba(217,119,6,.2); }
.rcard-body {
  padding: 28px 28px 24px;
  font-size: .93rem;
  line-height: 1.82;
  color: var(--ink-2);
}
.rcard-body h1, .rcard-body h2 {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  color: var(--ink);
  font-size: 1.15rem;
  margin: 1.8em 0 .5em;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.rcard-body h3 {
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  color: var(--ink);
  font-size: .97rem;
  margin: 1.4em 0 .4em;
}
.rcard-body strong { color: var(--ink); font-weight: 700; }
.rcard-body a { color: var(--green); text-decoration: underline; }
.rcard-body ul { padding-left: 20px; margin: .5em 0; }
.rcard-body li { margin-bottom: 5px; }
.rcard-body table {
  width: 100%;
  border-collapse: collapse;
  font-size: .84rem;
  margin: 1.2em 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}
.rcard-body th {
  background: var(--ink);
  color: #fff;
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  font-size: .75rem;
  letter-spacing: .3px;
}
.rcard-body td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--ink-2);
}
.rcard-body tr:nth-child(even) td { background: var(--bg); }

/* Preview fade */
.pfade {
  position: relative;
  overflow: hidden;
  max-height: 300px;
}
.pfade::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 130px;
  background: linear-gradient(transparent, var(--white));
  pointer-events: none;
}

/* ── Betaalmuur ───────────────────────────────────── */
.paywall {
  background: linear-gradient(160deg, #EEF4FF 0%, #E0ECFF 100%);
  border: 1.5px solid #BDD0F5;
  border-radius: var(--r-lg);
  padding: 40px 32px 36px;
  text-align: center;
  margin-bottom: 14px;
}
.paywall-title {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.55rem;
  color: var(--ink);
  margin-bottom: 12px;
  letter-spacing: -0.4px;
}
.paywall-sub {
  font-size: .9rem;
  color: var(--ink-2);
  line-height: 1.65;
  max-width: 420px;
  margin: 0 auto 22px;
}
.paywall-price {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: 3rem;
  color: var(--ink);
  line-height: 1;
  margin-bottom: 6px;
}
.paywall-per {
  font-family: 'Outfit', sans-serif;
  font-size: .78rem;
  color: var(--muted);
  margin-bottom: 22px;
}
.paywall-features {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 22px;
  margin-bottom: 28px;
  font-size: .8rem;
  color: var(--ink-2);
}
.paywall-features span { display: flex; align-items: center; gap: 5px; }
.chk { color: var(--green); font-weight: 700; }

/* ── Succes ───────────────────────────────────────── */
.succes {
  background: linear-gradient(135deg, #ECFDF5, #D1FAE5);
  border: 1.5px solid #6EE7B7;
  border-radius: var(--r-lg);
  padding: 22px 26px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 24px;
}
.succes-ico { font-size: 1.5rem; flex-shrink: 0; }
.succes-t { font-weight: 700; color: #065F46; font-size: .92rem; margin-bottom: 3px; }
.succes-s { font-size: .83rem; color: #047857; }

/* ── How it works ─────────────────────────────────── */
.how { margin-bottom: 56px; }
.how-h {
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--ink);
  text-align: center;
  margin-bottom: 28px;
  letter-spacing: -0.4px;
}
.steps { display: flex; flex-direction: column; gap: 10px; }
.step {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 20px 22px;
  box-shadow: var(--sh-1);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.step:hover { border-color: var(--border-2); box-shadow: var(--sh-2); transform: translateX(4px); }
.step-n {
  width: 34px; height: 34px; min-width: 34px;
  background: var(--ink);
  color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Outfit', sans-serif;
  font-size: .78rem; font-weight: 700;
}
.step-t { font-weight: 700; font-size: .9rem; color: var(--ink); margin-bottom: 4px; }
.step-d { font-size: .8rem; color: var(--muted); line-height: 1.55; }

/* ── Features ─────────────────────────────────────── */
.feats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 56px;
}
.feat {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 24px;
  box-shadow: var(--sh-1);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.feat:hover { border-color: var(--border-2); box-shadow: var(--sh-2); transform: translateY(-3px); }
.feat-ic {
  width: 42px; height: 42px;
  background: var(--green-lt);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  margin-bottom: 14px;
}
.feat-t { font-weight: 700; font-size: .9rem; color: var(--ink); margin-bottom: 6px; }
.feat-d { font-size: .8rem; color: var(--muted); line-height: 1.6; }

/* ── Stats ────────────────────────────────────────── */
.stats {
  display: flex;
  justify-content: center;
  gap: 56px;
  padding: 40px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  margin-bottom: 56px;
  flex-wrap: wrap;
}
.stat { text-align: center; }
.stat-n {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: 2.2rem;
  color: var(--ink);
  line-height: 1;
}
.stat-l {
  font-size: .65rem;
  font-weight: 600;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--muted);
  margin-top: 6px;
}

/* ── Footer ───────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 28px 0 8px;
  border-top: 1px solid var(--border);
  font-size: .72rem;
  color: var(--muted);
  line-height: 1.9;
}

/* ═══════════════════════════════════════════════════
   STREAMLIT OVERRIDES
   ═══════════════════════════════════════════════════ */

/* Text input */
div[data-testid="stTextInput"] > div > div {
  border: 1.5px solid var(--border-2) !important;
  border-radius: var(--r) !important;
  background: var(--white) !important;
  box-shadow: var(--sh-1) !important;
  transition: border-color .2s, box-shadow .2s !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
  border-color: var(--green) !important;
  box-shadow: 0 0 0 3px rgba(12,155,106,.12), var(--sh-1) !important;
}
div[data-testid="stTextInput"] input {
  font-family: 'Outfit', sans-serif !important;
  font-size: 1rem !important;
  color: var(--ink) !important;
  padding: 15px 18px !important;
  background: transparent !important;
  text-align: center !important;
}
div[data-testid="stTextInput"] input::placeholder {
  color: var(--muted) !important;
}

/* Center all buttons */
div[data-testid="stButton"],
div[data-testid="stDownloadButton"],
div[data-testid="stLinkButton"] {
  display: flex !important;
  justify-content: center !important;
  margin: 0 !important;
}

/* Primary button — scan */
div[data-testid="stButton"] > button {
  background: var(--ink) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 999px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 600 !important;
  font-size: .95rem !important;
  padding: 13px 36px !important;
  letter-spacing: .1px !important;
  box-shadow: 0 4px 18px rgba(11,29,58,.22) !important;
  transition: all .2s !important;
  width: auto !important;
  min-width: 220px !important;
  cursor: pointer !important;
  margin-top: 14px !important;
  margin-bottom: 0 !important;
}
div[data-testid="stButton"] > button:hover {
  background: #162c50 !important;
  box-shadow: 0 6px 26px rgba(11,29,58,.30) !important;
  transform: translateY(-2px) !important;
}

/* Download button */
div[data-testid="stDownloadButton"] > button {
  background: var(--ink) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 999px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 600 !important;
  font-size: .92rem !important;
  padding: 13px 36px !important;
  box-shadow: 0 4px 18px rgba(11,29,58,.2) !important;
  transition: all .2s !important;
  width: auto !important;
  min-width: 240px !important;
  cursor: pointer !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: #162c50 !important;
  transform: translateY(-2px) !important;
}

/* Link button — Stripe */
div[data-testid="stLinkButton"] > a {
  display: inline-block !important;
  background: var(--green) !important;
  color: #fff !important;
  border-radius: 999px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 700 !important;
  font-size: .97rem !important;
  padding: 14px 40px !important;
  text-align: center !important;
  text-decoration: none !important;
  box-shadow: 0 4px 20px rgba(12,155,106,.28) !important;
  transition: all .2s !important;
  min-width: 280px !important;
  cursor: pointer !important;
  width: auto !important;
}
div[data-testid="stLinkButton"] > a:hover {
  background: var(--green-dk) !important;
  box-shadow: 0 6px 28px rgba(12,155,106,.38) !important;
  transform: translateY(-2px) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  border-radius: var(--r) !important;
  font-family: 'Outfit', sans-serif !important;
  font-size: .86rem !important;
}

/* Map */
[data-testid="stDeckGlJsonChart"],
[data-testid="stDeckGlJsonChart"] > div {
  border-radius: var(--r) !important;
  overflow: hidden !important;
  max-height: 220px !important;
  border: 1px solid var(--border) !important;
}

/* Spinner */
[data-testid="stSpinner"] p {
  font-family: 'Outfit', sans-serif !important;
  color: var(--muted) !important;
  font-size: .86rem !important;
}

/* Caption */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: .72rem !important;
  text-align: center !important;
  padding: 8px 0 0 !important;
}

/* Remove extra spacing from empty elements */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:empty,
[data-testid="stElementContainer"]:has(> div:empty) {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* Responsive */
@media (max-width: 600px) {
  [data-testid="stMainBlockContainer"], .block-container {
    padding: 0 16px 60px !important;
  }
  .hero { padding: 36px 0 32px; }
  .hero-h1 { font-size: 2.1rem; }
  .feats { grid-template-columns: 1fr; }
  .stats { gap: 30px; }
  .wcard-metrics { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  NAVBAR
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="nav">
  <div class="nav-logo">Woning<span>Check</span>AI</div>
  <div class="nav-tag">✦ Beta</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  BETALING TERUGKEER
# ─────────────────────────────────────────────────────────────
betaald, url_adres = controleer_betaling()

if betaald:
    adres_b  = st.session_state.huidig_adres or url_adres
    rapport_b = st.session_state.huidig_rapport
    bouwjaar_b = st.session_state.huidig_bouwjaar
    oppervlak_b = st.session_state.huidig_oppervlakte

    if not rapport_b:
        with st.spinner("Rapport ophalen..."):
            scans = haal_recente_scans_op(limiet=1)
            if scans:
                laatste = scans[0]
                adres_b = laatste.get("adres", adres_b)
                bouwjaar_b = laatste.get("bouwjaar", "Onbekend")
                oppervlak_b = laatste.get("oppervlakte", "Onbekend")
                rapport_b = zoek_bestaand_rapport(adres_b)
            if not rapport_b and adres_b:
                bag_t = cached_bag_data(adres_b)
                if bag_t:
                    rapport_b = cached_advies(
                        bag_t.get("bouwjaar", "Onbekend"),
                        bag_t.get("oppervlakte", "Onbekend"),
                        bag_t.get("woningtype", "Woning"),
                    )

    st.markdown("""
    <div class="succes">
      <div class="succes-ico">✅</div>
      <div>
        <div class="succes-t">Betaling geslaagd — bedankt!</div>
        <div class="succes-s">Uw volledige verduurzamingsrapport staat hieronder klaar om te downloaden.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if rapport_b:
        st.markdown("""
        <div class="rcard">
          <div class="rcard-head">
            <span class="rcard-title">📄 Uw Volledige Verduurzamingsplan</span>
            <span class="rcard-badge full">Volledig</span>
          </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="rcard-body">{rapport_b}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        pdf_bytes = create_pdf(rapport_b, adres_b, bouwjaar_b, oppervlak_b)
        safe_name = adres_b.replace(" ", "_").replace(",", "").replace("/", "-")
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="⬇️  Download PDF Rapport",
            data=pdf_bytes,
            file_name=f"WoningCheckAI_{safe_name}.pdf",
            mime="application/pdf",
        )
    else:
        st.warning("Rapport kon niet worden opgehaald. Voer uw adres hieronder opnieuw in.")

    st.query_params.clear()
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  HERO
# ─────────────────────────────────────────────────────────────
if not betaald:
    st.markdown("""
    <div class="hero">
      <div class="hero-pill">
        <span class="pill-dot"></span>
        Kadaster BAG-data · Claude AI
      </div>
      <h1 class="hero-h1">
        Uw woning verduurzamen?<br>
        <em>Wij regelen het advies.</em>
      </h1>
      <p class="hero-sub">
        Vul een adres in en ontvang binnen 30 seconden een persoonlijk
        energiebesparingsplan — gratis, zonder account.
      </p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  ZOEKFORMULIER
# ─────────────────────────────────────────────────────────────
st.markdown('<div style="text-align:center; font-size:.65rem; font-weight:700; letter-spacing:.9px; text-transform:uppercase; color:#7A8BA8; margin-bottom:8px;">🔍 Voer een Nederlands adres in</div>', unsafe_allow_html=True)

adres_input = st.text_input(
    label="adres",
    label_visibility="collapsed",
    placeholder="Bijv. Keizersgracht 123, Amsterdam",
)
scan_clicked = st.button("Analyseer dit adres →")

st.markdown("""
<div class="trust">
  <span class="trust-item"><span class="tck">✓</span> Preview gratis</span>
  <span class="trust-item"><span class="tck">✓</span> Officiële BAG-data</span>
  <span class="trust-item"><span class="tck">✓</span> Geen account nodig</span>
  <span class="trust-item"><span class="tck">✓</span> Volledig rapport €4,95</span>
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
        <div class="wcard">
          <div class="wcard-top">
            <div class="wcard-top-label">Gevonden pand</div>
            <div class="wcard-top-adres">📍 {adres_input}</div>
          </div>
          <div class="wcard-metrics">
            <div class="metric">
              <div class="metric-lbl">Bouwjaar</div>
              <div class="metric-val">{bouwjaar}</div>
            </div>
            <div class="metric">
              <div class="metric-lbl">Oppervlak</div>
              <div class="metric-val">{oppervlakte}</div>
              <div class="metric-unit">m²</div>
            </div>
            <div class="metric">
              <div class="metric-lbl">Gesch. label</div>
              <div class="metric-val">{label}</div>
              <div class="metric-unit">indicatief</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.map([{"lat": data["lat"], "lon": data["lon"]}], zoom=16)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Rapport ophalen
        bestaand = zoek_bestaand_rapport(adres_input)
        if bestaand:
            rapport = bestaand
        else:
            with st.spinner("AI schrijft uw persoonlijk verduurzamingsplan..."):
                rapport = cached_advies(bouwjaar, oppervlakte, woningtype)

        st.session_state.huidig_adres       = adres_input
        st.session_state.huidig_rapport     = rapport
        st.session_state.huidig_bouwjaar    = bouwjaar
        st.session_state.huidig_oppervlakte = oppervlakte

        if not bestaand:
            sla_scan_op(adres=adres_input, bag_data=data, rapport=rapport, energielabel=label)

        # Preview tonen
        preview, rest = splits_rapport(rapport)

        st.markdown("""
        <div class="rcard">
          <div class="rcard-head">
            <span class="rcard-title">🤖 Uw Verduurzamingsplan</span>
            <span class="rcard-badge">Preview</span>
          </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="rcard-body"><div class="pfade">{preview}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Betaalmuur
        stripe_url = maak_stripe_url(adres_input)

        if stripe_url:
            st.markdown(f"""
            <div class="paywall">
              <div class="paywall-title">Ontgrendel uw volledige rapport</div>
              <div class="paywall-sub">
                Alle aanbevelingen, het complete kostenoverzicht,
                stap-voor-stap subsidie-aanvraaginstructies en uw persoonlijke PDF.
              </div>
              <div class="paywall-price">€4,95</div>
              <div class="paywall-per">eenmalig · direct beschikbaar</div>
              <div class="paywall-features">
                <span><span class="chk">✓</span> Alle maatregelen + besparingen</span>
                <span><span class="chk">✓</span> Subsidiegids per maatregel</span>
                <span><span class="chk">✓</span> Kostenoverzicht tabel</span>
                <span><span class="chk">✓</span> PDF download</span>
                <span><span class="chk">✓</span> Veilig via Stripe</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button(
                "🔒  Volledig rapport voor €4,95",
                stripe_url,
            )
        else:
            st.markdown(f'<div class="rcard-body">{rest}</div>', unsafe_allow_html=True)
            pdf_bytes = create_pdf(rapport, adres_input, bouwjaar, oppervlakte)
            safe_name = adres_input.replace(" ", "_").replace(",", "").replace("/", "-")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.download_button(
                label="⬇️  Download rapport (testmodus)",
                data=pdf_bytes,
                file_name=f"WoningCheckAI_{safe_name}.pdf",
                mime="application/pdf",
            )

        st.caption("Dit rapport is indicatief op basis van officiële BAG-data en AI-analyse. Het vervangt geen officieel energielabel.")


# ─────────────────────────────────────────────────────────────
#  HOE HET WERKT + FEATURES + STATS
# ─────────────────────────────────────────────────────────────
if not scan_clicked and not betaald:
    st.markdown("""
    <hr class="divider">

    <div class="how">
      <div class="how-h">Hoe het werkt</div>
      <div class="steps">
        <div class="step">
          <div class="step-n">1</div>
          <div>
            <div class="step-t">Vul uw adres in</div>
            <div class="step-d">Wij zoeken uw woning op in het Kadaster en halen bouwjaar, oppervlakte en locatie op.</div>
          </div>
        </div>
        <div class="step">
          <div class="step-n">2</div>
          <div>
            <div class="step-t">AI analyseert uw woning</div>
            <div class="step-d">Claude AI genereert op basis van uw woningkenmerken een persoonlijk verduurzamingsadvies.</div>
          </div>
        </div>
        <div class="step">
          <div class="step-n">3</div>
          <div>
            <div class="step-t">Ontvang uw rapport</div>
            <div class="step-d">Gratis preview direct zichtbaar. Volledig rapport met subsidiegids en PDF voor €4,95.</div>
          </div>
        </div>
      </div>
    </div>

    <div class="feats">
      <div class="feat">
        <div class="feat-ic">⚡</div>
        <div class="feat-t">Klaar in 30 seconden</div>
        <div class="feat-d">Direct een volledig besparingsplan, geen wachttijd en geen account nodig.</div>
      </div>
      <div class="feat">
        <div class="feat-ic">🏛️</div>
        <div class="feat-t">Officiële overheidsdata</div>
        <div class="feat-d">Bouwjaar en oppervlakte direct uit het Kadaster BAG-register.</div>
      </div>
      <div class="feat">
        <div class="feat-ic">🏦</div>
        <div class="feat-t">Subsidiegids inbegrepen</div>
        <div class="feat-d">Stap-voor-stap ISDE, SEEH en meer — met directe aanvraaglinks.</div>
      </div>
      <div class="feat">
        <div class="feat-ic">📄</div>
        <div class="feat-t">Professionele PDF</div>
        <div class="feat-d">Download uw rapport en deel het met uw aannemer of energieadviseur.</div>
      </div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="stat-n">2.400+</div>
        <div class="stat-l">Woningen gescand</div>
      </div>
      <div class="stat">
        <div class="stat-n">€847</div>
        <div class="stat-l">Gem. besparing/jaar</div>
      </div>
      <div class="stat">
        <div class="stat-n">30 sec</div>
        <div class="stat-l">Gemiddelde levertijd</div>
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