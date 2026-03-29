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
#  CSS — Professional Light / Navy & Emerald
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&family=Instrument+Serif:ital@0;1&family=Figtree:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

:root {
  /* Brand */
  --navy:       #0B1D3A;
  --navy-mid:   #132E5B;
  --navy-lt:    #1E4D8C;
  --accent:     #0EA56F;
  --accent-dk:  #0A8A5C;
  --accent-lt:  #E7F9F1;
  --warm:       #F5A623;
  --warm-lt:    #FFF8EC;
  /* Backgrounds */
  --bg:         #F6F8FB;
  --surface:    #FFFFFF;
  --surface-2:  #F0F4FA;
  /* Text */
  --text:       #1A1F2E;
  --text-2:     #3D4663;
  --muted:      #6B7896;
  /* Borders */
  --border:     #E4E9F2;
  --border-h:   #CDD5E3;
  /* Shadows */
  --shadow-s:   0 1px 3px rgba(11,29,58,.05), 0 4px 14px rgba(11,29,58,.07);
  --shadow-m:   0 2px 6px rgba(11,29,58,.05), 0 10px 28px rgba(11,29,58,.09);
  --shadow-l:   0 4px 10px rgba(11,29,58,.05), 0 20px 48px rgba(11,29,58,.11);
  /* Shape */
  --radius:     14px;
  --radius-lg:  22px;
}

*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
.stApp {
  background: var(--bg) !important;
  font-family: 'Figtree', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--text) !important;
}

/* Hide Streamlit chrome */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
footer, #MainMenu,
.stDeployButton { display: none !important; }

[data-testid="stMain"] { background: var(--bg) !important; }

.block-container,
[data-testid="stMainBlockContainer"] {
  max-width: 780px !important;
  margin: 0 auto !important;
  padding: 0 36px 100px !important;
}

[data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
[data-testid="stElementContainer"]:has(> div:empty),
[data-testid="stVerticalBlock"] > div:empty,
.element-container:empty {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 0 !important;
}

/* ── Navbar ───────────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 0 28px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 56px;
}
.nav-logo {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.2rem;
  color: var(--navy);
  letter-spacing: -0.4px;
  line-height: 1;
}
.nav-logo em {
  font-style: normal;
  color: var(--accent);
}
.nav-pills { display: flex; align-items: center; gap: 8px; }
.nav-badge {
  background: var(--accent-lt);
  color: var(--accent);
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: .8px;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(14,165,111,.15);
}
.nav-secure {
  background: var(--warm-lt);
  color: var(--warm);
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: .8px;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(245,166,35,.15);
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 32px 0 60px;
}
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: .63rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: .9px;
  text-transform: uppercase;
  margin-bottom: 22px;
  background: var(--accent-lt);
  padding: 6px 16px 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(14,165,111,.15);
}
.hero-eyebrow-dot {
  width: 6px; height: 6px;
  background: var(--accent);
  border-radius: 50%;
  animation: hpulse 2.8s ease-in-out infinite;
}
@keyframes hpulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: .35; transform: scale(1.7); }
}
.hero-title {
  font-family: 'Instrument Serif', serif;
  font-weight: 400;
  font-size: clamp(2.1rem, 5.5vw, 3.2rem);
  color: var(--navy);
  line-height: 1.14;
  letter-spacing: -0.3px;
  margin-bottom: 20px;
}
.hero-title em {
  font-style: italic;
  color: var(--accent);
}
.hero-sub {
  font-size: 1.02rem;
  color: var(--text-2);
  font-weight: 400;
  line-height: 1.72;
  max-width: 520px;
  margin: 0 auto;
  text-align: center;
}

/* ── Trust strip ──────────────────────────────────── */
.trust {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px 26px;
  margin-top: 18px;
  margin-bottom: 72px;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: .72rem;
  color: var(--muted);
  font-weight: 500;
}
.trust-check { color: var(--accent); font-size: .78rem; font-weight: 700; }

/* ── Resultaat card ───────────────────────────────── */
.result-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-m);
  margin-bottom: 20px;
}
.result-card-header {
  background: var(--navy);
  padding: 16px 22px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-card-header-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 600;
  font-size: .9rem;
  color: #fff;
}
.result-card-body { padding: 24px; }

/* ── Metric pills ─────────────────────────────────── */
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (max-width: 480px) { .metrics { grid-template-columns: 1fr; } }
.metric {
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 12px;
  padding: 18px 14px;
  text-align: center;
  transition: border-color .2s, box-shadow .2s;
}
.metric:hover {
  border-color: var(--border-h);
  box-shadow: var(--shadow-s);
}
.metric-label {
  font-size: .6rem;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}
.metric-value {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.75rem;
  color: var(--navy);
  line-height: 1.1;
}
.metric-unit {
  font-size: .65rem;
  color: var(--muted);
  margin-top: 4px;
}

/* ── Rapport card ─────────────────────────────────── */
.rapport-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-m);
  margin-bottom: 20px;
}
.rapport-header {
  padding: 17px 22px;
  border-bottom: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface);
}
.rapport-header-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: .92rem;
  color: var(--text);
}
.rapport-badge {
  background: var(--accent-lt);
  color: var(--accent);
  font-size: .6rem;
  font-weight: 700;
  padding: 4px 11px;
  border-radius: 999px;
  letter-spacing: .5px;
  text-transform: uppercase;
  border: 1px solid rgba(14,165,111,.18);
}
.rapport-body {
  padding: 28px 30px 26px;
  font-size: .92rem;
  line-height: 1.82;
  color: var(--text-2);
}
.rapport-body h1, .rapport-body h2 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  color: var(--navy);
  font-size: 1.08rem;
  margin: 1.8em 0 .6em;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border);
}
.rapport-body h3 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  color: var(--text);
  font-size: .96rem;
  margin: 1.4em 0 .45em;
}
.rapport-body strong { color: var(--text); font-weight: 700; }
.rapport-body a { color: var(--accent); text-decoration: underline; }
.rapport-body ul { padding-left: 22px; margin: .6em 0; }
.rapport-body li { margin-bottom: 5px; }
.rapport-body table {
  width: 100%; border-collapse: collapse;
  font-size: .82rem; margin: 1.4em 0;
  border-radius: 10px; overflow: hidden;
  border: 1.5px solid var(--border);
}
.rapport-body th {
  background: var(--navy);
  color: #fff;
  padding: 11px 14px; text-align: left;
  font-weight: 700; font-size: .72rem;
  letter-spacing: .4px; text-transform: uppercase;
}
.rapport-body td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-2);
}
.rapport-body tr:nth-child(even) td { background: var(--bg); }

/* Preview fade */
.preview-wrap {
  position: relative;
  overflow: hidden;
  max-height: 320px;
}
.preview-wrap::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 140px;
  background: linear-gradient(transparent, var(--surface));
  pointer-events: none;
}

/* ── Betaalmuur ───────────────────────────────────── */
.paywall {
  background: linear-gradient(145deg, #F0F6FF 0%, #E4EEFA 100%);
  border: 1.5px solid #B8D0F0;
  border-radius: var(--radius);
  padding: 36px 30px;
  text-align: center;
  margin-bottom: 14px;
}
.paywall-icon { font-size: 1.8rem; margin-bottom: 12px; }
.paywall-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.4rem;
  color: var(--navy);
  margin-bottom: 10px;
  letter-spacing: -0.3px;
}
.paywall-sub {
  font-size: .87rem;
  color: var(--text-2);
  line-height: 1.65;
  margin-bottom: 20px;
  max-width: 440px;
  margin-left: auto;
  margin-right: auto;
}
.paywall-price {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 2.5rem;
  color: var(--navy);
  margin-bottom: 18px;
  line-height: 1;
}
.paywall-price small {
  font-family: 'Figtree', sans-serif;
  font-size: .78rem;
  font-weight: 400;
  color: var(--muted);
}
.paywall-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 20px;
  margin-bottom: 24px;
  font-size: .78rem;
  color: var(--text-2);
}
.paywall-list span { display: flex; align-items: center; gap: 5px; }
.paywall-list .chk { color: var(--accent); font-weight: 700; }

/* ── Succes banner ────────────────────────────────── */
.succes {
  background: linear-gradient(145deg, #ECFDF5 0%, #D1FAE5 100%);
  border: 1.5px solid #86EFAC;
  border-radius: var(--radius);
  padding: 22px 24px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 24px;
}
.succes-icon { font-size: 1.5rem; flex-shrink: 0; }
.succes-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  color: #065F46;
  font-size: .9rem;
  margin-bottom: 3px;
}
.succes-sub { font-size: .82rem; color: #047857; line-height: 1.55; }

/* ── Features ─────────────────────────────────────── */
.features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 52px;
}
@media (max-width: 480px) { .features { grid-template-columns: 1fr; } }
.feature {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow-s);
  transition: box-shadow .22s, transform .2s, border-color .2s;
}
.feature:hover {
  box-shadow: var(--shadow-m);
  transform: translateY(-3px);
  border-color: var(--border-h);
}
.feature-icon {
  width: 40px; height: 40px;
  background: var(--accent-lt);
  border: 1px solid rgba(14,165,111,.15);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.05rem;
  margin-bottom: 14px;
}
.feature-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: .88rem;
  color: var(--text);
  margin-bottom: 6px;
}
.feature-desc {
  font-size: .79rem;
  color: var(--muted);
  line-height: 1.6;
}

/* ── Hoe het werkt ────────────────────────────────── */
.how-section { margin-bottom: 52px; }
.how-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.35rem;
  color: var(--navy);
  text-align: center;
  margin-bottom: 26px;
  letter-spacing: -0.3px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  box-shadow: var(--shadow-s);
  transition: border-color .2s, box-shadow .2s;
}
.step:hover {
  border-color: var(--border-h);
  box-shadow: var(--shadow-m);
}
.step-num {
  width: 32px; height: 32px;
  min-width: 32px;
  background: var(--navy);
  color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: .78rem;
  font-weight: 800;
}
.step-text { flex: 1; }
.step-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: .88rem;
  color: var(--text);
  margin-bottom: 4px;
}
.step-desc { font-size: .79rem; color: var(--muted); line-height: 1.55; }

/* ── Social proof ─────────────────────────────────── */
.social-proof {
  text-align: center;
  padding: 36px 0;
  margin-bottom: 52px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.social-proof-stats {
  display: flex;
  justify-content: center;
  gap: 50px;
  flex-wrap: wrap;
}
.sp-stat { text-align: center; }
.sp-number {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 2rem;
  color: var(--navy);
  line-height: 1;
}
.sp-label {
  font-size: .67rem;
  color: var(--muted);
  font-weight: 600;
  margin-top: 5px;
  text-transform: uppercase;
  letter-spacing: .7px;
}

/* ── Footer ───────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 32px 0 12px;
  border-top: 1px solid var(--border);
  font-size: .71rem;
  color: var(--muted);
  line-height: 1.9;
}

/* ═════════════════════════════════════════════════════
   STREAMLIT WIDGET OVERRIDES
   ═════════════════════════════════════════════════════ */

/* Text input */
div[data-testid="stTextInput"] > div > div {
  border: 1.5px solid var(--border-h) !important;
  border-radius: 12px !important;
  background: var(--surface) !important;
  box-shadow: var(--shadow-m) !important;
  transition: border-color .22s, box-shadow .22s !important;
  margin-bottom: 18px !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
  border-color: var(--navy-lt) !important;
  box-shadow: 0 0 0 3px rgba(30,77,140,.10), var(--shadow-m) !important;
}
div[data-testid="stTextInput"] input {
  font-family: 'Figtree', sans-serif !important;
  font-size: 1.08rem !important;
  color: var(--text) !important;
  padding: 16px 18px !important;
  background: transparent !important;
  text-align: center !important;
}
div[data-testid="stTextInput"] input::placeholder {
  color: var(--muted) !important;
  font-size: 1rem !important;
}

/* Buttons centered */
div[data-testid="stButton"],
div[data-testid="stDownloadButton"],
div[data-testid="stLinkButton"] {
  display: flex !important;
  justify-content: center !important;
}

/* Primary button — navy */
div[data-testid="stButton"] > button {
  max-width: 380px !important;
  width: 100% !important;
  margin: 16px auto 44px auto !important;
  background: var(--navy) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 700 !important;
  font-size: .92rem !important;
  padding: 14px 28px !important;
  letter-spacing: .2px !important;
  box-shadow: 0 4px 22px rgba(11,29,58,.22) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--navy-mid) !important;
  box-shadow: 0 6px 30px rgba(11,29,58,.3) !important;
  transform: translateY(-2px) !important;
}

/* Download button */
div[data-testid="stDownloadButton"] > button {
  max-width: 380px !important;
  width: 100% !important;
  background: var(--navy) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 700 !important;
  font-size: .9rem !important;
  padding: 13px 28px !important;
  box-shadow: 0 4px 18px rgba(11,29,58,.2) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: var(--navy-mid) !important;
  transform: translateY(-1px) !important;
}

/* Link button — accent green */
div[data-testid="stLinkButton"] > a {
  display: block !important;
  max-width: 380px !important;
  width: 100% !important;
  background: var(--accent) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 800 !important;
  font-size: .94rem !important;
  padding: 15px 28px !important;
  text-align: center !important;
  text-decoration: none !important;
  box-shadow: 0 4px 22px rgba(14,165,111,.26) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stLinkButton"] > a:hover {
  background: var(--accent-dk) !important;
  box-shadow: 0 6px 30px rgba(14,165,111,.36) !important;
  transform: translateY(-2px) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  background: var(--surface) !important;
  border-radius: 10px !important;
  font-family: 'Figtree', sans-serif !important;
  font-size: .86rem !important;
}

/* Map */
[data-testid="stDeckGlJsonChart"],
[data-testid="stDeckGlJsonChart"] > div {
  border-radius: 12px !important;
  overflow: hidden !important;
  max-height: 220px !important;
  border: 1.5px solid var(--border) !important;
}

/* Spinner */
[data-testid="stSpinner"] p {
  font-family: 'Figtree', sans-serif !important;
  color: var(--navy) !important;
  font-size: .86rem !important;
}

/* Caption */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: .72rem !important;
  text-align: center !important;
}

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 600px) {
  .block-container,
  [data-testid="stMainBlockContainer"] {
    padding-left: 16px !important;
    padding-right: 16px !important;
  }
  .navbar  { padding: 16px 0 18px; margin-bottom: 30px; }
  .hero    { padding: 8px 0 30px; }
  .paywall { padding: 26px 20px; }
  .trust   { gap: 6px 14px; }
  .trust-item { font-size: .67rem; }
  .nav-secure { display: none; }
  .sp-number  { font-size: 1.6rem; }
  .metrics    { grid-template-columns: 1fr; }
  .social-proof-stats { gap: 30px; }
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
      <div class="hero-bg"></div>
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

st.markdown(
    '<div style="text-align:center; margin-bottom:12px; font-size:0.63rem; '
    'color:#6B7896; font-weight:700; text-transform:uppercase; letter-spacing:1px;">'
    '🔍 Voer een Nederlands adres in</div>',
    unsafe_allow_html=True,
)
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

        st.markdown(f"""
        <div class="result-card">
          <div class="result-card-header">
            <span class="result-card-header-title">📍 {adres_input}</span>
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
