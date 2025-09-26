# narayanganj_green_access_ndvi_osm.py
# Combines Google Earth Engine (Sentinel-2 NDVI) + OSM green areas to compute
# 5/10-minute walking access and propose micro-park candidates in Narayanganj.
#
# Deps:
#   pip install earthengine-api folium osmnx geopandas shapely networkx
#   # If you hit NumPy 2.x ABI issues with GeoPandas/Shapely wheels:
#   # pip install "numpy<2" && pip install --force-reinstall geopandas shapely pyproj fiona rtree
#
# First run will prompt a browser for Earth Engine auth (ee.Authenticate()).

import os
import math
import warnings

# ---- Load heavy libs with a friendly error if NumPy ABI is mismatched ----
try:
    import ee
    import folium
    import networkx as nx
    import osmnx as ox
    import geopandas as gpd
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
except Exception as e:
    raise SystemExit(
        f"\nImport error: {e}\n\n"
        "This often happens when GeoPandas/Shapely wheels were built for NumPy 1.x but you're on NumPy 2.x.\n"
        "Quick fix (in a clean venv):\n"
        "  pip install 'numpy<2'\n"
        "  pip install --force-reinstall geopandas shapely pyproj fiona rtree\n"
        "Or use a fresh 'conda create -n aoi python=3.11' env and install the deps.\n"
    )

warnings.filterwarnings("ignore", category=UserWarning)

# ----------------------------
# OSMNX COMPATIBILITY HELPERS
# ----------------------------
try:
    # osmnx >= 2.x
    from osmnx.features import features_from_polygon as osm_features_from_polygon
except Exception:
    try:
        # osmnx <= 1.x
        from osmnx import geometries_from_polygon as osm_features_from_polygon
    except Exception:
        raise SystemExit(
            "Your osmnx version is missing polygon geometries. Please: pip install --upgrade osmnx."
        )

# ----------------------------
# SETTINGS
# ----------------------------
PLACE = "Narayanganj, Dhaka Division, Bangladesh"

# NDVI thresholds
NDVI_GREEN_MIN = 0.35   # pixels with NDVI >= 0.35 are considered 'green' (tweakable)

# Walking thresholds (seconds)
T5 = 5 * 60       # 5 minutes
T10 = 10 * 60     # 10 minutes
WALK_MPS = 1.3    # ~4.7 km/h

# OSM tags to include as green destinations
GREEN_TAGS = {
    "leisure": ["park", "garden"],
    "landuse": ["recreation_ground", "grass"],
    "natural": ["wood"],
}

# Buffer for visualizing reachable edges as polygons (purely cosmetic on the map)
EDGE_BUFFER_M = 25

# Number of micro-park candidates to propose (midpoints of longest uncovered edges)
TOP_N_CANDIDATES = 20

# GEE composite tries (recent → broader → cloudier)
DATE_TRIES = [
    ("2025-09-01", "2025-09-25", 20),
    ("2025-08-01", "2025-09-25", 40),
    ("2025-06-01", "2025-09-25", 80),
]

# Output paths
USER = os.getenv("USER") or os.getenv("USERNAME") or "yourusername"
DOWNLOADS = os.path.expanduser(f"~/Downloads")
OUT_HTML = os.path.join("web_outputs", "narayanganj_green_access_ndvi_osm.html")


# ----------------------------
# EARTH ENGINE HELPERS
# ----------------------------
def ee_init():
    try:
        ee.Initialize()
    except Exception:
        ee.Authenticate()   # opens browser once
        ee.Initialize()


def choose_s2_composite(aoi_geom):
    """Pick a recent, low-cloud Sentinel-2 composite (L2A preferred, fallback to L1C)."""
    for (start, end, cloud) in DATE_TRIES:
        s2sr = (ee.ImageCollection("COPERNICUS/S2_SR")
                .filterBounds(aoi_geom)
                .filterDate(start, end)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud)))
        if s2sr.size().getInfo() > 0:
            return s2sr.median(), f"S2_SR {start}..{end} cloud<{cloud}%"
        s2l1c = (ee.ImageCollection("COPERNICUS/S2")
                 .filterBounds(aoi_geom)
                 .filterDate(start, end)
                 .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud)))
        if s2l1c.size().getInfo() > 0:
            return s2l1c.median(), f"S2_L1C {start}..{end} cloud<{cloud}%"
    raise SystemExit("No recent Sentinel-2 scenes found for AOI after fallbacks.")


def gee_green_polygons(aoi_geom, ndvi_min=NDVI_GREEN_MIN, scale=30, max_features=500):
    """
    Build green polygons from NDVI on GEE:
      - Compute NDVI = (B8 - B4)/(B8 + B4)
      - Threshold NDVI >= ndvi_min
      - Vectorize (reduceToVectors), simplify, and return as GeoJSON-like dict
    """
    composite, desc = choose_s2_composite(aoi_geom)
    print("GEE composite picked:", desc)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    green_mask = ndvi.gte(ndvi_min).selfMask()

    # Vectorize (beware of complexity → use bestEffort + limit)
    vectors = green_mask.reduceToVectors(
        geometry=aoi_geom,
        scale=scale,                 # 10-30 m typical; larger → simpler geometry
        geometryType="polygon",
        labelProperty="class",
        bestEffort=True,
        maxPixels=1e13
    )

    vectors = vectors.limit(max_features)  # keep client payload manageable
    fc = vectors.getInfo()  # bring small feature collection client-side

    # Convert to GeoDataFrame
    feats = fc.get("features", [])
    if not feats:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    geoms = []
    for f in feats:
        geom = f.get("geometry")
        if geom:
            geoms.append(geom)

    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    # Keep only polygons
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    return gdf


# ----------------------------
# CORE LOGIC
# ----------------------------
def line_midpoint(geom: LineString):
    try:
        return geom.interpolate(0.5, normalized=True)
    except Exception:
        if geom.geom_type == "LineString" and len(geom.coords) >= 2:
            (x1, y1), (x2, y2) = geom.coords[0], geom.coords[-1]
            return Point((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        return geom.centroid


def make_iso_polygon(edges_subset, buffer_m=EDGE_BUFFER_M):
    if edges_subset.empty:
        return None
    buffered = edges_subset.geometry.buffer(buffer_m)
    merged = unary_union(list(buffered.values))
    return gpd.GeoSeries([merged], crs=edges_subset.crs)


def main():
    # Earth Engine init
    ee_init()

    # OSMnx settings
    ox.settings.log_console = True
    ox.settings.use_cache = True
    ox.settings.timeout = 180

    print("Geocoding AOI…")
    aoi = ox.geocode_to_gdf(PLACE)
    if aoi.empty:
        raise SystemExit("Could not geocode the AOI name.")
    aoi_polygon = aoi.geometry.iloc[0]

    print("Downloading pedestrian network…")
    G = ox.graph_from_polygon(aoi_polygon, network_type="walk", simplify=True)

    print("Projecting graph to local metric CRS…")
    Gp = ox.project_graph(G)
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(Gp)
    if "u" not in edges_gdf.columns or "v" not in edges_gdf.columns:
        edges_gdf = edges_gdf.reset_index()
    graph_crs = nodes_gdf.crs

    # ---- Pull OSM green polygons
    print("Downloading OSM green areas (parks and related tags)…")
    green_layers = []
    for k, v in GREEN_TAGS.items():
        try:
            g = osm_features_from_polygon(aoi_polygon, tags={k: v})
            if g is not None and not g.empty:
                green_layers.append(g)
        except Exception:
            pass
    osm_greens = None
    if green_layers:
        base_crs = getattr(green_layers[0], "crs", None) or "EPSG:4326"
        osm_greens = gpd.GeoDataFrame(
            gpd.pd.concat(green_layers, ignore_index=True), crs=base_crs
        )
        osm_greens = osm_greens[osm_greens.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

    # ---- Pull NDVI-based green polygons from GEE (limited count/complexity)
    print("Vectorizing NDVI green polygons from GEE (this is server-side fast)…")
    # Build a simple rectangle AOI for GEE from the OSM aoi bounds
    minx, miny, maxx, maxy = aoi.to_crs(epsg=4326).total_bounds
    gee_aoi = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

    ndvi_greens = gee_green_polygons(gee_aoi, ndvi_min=NDVI_GREEN_MIN, scale=30, max_features=600)

    # ---- Merge OSM + NDVI polygons
    greens_list = []
    if osm_greens is not None and not osm_greens.empty:
        greens_list.append(osm_greens.to_crs(epsg=4326))
    if ndvi_greens is not None and not ndvi_greens.empty:
        greens_list.append(ndvi_greens.to_crs(epsg=4326))

    if not greens_list:
        raise SystemExit("No green polygons found from OSM or NDVI. Try lowering NDVI_GREEN_MIN or broadening dates.")
    greens_all = gpd.GeoDataFrame(gpd.pd.concat(greens_list, ignore_index=True), crs="EPSG:4326")
    print(f"Green polygons: OSM={0 if osm_greens is None else len(osm_greens)} | NDVI={len(ndvi_greens)} | merged={len(greens_all)}")

    # Project green polygons to graph CRS
    greens_poly_proj = greens_all.to_crs(graph_crs)

    # Destination nodes = nearest graph nodes to green centroids
    print("Computing destination nodes from green centroids…")
    greens_poly_proj["centroid"] = greens_poly_proj.geometry.centroid
    dest_nodes = set()
    for c in greens_poly_proj["centroid"]:
        try:
            nid = ox.distance.nearest_nodes(Gp, X=c.x, Y=c.y)
            dest_nodes.add(nid)
        except Exception:
            pass

    if not dest_nodes:
        raise SystemExit("No destination nodes mapped from green centroids. Check green layers / AOI.")

    # Edge travel times (seconds)
    print("Assigning time costs to edges…")
    for u, v, k, data in Gp.edges(keys=True, data=True):
        length_m = float(data.get("length", 0.0)) or 0.0
        data["time_s"] = length_m / WALK_MPS

    # Multi-source Dijkstra to nearest green (min time per node)
    print("Running multi-source shortest path (Dijkstra)…")
    Gr = Gp.reverse()  # reverse trick for multi-destination
    min_time_s = nx.multi_source_dijkstra_path_length(Gr, sources=list(dest_nodes), weight="time_s")

    def covered_by_threshold(u, v, threshold_s):
        tu = min_time_s.get(u, math.inf)
        tv = min_time_s.get(v, math.inf)
        return (tu <= threshold_s) or (tv <= threshold_s)

    def both_beyond_10(u, v):
        return (min_time_s.get(u, math.inf) > T10) and (min_time_s.get(v, math.inf) > T10)

    print("Classifying edges by coverage (5 and 10 minutes)…")
    edges_gdf["covered_5min"] = edges_gdf.apply(lambda r: covered_by_threshold(r["u"], r["v"], T5), axis=1)
    edges_gdf["covered_10min"] = edges_gdf.apply(lambda r: covered_by_threshold(r["u"], r["v"], T10), axis=1)
    edges_gdf["uncovered_10min"] = edges_gdf.apply(lambda r: both_beyond_10(r["u"], r["v"]), axis=1)
    uncovered = edges_gdf[edges_gdf["uncovered_10min"]].copy()
    print(f"Uncovered road segments beyond 10 minutes: {len(uncovered)}")

    # Isochrone polygons (from covered edges)
    print("Building isochrone polygons…")
    iso5_edges = edges_gdf[edges_gdf["covered_5min"]]
    iso10_edges = edges_gdf[edges_gdf["covered_10min"]]
    iso5_poly = make_iso_polygon(iso5_edges, buffer_m=EDGE_BUFFER_M)
    iso10_poly = make_iso_polygon(iso10_edges, buffer_m=EDGE_BUFFER_M)

    # Candidate micro-park points: midpoints of longest uncovered segments
    print("Selecting candidate micro-park points…")
    uncovered["length_m"] = uncovered.geometry.length
    candidates = uncovered.sort_values("length_m", ascending=False).head(TOP_N_CANDIDATES).copy()
    candidates["midpt"] = candidates.geometry.apply(line_midpoint)

    # -----------------------
    # Folium map (WGS84)
    # -----------------------
    print("Building Folium map…")
    aoi_latlon = aoi.to_crs(epsg=4326)
    center = [aoi_latlon.geometry.iloc[0].centroid.y, aoi_latlon.geometry.iloc[0].centroid.x]

    edges_latlon = edges_gdf.to_crs(epsg=4326)
    uncovered_latlon = uncovered.to_crs(epsg=4326)
    greens_latlon = greens_poly_proj.to_crs(epsg=4326)
    cand_latlon = gpd.GeoDataFrame(geometry=candidates["midpt"], crs=graph_crs).to_crs(epsg=4326)
    iso5_latlon = iso5_poly.to_crs(epsg=4326) if iso5_poly is not None else None
    iso10_latlon = iso10_poly.to_crs(epsg=4326) if iso10_poly is not None else None

    m = folium.Map(location=center, zoom_start=12, control_scale=True, tiles="cartodbpositron")

    # Green polygons (merged OSM + NDVI)
    folium.GeoJson(
        greens_latlon[["geometry"]],
        name=f"Green areas (OSM + NDVI≥{NDVI_GREEN_MIN:.2f})",
        style_function=lambda _: {"color": "#2e7d32", "weight": 1, "fillColor": "#66bb6a", "fillOpacity": 0.35},
    ).add_to(m)

    # 10-min isochrone
    if iso10_latlon is not None:
        folium.GeoJson(
            iso10_latlon.__geo_interface__,
            name="Within 10 min of green",
            style_function=lambda _: {"color": "#ff9800", "weight": 1, "fillColor": "#ffcc80", "fillOpacity": 0.25},
        ).add_to(m)

    # 5-min isochrone
    if iso5_latlon is not None:
        folium.GeoJson(
            iso5_latlon.__geo_interface__,
            name="Within 5 min of green",
            style_function=lambda _: {"color": "#1976d2", "weight": 1, "fillColor": "#90caf9", "fillOpacity": 0.25},
        ).add_to(m)

    # Uncovered segments (>10 min)
    folium.GeoJson(
        uncovered_latlon[["geometry"]],
        name="Road segments beyond 10 min (need green access)",
        style_function=lambda _: {"color": "#e53935", "weight": 2, "opacity": 0.9},
    ).add_to(m)

    # Candidate micro-park markers — DISTINCT COLOR (bright blue)
    for i, row in cand_latlon.iterrows():
        y, x = row.geometry.y, row.geometry.x
        folium.CircleMarker(
            location=(y, x),
            radius=6,
            color="#2962FF",
            fill=True,
            fill_color="#2962FF",
            fill_opacity=0.95,
            popup=f"Candidate site #{i+1}",
        ).add_to(m)

    # Simple legend
    legend_html = f"""
    <div style="position: fixed; bottom: 18px; left: 18px; z-index:9999; background: white;
                padding: 10px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px;">
      <b>Legend</b><br>
      <span style="display:inline-block;width:12px;height:12px;background:#66bb6a;border:1px solid #2e7d32;"></span>
      Green areas (OSM + NDVI≥{NDVI_GREEN_MIN:.2f})<br>
      <span style="display:inline-block;width:12px;height:12px;background:#ffcc80;border:1px solid #ff9800;"></span>
      ≤ 10 min walk<br>
      <span style="display:inline-block;width:12px;height:12px;background:#90caf9;border:1px solid #1976d2;"></span>
      ≤ 5 min walk<br>
      <span style="display:inline-block;width:18px;height:2px;background:#e53935;vertical-align:middle;display:inline-block;"></span>
      Uncovered roads (>10 min)<br>
      <span style="display:inline-block;width:12px;height:12px;background:#2962FF;border:1px solid #2962FF;"></span>
      Candidate micro-park
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl(collapsed=False).add_to(m)

    # Save map
    # out_cwd = "narayanganj_green_access_ndvi_osm.html"
    # m.save(out_cwd)
    # print(f"✅ Saved map in current folder: {out_cwd}")

    try:
        os.makedirs(DOWNLOADS, exist_ok=True)
        m.save(OUT_HTML)
        print(f"✅ Also saved to: {OUT_HTML}")
    except Exception as e:
        print("Could not save to ~/Downloads:", e)

    print("Done.")


if __name__ == "__main__":
    main()
