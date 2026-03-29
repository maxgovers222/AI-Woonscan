"""
database.py — Supabase persistentielaag voor WoningCheckAI.nl

Functies:
  - Scan opslaan na elke succesvolle analyse
  - Controleren of een adres al eerder gescand is (voorkomt dubbele AI-calls)
  - Recente scans ophalen (voor toekomstig admin-dashboard)
  - Faalt altijd stil: als Supabase niet beschikbaar is crasht de app NIET
"""

from __future__ import annotations
import os
import re


# ─────────────────────────────────────────────────────────────
#  CLIENT  (lazy init — wordt alleen aangemaakt als keys bestaan)
# ─────────────────────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key:
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
#  ADRES NORMALISATIE
#  Zorgt dat "Keizersgracht 123 Amsterdam" en
#  "keizersgracht 123, amsterdam" als hetzelfde adres worden herkend
# ─────────────────────────────────────────────────────────────

def _normaliseer_adres(adres: str) -> str:
    """
    Zet een adres om naar een gestandaardiseerde vorm voor vergelijking.
    Verwijdert komma's, extra spaties, en maakt alles lowercase.

    Voorbeelden:
      "Keizersgracht 123, Amsterdam" → "keizersgracht 123 amsterdam"
      "keizersgracht  123 amsterdam" → "keizersgracht 123 amsterdam"
      "HOOFDSTRAAT 1, UTRECHT"       → "hoofdstraat 1 utrecht"
    """
    adres = adres.lower()
    adres = adres.replace(",", " ")
    adres = re.sub(r"\s+", " ", adres)
    return adres.strip()


# ─────────────────────────────────────────────────────────────
#  PUBLIEKE FUNCTIES
# ─────────────────────────────────────────────────────────────

def zoek_bestaand_rapport(adres: str) -> str | None:
    """
    Controleert of dit adres al eerder gescand is en geeft het
    opgeslagen rapport terug als dat zo is.

    Zo werkt het:
      1. Het ingevoerde adres wordt genormaliseerd (lowercase, geen komma's)
      2. We zoeken in de database naar alle rijen waar het genormaliseerde
         adres overeenkomt
      3. Als we een match vinden geven we het opgeslagen rapport terug
      4. De app slaat dan de AI-call over — dat bespaart geld en tijd

    Args:
        adres: Het adres zoals de gebruiker het heeft ingetypt.

    Returns:
        Het opgeslagen rapport als string, of None als het adres nieuw is.
    """
    client = _get_client()
    if client is None:
        return None

    genormaliseerd = _normaliseer_adres(adres)

    try:
        # Haal alle opgeslagen adressen op en vergelijk genormaliseerd
        # (Supabase heeft geen ingebouwde normalisatie, dus we doen het in Python)
        response = (
            client.table("woonscan_data")
            .select("adres, rapport")
            .order("created_at", desc=True)
            .limit(500)  # Ruim genoeg voor de MVP-fase
            .execute()
        )

        rows = response.data or []

        for row in rows:
            opgeslagen_adres = row.get("adres", "")
            if _normaliseer_adres(opgeslagen_adres) == genormaliseerd:
                rapport = row.get("rapport")
                if rapport:  # Alleen teruggeven als er écht een rapport is
                    return rapport

        return None

    except Exception as e:
        print(f"[Supabase] Fout bij zoeken bestaand rapport: {e}")
        return None


def sla_scan_op(
    adres: str,
    bag_data: dict,
    rapport: str,
    energielabel: str = "?",
) -> bool:
    """
    Slaat een nieuwe scan op in de database.

    Args:
        adres:        Het adres zoals de gebruiker het heeft ingetypt.
        bag_data:     De dict die get_bag_data() teruggeeft (bouwjaar, oppervlakte, lat, lon).
        rapport:      Het gegenereerde AI-rapport als Markdown-string.
        energielabel: Het geschatte energielabel (A t/m F of '?').

    Returns:
        True als opslaan gelukt is, False bij elke fout.
    """
    client = _get_client()
    if client is None:
        return False

    # Splits adres in woonplaats (alles na de laatste komma)
    parts = adres.rsplit(",", 1)
    woonplaats = parts[-1].strip() if len(parts) > 1 else None

    # Zet oppervlakte en bouwjaar om naar integers (kunnen "Onbekend" zijn)
    try:
        oppervlakte_int = int(bag_data.get("oppervlakte"))
    except (ValueError, TypeError):
        oppervlakte_int = None

    try:
        bouwjaar_int = int(bag_data.get("bouwjaar"))
    except (ValueError, TypeError):
        bouwjaar_int = None

    record = {
        "adres":        adres,
        "woonplaats":   woonplaats,
        "bouwjaar":     bouwjaar_int,
        "oppervlakte":  oppervlakte_int,
        "lat":          bag_data.get("lat"),
        "lon":          bag_data.get("lon"),
        "energielabel": energielabel,
        "rapport":      rapport,
    }

    try:
        client.table("woonscan_data").insert(record).execute()
        return True
    except Exception as e:
        print(f"[Supabase] Fout bij opslaan scan: {e}")
        return False


def haal_recente_scans_op(limiet: int = 10) -> list[dict]:
    """
    Haalt de meest recente scans op.
    Handig voor een toekomstig admin-dashboard.

    Args:
        limiet: Maximaal aantal rijen (standaard 10).

    Returns:
        Lijst van dicts met scan-info, of lege lijst bij fout.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        response = (
            client.table("woonscan_data")
            .select("id, adres, bouwjaar, oppervlakte, energielabel, created_at")
            .order("created_at", desc=True)
            .limit(limiet)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"[Supabase] Fout bij ophalen scans: {e}")
        return []


def is_supabase_actief() -> bool:
    """Geeft True terug als Supabase bereikbaar en correct geconfigureerd is."""
    return _get_client() is not None
