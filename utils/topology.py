"""
Topology & scoring utilities — logika PERSIS dari streamlit_old.
Hanya refactor, tidak ada perubahan rumus/logika.
"""
import re
import json
import time
import logging
import requests
import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from shapely.geometry import Point, shape
from shapely.validation import explain_validity

from utils.config import (
    GEOSERVER_USERNAME, GEOSERVER_PASSWORD,
    GEOSERVER_URL_APP   as GEOSERVER_APP_URL,
    GEOSERVER_URL_REST  as GEOSERVER_REST_URL,
    ARCGIS_URL_PORTAL   as ARCGIS_PORTAL_URL,
    ARCGIS_USERNAME,
    ARCGIS_PASSWORD,
    ARCGIS_URL_REST     as ARCGIS_REST_URL,
    METABASE_URL_SATU_PETA as METABASE_SATU_PETA_URL,
    DB_GIS_HOST     as DB_HOST,
    DB_GIS_PORT     as DB_PORT,
    DB_GIS_USERNAME as DB_USERNAME,
    DB_GIS_PASSWORD as DB_PASSWORD,
    DB_GIS_DATABASE as DB_NAME,
    SHP_PATH
)

# Re-export metadata functions from metadata_geonetwork
from utils.metadata_geonetwork import (
    get_scoring_metadata,
    get_metadata_compliance_code,
    get_metadata_included_with_dataset,
)

# list_metadata_geonetwork — alias untuk kompatibilitas
def list_metadata_geonetwork():
    """Tidak dipakai di versi baru, return empty list."""
    return []

# ─── TIMELINESS ───────────────────────────────────────────────────────────────
# Persis dari old code (topology_check.py nilai_timeliness list)
TIMELINESS_OPTIONS = [
    ('',                                              None),
    ('≤ 1 tahun : Nilai 10',                         100),
    ('> 1 tahun : Nilai 9',                           90),
    ('> 2 tahun : Nilai 8',                           80),
    ('> 3 tahun : Nilai 7',                           70),
    ('> 4 tahun : Nilai 6',                           60),
    ('> 5 tahun : Nilai 5',                           50),
    ('> 6 tahun : Nilai 4',                           40),
    ('> 7 tahun : Nilai 3',                           30),
    ('> 8 tahun : Nilai 2',                           20),
    ('> 9 tahun : Nilai 1',                           10),
    ('> 10 tahun : Nilai 0',                           0),
    ('Data tertentu (update terakhir) : Nilai 10',   100),
    ('Data tertentu (bukan update terakhir) : Nilai 0', 0),
]


def timeliness_score(label: str) -> int:
    """Konversi label timeliness → nilai numerik. Persis dari old if-elif chain."""
    for lbl, val in TIMELINESS_OPTIONS:
        if label == lbl:
            return val
    return 0


# ─── SATU PETA ────────────────────────────────────────────────────────────────

def _wms_to_wfs_url(wms_url: str) -> str:
    """Konversi WMS URL mapsetservice_url ke WFS GetFeature URL."""
    from urllib.parse import urlparse, parse_qs, unquote
    try:
        parsed = urlparse(wms_url)
        qs     = parse_qs(parsed.query)
        layer  = unquote(qs.get("layers", qs.get("LAYERS", [""]))[0])
        if not layer:
            return ""
        ows_path = parsed.path.replace("/wms", "/ows").replace("/WMS", "/ows")
        base     = f"{parsed.scheme}://{parsed.netloc}"
        return (f"{base}{ows_path}?service=WFS&version=1.0.0"
                f"&request=GetFeature&typeName={layer}"
                f"&outputFormat=application%2Fjson")
    except Exception:
        return ""


@st.cache_data(ttl=300, show_spinner=False)
def get_mapset_satu_peta() -> list:
    """
    Ambil daftar mapset dari Metabase API.
    Persis dari v1 yang berfungsi — filter, field, dan error handling.
    """
    url = METABASE_SATU_PETA_URL()
    if not url:
        return []
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        items = r.json()
        result = []
        for item in items:
            if not (
                str(item.get("validate", "")).strip() == "approve"
                and str(item.get("is_active", "")).strip() == "true"
                and str(item.get("is_deleted", "")).strip() == "false"
                and str(item.get("klasifikasi", "")).strip() == "public"
            ):
                continue
            wms_url = str(item.get("mapsetservice_url", "")).strip()
            description = (
                str(item.get("description", ""))
                .replace("<p>", "").replace("</p>", "")
                .replace("&nbsp;", " ").replace("<br>", "").strip()
            )
            result.append({
                "name":              str(item.get("name", "")).strip(),
                "owner":             str(item.get("owner", "")).strip(),
                "mapset_type_id":    str(item.get("mapset_type_id", "")).strip(),
                "mapset_source_id":  str(item.get("mapset_source_id", "")).strip(),
                "mapsetservice_url": wms_url,
                "wfs_url":           _wms_to_wfs_url(wms_url),
                "metadata_xml":      str(item.get("metadata_xml", "")).strip(),
                "description":       description,
            })
        return sorted(result, key=lambda x: x["name"])
    except Exception as e:
        st.error(f"❌ Gagal ambil data Satu Peta: {e}")
        return []


# ─── GEOSERVER ────────────────────────────────────────────────────────────────

def list_service_geoserver() -> list:
    """Persis dari old list_service(). Return [] tanpa error jika 403/tidak bisa diakses."""
    headers = {'Content-Type': 'application/json'}
    auth    = (GEOSERVER_USERNAME(), GEOSERVER_PASSWORD())
    url     = f"{GEOSERVER_REST_URL()}/layers.json"
    try:
        r = requests.get(url=url, headers=headers, auth=auth, verify=False, timeout=15)
        if r.status_code == 403:
            # Akses REST API diblokir — tidak tampilkan error, return kosong
            return []
        if r.status_code != 200:
            st.warning(f"⚠️ GeoServer tidak dapat diakses (HTTP {r.status_code}). Gunakan WFS URL langsung.")
            return []
        layer = r.json().get("layers", {}).get("layer", [])
        layers_name = []
        for lyr in layer:
            layer_name = lyr.get("name", "")
            workspace, _ = layer_name.split(":", 1)
            link_geojson = (
                f"{GEOSERVER_APP_URL()}/{workspace}/ows"
                f"?service=WFS&version=1.0.0&request=GetFeature"
                f"&typeName={layer_name}&outputFormat=application%2Fjson"
            )
            layers_name.append((layer_name, link_geojson))
        layers_name.sort(key=lambda x: x[0])
        return layers_name
    except Exception as e:
        st.warning(f"⚠️ Tidak dapat terhubung ke GeoServer: {e}")
        return []


def get_data_geoserver(url: str):
    """Persis dari old get_data()."""
    try:
        response = requests.get(url, auth=(GEOSERVER_USERNAME(), GEOSERVER_PASSWORD()))
        gdf = gpd.read_file(response.text)
        return gdf.to_crs(4326)
    except Exception as e:
        st.error(f"❌ Gagal mengambil data GeoServer: {e}")
        return None


def get_name_service_geoserver(url: str) -> str:
    """Persis dari old get_name_service() untuk GeoServer."""
    match = re.search(r"typeName=[^:]*:([^&]+)", url)
    return match.group(1) if match else None


# ─── ARCGIS ───────────────────────────────────────────────────────────────────

def _get_token_arcgis():
    """Persis dari old get_token_arcgis()."""
    try:
        url = f"{ARCGIS_PORTAL_URL()}/sharing/rest/generateToken"
        payload = (
            f'f=json&username={ARCGIS_USERNAME()}'
            f'&password={ARCGIS_PASSWORD()}&client=referer'
            f'&referer=https%3A%2F%2Farcgis.jabarprov.go.id%2Farcgis%2Fadmin'
            f'&expiration=60'
        )
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        retry_attempts = 5
        retry_delay    = 10
        while retry_attempts > 0:
            try:
                response = requests.post(url, headers=headers, data=payload)
                response.raise_for_status()
                token = response.json().get("token")
                if token is None:
                    raise Exception("Failed to retrieve access token")
                return token
            except requests.RequestException as e:
                retry_attempts -= 1
                if retry_attempts > 0:
                    time.sleep(retry_delay)
                else:
                    return None
    except Exception as e:
        st.error(f"❌ ArcGIS token error: {e}")
        return None


def _arcgis_headers():
    return {
        'Authorization': f'Bearer {_get_token_arcgis()}',
        'Content-Type':  'application/x-www-form-urlencoded',
        'User-Agent':    'Mozilla/5.0',
    }


def _clean_geometry(geometry: dict) -> dict:
    """Persis dari old clean_geometry()."""
    try:
        if geometry['type'] == 'Polygon':
            cleaned = []
            for ring in geometry['coordinates']:
                cleaned_ring = [(x[0], x[1]) for x in ring if x is not None and len(x) >= 2]
                if cleaned_ring:
                    cleaned.append(cleaned_ring)
            return {'type': 'Polygon', 'coordinates': cleaned}
        elif geometry['type'] == 'MultiPolygon':
            cleaned_mp = []
            for polygon in geometry['coordinates']:
                cleaned_p = []
                for ring in polygon:
                    cleaned_ring = [(x[0], x[1]) for x in ring if x is not None and len(x) >= 2]
                    if cleaned_ring:
                        cleaned_p.append(cleaned_ring)
                if cleaned_p:
                    cleaned_mp.append(cleaned_p)
            return {'type': 'MultiPolygon', 'coordinates': cleaned_mp}
        return geometry
    except Exception as e:
        st.error(f"❌ clean_geometry: {e}")
        return geometry


def folder_arcgis() -> list:
    """Persis dari old folder_arcgis()."""
    try:
        url = f"{ARCGIS_REST_URL()}?f=pjson"
        folder = requests.get(url, timeout=5, headers=_arcgis_headers()).json()['folders']
        return [f for f in folder if f not in ('Hosted', 'PrintingTools', 'raster', 'Utilities')]
    except Exception as e:
        st.error(f"❌ {e}")
        return []


def sub_folder_arcgis(folder: str) -> list:
    """Persis dari old sub_folder_arcgis()."""
    try:
        url = f"{ARCGIS_REST_URL()}/{folder}?f=pjson"
        services = requests.get(url, timeout=5, headers=_arcgis_headers()).json()['services']
        result = [s.get("name", "") + '/' + s.get("type", "") for s in services]
        result.sort()
        return result
    except Exception as e:
        st.error(f"❌ {e}")
        return []


def service_arcgis(mapservice: str) -> list:
    """Persis dari old service_arcgis()."""
    try:
        url = f"{ARCGIS_REST_URL()}/{mapservice}?f=pjson"
        services = requests.get(url, timeout=5, headers=_arcgis_headers()).json()['layers']
        result = []
        for s in services:
            sid  = s.get("id")
            name = s.get("name", "") + f" ({sid})"
            link = f"{ARCGIS_REST_URL()}/{mapservice}/{sid}"
            result.append((name, link))
        result.sort()
        return result
    except Exception as e:
        st.error(f"❌ {e}")
        return []


def get_columns_arcgis(url: str) -> list:
    """Persis dari old get_column_arcgis()."""
    try:
        fields = requests.get(f"{url}?f=pjson", timeout=5,
                              headers=_arcgis_headers()).json()['fields']
        return [f['name'] for f in fields]
    except Exception as e:
        st.error(f"❌ {e}")
        return []


def get_data_arcgis(url_service: str):
    """Persis dari old get_data_arcgis()."""
    try:
        headers = _arcgis_headers()
        query_url = url_service + '/query'
        total_rows = requests.get(
            query_url, {'where': '1=1', 'returnCountOnly': True, 'f': 'json'},
            timeout=5, headers=headers
        ).json()['count']

        data = []
        result_offset = 0
        while True:
            req  = requests.get(query_url, {
                'where': '1=1', 'units': 'esriSRUnit_Meter',
                'outFields': '*', 'resultOffset': result_offset, 'f': 'geojson'
            }, headers=headers)
            resp = req.json()
            for feature in resp.get('features', []):
                props    = feature['properties']
                geometry = feature.get('geometry')
                cleaned  = _clean_geometry(geometry)
                props.update(geometry=shape(cleaned))
                data.append(props)

            curr_total = len(data)
            st.text(f"Progress: {100*curr_total/total_rows:.0f}% | "
                    f"Total: {total_rows:,} | Loaded: {curr_total:,}")
            if not resp.get('exceededTransferLimit', False):
                break
            result_offset += len(resp.get('features', []))

        if data:
            return gpd.GeoDataFrame(data, crs='EPSG:4326')
        st.error("❌ Data kosong.")
        return None
    except Exception as e:
        st.error(f"❌ ArcGIS data error: {e}")
        return None


# ─── TOPOLOGY CHECKS ──────────────────────────────────────────────────────────

def _parse_validity_reason(reason: str):
    """Persis dari old parse_validity_reason()."""
    try:
        match = re.match(r"(.+?)\[(.+)\]", reason)
        if match:
            return match.group(1), match.group(2)
        return reason, None
    except Exception as e:
        st.error(f"❌ {e}")
        return reason, None


def check_duplicate_geometries(gdf, selected_columns: list):
    """Persis dari old check_duplicate_geometries()."""
    try:
        gdf = gdf.copy()
        gdf['all_attributes'] = gdf[selected_columns].apply(
            lambda row: '_'.join(map(str, row)), axis=1)
        gdf['is_duplicate'] = gdf.duplicated(subset='all_attributes', keep=False)
        duplicates = gdf[gdf['is_duplicate']].copy()
        duplicates['duplicate_pair'] = duplicates.groupby('all_attributes').ngroup()
        duplicates = duplicates.drop(columns=['all_attributes'])
        return duplicates
    except Exception as e:
        st.error(f"❌ check_duplicate_geometries: {e}")
        return pd.DataFrame()


def topology_check_gdf(gdf):
    """Persis dari old topology_check()."""
    try:
        gdf = gdf.copy()
        gdf['is_valid'] = gdf.is_valid
        gdf['validity_reason'], gdf['invalid_coords'] = zip(*gdf.apply(
            lambda row: _parse_validity_reason(explain_validity(row.geometry))
            if not row['is_valid'] else (None, None), axis=1
        ))
        return gdf[~gdf['is_valid']]
    except Exception as e:
        st.error(f"❌ topology_check: {e}")
        return pd.DataFrame()


def check_column_names(gdf) -> list:
    """Persis dari old check_column_names()."""
    try:
        exclude_columns = ['geometry', 'id', 'fid', 'gid', 'Shape_Length', 'Shape_Area']
        return [col for col in gdf.columns
                if col not in exclude_columns and not col.isupper()]
    except Exception as e:
        st.error(f"❌ check_column_names: {e}")
        return []


def check_completeness_commission(gdf):
    """
    Persis dari old check_completeness_commission().
    Commission = geometry NULL (ada baris tapi geometry-nya kosong).
    """
    return gdf[gdf['geometry'].isna()]


def check_completeness_omission(gdf):
    """
    Persis dari old check_completeness_omission().
    Omission = geometry ada tapi kosong (Point.is_empty).
    """
    return gdf[gdf['geometry'].apply(
        lambda geom: isinstance(geom, Point) and geom.is_empty
    )]


def load_jabar_boundary():
    # """Load batas administrasi Jawa Barat dari PostGIS."""
    # try:
    #     from sqlalchemy import create_engine
    #     conn_url = (f"postgresql+psycopg2://{DB_USERNAME()}:{DB_PASSWORD()}"
    #                 f"@{DB_HOST()}:{DB_PORT()}/{DB_NAME()}")
    #     engine = create_engine(conn_url)
    #     query  = ("SELECT * FROM batas_administrasi_big_september_2023"
    #               ".administrasi_ar_10k_provinsi_jabar_2023")
    #     return gpd.read_postgis(query, engine, geom_col='geom')
    # except Exception as e:
    #     st.error(f"❌ Gagal load batas Jawa Barat: {e}")
    #     return None
    """Load batas administrasi Jawa Barat dari Shapefile lokal."""
    try:
        # Membaca file shapefile (.shp) menggunakan geopandas
        return gpd.read_file(SHP_PATH())
    except Exception as e:
        st.error(f"❌ Gagal load batas Jawa Barat: {e}")
        return None


def check_points_outside_jabar(points_gdf, jabar_boundary):
    """Persis dari old check_points_outside_jabar()."""
    try:
        points_gdf = points_gdf.to_crs(jabar_boundary.crs)
        points_in  = gpd.sjoin(points_gdf, jabar_boundary, how='inner', predicate='within')
        return points_gdf[~points_gdf.index.isin(points_in.index)]
    except Exception as e:
        st.error(f"❌ check_points_outside_jabar: {e}")
        return pd.DataFrame()


def download_geojson(data, file_name: str):
    st.download_button(
        label="💾 Download GeoJSON",
        data=data.to_json(),
        file_name=file_name,
        mime="application/json"
    )


def display_map(data):
    import folium
    m = folium.Map(location=[-6.914744, 107.609810], zoom_start=8)
    exclude_cols = ["geometry", "all_attributes"]
    fields = [col for col in data.columns if col not in exclude_cols]
    folium.GeoJson(
        json.loads(data.to_json()),
        name="geojson",
        tooltip=folium.GeoJsonTooltip(fields=fields),
        popup=folium.GeoJsonPopup(fields=fields),
    ).add_to(m)
    st.components.v1.html(m._repr_html_(), height=600)


def display_duplicates(check_duplicate):
    """Persis dari old display_duplicates()."""
    df = pd.DataFrame(check_duplicate).sort_values(by='duplicate_pair')
    df = df.drop(columns=['geometry'], errors='ignore')
    num_colors = df['duplicate_pair'].nunique()
    colors     = plt.cm.get_cmap('tab20', num_colors)
    color_map  = {i: colors(i / num_colors) for i in range(num_colors)}

    def color_rows(row):
        color     = color_map[row['duplicate_pair']]
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(color[0]*255), int(color[1]*255), int(color[2]*255))
        return [f'background-color: {hex_color}' for _ in row]

    st.dataframe(df.style.apply(color_rows, axis=1), use_container_width=True)


# ─── RUN WRAPPERS ─────────────────────────────────────────────────────────────

def run_check_column_names(gdf):
    """Wrapper: cek nama kolom huruf kapital. Return (hasil_str, nilai)."""
    invalid = check_column_names(gdf)
    if invalid:
        st.warning(f"⚠️ Ada nama kolom belum menggunakan huruf kapital: {', '.join(invalid)}")
        return (f"Ada Kolom yang Belum Menggunakan Huruf Kapital. "
                f"Kolom tersebut adalah {', '.join(invalid)}"), 0
    st.success("✅ Semua nama kolom menggunakan huruf kapital.")
    return "Tidak Ada/Semua Kolom Menggunakan Huruf Kapital", 100


def run_check_commission(gdf):
    """
    Wrapper: cek Completeness Commission.
    OLD: commission = geometry NULL (geometry.isna()).
    """
    result = check_completeness_commission(gdf)
    if not result.empty:
        st.warning("⚠️ Completeness Commission detected.")
        safe = result.drop(columns=['geometry'], errors='ignore')
        st.dataframe(safe, use_container_width=True)
        return "Geometri ada, namun ada atribut NULL", 0
    st.success("✅ No Completeness Commission detected.")
    return "Tidak terdapat commisson", 100


def run_check_omission(gdf):
    """
    Wrapper: cek Completeness Omission.
    OLD: omission = geometry Point yang is_empty.
    """
    result = check_completeness_omission(gdf)
    if not result.empty:
        st.warning("⚠️ Completeness Omission detected.")
        safe = result.drop(columns=['geometry'], errors='ignore')
        st.dataframe(safe, use_container_width=True)
        return "Atribut ada, namun ada geometry NULL", 0
    st.success("✅ No Completeness Omission detected.")
    return "Tidak terdapat ommission", 100


def run_check_duplicates(gdf, url: str, selected_cols: list, engine: str):
    """
    Persis dari old check_and_display_duplicates().
    Return (hasil_str, nilai).
    """
    st.info("🔄 Processing Check Duplicate Geometry...")
    dups = check_duplicate_geometries(gdf, selected_cols)
    if not dups.empty:
        st.warning(f"⚠️ Ada geometri yang duplikat:")
        display_duplicates(dups)
        download_geojson(dups, f"duplicate_geometries.geojson")
        display_map(dups)
        return "Ada Data Duplikat", 0
    st.success("✅ Tidak Ada Data Duplikat.")
    return "Tidak Ada Data Duplikat", 100


def run_check_topology(gdf, url: str, engine: str):
    """
    Persis dari old check_and_display_topology().
    Untuk Polyline/Polygon. Return (hasil_str, nilai).
    """
    st.info("🔄 Processing Topology Check...")
    invalid = topology_check_gdf(gdf)
    if not invalid.empty:
        st.warning("⚠️ Ada geometri yang tidak valid:")
        invalid_points = invalid.dropna(subset=['invalid_coords'])
        if not invalid_points.empty:
            points_gdf = gpd.GeoDataFrame(
                invalid_points,
                geometry=invalid_points['invalid_coords'].apply(
                    lambda coords: Point(map(float, coords.split()))
                )
            ).to_crs(epsg=4326)
            include_cols = [col for col in points_gdf.columns
                            if col not in ['geometry', 'all_attributes']]
            st.table(pd.DataFrame(points_gdf)[include_cols])
            download_geojson(points_gdf[include_cols + ['geometry']],
                             "invalid_geometry.geojson")
            display_map(points_gdf)
        return "Topology Cek Tidak Lolos", 0
    st.success("✅ Semua geometri valid.")
    return "Topology Cek Lolos", 100


def run_check_point_in_jabar(gdf, url: str, engine: str):
    """
    Persis dari old process_point_data().
    Untuk Point. Return (hasil_str, nilai).
    """
    jabar_boundary = load_jabar_boundary()
    if jabar_boundary is None:
        return "Gagal load batas Jawa Barat", 0
    outside = check_points_outside_jabar(gdf, jabar_boundary)
    if not outside.empty:
        st.warning("⚠️ Some points are outside Jawa Barat boundary.")
        df = outside.drop(columns=['geometry'])
        st.dataframe(df)
        download_geojson(outside, "points_outside_jabar.geojson")
        display_map(outside)
        return "Ada Point diluar Jawa Barat", 0
    st.success("✅ All points are within Jawa Barat boundary.")
    return "Tidak Ada Point diluar Jawa Barat", 100


# ─── KUGI ─────────────────────────────────────────────────────────────────────

def get_data_api_kugi(url_kugi: str) -> list:
    """Persis dari old get_data_api_kugi()."""
    response_api = requests.get(url_kugi)
    if response_api.status_code == 200:
        api_data = response_api.json()
        list_kolom = [item.get("ptMemberName") for item in api_data]
        return list(set(list_kolom))
    return []


def cek_kugi(data, url_kugi: str):
    """
    Persis dari old cek_kugi().
    Return persentase float (bukan string).
    """
    list_kolom_kugi = get_data_api_kugi(url_kugi=url_kugi)
    gdf = data
    kolom_gdf = [col for col in gdf.columns if col != 'geometry']
    matching_columns = [col for col in kolom_gdf if col in list_kolom_kugi]
    empty_columns = [col for col in matching_columns
                     if col in gdf.columns and gdf[col].isna().all()]
    if empty_columns:
        persentase_kugi = round(
            100 - ((len(empty_columns) / len(list_kolom_kugi)) * 100), 2)
    else:
        persentase_kugi = round(
            (len(matching_columns) / len(list_kolom_kugi)) * 100, 2)
    return persentase_kugi


def run_kugi_check(gdf, compliance_code, included_with_dataset, url_kugi: str):
    """
    Persis dari old KUGI check logic di topology_check.py:

        nilai_a = 0, nilai_b = 0
        if a is None or a == 'false':
            hasil_kugi = "KUGI Tidak di Cek"
            nilai_a = 100
        elif a == 'true':
            if b is None or b == 'false':
                hasil_kugi = 0
                nilai_b = 0
            else:
                hasil_kugi = cek_kugi(...)
                nilai_a = 100
                nilai_b = 100

    Return: (hasil_kugi, nilai_a, nilai_b)
    """
    a = compliance_code
    b = included_with_dataset

    nilai_a = 0
    nilai_b = 0

    if a is None or str(a).lower() == 'false':
        hasil_kugi = "KUGI Tidak di Cek"
        nilai_a    = 100
    elif str(a).lower() == 'true':
        if b is None or str(b).lower() == 'false':
            hasil_kugi = 0
            nilai_b    = 0
        else:
            hasil_kugi = cek_kugi(data=gdf, url_kugi=url_kugi)
            nilai_a    = 100
            nilai_b    = 100
    else:
        hasil_kugi = "KUGI Tidak di Cek"
        nilai_a    = 100

    return hasil_kugi, nilai_a, nilai_b


# ─── SKOR AKHIR ───────────────────────────────────────────────────────────────

def calculate_final_score(
    nilai_a, nilai_b, nilai_nama_tabel,
    nilai_duplikat, nilai_topologi, nilai_upper_kolom,
    nilai_timeliness, hasil_kugi, persen_metadata,
    nilai_commission, nilai_omission,
    compliance_code_val
) -> float:
    """
    Persis dari old skor_akhir calculation:

    if a is None OR a == 'false':
        skor = (nilai_a + nilai_nama_tabel + nilai_duplikat + nilai_topologi
                + nilai_upper_kolom + nilai_timeliness
                + float(persen_metadata.strip('%'))
                + nilai_commission + nilai_omission) / 9

    elif a == 'true':
        skor = (nilai_a + nilai_b + nilai_nama_tabel + nilai_duplikat
                + nilai_topologi + nilai_upper_kolom + nilai_timeliness
                + hasil_kugi + float(persen_metadata.strip('%'))
                + nilai_commission + nilai_omission) / 11
    """
    a = compliance_code_val

    # Normalisasi persen_metadata ke float
    if isinstance(persen_metadata, str):
        try:
            meta_float = float(persen_metadata.strip('%'))
        except ValueError:
            meta_float = 0.0
    else:
        meta_float = float(persen_metadata or 0)

    # hasil_kugi bisa float (dari cek_kugi) atau string "KUGI Tidak di Cek"
    if isinstance(hasil_kugi, str):
        kugi_float = 0.0
    else:
        kugi_float = float(hasil_kugi)

    if a is None or str(a).lower() == 'false':
        skor = (
            nilai_a + nilai_nama_tabel + nilai_duplikat +
            nilai_topologi + nilai_upper_kolom + nilai_timeliness +
            meta_float + nilai_commission + nilai_omission
        ) / 9
    elif str(a).lower() == 'true':
        skor = (
            nilai_a + nilai_b + nilai_nama_tabel + nilai_duplikat +
            nilai_topologi + nilai_upper_kolom + nilai_timeliness +
            kugi_float + meta_float + nilai_commission + nilai_omission
        ) / 11
    else:
        # fallback: sama seperti false
        skor = (
            nilai_a + nilai_nama_tabel + nilai_duplikat +
            nilai_topologi + nilai_upper_kolom + nilai_timeliness +
            meta_float + nilai_commission + nilai_omission
        ) / 9

    return round(skor, 2)


def score_to_status(skor: float) -> tuple:
    """
    Persis dari old:
        if skor_akhir < 60:    status = "Perlu Diperbaiki"
        elif skor_akhir <= 75: status = "Cukup"
        elif skor_akhir <= 90: status = "Baik"
        elif skor_akhir > 90:  status = "Sangat Baik"
    """
    if skor < 60:
        return "Perlu Diperbaiki", "🔴"
    elif skor <= 75:
        return "Cukup", "🟡"
    elif skor <= 90:
        return "Baik", "🟢"
    else:
        return "Sangat Baik", "🌟"