# narayanganj_uhi_hotspots.py
# Urban heat island (UHI) hotspots from NASA MODIS LST (daytime), 60-day mean.
# Makes an easy-to-read Folium map with hotspot polygons + markers.

import os, base64, tempfile, dotenv
import math
from datetime import date, timedelta

import ee
import folium
from folium.plugins import MiniMap, Fullscreen, MousePosition, MeasureControl
from shapely.geometry import Point, MultiPoint

dotenv.load_dotenv()

# ------------- CONFIG -------------
AOI_BBOX = [90.32, 23.70, 90.52, 23.86]  # Narayanganj (W,S,E,N)
DAYS_BACK = 60
END = date.today()
START = END - timedelta(days=DAYS_BACK)

SCALE_M = 1000        # sampling grid; 1000 m ≈ MODIS 1km native
MAX_POINTS = 5000

# Hotspot selection
Z_THRESHOLD = 1.0     # ≥1σ above AOI mean
PCTL_THRESHOLD = 85.0 # or top 15%

# Clustering (pure python DBSCAN)
EPS_METERS = 1500.0
MIN_SAMPLES = 6

# Severity buckets by LST z-score
SEVERE_Z = 2.0
HIGH_Z   = 1.5
ELEV_Z   = 1.0

COLORS = {
    "severe": "#b71c1c",  # dark red
    "high":   "#e53935",  # red
    "elev":   "#fb8c00",  # orange
    "hull":   "#444444",
    "cool":   "#4fc3f7",  # optional cool overlay color
}

USER = os.getenv("USER") or os.getenv("USERNAME") or "user"
OUT_HTML = f"web_outputs/narayanganj_uhi_hotspots.html"
# ----------------------------------


def ee_init_headless():
    sa = os.environ["EE_SERVICE_ACCOUNT"]       # ee-runner@<project>.iam.gserviceaccount.com
    key_b64 = os.environ["EE_KEY_B64"]          # base64 of the JSON key

    # Write key to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(base64.b64decode(key_b64).decode("utf-8"))
        key_path = f.name

    creds = ee.ServiceAccountCredentials(sa, key_path)
    ee.Initialize(credentials=creds)


def build_lst_day_mean(aoi, start_iso, end_iso):
    """
    Use MODIS/061/MOD11A2 (8-day, 1km) Daytime LST.
    Units: Kelvin * 0.02. Convert to °C and mask invalids.
    """
    coll = (ee.ImageCollection("MODIS/061/MOD11A2")
            .filterBounds(aoi)
            .filterDate(start_iso, end_iso)
            .select("LST_Day_1km"))
    # mask zero or negative (fill) values
    coll = coll.map(lambda img: img.updateMask(img.gt(0)))
    lst_mean_k = coll.mean()  # still in scaled Kelvin
    lst_c = lst_mean_k.multiply(0.02).subtract(273.15).rename("lst_c").clip(aoi)
    return lst_c


def sample_grid(aoi, img, scale_m=SCALE_M, max_points=MAX_POINTS):
    fc = img.sample(region=aoi, scale=scale_m, geometries=True)
    feats = fc.limit(max_points).getInfo().get("features", [])
    rows = []
    for f in feats:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"]
        v = f.get("properties", {}).get("lst_c", None)
        if v is None or not math.isfinite(v):
            continue
        rows.append({"lat": float(lat), "lon": float(lon), "lst_c": float(v)})
    return rows


def zscores(vals):
    good = [v for v in vals if v is not None and math.isfinite(v)]
    if len(good) < 2:
        return [0.0 for _ in vals]
    mean = sum(good)/len(good)
    var  = sum((v-mean)**2 for v in good)/len(good)
    std  = math.sqrt(max(var, 1e-12))
    return [0.0 if (v is None or not math.isfinite(v)) else (v-mean)/std for v in vals]


def p_rank(all_vals, v):
    s = sorted(all_vals)
    if not s: return 0.0
    cnt = sum(1 for x in s if x <= v)
    return 100.0 * cnt / len(s)


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))


def cluster_dbscan(points, eps_m=EPS_METERS, min_samples=MIN_SAMPLES):
    n = len(points)
    visited = [False]*n
    clusters = [-1]*n
    nbrs = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            if haversine_m(points[i]["lat"], points[i]["lon"], points[j]["lat"], points[j]["lon"]) <= eps_m:
                nbrs[i].append(j); nbrs[j].append(i)
    cid = 0
    for i in range(n):
        if visited[i]: continue
        visited[i] = True
        if len(nbrs[i]) + 1 < min_samples:
            clusters[i] = -1; continue
        clusters[i] = cid
        seeds = list(nbrs[i]); k = 0
        while k < len(seeds):
            j = seeds[k]
            if not visited[j]:
                visited[j] = True
                if len(nbrs[j]) + 1 >= min_samples:
                    for q in nbrs[j]:
                        if q not in seeds: seeds.append(q)
            if clusters[j] < 0: clusters[j] = cid
            k += 1
        cid += 1
    return clusters


def severity_from_z(z):
    if z >= SEVERE_Z: return "severe"
    if z >= HIGH_Z:   return "high"
    if z >= ELEV_Z:   return "elev"
    return None


def build_map(aoi_bbox, hotspots, clusters):
    lat_c = (aoi_bbox[1] + aoi_bbox[3]) / 2.0
    lon_c = (aoi_bbox[0] + aoi_bbox[2]) / 2.0
    m = folium.Map(location=[lat_c, lon_c], zoom_start=12,
                   tiles="cartodbpositron", control_scale=True)

    # Draw cluster convex hulls (polygons) colored by average severity
    by_cluster = {}
    for hp, cid in zip(hotspots, clusters):
        if cid < 0: continue
        by_cluster.setdefault(cid, []).append(hp)

    for cid, pts in by_cluster.items():
        zs = [p["lst_z"] for p in pts]
        avgz = sum(zs)/len(zs)
        sev = severity_from_z(avgz) or "elev"
        color = COLORS[sev]
        mp = MultiPoint([Point(p["lon"], p["lat"]) for p in pts])
        try:
            hull = mp.convex_hull
            folium.GeoJson(
                data=hull.__geo_interface__,
                name=f"Cluster {cid} ({sev}, n={len(pts)})",
                style_function=lambda _, c=color: {"color": c, "weight": 2,
                                                   "fillColor": c, "fillOpacity": 0.18},
                tooltip=f"UHI Cluster {cid} — {sev.upper()} (n={len(pts)})"
            ).add_to(m)
        except Exception:
            pass

    # Hotspot markers
    for hp, cid in zip(hotspots, clusters):
        sev = severity_from_z(hp["lst_z"])
        if sev is None:
            continue
        color = COLORS[sev]
        radius = 6 if sev == "elev" else (8 if sev == "high" else 10)
        folium.CircleMarker(
            location=(hp["lat"], hp["lon"]),
            radius=radius,
            color=color, fill=True, fill_color=color, fill_opacity=0.95,
            tooltip=f"{sev.upper()} UHI hotspot",
            popup=(f"<b>{sev.upper()} UHI hotspot</b><br>"
                   f"LST: {hp['lst_c']:.1f} °C<br>"
                   f"LST z-score: {hp['lst_z']:.2f} (top {int(hp['percentile'])}%)")
        ).add_to(m)

    # Widgets + legend
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    Fullscreen().add_to(m)
    MousePosition(position="topright", separator=" | ", prefix="Lat/Lon:").add_to(m)
    MeasureControl(position="topright", primary_length_unit='kilometers').add_to(m)

    legend = f"""
    <div style="position: fixed; bottom: 18px; left: 18px; z-index:9999; background: white;
                padding: 10px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px;">
      <b>Urban Heat Island Hotspots (Daytime LST, {DAYS_BACK}-day mean)</b><br>
      <span style="display:inline-block;width:12px;height:12px;background:{COLORS['severe']};border:1px solid {COLORS['severe']};"></span>
      Severe (≥{SEVERE_Z}σ above AOI mean)<br>
      <span style="display:inline-block;width:12px;height:12px;background:{COLORS['high']};border:1px solid {COLORS['high']};"></span>
      High ({HIGH_Z}–{SEVERE_Z}σ)<br>
      <span style="display:inline-block;width:12px;height:12px;background:{COLORS['elev']};border:1px solid {COLORS['elev']};"></span>
      Elevated ({ELEV_Z}–{HIGH_Z}σ)<br>
      <i>Polygons show hotspot cluster areas.</i>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def main():
    print("Initializing Earth Engine…")
    ee_init_headless()

    aoi = ee.Geometry.Rectangle(AOI_BBOX)
    start_iso, end_iso = str(START), str(END)
    print(f"AOI: {AOI_BBOX} | Window: {start_iso} → {end_iso}")

    # Build 60-day mean daytime LST (°C)
    lst_img = build_lst_day_mean(aoi, start_iso, end_iso)

    # Sample grid
    print(f"Sampling ~{SCALE_M} m grid (<= {MAX_POINTS} points)…")
    rows = sample_grid(aoi, lst_img, scale_m=SCALE_M, max_points=MAX_POINTS)
    if not rows:
        raise SystemExit("No samples. Try increasing AOI, DAYS_BACK, or MAX_POINTS.")

    # Z-scores and selection
    lst_vals = [r["lst_c"] for r in rows]
    lst_z = zscores(lst_vals)
    pcts  = [p_rank(lst_z, v) for v in lst_z]

    hotspots = []
    for r, z, pr in zip(rows, lst_z, pcts):
        if (z >= Z_THRESHOLD) or (pr >= PCTL_THRESHOLD):
            hotspots.append({
                "lat": r["lat"], "lon": r["lon"],
                "lst_c": r["lst_c"], "lst_z": z, "percentile": pr
            })

    print(f"Hotspot points selected: {len(hotspots)}")

    # Cluster
    clusters = cluster_dbscan(hotspots, eps_m=EPS_METERS, min_samples=MIN_SAMPLES) if hotspots else []

    # Map
    m = build_map(AOI_BBOX, hotspots, clusters)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    m.save(OUT_HTML)
    print(f"✅ Saved UHI map to: {OUT_HTML}\nOpen this file in your browser to explore hotspots.")

if __name__ == "__main__":
    main()
