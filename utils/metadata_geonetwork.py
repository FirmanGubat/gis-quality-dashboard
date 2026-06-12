"""
Metadata GeoNetwork scoring — persis dari function_metadata_geonetwork.py (streamlit_old).
Mengambil dan menghitung keterisian ~100 field mandatory metadata geospasial dari XML GeoNetwork.

Menangani semua kasus error response:
- Response kosong (empty string)
- Response JSON (bukan XML)
- Response HTML (error page)
- BOM / karakter non-XML di awal
- UUID-only (bukan full URL) di field metadata_xml
- Response membutuhkan session/auth GeoNetwork
"""
import re
import streamlit as st
import pandas as pd
import requests
import xmltodict

from utils.config import (
    GEONETWORK_URL,
    GEONETWORK_USERNAME,
    GEONETWORK_PASSWORD,
)


# ─── XML FETCH dengan robust error handling ───────────────────────────────────

def _clean_xml_text(text: str) -> str:
    """
    Bersihkan teks agar bisa di-parse sebagai XML:
    - Strip BOM (EF BB BF)
    - Strip whitespace/newline sebelum <?xml
    - Strip karakter non-printable di awal
    """
    if not text:
        return ""
    # Strip BOM bytes jika ada
    text = text.lstrip('\ufeff\ufffe\u0000')
    # Cari posisi <?xml atau <gmd: (root element metadata)
    for marker in ['<?xml', '<gmd:MD_Metadata', '<MD_Metadata']:
        idx = text.find(marker)
        if idx > 0:
            text = text[idx:]
            break
    return text.strip()


def _is_xml_content(text: str) -> bool:
    """Cek apakah teks adalah XML (bukan JSON/HTML/empty)."""
    clean = _clean_xml_text(text)
    if not clean:
        return False
    return clean.startswith('<')


def _build_geonetwork_url(metadata_xml_field: str) -> str:
    """
    Konversi field metadata_xml menjadi URL XML GeoNetwork yang valid.
    Field bisa berupa:
    1. UUID saja: "abc-123-def"
    2. Full URL: "https://geonetwork.../records/uuid/formatters/xml..."
    3. URL GeoNetwork tanpa path lengkap
    """
    val = str(metadata_xml_field).strip()
    if not val or val in ('None', 'nan', ''):
        return ""

    # Sudah berupa full URL
    if val.startswith('http'):
        # Pastikan mengarah ke XML formatter
        if '/formatters/xml' not in val:
            # Coba tambahkan formatter XML
            if '/records/' in val:
                uuid = val.split('/records/')[-1].split('/')[0].split('?')[0]
                base = GEONETWORK_URL()
                if base:
                    return f"{base}/srv/api/records/{uuid}/formatters/xml?approved=true"
        return val

    # UUID saja — bangun URL dari GEONETWORK_URL di config
    base = GEONETWORK_URL()
    if base and val:
        # Bersihkan UUID dari karakter ekstra
        uuid = val.split('?')[0].strip()
        return f"{base}/srv/api/records/{uuid}/formatters/xml?approved=true"

    return ""


def _fetch_xml_with_session(url: str) -> tuple:
    """
    Fetch XML metadata dari GeoNetwork.
    Mencoba: 
      1. Request langsung (no auth)
      2. Request dengan basic auth
      3. Request dengan session (XSRF token) seperti di kode lama
    
    Return: (data_dict, None) atau (None, error_message)
    """
    if not url:
        return None, "URL metadata kosong atau tidak valid."

    headers = {"accept": "application/xml,text/xml,application/json;q=0.9,*/*;q=0.8"}

    # ── Attempt 1: Direct request ─────────────────────────────────────────────
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200 and _is_xml_content(resp.text):
            text = _clean_xml_text(resp.text)
            data = xmltodict.parse(text)
            if data:
                return data, None
    except Exception:
        pass

    # ── Attempt 2: With basic auth ────────────────────────────────────────────
    user = GEONETWORK_USERNAME()
    pwd  = GEONETWORK_PASSWORD()
    if user and pwd:
        try:
            resp = requests.get(url, headers=headers, auth=(user, pwd), timeout=20)
            if resp.status_code == 200 and _is_xml_content(resp.text):
                text = _clean_xml_text(resp.text)
                data = xmltodict.parse(text)
                if data:
                    return data, None
        except Exception:
            pass

    # ── Attempt 3: Session dengan XSRF token (persis dari kode lama) ──────────
    base = GEONETWORK_URL()
    if base:
        try:
            session = requests.Session()
            resp_auth = session.post(f"{base}/srv/eng/info?type=me", timeout=10)
            xsrf = resp_auth.cookies.get("XSRF-TOKEN", "")
            sess_headers = {
                "accept": "application/xml",
                "X-XSRF-TOKEN": xsrf,
            }
            resp = session.get(url, headers=sess_headers, timeout=20)
            if resp.status_code == 200 and _is_xml_content(resp.text):
                text = _clean_xml_text(resp.text)
                data = xmltodict.parse(text)
                if data:
                    return data, None
            elif resp.status_code != 200:
                return None, f"Metadata Belum Publish atau Masih Draft (HTTP {resp.status_code})"
        except Exception as e:
            pass

    # ── Diagnose what we actually got ─────────────────────────────────────────
    try:
        last_resp = requests.get(url, headers=headers, timeout=10)
        body = last_resp.text[:200]
        if not body.strip():
            return None, "Response kosong dari server GeoNetwork. Cek apakah metadata sudah dipublish."
        if body.strip().startswith('{') or body.strip().startswith('['):
            return None, "Server mengembalikan JSON bukan XML. Cek URL metadata dan status publish."
        if '<html' in body.lower():
            return None, "Server mengembalikan halaman HTML (kemungkinan error/redirect). Cek URL metadata."
        return None, f"Format response tidak dikenali: {body[:100]}"
    except Exception as e:
        return None, f"Tidak dapat terhubung ke GeoNetwork: {e}"


def _fetch_xml(url_metadata: str) -> tuple:
    """
    Public fetch function. Menangani konversi UUID → URL jika perlu.
    Return: (data_dict, None) atau (None, error_str)
    """
    # Konversi ke URL valid jika perlu
    url = _build_geonetwork_url(url_metadata)
    if not url:
        return None, f"Tidak dapat membentuk URL GeoNetwork dari: '{url_metadata}'. Pastikan GEONETWORK_URL diset di secrets.toml."
    return _fetch_xml_with_session(url)


# ─── HELPER ───────────────────────────────────────────────────────────────────

def _safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d not in ({}, None) else default


def _extract_contact(contact_obj: dict, suffix: str, records: dict):
    party = contact_obj.get("gmd:CI_ResponsibleParty", {})
    role  = _safe_get(party, "gmd:role", "gmd:CI_RoleCode", "@codeListValue") or suffix
    ci    = _safe_get(party, "gmd:contactInfo", "gmd:CI_Contact") or {}
    addr  = _safe_get(ci, "gmd:address", "gmd:CI_Address") or {}

    records[f"Contact Individual Name {role}"]       = _safe_get(party, "gmd:individualName", "gco:CharacterString")
    records[f"Contact Organisation Name {role}"]     = _safe_get(party, "gmd:organisationName", "gco:CharacterString")
    records[f"Contact Position Name {role}"]         = _safe_get(party, "gmd:positionName", "gco:CharacterString")
    records[f"Contact Voice {role}"]                 = _safe_get(ci, "gmd:phone", "gmd:CI_Telephone", "gmd:voice", "gco:CharacterString")
    records[f"Contact Delivery Point {role}"]        = _safe_get(addr, "gmd:deliveryPoint", "gco:CharacterString")
    records[f"Contact City {role}"]                  = _safe_get(addr, "gmd:city", "gco:CharacterString")
    records[f"Contact Administrative Area {role}"]   = _safe_get(addr, "gmd:administrativeArea", "gco:CharacterString")
    records[f"Contact Postal Code {role}"]           = _safe_get(addr, "gmd:postalCode", "gco:CharacterString")
    records[f"Contact Country {role}"]               = _safe_get(addr, "gmd:country", "gco:CharacterString")
    records[f"Contact Electronic Mail Address {role}"] = _safe_get(addr, "gmd:electronicMailAddress", "gco:CharacterString")
    records[f"Contact Hours of Service {role}"]      = _safe_get(ci, "gmd:hoursOfService", "gco:CharacterString")
    records[f"Contact Role {role}"]                  = role


def _extract_poc(poc_obj: dict, suffix: str, records: dict):
    party = poc_obj.get("gmd:CI_ResponsibleParty", {})
    role  = _safe_get(party, "gmd:role", "gmd:CI_RoleCode", "@codeListValue") or suffix
    ci    = _safe_get(party, "gmd:contactInfo", "gmd:CI_Contact") or {}
    addr  = _safe_get(ci, "gmd:address", "gmd:CI_Address") or {}

    records[f"Identification Information Point of Contact Individual Name {role}"]       = _safe_get(party, "gmd:individualName", "gco:CharacterString")
    records[f"Identification Information Point of Contact Organisation Name {role}"]     = _safe_get(party, "gmd:organisationName", "gco:CharacterString")
    records[f"Identification Information Point of Contact Position Name {role}"]         = _safe_get(party, "gmd:positionName", "gco:CharacterString")
    records[f"Identification Information Point of Contact Voice {role}"]                 = _safe_get(ci, "gmd:phone", "gmd:CI_Telephone", "gmd:voice", "gco:CharacterString")
    records[f"Identification Information Point of Contact Delivery Point {role}"]        = _safe_get(addr, "gmd:deliveryPoint", "gco:CharacterString")
    records[f"Identification Information Point of Contact City {role}"]                  = _safe_get(addr, "gmd:city", "gco:CharacterString")
    records[f"Identification Information Point of Contact Administrative Area {role}"]   = _safe_get(addr, "gmd:administrativeArea", "gco:CharacterString")
    records[f"Identification Information Point of Contact Postal Code {role}"]           = _safe_get(addr, "gmd:postalCode", "gco:CharacterString")
    records[f"Identification Information Point of Contact Country {role}"]               = _safe_get(addr, "gmd:country", "gco:CharacterString")
    records[f"Identification Information Point of Contact Electronic Mail Address {role}"] = _safe_get(addr, "gmd:electronicMailAddress", "gco:CharacterString")
    records[f"Identification Information Point of Contact Hours of Service {role}"]      = _safe_get(ci, "gmd:hoursOfService", "gco:CharacterString")
    records[f"Identification Information Point of Contact Role {role}"]                  = role


def _extract_mm(mm_obj: dict, suffix: str, records: dict):
    party = mm_obj.get("gmd:CI_ResponsibleParty", {})
    role  = _safe_get(party, "gmd:role", "gmd:CI_RoleCode", "@codeListValue") or suffix
    ci    = _safe_get(party, "gmd:contactInfo", "gmd:CI_Contact") or {}
    addr  = _safe_get(ci, "gmd:address", "gmd:CI_Address") or {}

    records[f"Metadata Maintenance Individual Name {role}"]           = _safe_get(party, "gmd:individualName", "gco:CharacterString")
    records[f"Metadata Maintenance Organisation Name {role}"]         = _safe_get(party, "gmd:organisationName", "gco:CharacterString")
    records[f"Metadata Maintenance Position Name {role}"]             = _safe_get(party, "gmd:positionName", "gco:CharacterString")
    records[f"Metadata Maintenance Voice {role}"]                     = _safe_get(ci, "gmd:phone", "gmd:CI_Telephone", "gmd:voice", "gco:CharacterString")
    records[f"Metadata Maintenance Delivery Point {role}"]            = _safe_get(addr, "gmd:deliveryPoint", "gco:CharacterString")
    records[f"Metadata Maintenance City {role}"]                      = _safe_get(addr, "gmd:city", "gco:CharacterString")
    records[f"Metadata Maintenance Administrative Area {role}"]       = _safe_get(addr, "gmd:administrativeArea", "gco:CharacterString")
    records[f"Metadata Maintenance Postal Code {role}"]               = _safe_get(addr, "gmd:postalCode", "gco:CharacterString")
    records[f"Metadata Maintenance Country {role}"]                   = _safe_get(addr, "gmd:country", "gco:CharacterString")
    records[f"Metadata Maintenance Electroonic Mail Address {role}"]  = _safe_get(addr, "gmd:electronicMailAddress", "gco:CharacterString")
    records[f"Metadata Hours of Service {role}"]                      = _safe_get(ci, "gmd:hoursOfService", "gco:CharacterString")
    records[f"Metadata Maintenance Role {role}"]                      = role


# ─── MAIN SCORING ─────────────────────────────────────────────────────────────

def get_scoring_metadata(url_metadata: str) -> str:
    """
    Scoring metadata berdasarkan keterisian ~100 field mandatory.
    Persis dari streamlit_old/pages/function_metadata_geonetwork.py.
    Return string persentase e.g. '87.5%'.
    """
    data_dict, err = _fetch_xml(url_metadata)
    if err:
        st.error(f"❌ {err}")
        return "0%"

    try:
        records = {}
        md = data_dict.get("gmd:MD_Metadata", {})

        if not md:
            st.error("❌ Struktur metadata tidak dikenali (bukan gmd:MD_Metadata). Cek format XML.")
            return "0%"

        # File Identifier
        records["File Identifier"] = _safe_get(md, "gmd:fileIdentifier", "gco:CharacterString")

        # Language
        lang = md.get("gmd:language", {})
        if isinstance(lang, dict):
            if "gco:CharacterString" in lang:
                records["Language"] = lang["gco:CharacterString"]
            elif "gmd:LanguageCode" in lang:
                records["Language"] = _safe_get(lang, "gmd:LanguageCode", "@codeListValue")
            else:
                records["Language"] = None
        else:
            records["Language"] = str(lang) if lang else None

        # Character Set
        records["Character Set"] = _safe_get(md, "gmd:characterSet", "gmd:MD_CharacterSetCode", "@codeListValue")

        # Hierarchy Level
        records["Hierarchy Level"] = _safe_get(md, "gmd:hierarchyLevel", "gmd:MD_ScopeCode", "@codeListValue")

        # Contact (2 kontak)
        contact = md.get("gmd:contact", {})
        if isinstance(contact, list):
            _extract_contact(contact[0], "1", records)
            if len(contact) > 1:
                _extract_contact(contact[1], "2", records)
        elif isinstance(contact, dict):
            _extract_contact(contact, "1", records)
            _extract_contact(contact, "2", records)

        # Date Stamp
        datestamp = md.get("gmd:dateStamp", {})
        if isinstance(datestamp, dict):
            records["Metadata Date Stamp"] = datestamp.get("gco:DateTime") or datestamp.get("gco:Date")
        else:
            records["Metadata Date Stamp"] = None

        # Metadata Standard
        records["Metadata Standard Name"]    = _safe_get(md, "gmd:metadataStandardName", "gco:CharacterString")
        records["Metadata Standard Version"] = _safe_get(md, "gmd:metadataStandardVersion", "gco:CharacterString")
        records["Dataset URI"]               = _safe_get(md, "gmd:dataSetURI", "gco:CharacterString")

        # Spatial Representation Information
        sri = _safe_get(md, "gmd:spatialRepresentationInfo", "gmd:MD_VectorSpatialRepresentation") or {}
        records["Spatial Representation Information Topology Level"]       = _safe_get(sri, "gmd:topologyLevel", "gmd:MD_TopologyLevelCode", "@codeListValue")
        records["Spatial Representation Information Geometry Object Type"] = _safe_get(sri, "gmd:geometricObjects", "gmd:MD_GeometricObjects", "gmd:geometricObjectType", "gmd:MD_GeometricObjectTypeCode", "@codeListValue")
        records["Spatial Representation Information Geometry Object Count"]= _safe_get(sri, "gmd:geometricObjects", "gmd:MD_GeometricObjects", "gmd:geometricObjectCount", "gco:Integer")

        # Identification Information
        md_ii = _safe_get(md, "gmd:identificationInfo", "gmd:MD_DataIdentification") or {}
        citation = _safe_get(md_ii, "gmd:citation", "gmd:CI_Citation") or {}

        records["Identification Information Title"]     = _safe_get(citation, "gmd:title", "gco:CharacterString")
        records["Identification Information Date"]      = _safe_get(citation, "gmd:date", "gmd:CI_Date", "gmd:date", "gco:Date")
        records["Identification Information Date Type"] = _safe_get(citation, "gmd:date", "gmd:CI_Date", "gmd:dateType", "gmd:CI_DateTypeCode", "@codeListValue")
        records["Identification Information Abstract"]  = _safe_get(md_ii, "gmd:abstract", "gco:CharacterString")

        # Point of Contact
        poc = md_ii.get("gmd:pointOfContact", {})
        if isinstance(poc, list):
            _extract_poc(poc[0], "1", records)
            if len(poc) > 1:
                _extract_poc(poc[1], "2", records)
        elif isinstance(poc, dict):
            _extract_poc(poc, "1", records)
            _extract_poc(poc, "2", records)

        records["Identification Information Spatial Representation Type"] = _safe_get(md_ii, "gmd:spatialRepresentationType", "gmd:MD_SpatialRepresentationTypeCode", "@codeListValue")

        # Language identification
        ii_lang = md_ii.get("gmd:language", {})
        if isinstance(ii_lang, dict):
            if "gco:CharacterString" in ii_lang:
                records["Identification Information Language"] = ii_lang["gco:CharacterString"]
            elif "gmd:LanguageCode" in ii_lang:
                records["Identification Information Language"] = _safe_get(ii_lang, "gmd:LanguageCode", "@codeListValue")
            else:
                records["Identification Information Language"] = None
        else:
            records["Identification Information Language"] = None

        records["Identification Information Character Set"]    = _safe_get(md_ii, "gmd:characterSet", "gmd:MD_CharacterSetCode", "@codeListValue")

        extent  = _safe_get(md_ii, "gmd:extent", "gmd:EX_Extent") or {}
        geo_el  = _safe_get(extent, "gmd:geographicElement", "gmd:EX_GeographicBoundingBox") or {}
        records["Identification Information Extent Description"]    = _safe_get(extent, "gmd:description", "gco:CharacterString")
        records["Identification Information West Bound Longitude"]  = _safe_get(geo_el, "gmd:westBoundLongitude", "gco:Decimal")
        records["Identification Information East Bound Longitude"]  = _safe_get(geo_el, "gmd:eastBoundLongitude", "gco:Decimal")
        records["Identification Information South Bound Latitude"]  = _safe_get(geo_el, "gmd:southBoundLatitude", "gco:Decimal")
        records["Identification Information North Bound Latitude"]  = _safe_get(geo_el, "gmd:northBoundLatitude", "gco:Decimal")

        # Content Information
        content_info = md.get("gmd:contentInfo", {})
        ci_src = content_info[1] if isinstance(content_info, list) and len(content_info) > 1 else content_info
        if isinstance(ci_src, dict):
            fcd = ci_src.get("gmd:MD_FeatureCatalogueDescription", {})
        else:
            fcd = {}
        fc_cit = _safe_get(fcd, "gmd:featureCatalogueCitation", "gmd:CI_Citation") or {}

        records["Content Information Compliance Code"]      = _safe_get(fcd, "gmd:complianceCode", "gco:Boolean")
        records["Content Information Included With Dataset"]= _safe_get(fcd, "gmd:includedWithDataset", "gco:Boolean")
        records["Content Information Features Types"]       = _safe_get(fcd, "gmd:featureTypes", "gco:LocalName")
        records["Content Information Title"]                = _safe_get(fc_cit, "gmd:title", "gco:CharacterString")
        records["Content Information Date"]                 = _safe_get(fc_cit, "gmd:date", "gmd:CI_Date", "gmd:date", "gco:Date")
        records["Content Information Date Type"]            = _safe_get(fc_cit, "gmd:date", "gmd:CI_Date", "gmd:dateType", "gmd:CI_DateTypeCode", "@codeListValue")

        # Distribution Information
        di      = (md.get("gmd:distributionInfo", {}).get("gmd:MD_Distribution", {})
                   .get("gmd:distributor", {}).get("gmd:MD_Distributor", {})
                   .get("gmd:distributorContact", {}).get("gmd:CI_ResponsibleParty", {}))
        di_ci   = _safe_get(di, "gmd:contactInfo", "gmd:CI_Contact") or {}
        di_addr = _safe_get(di_ci, "gmd:address", "gmd:CI_Address") or {}

        records["Distribution Information Individual Name Walidata"]        = _safe_get(di, "gmd:individualName", "gco:CharacterString")
        records["Distribution Information Organisation Name Walidata"]      = _safe_get(di, "gmd:organisationName", "gco:CharacterString")
        records["Distribution Information Position Name Walidata"]          = _safe_get(di, "gmd:positionName", "gco:CharacterString")
        records["Distribution Information Voice Walidata"]                  = _safe_get(di_ci, "gmd:phone", "gmd:CI_Telephone", "gmd:voice", "gco:CharacterString")
        records["Distribution Information Delivery Point Walidata"]         = _safe_get(di_addr, "gmd:deliveryPoint", "gco:CharacterString")
        records["Distribution Information City Walidata"]                   = _safe_get(di_addr, "gmd:city", "gco:CharacterString")
        records["Distribution Information Administrative Area Walidata"]    = _safe_get(di_addr, "gmd:administrativeArea", "gco:CharacterString")
        records["Distribution Information Postal Code Walidata"]            = _safe_get(di_addr, "gmd:postalCode", "gco:CharacterString")
        records["Distribution Information Country Walidata"]                = _safe_get(di_addr, "gmd:country", "gco:CharacterString")
        records["Distribution Information Electronic Mail Address Walidata"]= _safe_get(di_addr, "gmd:electronicMailAddress", "gco:CharacterString")
        records["Distribution Information Hours of Service Walidata"]       = _safe_get(di_ci, "gmd:hoursOfService", "gco:CharacterString")
        records["Distribution Information Role Walidata"]                   = _safe_get(di, "gmd:role", "gmd:CI_RoleCode", "@codeListValue")

        # Transfer Options
        dto = (md.get("gmd:distributionInfo", {}).get("gmd:MD_Distribution", {})
               .get("gmd:transferOptions", {}))

        def _get_online_fields(src):
            mdo = _safe_get(src, "gmd:MD_DigitalTransferOptions", "gmd:onLine") or {}
            ci_on = mdo.get("gmd:CI_OnlineResource", {}) if isinstance(mdo, dict) else {}
            return (
                _safe_get(ci_on, "gmd:linkage", "gmd:URL"),
                ci_on.get("gmd:protocol"),
                _safe_get(ci_on, "gmd:name", "gco:CharacterString"),
            )

        if isinstance(dto, list):
            l1,p1,n1 = _get_online_fields(dto[0])
            l2,p2,n2 = _get_online_fields(dto[1]) if len(dto) > 1 else (None,None,None)
        else:
            online_list = _safe_get(dto, "gmd:MD_DigitalTransferOptions", "gmd:onLine")
            if isinstance(online_list, list):
                def _ol(o): return (_safe_get(o,"gmd:CI_OnlineResource","gmd:linkage","gmd:URL"), o.get("gmd:CI_OnlineResource",{}).get("gmd:protocol"), _safe_get(o,"gmd:CI_OnlineResource","gmd:name","gco:CharacterString"))
                l1,p1,n1 = _ol(online_list[0])
                l2,p2,n2 = _ol(online_list[1]) if len(online_list)>1 else (None,None,None)
            else:
                l1,p1,n1 = _get_online_fields(dto)
                l2,p2,n2 = None,None,None

        records["Distribution Information Linkage1"]  = l1
        records["Distribution Information Protocol1"] = p1
        records["Distribution Information Name1"]     = n1
        records["Distribution Information Linkage2"]  = l2
        records["Distribution Information Protocol2"] = p2
        records["Distribution Information Name2"]     = n2

        # Metadata Maintenance
        mm_raw = (md.get("gmd:metadataMaintenance", {})
                  .get("gmd:MD_MaintenanceInformation", {})
                  .get("gmd:contact", {}))
        if isinstance(mm_raw, list):
            _extract_mm(mm_raw[0], "1", records)
            if len(mm_raw) > 1:
                _extract_mm(mm_raw[1], "2", records)
        elif isinstance(mm_raw, dict):
            _extract_mm(mm_raw, "1", records)
            _extract_mm(mm_raw, "2", records)

        # ── Hitung persentase (persis dari old code) ──────────────────────────
        df = pd.DataFrame(list(records.items()), columns=["Field", "Value"])
        df.index += 1
        df["Value"] = df["Value"].apply(lambda x: str(x) if x is not None else None)
        df.loc[df["Value"].isin(["None", "nan", ""]), "Value"] = None

        mandatory = len(df)
        data_null = int(df["Value"].isna().sum())
        filled    = mandatory - data_null
        pct       = round(100 - (data_null / mandatory * 100), 2)

        title_meta = _safe_get(md_ii, "gmd:citation", "gmd:CI_Citation", "gmd:title", "gco:CharacterString") or "-"

        df1 = pd.DataFrame([
            {"Field": "Nama Metadata Geospasial",                               "Value": title_meta},
            {"Field": "Jumlah Field Mandatory yang Tidak Terisi",               "Value": f"{data_null} Field"},
            {"Field": "Jumlah Field Mandatory yang Terisi",                     "Value": f"{filled} Field"},
            {"Field": "Tingkat Keterisian Metadata Berdasarkan Field Mandatory", "Value": f"{pct}%"},
        ])
        df1.index = range(1, len(df1)+1)
        st.success("✅ Hasil Penilaian Metadata:")
        st.table(df1)

        def _color_val(val):
            if val is None or str(val) in ("None", "nan", ""):
                return "background-color:rgba(255,82,82,.2);color:#FF5252"
            return "background-color:rgba(0,230,118,.12);color:#00E676"

        with st.expander(f"📄 Detail Keterisian {mandatory} Field Mandatory Metadata", expanded=False):
            st.dataframe(df.style.applymap(_color_val, subset=["Value"]), use_container_width=True)

        return f"{pct}%"

    except Exception as e:
        import traceback
        st.error(f"❌ Error scoring metadata: {e}")
        with st.expander("🔍 Detail Error"):
            st.code(traceback.format_exc())
        return "0%"


# ─── COMPLIANCE CODE & INCLUDED WITH DATASET ──────────────────────────────────

def get_metadata_compliance_code(url_metadata: str):
    data_dict, err = _fetch_xml(url_metadata)
    if err:
        st.warning(f"⚠️ Tidak dapat membaca compliance code: {err}")
        return {"Content Information Compliance Code": None}
    content_info = data_dict.get("gmd:MD_Metadata", {}).get("gmd:contentInfo", {})
    ci_src = content_info[1] if isinstance(content_info, list) and len(content_info) > 1 else content_info
    fcd = ci_src.get("gmd:MD_FeatureCatalogueDescription", {}) if isinstance(ci_src, dict) else {}
    val = _safe_get(fcd, "gmd:complianceCode", "gco:Boolean")
    return {"Content Information Compliance Code": val}


def get_metadata_included_with_dataset(url_metadata: str):
    data_dict, err = _fetch_xml(url_metadata)
    if err:
        return {"Content Information Included With Dataset": None}
    content_info = data_dict.get("gmd:MD_Metadata", {}).get("gmd:contentInfo", {})
    ci_src = content_info[1] if isinstance(content_info, list) and len(content_info) > 1 else content_info
    fcd = ci_src.get("gmd:MD_FeatureCatalogueDescription", {}) if isinstance(ci_src, dict) else {}
    val = _safe_get(fcd, "gmd:includedWithDataset", "gco:Boolean")
    return {"Content Information Included With Dataset": val}
