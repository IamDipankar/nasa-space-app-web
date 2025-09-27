import geopandas as gpd
import folium

# -----------------------------
# 1) Load upazila polygons
# -----------------------------
shapefile_path = "Area boundary/Nasa-Area-Boundary/BD_Upazila_BBS21.shp"
gdf = gpd.read_file(shapefile_path)

# Ensure WGS84 (lat/lon) for web maps
if gdf.crs is None:
    # If you know the original CRS, set it here instead of assuming WGS84.
    # Example if it's already lon/lat WGS84:
    gdf = gdf.set_crs(epsg=4326)
else:
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

# -----------------------------
# 2) Build district boundaries
# -----------------------------
# Dissolve upazilas by district name to get district polygons
def get_district_data():
    dist = gdf[['DISTRICT_N', 'geometry']].dissolve(by='DISTRICT_N', as_index=False)
    dist = dist.sort_values('DISTRICT_N').reset_index(drop=True)

    # -----------------------------
    # 3) Print compact preview
    # -----------------------------
    # geometry type + bounding box for a quick “print the district boundary” view
    preview = dist.copy()
    preview["geom_type"] = preview.geometry.geom_type

    b = preview.geometry.bounds  # This is a DataFrame with columns: minx, miny, maxx, maxy
    preview["bounds"] = list(zip(b["minx"], b["miny"], b["maxx"], b["maxy"]))

    return preview

def get_upazila_data():
    upz = gdf[['UPAZILA_NA', 'DISTRICT_N', 'geometry']].sort_values(['DISTRICT_N', 'UPAZILA_NA']).reset_index(drop=True)
    preview = upz.copy()
    preview["geom_type"] = preview.geometry.geom_type

    b = preview.geometry.bounds  # This is a DataFrame with columns: minx, miny, maxx, maxy
    preview["bounds"] = list(zip(b["minx"], b["miny"], b["maxx"], b["maxy"]))

    return preview

# print(preview[['DISTRICT_N', 'geom_type', 'bounds']].head(10))


# # -----------------------------
# # 4) Extract Dhaka district
# # -----------------------------
# target_name = "Dhaka"
# nar = dist[dist["DISTRICT_N"].str.casefold() == target_name.casefold()]

# if nar.empty:
#     # Helpful hint if the name doesn't match exactly
#     available = ", ".join(dist["DISTRICT_N"].head(10).tolist()) + ("..." if len(dist) > 10 else "")
#     raise ValueError(
#         f"District '{target_name}' not found in DISTRICT_N. "
#         f"Example names in your data: {available}"
#     )

# # Use centroid for initial map centering
# centroid = nar.geometry.centroid.iloc[0]  # OK for centering even in geographic CRS
# center_latlon = [centroid.y, centroid.x]

# # -----------------------------
# # 5) Build Folium map
# # -----------------------------
# m = folium.Map(location=center_latlon, zoom_start=9, tiles="cartodbpositron")

# # Layer: all districts (thin outline, no fill)
# folium.GeoJson(
#     dist.__geo_interface__,
#     name="All District Boundaries",
#     style_function=lambda feat: {"color": "#555555", "weight": 1, "fill": False},
#     tooltip=folium.GeoJsonTooltip(fields=["DISTRICT_N"], aliases=["District"])
# ).add_to(m)

# # Layer: Narayanganj (thicker red outline + light fill)
# folium.GeoJson(
#     nar.__geo_interface__,
#     name="Dhaka",
#     style_function=lambda feat: {
#         "color": "#d73027",
#         "weight": 3,
#         "fill": True,
#         "fillOpacity": 0.25
#     },
#     tooltip=folium.GeoJsonTooltip(fields=["DISTRICT_N"], aliases=["District"])
# ).add_to(m)

# # Marker at Narayanganj centroid
# folium.Marker(
#     location=center_latlon,
#     popup=f"{target_name} District",
#     icon=folium.Icon(color="red", icon="info-sign")
# ).add_to(m)

# # Fit view to Narayanganj bounds (nice tight framing)
# minx, miny, maxx, maxy = nar.total_bounds
# m.fit_bounds([[miny, minx], [maxy, maxx]])

# folium.LayerControl(collapsed=False).add_to(m)

# # -----------------------------
# # 6) Save map
# # -----------------------------
# out_html = "bangladesh_districts_narayanganj.html"
# m.save(out_html)
# print(f"Map saved to: {out_html}")