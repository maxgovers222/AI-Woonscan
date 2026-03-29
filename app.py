import streamlit as st
import datetime
import os
import urllib.parse
from adres_bag_gegevens import get_bag_data
from ai_architect import genereer_energie_advies
from database import sla_scan_op, zoek_bestaand_rapport, is_supabase_actief
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
#  STRIPE HELPER
#  Hoe het werkt:
#  1. Gebruiker klikt op "Koop PDF voor €4,95"
#  2. App stuurt hem naar een Stripe betaalpagina
#  3. Na betaling stuurt Stripe hem terug naar onze app
#     met ?betaald=ja&adres=... in de URL
#  4. App detecteert die terugkeer en toont de downloadknop
# ─────────────────────────────────────────────────────────────

STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK", "")
# Dit is de link die je in Stripe aanmaakt (begint met https://buy.stripe.com/...)
# Zie instructies onderaan dit bestand


def maak_stripe_url(adres: str) -> str:
    """
    Voegt het adres toe aan de Stripe betaallink als metadata.
    Na betaling stuurt Stripe de gebruiker terug met dit adres in de URL,
    zodat we weten voor welk adres er betaald is.
    """
    if not STRIPE_PAYMENT_LINK:
        return ""
    # We coderen het adres in de success URL zodat we het terugkrijgen
    adres_encoded = urllib.parse.quote(adres)
    app_url = os.getenv("APP_URL", "https://woningcheckai.nl")
    success_url = f"{app_url}?betaald=ja&adres={adres_encoded}"
    return f"{STRIPE_PAYMENT_LINK}?success_url={urllib.parse.quote(success_url)}"


def controleer_betaling() -> tuple[bool, str]:
    """
    Controleert of de gebruiker zojuist terugkomt van Stripe.
    Geeft (True, adres) terug als er betaald is, anders (False, "").

    Hoe: Stripe stuurt de gebruiker terug naar de success_url die wij
    hebben meegegeven. Die URL bevat ?betaald=ja&adres=...
    Streamlit leest die parameters uit via st.query_params.
    """
    params = st.query_params
    betaald = params.get("betaald", "") == "ja"
    adres   = urllib.parse.unquote(params.get("adres", ""))
    return betaald, adres


# ─────────────────────────────────────────────────────────────
#  PDF HELPER
# ─────────────────────────────────────────────────────────────
def create_pdf(rapport_tekst: str, adres: str, bouwjaar, oppervlakte) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Header-blok
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

    # Adres & metadata
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

    # Rapport body
    pdf.set_text_color(25, 25, 25)
    pdf.set_font("Arial", "", 11)
    safe_text = rapport_tekst.encode("latin-1", "replace").decode("latin-1")
    for sym in ["##", "**", "__", "---", "```", "# "]:
        safe_text = safe_text.replace(sym, "")
    pdf.multi_cell(0, 7, safe_text)

    # Footer
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


# ─────────────────────────────────────────────────────────────
#  ENERGIELABEL SCHATTING
# ─────────────────────────────────────────────────────────────
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
    --amber:    #F59E0B;
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

  /* ── Hero ─────────────────────────────────────────── */
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
  .hero-logo {
    font-family:'Syne',sans-serif; font-weight:800;
    font-size:2.3rem; color:#fff; letter-spacing:-.5px; line-height:1;
  }
  .hero-logo span { color:var(--teal-lt); }
  .hero-sub { font-weight:300; font-size:1.05rem; color:rgba(255,255,255,.70); margin-top:10px; }

  /* ── Cards ────────────────────────────────────────── */
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

  /* ── Metric pills ─────────────────────────────────── */
  .pills { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
  .pill {
    flex:1; min-width:110px; background:var(--bg);
    border:1px solid var(--border); border-radius:10px;
    padding:14px 16px; text-align:center;
  }
  .pill-lbl { font-size:.68rem; font-weight:500; letter-spacing:.9px;
              text-transform:uppercase; color:var(--muted); margin-bottom:6px; }
  .pill-val { font-family:'Syne',sans-serif; font-weight:700;
              font-size:1.45rem; color:var(--navy); line-height:1; }
  .pill-unit { font-size:.78rem; color:var(--muted); margin-top:3px; }

  /* ── Accent bar ───────────────────────────────────── */
  .accent { height:4px; border-radius:4px; margin-bottom:22px;
            background:linear-gradient(90deg,var(--teal),var(--teal-lt)); }

  /* ── Report body ──────────────────────────────────── */
  .report-body { font-size:.97rem; line-height:1.78; color:var(--text); }
  .report-body h2,.report-body h3 {
    font-family:'Syne',sans-serif; color:var(--navy); margin-top:1.3em;
  }
  .report-body table { width:100%; border-collapse:collapse; font-size:.88rem; margin:1em 0; }
  .report-body th { background:var(--navy); color:#fff; padding:8px 12px; text-align:left; }
  .report-body td { padding:7px 12px; border-bottom:1px solid var(--border); }
  .report-body tr:nth-child(even) td { background:#F8FAFD; }

  /* ── Betaalmuur blok ──────────────────────────────── */
  .paywall {
    background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%);
    border: 2px solid #F59E0B;
    border-radius: var(--r);
    padding: 28px 32px;
    text-align: center;
    margin-bottom: 22px;
    box-shadow: 0 4px 20px rgba(245,158,11,.15);
  }
  .paywall-title {
    font-family:'Syne',sans-serif; font-weight:800;
    font-size:1.3rem; color:var(--navy); margin-bottom:8px;
  }
  .paywall-sub {
    font-size:.93rem; color:#92400E; margin-bottom:20px; line-height:1.6;
  }
  .paywall-price {
    font-family:'Syne',sans-serif; font-weight:800;
    font-size:2rem; color:var(--navy);
  }
  .paywall-price span { font-size:1rem; font-weight:400; color:var(--muted); }
  .paywall-features {
    display:flex; justify-content:center; gap:20px;
    flex-wrap:wrap; margin:16px 0 22px; font-size:.83rem; color:#78350F;
  }
  .pf { display:flex; align-items:center; gap:5px; }

  /* ── Succes banner ────────────────────────────────── */
  .succes-banner {
    background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
    border: 2px solid var(--teal);
    border-radius: var(--r);
    padding: 20px 28px;
    text-align: center;
    margin-bottom: 22px;
  }
  .succes-banner h3 {
    font-family:'Syne',sans-serif; color:#065F46; margin:0 0 6px;
  }
  .succes-banner p { color:#047857; margin:0; font-size:.9rem; }

  /* ── Trust bar ────────────────────────────────────── */
  .trust { display:flex; align-items:center; justify-content:center;
           gap:26px; padding:16px 0 2px; flex-wrap:wrap; }
  .ti { display:flex; align-items:center; gap:7px; font-size:.80rem; color:var(--muted); }
  .td { width:7px; height:7px; background:var(--teal); border-radius:50%; flex-shrink:0; }

  /* ── Feature strip ────────────────────────────────── */
  .features { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }
  .feat {
    flex:1; min-width:140px; background:var(--surface);
    border:1px solid var(--border); border-radius:12px;
    padding:22px 20px; box-shadow:var(--sh);
  }
  .feat-icon { font-size:1.5rem; margin-bottom:10px; }
  .feat-title { font-family:'Syne',sans-serif; font-weight:700;
                font-size:.95rem; color:var(--navy); margin-bottom:6px; }
  .feat-desc { font-size:.83rem; color:var(--muted); line-height:1.5; }

  /* ── Widget overrides ─────────────────────────────── */
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
    font-size:1rem !important; padding:16px 24px !important;
    box-shadow:0 4px 16px rgba(15,40,80,.28) !important;
    transition:transform .15s,box-shadow .15s !important;
    font-size:1.05rem !important;
  }
  div[data-testid="stDownloadButton"]>button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 24px rgba(15,40,80,.38) !important;
  }
  [data-testid="stAlert"] { border-radius:10px !important; }

  /* ── Stripe betaalknop ────────────────────────────── */
  .stripe-btn {
    display:block; width:100%;
    background:linear-gradient(135deg,#F59E0B 0%,#D97706 100%);
    color:#fff !important; text-decoration:none !important;
    font-family:'Syne',sans-serif; font-weight:800; font-size:1.1rem;
    padding:16px 24px; border-radius:10px; text-align:center;
    box-shadow:0 4px 16px rgba(245,158,11,.40);
    transition:transform .15s,box-shadow .15s;
    cursor:pointer; border:none;
  }
  .stripe-btn:hover {
    transform:translateY(-2px);
    box-shadow:0 8px 24px rgba(245,158,11,.50);
  }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  HERO
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-badge">✦ Gratis rapport &nbsp;·&nbsp; AI-gedreven &nbsp;·&nbsp; Officiële Kadaster BAG-data</div>
  <div class="hero-logo">Woning<span>Check</span>AI</div>
  <div class="hero-sub">Vul een adres in — ontvang binnen seconden een persoonlijk verduurzamingsrapport</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  BETALING TERUGKEER DETECTIE
#  Als Stripe de gebruiker terugstuurde na een betaling,
#  tonen we direct de downloadknop voor dat adres.
# ─────────────────────────────────────────────────────────────
betaald, betaald_adres = controleer_betaling()

if betaald and betaald_adres:
    st.markdown("""
    <div class="succes-banner">
      <h3>✅ Betaling geslaagd!</h3>
      <p>Bedankt voor uw aankoop. Uw PDF rapport staat hieronder klaar.</p>
    </div>
    """, unsafe_allow_html=True)

    # Haal het rapport op voor dit adres (uit database of cache)
    with st.spinner("Rapport ophalen…"):
        bag_data_betaald = cached_bag_data(betaald_adres)

    if bag_data_betaald:
        rapport_betaald = zoek_bestaand_rapport(betaald_adres)
        if not rapport_betaald:
            with st.spinner("Rapport genereren…"):
                rapport_betaald = cached_advies(
                    bag_data_betaald.get("bouwjaar", "Onbekend"),
                    bag_data_betaald.get("oppervlakte", "Onbekend"),
                    bag_data_betaald.get("woningtype", "Woning"),
                )

        pdf_bytes = create_pdf(
            rapport_betaald,
            betaald_adres,
            bag_data_betaald.get("bouwjaar", "Onbekend"),
            bag_data_betaald.get("oppervlakte", "Onbekend"),
        )
        safe_name = betaald_adres.replace(" ", "_").replace(",", "").replace("/", "-")

        st.download_button(
            label="📄  Download uw PDF Rapport",
            data=pdf_bytes,
            file_name=f"WoningCheckAI_{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.caption("Sla de PDF op — u kunt hem altijd opnieuw downloaden door dit adres opnieuw in te voeren en te betalen.")
    else:
        st.error("Adres niet gevonden. Neem contact op via info@woningcheckai.nl")

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
scan_clicked = st.button("⚡  Genereer Gratis Energiescan", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="trust">
  <span class="ti"><span class="td"></span>Rapport gratis</span>
  <span class="ti"><span class="td"></span>Officiële BAG-data</span>
  <span class="ti"><span class="td"></span>Claude AI analyse</span>
  <span class="ti"><span class="td"></span>PDF voor €4,95</span>
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

        # Stap 3: Rapport — eerst database checken
        bestaand_rapport = zoek_bestaand_rapport(adres_input)
        if bestaand_rapport:
            rapport = bestaand_rapport
            st.info("💾 Dit adres is eerder gescand — rapport direct geladen.")
        else:
            with st.spinner("AI schrijft uw persoonlijk verduurzamingsplan…"):
                rapport = cached_advies(bouwjaar, oppervlakte, woningtype)

        # Stap 4: Rapport tonen (gratis)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🤖 &nbsp;Persoonlijk Verduurzamingsplan</div>', unsafe_allow_html=True)
        st.markdown('<div class="accent"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="report-body">{rapport}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Stap 5: Opslaan in Supabase
        sla_scan_op(
            adres=adres_input,
            bag_data=data,
            rapport=rapport,
            energielabel=label,
        )

        # Stap 6: BETAALMUUR voor PDF
        stripe_url = maak_stripe_url(adres_input)

        if stripe_url:
            # Stripe is geconfigureerd — toon betaalmuur
            st.markdown(f"""
            <div class="paywall">
              <div class="paywall-title">📄 Download uw Persoonlijk PDF Rapport</div>
              <div class="paywall-sub">
                Het volledige rapport inclusief alle subsidie-aanvraaginstructies,<br>
                kostenoverzicht en stap-voor-stap actieplan — klaar om te bewaren en te delen.
              </div>
              <div class="paywall-price">€4,95 <span>eenmalig</span></div>
              <div class="paywall-features">
                <span class="pf">✓ Volledige PDF direct beschikbaar</span>
                <span class="pf">✓ Subsidie-aanvraaginstructies</span>
                <span class="pf">✓ Kostenoverzicht tabel</span>
                <span class="pf">✓ Veilig betalen via Stripe</span>
              </div>
              <a href="{stripe_url}" class="stripe-btn" target="_self">
                🔒 &nbsp; Koop PDF Rapport voor €4,95
              </a>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Stripe nog niet geconfigureerd — toon gewoon de downloadknop (testmodus)
            pdf_bytes = create_pdf(rapport, adres_input, bouwjaar, oppervlakte)
            safe_name = adres_input.replace(" ", "_").replace(",", "").replace("/", "-")
            st.download_button(
                label="📄  Download volledig rapport als PDF",
                data=pdf_bytes,
                file_name=f"WoningCheckAI_{safe_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.caption("⚠️ Stripe nog niet geconfigureerd — PDF is tijdelijk gratis (testmodus).")

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
        <div class="feat-title">Rapport gratis</div>
        <div class="feat-desc">Vul een adres in en ontvang direct een volledig besparingsplan. Gratis.</div>
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
        <div class="feat-title">PDF voor €4,95</div>
        <div class="feat-desc">Download het volledige rapport als PDF om te bewaren of te delen met uw aannemer.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align:center; padding:24px 0 8px; font-size:.78rem; color:#9CA3AF;">
  © 2026 WoningCheckAI.nl &nbsp;·&nbsp; Alle rechten voorbehouden<br>
  <span style="opacity:.6;">Niet gelieerd aan de Nederlandse overheid · Indicatief advies</span>
</div>
""", unsafe_allow_html=True)