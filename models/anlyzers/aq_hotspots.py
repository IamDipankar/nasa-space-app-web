# narayanganj_aq_hotspots_readable.py
# Same data/logic as before (S5P NO2, S5P CO, MAIAC AOD -> PM2.5 proxy),
# but with a presentation geared for general users.

import os, base64, tempfile
import math
from datetime import date, timedelta
import dotenv
import ee
import folium
from folium.plugins import MiniMap, Fullscreen, MousePosition, MeasureControl
from shapely.geometry import Point, MultiPoint

dotenv.load_dotenv()

# ------------------ CONFIG ------------------
AOI_BBOX = [90.32, 23.70, 90.52, 23.86]  # Narayanganj (W,S,E,N)
DAYS_BACK = 60
END = date.today()
START = END - timedelta(days=DAYS_BACK)

SCALE_M = 1000
MAX_POINTS = 5000

W_NO2 = 0.6
W_PM25 = 0.6
W_CO  = 0.3

# Hotspot selection
Z_THRESHOLD = 1.0
PCTL_THRESHOLD = 85.0

# Clustering (pure python)
EPS_METERS = 1500.0
MIN_SAMPLES = 6

# Severity buckets (z-score of combined AQ index)
SEVERE_Z = 2.0
HIGH_Z   = 1.0
ELEV_Z   = 0.5

COLORS = {
    "severe": "#d32f2f",
    "high":   "#fb8c00",
    "elev":   "#ffd54f",
    "hull":   "#444444",
    "gray":   "#9e9e9e",
}

USER = os.getenv("USER") or os.getenv("USERNAME") or "user"
OUT_HTML = f"web_outputs/aq_hotspots.html"
# --------------------------------------------


def ee_init_headless():
    sa = os.environ["EE_SERVICE_ACCOUNT"]       # ee-runner@<project>.iam.gserviceaccount.com
    key_b64 = os.environ["EE_KEY_B64"]          # base64 of the JSON key

    # Write key to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(base64.b64decode(key_b64).decode("utf-8"))
        key_path = f.name

    creds = ee.ServiceAccountCredentials(sa, key_path)
    ee.Initialize(credentials=creds)


def build_mean_images(aoi, start_iso, end_iso):
    no2 = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
           .filterBounds(aoi).filterDate(start_iso, end_iso)
           .select("tropospheric_NO2_column_number_density")
           .mean().rename("no2")).clip(aoi)

    co = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_CO")
          .filterBounds(aoi).filterDate(start_iso, end_iso)
          .select("CO_column_number_density")
          .mean().rename("co")).clip(aoi)

    aod = (ee.ImageCollection("MODIS/061/MCD19A2_GRANULES")
           .filterBounds(aoi).filterDate(start_iso, end_iso)
           .select("Optical_Depth_047")
           .mean().rename("aod")).clip(aoi)

    pm25 = aod.multiply(60.0).rename("pm25")  # simple proxy
    return no2, pm25, co


def sample_grid(aoi, img_stack, scale_m=SCALE_M, max_points=MAX_POINTS):
    fc = img_stack.sample(region=aoi, scale=scale_m, geometries=True)
    feats = fc.limit(max_points).getInfo().get("features", [])
    rows = []
    for f in feats:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point": continue
        lon, lat = geom["coordinates"]
        p = f.get("properties", {})
        no2, pm25, co = p.get("no2"), p.get("pm25"), p.get("co")
        if None in (no2, pm25, co): continue
        rows.append({"lat": float(lat), "lon": float(lon),
                     "no2": float(no2), "pm25": float(pm25), "co": float(co)})
    return rows


def zscores(vals):
    good = [v for v in vals if v is not None and math.isfinite(v)]
    if len(good) < 2: return [0.0 for _ in vals]
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

    # Cluster hulls (soft polygons)
    by_cluster = {}
    for hp, cid in zip(hotspots, clusters):
        if cid < 0: continue
        by_cluster.setdefault(cid, []).append(hp)

    for cid, pts in by_cluster.items():
        zs = [p["aq_index_z"] for p in pts]
        avgz = sum(zs)/len(zs)
        sev = severity_from_z(avgz) or "elev"
        color = COLORS[sev]
        # convex hull in WGS84 (approximate)
        mp = MultiPoint([Point(p["lon"], p["lat"]) for p in pts])
        try:
            hull = mp.convex_hull
            folium.GeoJson(
                data=hull.__geo_interface__,
                name=f"Cluster {cid} ({sev}, n={len(pts)})",
                style_function=lambda _,
                                   c=color: {"color": c, "weight": 2, "fillColor": c, "fillOpacity": 0.18},
                tooltip=f"Cluster {cid} — {sev.upper()} (n={len(pts)})"
            ).add_to(m)
        except Exception:
            pass

    # Hotspot markers with intuitive size/color and plain-language popup
    for hp, cid in zip(hotspots, clusters):
        sev = severity_from_z(hp["aq_index_z"])
        if sev is None:
            continue  # hide low-evidence points
        color = COLORS[sev]
        # size by severity
        radius = 6 if sev == "elev" else (8 if sev == "high" else 10)
        hint = []
        if hp["no2_z"] >= 1.0: hint.append("High NO₂ → traffic/industry")
        if hp["pm25_z"] >= 1.0: hint.append("High PM₂.₅ (AOD proxy) → dust/combustion")
        if hp["co_z"]  >= 1.0: hint.append("High CO → combustion/transport")
        hint_text = "<br>".join(hint) if hint else "Mixed drivers"

        folium.CircleMarker(
            location=(hp["lat"], hp["lon"]),
            radius=radius,
            color=color, fill=True, fill_color=color, fill_opacity=0.95,
            tooltip=f"{sev.upper()} hotspot",
            popup=(f"<b>{sev.upper()} hotspot</b><br>"
                   f"AQ index z = {hp['aq_index_z']:.2f} (top {int(hp['percentile'])}%)<br>"
                   f"NO₂ z: {hp['no2_z']:.2f} | PM₂.₅ z: {hp['pm25_z']:.2f} | CO z: {hp['co_z']:.2f}<br>"
                   f"{hint_text}")
        ).add_to(m)

    # Map widgets
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    Fullscreen().add_to(m)
    MousePosition(position="topright",
                  separator=" | ",
                  prefix="Lat/Lon:").add_to(m)
    MeasureControl(position="topright", primary_length_unit='kilometers').add_to(m)

    # Legend
    legend = """
    <div style="position: fixed; bottom: 18px; left: 18px; z-index:9999; background: white;
                padding: 10px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px;">
      <b>Air-Quality Hotspots (60-day avg)</b><br>
      <span style="display:inline-block;width:12px;height:12px;background:#d32f2f;border:1px solid #d32f2f;"></span>
      Severe (≥ 2σ above AOI mean)<br>
      <span style="display:inline-block;width:12px;height:12px;background:#fb8c00;border:1px solid #fb8c00;"></span>
      High (1–2σ)<br>
      <span style="display:inline-block;width:12px;height:12px;background:#ffd54f;border:1px solid #ffd54f;"></span>
      Elevated (0.5–1σ)<br>
      <i>Shaded polygons show cluster areas.</i>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def run(session_id=None, ee_geometry=None, aoi_bbox=None):
    print("Initializing Earth Engine…")
    ee_init_headless()

    if ee_geometry is None or aoi_bbox is None:
        print("Using default AOI (Narayanganj)…")
        aoi_bbox = AOI_BBOX
        ee_geometry = ee.Geometry.Rectangle(AOI_BBOX)
    if session_id is None:
        save_dir = OUT_HTML
    else:
        save_dir = os.path.join("web_outputs", session_id, 'aq_hotspots.html')

    aoi = ee_geometry
    start_iso, end_iso = str(START), str(END)
    print(f"AOI: {aoi_bbox} | Window: {start_iso} → {end_iso}")

    # Means
    no2_img, pm25_img, co_img = build_mean_images(aoi, start_iso, end_iso)
    stack = no2_img.addBands(pm25_img).addBands(co_img)

    # Sample grid
    rows = sample_grid(aoi, stack, scale_m=SCALE_M, max_points=MAX_POINTS)
    if not rows:
        raise SystemExit("No samples. Try expanding AOI or increasing DAYS_BACK.")

    # Z-scores
    no2_z = zscores([r["no2"] for r in rows])
    pm25_z = zscores([r["pm25"] for r in rows])
    co_z   = zscores([r["co"] for r in rows])
    aq_raw = [W_NO2*n + W_PM25*p + W_CO*c for n, p, c in zip(no2_z, pm25_z, co_z)]
    aq_index_z = zscores(aq_raw)

    # Pick hotspots (≥1σ or ≥85th percentile)
    def prc(vs, v): return p_rank(vs, v)
    pcts = [prc(aq_index_z, v) for v in aq_index_z]
    hotspots = []
    for r, nz, pz, cz, az, pr in zip(rows, no2_z, pm25_z, co_z, aq_index_z, pcts):
        if (az >= Z_THRESHOLD) or (pr >= PCTL_THRESHOLD):
            hotspots.append({
                "lat": r["lat"], "lon": r["lon"],
                "no2_z": nz, "pm25_z": pz, "co_z": cz,
                "aq_index_z": az, "percentile": pr
            })

    # Cluster
    clusters = cluster_dbscan(hotspots, eps_m=EPS_METERS, min_samples=MIN_SAMPLES) if hotspots else []

    # Map
    m = build_map(aoi_bbox, hotspots, clusters)
    os.makedirs(os.path.dirname(save_dir), exist_ok=True)
    m.save(save_dir)
    print(f"✅ Saved: {save_dir}")

def main():
    return run()

if __name__ == "__main__":
    main()