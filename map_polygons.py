"""
Point-in-Polygon Mapping: Ordnet Referenzpunkte den XC-Thermik-Polygonen zu.

Liest:
  - data/regionen_xc_thermik.geojson     (GeometryCollection, leere Polygone)
  - data/regionen_referenzpunkte.geojson  (FeatureCollection, Points mit Properties)

Schreibt:
  - data/regionen_polygone_mapped.geojson (FeatureCollection, Polygone MIT Properties)

Raeumt auf:
  - Verschiebt alte, ersetzte GeoJSON-Dateien nach data/backup_geojson/
"""

import json
import shutil
from pathlib import Path

try:
    from shapely.geometry import shape, Point
except ImportError:
    print("FEHLER: shapely ist nicht installiert.")
    print("  pip install shapely")
    exit(1)


DATA_DIR = Path(__file__).parent / "data"


def main():
    # =========================================================================
    # SCHRITT 1: Point-in-Polygon Mapping
    # =========================================================================
    print("=" * 60)
    print("Point-in-Polygon Mapping")
    print("=" * 60)

    # 1a. Lade die Polygon-Quelldatei (GeometryCollection - keine Properties)
    poly_path = DATA_DIR / "regionen_xc_thermik.geojson"
    if not poly_path.exists():
        print(f"FEHLER: {poly_path} nicht gefunden!")
        return
    with open(poly_path, "r", encoding="utf-8") as f:
        poly_raw = json.load(f)

    # GeometryCollection -> FeatureCollection konvertieren
    # Jede nackte Geometrie wird in ein Feature-Objekt mit leeren Properties gewickelt
    geometries = poly_raw.get("geometries", [])
    features = []
    for geom in geometries:
        features.append({
            "type": "Feature",
            "properties": {},
            "geometry": geom,
        })
    print(f"  Polygone geladen: {len(features)}")

    # 1b. Lade die Referenzpunkte (FeatureCollection mit id, region, name, elevation_ref)
    points_path = DATA_DIR / "regionen_referenzpunkte.geojson"
    if not points_path.exists():
        print(f"FEHLER: {points_path} nicht gefunden!")
        return
    with open(points_path, "r", encoding="utf-8") as f:
        points_fc = json.load(f)

    ref_points = points_fc.get("features", [])
    print(f"  Referenzpunkte geladen: {len(ref_points)}")
    print()

    def _assign(feat, pt_feat):
        p = pt_feat["properties"]
        feat["properties"] = {
            "id": p.get("id", ""),
            "region": p.get("region", ""),
            "name": p.get("name", ""),
            "elevation_ref": p.get("elevation_ref"),
        }

    def _log_ok(pt_feat):
        p = pt_feat["properties"]
        print(f"  [OK] {p.get('id','???'):30s} -> Polygon zugeordnet ({p.get('name', '')})")

    # 1c. Optimales Matching: Jeder Punkt genau einem Polygon zuordnen
    # Phase 1: Finde alle exakten Point-in-Polygon Treffer
    shapely_polys = [shape(f["geometry"]) for f in features]
    pt_objects = []
    for pt_feature in ref_points:
        c = pt_feature["geometry"]["coordinates"]
        pt_objects.append(Point(c[0], c[1]))

    # candidates[poly_idx] = [(pt_idx, distance_to_centroid), ...]
    candidates = {i: [] for i in range(len(features))}
    pt_hits = {i: [] for i in range(len(ref_points))}

    for pi, pt in enumerate(pt_objects):
        for fi, poly in enumerate(shapely_polys):
            if poly.contains(pt):
                dist = pt.distance(poly.centroid)
                candidates[fi].append((pi, dist))
                pt_hits[pi].append((fi, dist))

    # Phase 2: Eindeutige Zuordnungen zuerst (Punkt in genau 1 Polygon)
    assigned_pts = set()
    assigned_polys = set()

    # Punkte mit genau einem Polygon-Treffer zuerst zuordnen
    for pi in range(len(ref_points)):
        hits = pt_hits[pi]
        if len(hits) == 1:
            fi = hits[0][0]
            if fi not in assigned_polys:
                _assign(features[fi], ref_points[pi])
                assigned_pts.add(pi)
                assigned_polys.add(fi)
                _log_ok(ref_points[pi])

    # Phase 3: Kollisionen loesen (mehrere Punkte in einem Polygon)
    for fi, cands in candidates.items():
        if fi in assigned_polys:
            continue
        # Nur noch nicht zugeordnete Punkte betrachten
        available = [(pi, d) for pi, d in cands if pi not in assigned_pts]
        if len(available) == 1:
            pi = available[0][0]
            _assign(features[fi], ref_points[pi])
            assigned_pts.add(pi)
            assigned_polys.add(fi)
            _log_ok(ref_points[pi])
        elif len(available) > 1:
            # Naechsten zum Centroid behalten
            available.sort(key=lambda x: x[1])
            pi = available[0][0]
            _assign(features[fi], ref_points[pi])
            assigned_pts.add(pi)
            assigned_polys.add(fi)
            _log_ok(ref_points[pi])

    # Phase 4: Uebrige Punkte dem naechsten freien Polygon zuordnen
    unmatched_points = []
    for pi in range(len(ref_points)):
        if pi in assigned_pts:
            continue
        pt = pt_objects[pi]
        props = ref_points[pi]["properties"]
        pt_id = props.get("id", "???")

        min_dist = float("inf")
        nearest_fi = None
        for fi in range(len(features)):
            if fi in assigned_polys:
                continue
            dist = shapely_polys[fi].distance(pt)
            if dist < min_dist:
                min_dist = dist
                nearest_fi = fi

        if nearest_fi is not None:
            _assign(features[nearest_fi], ref_points[pi])
            assigned_pts.add(pi)
            assigned_polys.add(nearest_fi)
            dist_km = min_dist * 111
            print(
                f"  [~]  {pt_id:30s} -> Naechstes Polygon zugeordnet "
                f"(~{dist_km:.1f}km entfernt, {props.get('name', '')})"
            )
        else:
            unmatched_points.append(pt_id)
            print(f"  [!!] {pt_id:30s} -> KEIN Polygon gefunden!")

    matched = len(assigned_pts)

    # Bericht
    empty_polygons = sum(1 for f in features if not f["properties"])
    print()
    print(f"--- Ergebnis ---")
    print(f"  Zugeordnet:             {matched}/{len(ref_points)} Punkte")
    print(f"  Polygone mit Properties: {matched}/{len(features)}")
    print(f"  Polygone ohne (leer):    {empty_polygons}/{len(features)}")

    if unmatched_points:
        print(f"  Punkte ohne Polygon:     {unmatched_points}")

    # 1d. Speichere als saubere FeatureCollection
    output = {
        "type": "FeatureCollection",
        "features": features,
    }

    out_path = DATA_DIR / "regionen_polygone_mapped.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"\n  [OK] Gespeichert: {out_path}")

    # =========================================================================
    # SCHRITT 2: Alte, ersetzte Dateien aufraeumen
    # =========================================================================
    print()
    print("=" * 60)
    print("Aufraeumen")
    print("=" * 60)

    backup_dir = DATA_DIR / "backup_geojson"
    backup_dir.mkdir(exist_ok=True)

    # Nur Dateien verschieben, die durch die neuen ERSETZT wurden
    old_files = [
        "regions_polygons.geojson",  # Ersetzt durch regionen_polygone_mapped.geojson
    ]

    for filename in old_files:
        src = DATA_DIR / filename
        if src.exists():
            dst = backup_dir / filename
            shutil.move(str(src), str(dst))
            print(f"  Verschoben: {filename} -> backup_geojson/")
        else:
            print(f"  Uebersprungen (nicht vorhanden): {filename}")

    # Zusammenfassung: Welche GeoJSON-Dateien sind jetzt im data/ Ordner?
    print()
    print("Produktive GeoJSON-Dateien in data/:")
    for f in sorted(DATA_DIR.glob("*.geojson")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
