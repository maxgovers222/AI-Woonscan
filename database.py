"""
database.py — Supabase persistentielaag voor WoningCheckAI.nl

Verantwoordelijkheden:
  - Elke succesvolle scan opslaan (adres, BAG-data, AI-rapport)
  - Scan-geschiedenis ophalen (voor toekomstige gebruikerspagina / analytics)
  - Graceful degradation: als Supabase niet bereikbaar is crasht de app NIET

Setup (eenmalig):
  1. Maak een gratis project op https://supabase.com
  2. Ga naar de SQL-editor en voer het schema hieronder uit
  3. Voeg SUPABASE_URL en SUPABASE_KEY toe aan je .env of Streamlit Secrets

SQL-schema (plak dit in de Supabase SQL-editor):
─────────────────────────────────────────────────────────────
create table woonscan_data (
  id           uuid default gen_random_uuid() primary key,
  adres        text          not null,
  postcode     text,
  woonplaats   text,
  bouwjaar     int4,
  oppervlakte  int4,
  lat          float8,
  lon          float8,
  energielabel text,
  rapport      text,
  created_at   timestamp with time zone default now()
);

-- Optioneel: index op adres voor snelle lookups
create index on woonscan_data (adres);
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
from typing import Optional


# ─────────────────────────────────────────────────────────────
#  CLIENT  (lazy init — importeert supabase alleen als keys aanwezig zijn)
# ─────────────────────────────────────────────────────────────

_client = None  # module-level singleton


def _get_client():
    """
    Geeft een gecachede Supabase-client terug.
    Geeft None terug als de omgevingsvariabelen ontbreken,
    zodat de rest van de app gewoon blijft werken.
    """
    global _client

    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key:
        return None  # Supabase niet geconfigureerd — silent fallback

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except ImportError:
        # supabase package niet geïnstalleerd — geen crash
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
#  PUBLIEKE FUNCTIES
# ─────────────────────────────────────────────────────────────

def sla_scan_op(
    adres: str,
    bag_data: dict,
    rapport: str,
    energielabel: str = "?",
) -> bool:
    """
    Slaat een voltooide scan op in Supabase.

    Args:
        adres:        Het ingevoerde adres (vrije tekst).
        bag_data:     De dict die get_bag_data() teruggeeft.
        rapport:      De Markdown-string van het AI-rapport.
        energielabel: Het geschatte energielabel (A–F of '?').

    Returns:
        True als het opslaan gelukt is, False bij elke fout.
    """
    client = _get_client()
    if client is None:
        return False  # Supabase niet beschikbaar — stil falen

    # Splits adres heuristisch in woonplaats (alles na de laatste komma)
    parts = adres.rsplit(",", 1)
    woonplaats = parts[-1].strip() if len(parts) > 1 else None

    # Normaliseer oppervlakte naar int (kan str "Onbekend" zijn)
    oppervlakte_raw = bag_data.get("oppervlakte")
    try:
        oppervlakte_int = int(oppervlakte_raw)
    except (ValueError, TypeError):
        oppervlakte_int = None

    bouwjaar_raw = bag_data.get("bouwjaar")
    try:
        bouwjaar_int = int(bouwjaar_raw)
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
    Haalt de meest recente scans op — handig voor een admin-dashboard later.

    Args:
        limiet: Maximaal aantal rijen (standaard 10).

    Returns:
        Lijst van dicts, of lege lijst bij fout / geen connectie.
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
    """Geeft True terug als Supabase bereikbaar en geconfigureerd is."""
    return _get_client() is not None
