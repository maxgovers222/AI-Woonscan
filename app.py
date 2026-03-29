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
#  CSS — Dark Amber Editorial
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&family=Instrument+Serif:ital@0;1&family=Figtree:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

:root {
  --bg:          #07091C;
  --surface:     #0D1226;
  --surface-2:   #131A35;
  --surface-3:   #1B2448;
  --border:      rgba(255,255,255,0.065);
  --border-h:    rgba(245,158,11,0.35);
  --amber:       #F59E0B;
  --amber-dk:    #D97706;
  --amber-lt:    rgba(245,158,11,0.11);
  --amber-glow:  rgba(245,158,11,0.22);
  --teal:        #2DD4BF;
  --teal-lt:     rgba(45,212,191,0.11);
  --teal-glow:   rgba(45,212,191,0.18);
  --text:        #EEF2FF;
  --text-2:      #8892B0;
  --muted:       #4A5270;
  --radius:      14px;
  --radius-lg:   22px;
}

*, *::before, *::after { box-sizing: border-box; }

/* Grain overlay */
body::after {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity: .022;
  pointer-events: none;
  z-index: 9999;
}

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
  max-width: 700px !important;
  margin: 0 auto !important;
  padding: 0 24px 80px !important;
}

[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
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
  padding: 22px 0 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 44px;
  position: relative;
}
.navbar::after {
  content: '';
  position: absolute;
  bottom: -1px; left: 0;
  width: 56px; height: 2px;
  background: var(--amber);
  box-shadow: 0 0 14px var(--amber-glow);
  border-radius: 2px;
}
.nav-logo {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.18rem;
  color: var(--text);
  letter-spacing: -0.5px;
  line-height: 1;
}
.nav-logo em {
  font-style: normal;
  color: var(--amber);
  text-shadow: 0 0 24px var(--amber-glow);
}
.nav-pills { display: flex; align-items: center; gap: 8px; }
.nav-badge {
  background: var(--amber-lt);
  color: var(--amber);
  font-size: .58rem;
  font-weight: 700;
  letter-spacing: .9px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(245,158,11,.18);
}
.nav-secure {
  background: var(--teal-lt);
  color: var(--teal);
  font-size: .58rem;
  font-weight: 700;
  letter-spacing: .9px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(45,212,191,.18);
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 24px 0 52px;
  position: relative;
}
.hero-bg {
  position: absolute;
  top: -60px; left: 50%;
  transform: translateX(-50%);
  width: 600px; height: 340px;
  background:
    radial-gradient(ellipse at 50% 40%, rgba(245,158,11,.07) 0%, transparent 65%),
    radial-gradient(ellipse at 25% 70%, rgba(45,212,191,.04) 0%, transparent 55%);
  pointer-events: none;
  z-index: 0;
}
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: .63rem;
  font-weight: 600;
  color: var(--amber);
  letter-spacing: 1.1px;
  text-transform: uppercase;
  margin-bottom: 20px;
  background: var(--amber-lt);
  padding: 5px 14px 5px 10px;
  border-radius: 999px;
  border: 1px solid rgba(245,158,11,.16);
  position: relative; z-index: 1;
}
.hero-eyebrow-dot {
  width: 6px; height: 6px;
  background: var(--amber);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--amber);
  animation: hpulse 2.8s ease-in-out infinite;
}
@keyframes hpulse {
  0%, 100% { opacity: 1; transform: scale(1); box-shadow: 0 0 6px var(--amber); }
  50%       { opacity: .45; transform: scale(1.6); box-shadow: 0 0 18px var(--amber); }
}
.hero-title {
  font-family: 'Instrument Serif', serif;
  font-weight: 400;
  font-size: clamp(2rem, 5.5vw, 3.1rem);
  color: var(--text);
  line-height: 1.14;
  letter-spacing: -0.3px;
  margin-bottom: 18px;
  position: relative; z-index: 1;
}
.hero-title em {
  font-style: italic;
  color: var(--amber);
  text-shadow: 0 0 50px rgba(245,158,11,.28);
}
.hero-sub {
  font-size: .98rem;
  color: var(--text-2);
  font-weight: 400;
  line-height: 1.7;
  max-width: 480px;
  margin: 0 auto;
  position: relative; z-index: 1;
}

/* ── Trust strip ──────────────────────────────────── */
.trust {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 22px;
  margin-top: 14px;
  margin-bottom: 68px;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: .71rem;
  color: var(--text-2);
  font-weight: 500;
}
.trust-check { color: var(--teal); font-size: .75rem; font-weight: 700; }

/* ── Resultaat card ───────────────────────────────── */
.result-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: 0 0 0 1px rgba(245,158,11,.04), 0 8px 32px rgba(0,0,0,.45);
  margin-bottom: 16px;
}
.result-card-header {
  background: linear-gradient(135deg, var(--surface-3) 0%, var(--surface-2) 100%);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(245,158,11,.12);
}
.result-card-header::before {
  content: '';
  display: block;
  width: 3px; height: 18px;
  background: var(--amber);
  border-radius: 2px;
  box-shadow: 0 0 10px var(--amber-glow);
  flex-shrink: 0;
}
.result-card-header-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 600;
  font-size: .88rem;
  color: var(--text);
}
.result-card-body { padding: 20px; }

/* ── Metric pills ─────────────────────────────────── */
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 480px) { .metrics { grid-template-columns: 1fr; } }
.metric {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  text-align: center;
  transition: border-color .22s, box-shadow .22s;
}
.metric:hover {
  border-color: rgba(245,158,11,.22);
  box-shadow: 0 0 16px rgba(245,158,11,.07);
}
.metric-label {
  font-size: .58rem;
  font-weight: 700;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 5px;
}
.metric-value {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.65rem;
  color: var(--amber);
  line-height: 1.1;
  text-shadow: 0 0 22px rgba(245,158,11,.28);
}
.metric-unit {
  font-size: .63rem;
  color: var(--muted);
  margin-top: 3px;
}

/* ── Rapport card ─────────────────────────────────── */
.rapport-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,.45);
  margin-bottom: 16px;
}
.rapport-header {
  padding: 15px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-2);
}
.rapport-header-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: .9rem;
  color: var(--text);
}
.rapport-badge {
  background: var(--amber-lt);
  color: var(--amber);
  font-size: .58rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
  letter-spacing: .6px;
  text-transform: uppercase;
  border: 1px solid rgba(245,158,11,.18);
}
.rapport-body {
  padding: 24px 26px 22px;
  font-size: .9rem;
  line-height: 1.78;
  color: var(--text-2);
}
.rapport-body h1, .rapport-body h2 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  color: var(--text);
  font-size: 1.05rem;
  margin: 1.5em 0 .5em;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.rapport-body h3 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 600;
  color: var(--text);
  font-size: .95rem;
  margin: 1.2em 0 .4em;
}
.rapport-body strong { color: var(--amber); font-weight: 600; }
.rapport-body a { color: var(--teal); text-decoration: underline; }
.rapport-body ul { padding-left: 20px; margin: .5em 0; }
.rapport-body li { margin-bottom: 4px; }
.rapport-body table {
  width: 100%; border-collapse: collapse;
  font-size: .8rem; margin: 1.2em 0;
  border-radius: 10px; overflow: hidden;
  border: 1px solid var(--border);
}
.rapport-body th {
  background: var(--surface-3);
  color: var(--amber);
  padding: 10px 13px; text-align: left;
  font-weight: 700; font-size: .68rem;
  letter-spacing: .6px; text-transform: uppercase;
}
.rapport-body td {
  padding: 9px 13px;
  border-bottom: 1px solid var(--border);
  color: var(--text-2);
}
.rapport-body tr:nth-child(even) td { background: var(--surface-2); }

/* Preview fade */
.preview-wrap {
  position: relative;
  overflow: hidden;
  max-height: 320px;
}
.preview-wrap::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 150px;
  background: linear-gradient(transparent, var(--surface));
  pointer-events: none;
}

/* ── Betaalmuur ───────────────────────────────────── */
.paywall {
  background: linear-gradient(145deg, rgba(245,158,11,.08) 0%, rgba(245,158,11,.03) 100%);
  border: 1px solid rgba(245,158,11,.2);
  border-radius: var(--radius);
  padding: 32px 26px;
  text-align: center;
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
}
.paywall::before {
  content: '';
  position: absolute;
  top: -60px; right: -60px;
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(245,158,11,.09) 0%, transparent 70%);
  pointer-events: none;
}
.paywall::after {
  content: '';
  position: absolute;
  bottom: -40px; left: -40px;
  width: 160px; height: 160px;
  background: radial-gradient(circle, rgba(45,212,191,.05) 0%, transparent 70%);
  pointer-events: none;
}
.paywall-icon { font-size: 1.9rem; margin-bottom: 12px; }
.paywall-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.35rem;
  color: var(--text);
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}
.paywall-sub {
  font-size: .85rem;
  color: var(--text-2);
  line-height: 1.62;
  margin-bottom: 18px;
  max-width: 420px;
  margin-left: auto;
  margin-right: auto;
}
.paywall-price {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 2.4rem;
  color: var(--amber);
  margin-bottom: 16px;
  line-height: 1;
  text-shadow: 0 0 32px rgba(245,158,11,.3);
  position: relative; z-index: 1;
}
.paywall-price small {
  font-family: 'Figtree', sans-serif;
  font-size: .76rem;
  font-weight: 400;
  color: var(--muted);
}
.paywall-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 5px 18px;
  margin-bottom: 22px;
  font-size: .76rem;
  color: var(--text-2);
  position: relative; z-index: 1;
}
.paywall-list span { display: flex; align-items: center; gap: 5px; }
.paywall-list .chk { color: var(--teal); font-weight: 700; }

/* ── Succes banner ────────────────────────────────── */
.succes {
  background: linear-gradient(145deg, rgba(45,212,191,.08) 0%, rgba(45,212,191,.03) 100%);
  border: 1px solid rgba(45,212,191,.2);
  border-radius: var(--radius);
  padding: 20px 22px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 20px;
}
.succes-icon { font-size: 1.6rem; flex-shrink: 0; }
.succes-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  color: var(--teal);
  font-size: .9rem;
  margin-bottom: 3px;
}
.succes-sub { font-size: .82rem; color: var(--text-2); line-height: 1.55; }

/* ── Features ─────────────────────────────────────── */
.features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 44px;
}
@media (max-width: 480px) { .features { grid-template-columns: 1fr; } }
.feature {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: 0 4px 22px rgba(0,0,0,.32);
  transition: border-color .25s, transform .2s, box-shadow .25s;
}
.feature:hover {
  border-color: rgba(245,158,11,.22);
  transform: translateY(-3px);
  box-shadow: 0 10px 32px rgba(0,0,0,.4), 0 0 0 1px rgba(245,158,11,.08);
}
.feature-icon {
  width: 38px; height: 38px;
  background: linear-gradient(135deg, rgba(245,158,11,.14), rgba(245,158,11,.05));
  border: 1px solid rgba(245,158,11,.14);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
  margin-bottom: 13px;
}
.feature-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: .87rem;
  color: var(--text);
  margin-bottom: 5px;
}
.feature-desc {
  font-size: .77rem;
  color: var(--muted);
  line-height: 1.58;
}

/* ── Hoe het werkt ────────────────────────────────── */
.how-section { margin-bottom: 44px; }
.how-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.3rem;
  color: var(--text);
  text-align: center;
  margin-bottom: 22px;
  letter-spacing: -0.3px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}
.steps::before {
  content: '';
  position: absolute;
  left: 14px; top: 15px;
  width: 1px;
  height: calc(100% - 30px);
  background: linear-gradient(to bottom, var(--amber) 0%, rgba(45,212,191,.4) 60%, transparent 100%);
  opacity: .25;
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  transition: border-color .22s;
}
.step:hover { border-color: rgba(245,158,11,.18); }
.step-num {
  width: 30px; height: 30px;
  min-width: 30px;
  background: linear-gradient(135deg, rgba(245,158,11,.18), rgba(245,158,11,.06));
  border: 1px solid rgba(245,158,11,.22);
  color: var(--amber);
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
  font-size: .87rem;
  color: var(--text);
  margin-bottom: 3px;
}
.step-desc { font-size: .77rem; color: var(--muted); line-height: 1.52; }

/* ── Social proof ─────────────────────────────────── */
.social-proof {
  text-align: center;
  padding: 30px 0;
  margin-bottom: 44px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  position: relative;
}
.social-proof::before {
  content: '';
  position: absolute;
  top: -1px; left: 50%;
  transform: translateX(-50%);
  width: 72px; height: 2px;
  background: var(--amber);
  box-shadow: 0 0 12px var(--amber-glow);
  border-radius: 2px;
}
.social-proof-stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  flex-wrap: wrap;
}
.sp-stat { text-align: center; }
.sp-number {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.9rem;
  color: var(--amber);
  line-height: 1;
  text-shadow: 0 0 24px rgba(245,158,11,.25);
}
.sp-label {
  font-size: .65rem;
  color: var(--muted);
  font-weight: 600;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: .6px;
}

/* ── Footer ───────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 28px 0 10px;
  border-top: 1px solid var(--border);
  font-size: .7rem;
  color: var(--muted);
  line-height: 1.85;
}

/* ═════════════════════════════════════════════════════
   STREAMLIT WIDGET OVERRIDES
   ═════════════════════════════════════════════════════ */

/* Text input */
div[data-testid="stTextInput"] > div > div {
  border: 1px solid rgba(255,255,255,.08) !important;
  border-radius: 12px !important;
  background: var(--surface) !important;
  box-shadow: 0 4px 22px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.025) !important;
  transition: border-color .22s, box-shadow .22s !important;
  margin-bottom: 16px !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
  border-color: rgba(245,158,11,.38) !important;
  box-shadow: 0 0 0 3px rgba(245,158,11,.07), 0 4px 22px rgba(0,0,0,.32) !important;
}
div[data-testid="stTextInput"] input {
  font-family: 'Figtree', sans-serif !important;
  font-size: 1.05rem !important;
  color: var(--text) !important;
  padding: 15px 16px !important;
  background: transparent !important;
  text-align: center !important;
}
div[data-testid="stTextInput"] input::placeholder {
  color: var(--muted) !important;
  font-size: .95rem !important;
}

/* Buttons centered */
div[data-testid="stButton"],
div[data-testid="stDownloadButton"],
div[data-testid="stLinkButton"] {
  display: flex !important;
  justify-content: center !important;
}

/* Primary button — amber */
div[data-testid="stButton"] > button {
  max-width: 360px !important;
  width: 100% !important;
  margin: 14px auto 38px auto !important;
  background: var(--amber) !important;
  color: #0A0A0A !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 700 !important;
  font-size: .9rem !important;
  padding: 13px 24px !important;
  letter-spacing: .2px !important;
  box-shadow: 0 4px 22px rgba(245,158,11,.32) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--amber-dk) !important;
  box-shadow: 0 6px 30px rgba(245,158,11,.42) !important;
  transform: translateY(-2px) !important;
}

/* Download button — dark surface */
div[data-testid="stDownloadButton"] > button {
  max-width: 360px !important;
  width: 100% !important;
  background: var(--surface-2) !important;
  color: var(--text) !important;
  border: 1px solid rgba(255,255,255,.1) !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 700 !important;
  font-size: .88rem !important;
  padding: 12px 24px !important;
  box-shadow: 0 4px 18px rgba(0,0,0,.3) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: var(--surface-3) !important;
  border-color: rgba(245,158,11,.22) !important;
  transform: translateY(-1px) !important;
}

/* Link button — amber gradient */
div[data-testid="stLinkButton"] > a {
  display: block !important;
  max-width: 360px !important;
  width: 100% !important;
  background: linear-gradient(135deg, var(--amber) 0%, var(--amber-dk) 100%) !important;
  color: #0A0A0A !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'Bricolage Grotesque', sans-serif !important;
  font-weight: 800 !important;
  font-size: .92rem !important;
  padding: 14px 24px !important;
  text-align: center !important;
  text-decoration: none !important;
  box-shadow: 0 4px 26px rgba(245,158,11,.38) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
div[data-testid="stLinkButton"] > a:hover {
  box-shadow: 0 6px 34px rgba(245,158,11,.52) !important;
  transform: translateY(-2px) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  background: var(--surface) !important;
  border-color: rgba(255,255,255,.08) !important;
  border-radius: 10px !important;
  font-family: 'Figtree', sans-serif !important;
  font-size: .84rem !important;
  color: var(--text-2) !important;
}

/* Map */
[data-testid="stDeckGlJsonChart"],
[data-testid="stDeckGlJsonChart"] > div {
  border-radius: 12px !important;
  overflow: hidden !important;
  max-height: 200px !important;
  border: 1px solid var(--border) !important;
}

/* Spinner */
[data-testid="stSpinner"] p {
  font-family: 'Figtree', sans-serif !important;
  color: var(--amber) !important;
  font-size: .84rem !important;
}

/* Caption */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: .7rem !important;
  text-align: center !important;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--surface-3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(245,158,11,.28); }

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 560px) {
  .block-container,
  [data-testid="stMainBlockContainer"] {
    padding-left: 14px !important;
    padding-right: 14px !important;
  }
  .navbar  { padding: 14px 0 16px; margin-bottom: 24px; }
  .hero    { padding: 4px 0 26px; }
  .paywall { padding: 22px 18px; }
  .trust   { gap: 4px 12px; }
  .trust-item { font-size: .66rem; }
  .nav-secure { display: none; }
  .sp-number  { font-size: 1.55rem; }
  .metrics    { grid-template-columns: 1fr; }
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
    <div class="nav-secure">🔒 Beveiligd</div>
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
    '<div style="text-align:center; margin-bottom:10px; font-size:0.63rem; '
    'color:#F59E0B; font-weight:700; text-transform:uppercase; letter-spacing:1.2px;">'
    '⌕ &nbsp;Voer een Nederlands adres in</div>',
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
