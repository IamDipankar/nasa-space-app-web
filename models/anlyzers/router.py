from . import aq_hotspots, geom_provider as gp
from . import green_access_ndvi, uhi_hotspots
from folium import GeoJson
from shapely.geometry import mapping
from ee import Geometry
import os, tempfile, base64
import dotenv
dotenv.load_dotenv()
import ee

def ee_init_headless():
    sa = os.environ["EE_SERVICE_ACCOUNT"]       # ee-runner@<project>.iam.gserviceaccount.com
    key_b64 = os.environ["EE_KEY_B64"]          # base64 of the JSON key

    # Write key to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(base64.b64decode(key_b64).decode("utf-8"))
        key_path = f.name

    creds = ee.ServiceAccountCredentials(sa, key_path)
    ee.Initialize(credentials=creds)

ee_init_headless()

dist = gp.get_district_data()
upz = gp.get_upazila_data()

UPAZILA_NAMES = {dist : [] for dist in dist.DISTRICT_N.unique()}
for _, row in upz.iterrows():
    UPAZILA_NAMES[row.DISTRICT_N].append(row.UPAZILA_NA)

def get_districts_list():
    """Get list of available districts"""
    return sorted(dist.DISTRICT_N.unique().tolist())

def get_upazilas_by_district(district_name: str):
    """Get list of upazilas for a specific district"""
    filtered_upz = upz[upz['DISTRICT_N'] == district_name]
    return sorted(filtered_upz['UPAZILA_NA'].unique().tolist())

def get_gdf(district_name: str, upazila_name: str = None):
    """Get GeoDataFrame for a specific district or upazila"""
    if upazila_name:
        filtered_upz = upz[(upz['UPAZILA_NA'] == upazila_name) & (upz['DISTRICT_N'] == district_name)]
        if filtered_upz.empty:
            raise ValueError(f"Could not find upazila '{upazila_name}' in district '{district_name}'")
        return filtered_upz
    else:
        filtered_dist = dist[dist['DISTRICT_N'] == district_name]
        if filtered_dist.empty:
            raise ValueError(f"Could not find district '{district_name}'")
        return filtered_dist

def get_polygon_and_bbox(district_name: str, upazila_name: str = None):
    functions = {
        "aq_hotspots": aq_hotspots.run,
        "green_access": green_access_ndvi.run,
        "uhi_hotspots": uhi_hotspots.run,
    }

    try:
        if upazila_name:
            # Filter by both district and upazila name
            filtered_upz = upz[(upz['UPAZILA_NA'] == upazila_name) & (upz['DISTRICT_N'] == district_name)]
            if filtered_upz.empty:
                raise ValueError(f"Could not find upazila '{upazila_name}' in district '{district_name}'")
            polygon = filtered_upz.geometry.iloc[0]
            aoi_bbox = list(filtered_upz.bounds.iloc[0])
        else:
            # Filter by district name only
            filtered_dist = dist[dist['DISTRICT_N'] == district_name]
            if filtered_dist.empty:
                raise ValueError(f"Could not find district '{district_name}'")
            polygon = filtered_dist.geometry.iloc[0]
            aoi_bbox = list(filtered_dist.bounds.iloc[0])
            
        if polygon is None:
            raise ValueError(f"Could not find geometry for district '{district_name}' and upazila '{upazila_name}'")
    except Exception as e:
        raise ValueError(f"Error retrieving geometry for district '{district_name}' and upazila '{upazila_name}': {e}")
    ee_geometry = Geometry(mapping(polygon))
    return ee_geometry, aoi_bbox