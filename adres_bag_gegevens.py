"""
Zoek bouwjaar (pand) en oppervlakte (verblijfsobject) bij een Nederlands adres.
Nu geoptimaliseerd voor import in main.py
"""

from __future__ import annotations
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
BAG_PAND_ITEMS = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"

# --- INTERNE HULPFUNCTIES (ongewijzigd) ---

def _http_get_json(url: str, *, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def geocode_mapbox(address: str, access_token: str) -> tuple[float, float, dict]:
    query = urllib.parse.quote(address, safe="")
    params = urllib.parse.urlencode({"access_token": access_token, "limit": 1, "country": "NL"})
    url = f"{MAPBOX_GEOCODE_URL.format(query=query)}?{params}"
    data = _http_get_json(url)
    features = data.get("features") or []
    if not features:
        raise ValueError("Geen locatie gevonden voor dit adres (Mapbox).")
    coords = features[0]["geometry"]["coordinates"]
    return float(coords[0]), float(coords[1]), features[0]

def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3: return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-30) + xi):
            inside = not inside
        j = i
    return inside

def point_in_polygon(lon: float, lat: float, geom: dict) -> bool:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon" and coords:
        if not point_in_ring(lon, lat, coords[0]): return False
        for hole in coords[1:]:
            if point_in_ring(lon, lat, hole): return False
        return True
    if gtype == "MultiPolygon" and coords:
        for poly in coords:
            if point_in_ring(lon, lat, poly[0]):
                if not any(point_in_ring(lon, lat, h) for h in poly[1:]): return True
        return False
    return False

def ring_area_sq_deg(ring: list[list[float]]) -> float:
    n = len(ring)
    if n < 3: return 0.0
    s = 0.0
    for i in range(n - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5

def containing_shell_area(lon: float, lat: float, feat: dict) -> float:
    geom = feat.get("geometry") or {}
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon" and c:
        if point_in_ring(lon, lat, c[0]) and not any(point_in_ring(lon, lat, h) for h in c[1:]):
            return ring_area_sq_deg(c[0])
    elif t == "MultiPolygon" and c:
        for poly in c:
            if poly and point_in_ring(lon, lat, poly[0]) and not any(point_in_ring(lon, lat, h) for h in poly[1:]):
                return ring_area_sq_deg(poly[0])
    return float("inf")

def fetch_pand_features(lon: float, lat: float, half_size: float) -> list[dict]:
    bbox = f"{lon - half_size},{lat - half_size},{lon + half_size},{lat + half_size}"
    params = urllib.parse.urlencode({"bbox": bbox, "f": "json", "limit": "50"})
    return list(_http_get_json(f"{BAG_PAND_ITEMS}?{params}").get("features") or [])

def pick_pand(lon: float, lat: float) -> dict:
    for hs in [0.00015, 0.0004, 0.001, 0.003]:
        candidates = [f for f in fetch_pand_features(lon, lat, hs) if point_in_polygon(lon, lat, f.get("geometry", {}))]
        if candidates:
            candidates.sort(key=lambda f: containing_shell_area(lon, lat, f))
            return candidates[0]
    raise ValueError("Geen pand gevonden op deze locatie.")

def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))

def verblijfsobject_urls(pand_props: dict) -> list[str]:
    res = pand_props.get("verblijfsobject.href") or pand_props.get("verblijfsobject") or []
    return [res] if isinstance(res, str) else res

# --- DE NIEUWE "VOORDEUR" VOOR MAIN.PY ---

def get_bag_data(address: str) -> dict | None:
    """De hoofdfunctie die wordt aangeroepen door main.py"""
    token = os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        print("Fout: MAPBOX_ACCESS_TOKEN ontbreekt in .env")
        return None

    try:
        # 1. Geocoding
        lon, lat, mb_feat = geocode_mapbox(address, token)
        
        # 2. Pand zoeken
        pand = pick_pand(lon, lat)
        props = pand.get("properties") or {}
        
        # 3. Verblijfsobject zoeken voor oppervlakte
        urls = verblijfsobject_urls(props)
        vo_feature = None
        target_nr = None
        
        # Probeer huisnummer match
        addr_props = mb_feat.get("properties") or {}
        if addr_props.get("address"):
            try: target_nr = int(str(addr_props.get("address")).strip())
            except: pass

        if target_nr and urls:
            for href in urls:
                url = href if href.endswith("f=json") else f"{href}{'&' if '?' in href else '?'}f=json"
                try:
                    vo = _http_get_json(url)
                    if (vo.get("properties") or {}).get("huisnummer") == target_nr:
                        vo_feature = vo
                        break
                except: continue

        # Geen huisnummer match? Pak de dichtstbijzijnde
        if not vo_feature and urls:
            best_d = float("inf")
            for href in urls:
                url = href if href.endswith("f=json") else f"{href}{'&' if '?' in href else '?'}f=json"
                try:
                    vo = _http_get_json(url)
                    c = (vo.get("geometry") or {}).get("coordinates")
                    if c:
                        d = haversine_m(lon, lat, float(c[0]), float(c[1]))
                        if d < best_d:
                            best_d, vo_feature = d, vo
                except: continue

        oppervlakte = (vo_feature.get("properties") or {}).get("oppervlakte") if vo_feature else "Onbekend"
        
        # 4. Resultaat teruggeven in het juiste formaat
        return {
            "bouwjaar": props.get("bouwjaar", "Onbekend"),
            "oppervlakte": oppervlakte,
            "woningtype": mb_feat.get("properties", {}).get("category", "Woning"), # Mapbox gokt type
            "lat": lat,
            "lon": lon
        }

    except Exception as e:
        print(f"Fout bij ophalen BAG data: {e}")
        return None

# Laat de main() hieronder staan voor losse tests
if __name__ == "__main__":
    test_adres = " ".join(sys.argv[1:]).strip() or "Abel Eppensstraat 1, Delfzijl"
    print(get_bag_data(test_adres))