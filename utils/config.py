"""
Centralized access ke Streamlit secrets.
Semua konfigurasi diambil dari .streamlit/secrets.toml
"""
import streamlit as st


def get(section: str, key: str, default=None):
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError):
        return default


# GeoServer
GEOSERVER_USERNAME = lambda: get("geoserver", "username", "admin")
GEOSERVER_PASSWORD = lambda: get("geoserver", "password", "geoserver")
GEOSERVER_URL_REST = lambda: get("geoserver", "url_rest", "")
GEOSERVER_URL_APP  = lambda: get("geoserver", "url_app", "")

# ArcGIS
ARCGIS_URL_PORTAL  = lambda: get("arcgis", "url_portal", "")
ARCGIS_USERNAME    = lambda: get("arcgis", "username", "")
ARCGIS_PASSWORD    = lambda: get("arcgis", "password", "")
ARCGIS_URL_REST    = lambda: get("arcgis", "url_rest", "")

# DB GIS
DB_GIS_HOST     = lambda: get("db_gis", "host", "localhost")
DB_GIS_PORT     = lambda: get("db_gis", "port", "5432")
DB_GIS_USERNAME = lambda: get("db_gis", "username", "postgres")
DB_GIS_PASSWORD = lambda: get("db_gis", "password", "")
DB_GIS_DATABASE = lambda: get("db_gis", "database", "gis_db")

# GeoNetwork
GEONETWORK_URL      = lambda: get("geonetwork", "url", "")
GEONETWORK_USERNAME = lambda: get("geonetwork", "username", "admin")
GEONETWORK_PASSWORD = lambda: get("geonetwork", "password", "admin")

# Metabase
METABASE_URL_SATU_PETA = lambda: get("metabase", "url_satu_peta", "")
METABASE_URL_SCORING   = lambda: get(
    "metabase",
    "url_scoring",
    "https://metabase.ekosistemdata.id/api/public/card/1acbc4ea-1fb9-4840-8aa6-a3ed71725e78/query/json"
)

# Shapefile Jabar
SHP_PATH = lambda: get("shp", "shp_path", "")
