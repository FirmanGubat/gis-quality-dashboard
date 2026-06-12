"""
Halaman Topology Check & Scoring Kualitas Data Geospasial
Logika penilaian persis mengikuti streamlit_old (function_topology_check.py)
"""
import os
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.topology import (
    # metadata functions sekarang dari metadata_geonetwork via topology:
    list_service_geoserver, get_data_geoserver,
    folder_arcgis, sub_folder_arcgis, service_arcgis,
    get_columns_arcgis, get_data_arcgis,
    list_metadata_geonetwork, get_scoring_metadata,
    get_metadata_compliance_code, get_metadata_included_with_dataset,
    get_mapset_satu_peta,
    run_check_column_names, run_check_commission, run_check_omission,
    run_check_duplicates, run_check_topology, run_check_point_in_jabar,
    run_kugi_check,
    TIMELINESS_OPTIONS, timeliness_score,
    calculate_final_score, score_to_status,
    GEOSERVER_USERNAME, GEOSERVER_PASSWORD,
)
from utils.pdf_generator import generate_pdf
from utils.history_store import load_history, save_history, upsert_entry


def _bool_label(v) -> str:
    """Konversi boolean string true/false ke Ya/Tidak."""
    s = str(v).lower().strip()
    if s == "true":  return "Ya"
    if s == "false": return "Tidak"
    return "—"


def _step(num, title):
    st.markdown(f"""
    <div class="step-header">
        <div class="step-num">{num}</div>
        <div class="step-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)


def _card(content_html):
    st.markdown(f'<div class="gis-card">{content_html}</div>', unsafe_allow_html=True)


def _load_geoserver_columns(url: str) -> list:
    try:
        import requests, geopandas as gpd
        preview_url = url + ("&maxFeatures=1" if "?" in url else "?maxFeatures=1")
        resp = requests.get(preview_url, auth=(GEOSERVER_USERNAME(), GEOSERVER_PASSWORD()), timeout=20)
        gdf = gpd.read_file(resp.text)
        return [c for c in gdf.columns if c != "geometry"]
    except Exception:
        return []


def _column_checkbox(items: list, prefix: str) -> list:
    if not items:
        st.warning("⚠️ Tidak ada kolom ditemukan.")
        return []
    st.markdown("**Pilih kolom untuk cek duplikasi geometri:**")
    st.caption("Centang kolom yang dijadikan acuan deteksi duplikat data.")
    selected = []
    n_cols = min(4, len(items))
    cols = st.columns(n_cols)
    for i, item in enumerate(items):
        with cols[i % n_cols]:
            if st.checkbox(item, key=f"{prefix}_col_{item}"):
                selected.append(item)
    if selected:
        st.success(f"✅ {len(selected)} kolom dipilih")
    else:
        st.info("ℹ️ Pilih minimal 1 kolom.")
    return selected


def _score_color(skor: float) -> str:
    if skor > 90:   return "#00E676"
    elif skor > 75: return "#00D4FF"
    elif skor >= 60: return "#FFB74D"
    else:           return "#FF5252"


def render(user: dict):
    st.markdown("""
    <div style="margin-bottom:1rem;">
        <h1 style="font-size:1.7rem; font-weight:800; margin:0;">
            🔬 Topology Check Data Geospasial
        </h1>
        <p style="color:var(--muted); margin:.4rem 0 0; font-size:.875rem;">
            Pengecekan kualitas data geospasial otomatis — duplikasi, topologi, kelengkapan, metadata, dan KUGI.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── STEP 1: Identifikasi Mapset ───────────────────────────────────────────
    _step("1", "Identifikasi Mapset (dari Satu Peta)")

    with st.spinner("Memuat daftar mapset..."):
        list_mapset = get_mapset_satu_peta()

    mapset_data = {}
    url_metadata = None
    url_layer_auto = None
    layer_name = "layer"
    tipe_auto = ""   # akan diisi dari mapset_type_id

    if not list_mapset:
        st.warning("⚠️ Data mapset tidak tersedia. Periksa konfigurasi URL Metabase di secrets.toml → [metabase] url_satu_peta")
    else:
        mapset_options = [""] + [f"{i+1}. {m['name']}" for i, m in enumerate(list_mapset)]
        selected_mapset_label = st.selectbox(
            "Pilih Mapset", mapset_options,
            help="Pilih dataset yang ingin dicek kualitasnya dari Satu Peta"
        )

        if selected_mapset_label:
            idx = int(selected_mapset_label.split(".")[0]) - 1
            m = list_mapset[idx]
            layer_name = m["name"]
            tipe_auto = {"2": "Point", "3": "Polyline", "4": "Polygon"}.get(str(m["mapset_type_id"]), "")
            mapset_data = {
                "Judul Mapset":         m["name"],
                "Nama Organisasi":      m["owner"],
                "Mapset Type":          tipe_auto or str(m["mapset_type_id"]),
                "Sumber Mapservice":    {"2": "ArcGIS", "11": "Geoserver"}.get(str(m["mapset_source_id"]), str(m["mapset_source_id"])),
                "Mapservice Link": m["mapsetservice_url"],
                "Description":          m["description"],
            }
            url_metadata = m["metadata_xml"] or None
            url_layer_auto = m["wfs_url"] or None

            # Set session state supaya tipe langsung tersimpan
            if tipe_auto:
                st.session_state["selected_tipe"] = tipe_auto

            with st.expander("📋 Detail Mapset", expanded=False):
                for k, v in mapset_data.items():
                    st.markdown(f"**{k}:** {v}")

    col_date, col_pj = st.columns(2)
    with col_date:
        tanggal = st.date_input("📅 Tanggal Penilaian")
    with col_pj:
        penanggung_jawab = st.text_input("👤 Penanggung Jawab")

    if mapset_data:
        mapset_data["Nama Penanggung Jawab"] = penanggung_jawab
        mapset_data["Tanggal Penilaian"] = tanggal.strftime("%d-%m-%Y")

    st.markdown("---")

    # ── STEP 2: Metadata ──────────────────────────────────────────────────────
    _step("2", "Metadata Geospasial (GeoNetwork)")

    if url_metadata:
        st.success("✅ Metadata otomatis terdeteksi dari mapset")
        st.markdown(f"[🔗 Link Metadata GeoNetwork]({url_metadata})")
        url_override = st.text_input("🔗 Override URL Metadata (kosongkan jika pakai otomatis)", value="",
                                     placeholder="https://geonetwork.jabarprov.go.id/...")
        if url_override.strip():
            url_metadata = url_override.strip()
    else:
        st.info("ℹ️ Metadata tidak terdeteksi otomatis. Isi manual jika ada.")
        url_meta_manual = st.text_input("🔗 URL Metadata GeoNetwork (opsional)",
                                        placeholder="https://geonetwork.jabarprov.go.id/.../formatters/xml")
        url_metadata = url_meta_manual.strip() if url_meta_manual.strip() else None

    input_url_kugi = st.text_input("🔗 URL KUGI (opsional)", placeholder="https://...")

    st.markdown("---")

    # ── STEP 3: Layer & Engine ────────────────────────────────────────────────
    _step("3", "Layer & Kolom Data")

    url_layer = None
    selected_columns = []
    engine = "GeoServer"

    if url_layer_auto:
        st.success("✅ Layer GeoServer otomatis terdeteksi dari mapset")
        st.code(url_layer_auto, language=None)
        url_override2 = st.text_input("🔗 Override WFS URL (kosongkan jika pakai otomatis)", value="",
                                       placeholder="https://geoserver.../ows?service=WFS&...")
        url_layer = url_override2.strip() if url_override2.strip() else url_layer_auto
        engine = "GeoServer"

        tipe_options = ["", "Point", "Polyline", "Polygon"]
        tipe_index = tipe_options.index(tipe_auto) if tipe_auto in tipe_options else 0
        if tipe_auto:
            st.success(f"✅ Tipe Data otomatis terdeteksi: **{tipe_auto}**")
        tipe = st.selectbox(
            "Tipe Data Geometri",
            tipe_options,
            index=tipe_index,
            help="Terisi otomatis dari mapset. Ubah jika tidak sesuai.",
        )
        if not tipe_auto:
            st.warning("⚠️ JANGAN SALAH PILIH TIPE DATA!")
        st.session_state["selected_tipe"] = tipe

        if url_layer:
            with st.spinner("⏳ Memuat kolom data dari GeoServer..."):
                items = _load_geoserver_columns(url_layer)
            if items:
                selected_columns = _column_checkbox(items, prefix="geo")
            else:
                st.warning("⚠️ Gagal memuat kolom. Cek koneksi GeoServer atau URL layer.")
    else:
        st.info("ℹ️ Layer tidak terdeteksi otomatis. Pilih engine secara manual:")
        tab_geo, tab_arc = st.tabs(["🟢  GeoServer", "🔵  ArcGIS"])

        with tab_geo:
            engine = "GeoServer"
            with st.spinner("Memuat layer GeoServer..."):
                layers = list_service_geoserver()
            if layers:
                layer_options = [""] + [n for n, _ in layers]
                sel = st.selectbox("Layer GeoServer", layer_options, key="geo_layer")
                if sel:
                    url_layer = next(link for name, link in layers if name == sel)
                    tipe = st.selectbox("Tipe Data", ["", "Point", "Polyline", "Polygon"], key="geo_tipe")
                    st.warning("⚠️ JANGAN SALAH PILIH TIPE DATA!")
                    st.session_state["selected_tipe"] = tipe
                    with st.spinner("Memuat kolom..."):
                        items = _load_geoserver_columns(url_layer)
                    selected_columns = _column_checkbox(items, "geo2")
            else:
                st.info("ℹ️ List layer GeoServer tidak tersedia (REST API tidak dapat diakses).")
                st.markdown("**Masukkan WFS URL secara manual:**")
                manual_wfs = st.text_input(
                    "WFS URL",
                    placeholder="https://geoserver.../ows?service=WFS&version=1.0.0&request=GetFeature&typeName=workspace:layer&outputFormat=application%2Fjson",
                    key="geo_manual_url"
                )
                if manual_wfs.strip():
                    url_layer = manual_wfs.strip()
                    tipe = st.selectbox("Tipe Data", ["", "Point", "Polyline", "Polygon"], key="geo_tipe_manual")
                    st.warning("⚠️ JANGAN SALAH PILIH TIPE DATA!")
                    st.session_state["selected_tipe"] = tipe
                    with st.spinner("Memuat kolom..."):
                        items = _load_geoserver_columns(url_layer)
                    if items:
                        selected_columns = _column_checkbox(items, "geo_manual")
                    else:
                        st.warning("⚠️ Gagal memuat kolom dari URL tersebut.")

        with tab_arc:
            if not url_layer:
                engine = "ArcGIS"
                folders = folder_arcgis()
                if folders:
                    sel_f = st.selectbox("Folder ArcGIS", [""] + folders, key="arc_f")
                    if sel_f:
                        subs = sub_folder_arcgis(sel_f)
                        sel_s = st.selectbox("Directory", [""] + subs, key="arc_s")
                        if sel_s:
                            services = service_arcgis(sel_s)
                            if services:
                                sel_srv = st.selectbox("Layer", [""] + [n for n, _ in services], key="arc_srv")
                                if sel_srv:
                                    url_layer = next(link for name, link in services if name == sel_srv)
                                    tipe = st.selectbox("Tipe Data", ["", "Point", "Polyline", "Polygon"], key="arc_tipe")
                                    st.warning("⚠️ JANGAN SALAH PILIH TIPE DATA!")
                                    st.session_state["selected_tipe"] = tipe
                                    with st.spinner("Memuat kolom..."):
                                        cols = get_columns_arcgis(url_layer)
                                    selected_columns = _column_checkbox(cols, "arc")

    if url_layer:
        st.caption(f"[🔗 Preview layer]({url_layer})")

    st.markdown("---")

    # ── STEP 4: Parameter Penilaian ───────────────────────────────────────────
    _step("4", "Parameter Penilaian")

    col_k, col_t = st.columns(2)
    with col_k:
        kesesuaian = st.selectbox(
            "Kesesuaian Nama Mapset",
            ["", "Sesuai", "Tidak Sesuai"],
            help="Apakah nama layer/mapset sesuai standar penamaan?"
        )
    with col_t:
        timeliness_labels = [opt[0] for opt in TIMELINESS_OPTIONS]
        timeliness_label = st.selectbox(
            "Timeliness (Kebaruan Data)",
            timeliness_labels,
            help="Pilih kategori kebaruan data berdasarkan tahun"
        )

    st.markdown("---")

    # ── STEP 5: Jalankan ──────────────────────────────────────────────────────
    _step("5", "Jalankan Pengecekan")

    col_run, col_reset, _ = st.columns([1.2, 1, 5])
    with col_run:
        run_btn = st.button("▶️  Mulai Cek", type="primary", width="stretch")
    with col_reset:
        if st.button("🔄  Reset", width="stretch"):
            st.rerun()

    if run_btn:
        errors = []
        if not url_layer:
            errors.append("Layer belum dipilih.")
        if not selected_columns:
            errors.append("Kolom untuk cek duplikat belum dipilih.")
        if not kesesuaian:
            errors.append("Kesesuaian nama mapset belum dipilih.")
        if not timeliness_label:
            errors.append("Timeliness belum dipilih.")
        tipe = st.session_state.get("selected_tipe", "")
        if not tipe:
            errors.append("Tipe data geometri belum dipilih.")

        if errors:
            for e in errors:
                st.warning(f"⚠️ {e}")
        else:
            _run_full_check(
                url_layer=url_layer,
                engine=engine,
                selected_columns=selected_columns,
                url_metadata=url_metadata,
                url_kugi=input_url_kugi,
                kesesuaian=kesesuaian,
                timeliness_label=timeliness_label,
                mapset_data=mapset_data,
                layer_name=layer_name,
                tipe=tipe,
                user=user,
            )


# ─── FULL CHECK ───────────────────────────────────────────────────────────────

def _run_full_check(
    url_layer, engine, selected_columns, url_metadata, url_kugi,
    kesesuaian, timeliness_label, mapset_data, layer_name, tipe, user
):
    st.markdown("---")
    st.markdown("""
    <h2 style="font-size:1.4rem; font-weight:800; margin-bottom:.25rem;">
        📋 Hasil Pengecekan Kualitas Data
    </h2>
    """, unsafe_allow_html=True)

    # ── Fetch data ────────────────────────────────────────────────────────────
    with st.spinner(f"📥 Mengambil data dari {engine}..."):
        if engine == "GeoServer":
            gdf = get_data_geoserver(url_layer)
        else:
            gdf = get_data_arcgis(url_layer)

    if gdf is None or gdf.empty:
        st.error("❌ Data kosong atau gagal diambil. Cek URL dan koneksi.")
        return

    st.success(f"✅ Data berhasil diambil: **{len(gdf):,} fitur**, **{len(gdf.columns)} kolom**")

    # ── Init nilai default (persis dari old code) ─────────────────────────────
    nilai_a          = 100  # compliance code default
    nilai_b          = 0    # included with dataset default
    compliance_val   = None
    included_val     = None
    hasil_kugi       = "KUGI Tidak di Cek"
    persen_metadata  = "0%"

    # ── Metadata & KUGI ───────────────────────────────────────────────────────
    if url_metadata:
        st.markdown("### 📑 Metadata Geospasial (GeoNetwork)")

        with st.spinner("🔍 Membaca compliance code & included with dataset..."):
            compliance_raw = get_metadata_compliance_code(url_metadata)
            included_raw   = get_metadata_included_with_dataset(url_metadata)

        # Kedua fungsi return dict — ekstrak nilai string-nya
        if isinstance(compliance_raw, dict):
            compliance_val = compliance_raw.get("Content Information Compliance Code")
        else:
            compliance_val = compliance_raw

        if isinstance(included_raw, dict):
            included_val = included_raw.get("Content Information Included With Dataset")
        else:
            included_val = included_raw

        # Normalisasi ke lowercase string atau None
        compliance_val = str(compliance_val).lower().strip() if compliance_val not in (None, "None", "") else None
        included_val   = str(included_val).lower().strip()   if included_val   not in (None, "None", "") else None

        col_a, col_b = st.columns(2)
        with col_a:
            _metric_pill("Compliance Code",
                         compliance_val if compliance_val else "false",
                         "cyan")
        with col_b:
            _metric_pill("Included With Dataset",
                         included_val if included_val else "false",
                         "cyan")

        st.markdown("#### 🗂️ Pengecekan KUGI")
        hasil_kugi, nilai_a, nilai_b = run_kugi_check(
            gdf=gdf,
            compliance_code=compliance_val,
            included_with_dataset=included_val,
            url_kugi=url_kugi,
        )

        st.markdown("#### 📋 Scoring Field Mandatory Metadata")
        with st.spinner("🔍 Menghitung keterisian field mandatory..."):
            persen_metadata = get_scoring_metadata(url_metadata)

        _metric_pill("Skor Keterisian Metadata", persen_metadata, "purple")
    else:
        st.info("ℹ️ Metadata tidak dipilih — skor metadata = 0%, KUGI tidak dicek.")

    # ── Cek per kategori (tab) ────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📐  Kolom & Kelengkapan",
        "🔁  Duplikasi",
        "🔺  Topologi",
        "⏱️  Timeliness",
    ])

    with tab1:
        st.markdown("#### Cek Nama Kolom (Huruf Kapital)")
        hasil_upper, nilai_upper = run_check_column_names(gdf)
        st.markdown("---")
        st.markdown("#### Completeness Commission")
        st.caption("Geometri ada, namun atribut NULL → artinya ada data yang tidak lengkap.")
        hasil_commission, nilai_commission = run_check_commission(gdf)
        st.markdown("---")
        st.markdown("#### Completeness Omission")
        st.caption("Atribut ada, namun geometry NULL/kosong → artinya ada geometri yang hilang.")
        hasil_omission, nilai_omission = run_check_omission(gdf)

    with tab2:
        st.markdown("#### Cek Duplikasi Data")
        st.caption("Mendeteksi baris dengan kombinasi kolom yang sama persis.")
        hasil_duplikat, nilai_duplikat = run_check_duplicates(gdf, url_layer, selected_columns, engine)

    with tab3:
        st.markdown("#### Cek Topologi Geometri")
        # Logika persis dari kode lama:
        # - Point → cek in/out Jawa Barat
        # - Polyline/Polygon → cek self-intersection / invalid geometry
        if tipe == "Point":
            st.info("🔄 Processing Point Data: cek apakah semua titik berada di dalam wilayah Jawa Barat...")
            st.warning("⚠️ Processing tipe data Point membutuhkan waktu lebih lama karena ada proses pengecekan wilayah Jawa Barat.")
            hasil_topo, nilai_topo = run_check_point_in_jabar(gdf, url_layer, engine)
        else:
            hasil_topo, nilai_topo = run_check_topology(gdf, url_layer, engine)

    with tab4:
        st.markdown("#### Timeliness (Kebaruan Data)")
        nilai_timeliness = timeliness_score(timeliness_label)
        nilai_kesesuaian = 100 if kesesuaian == "Sesuai" else 0

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            _metric_pill("Timeliness", timeliness_label or "-",
                         "green" if nilai_timeliness >= 80 else "amber" if nilai_timeliness >= 60 else "red")
            st.caption(f"Nilai: **{nilai_timeliness}**")
        with col_t2:
            _metric_pill("Kesesuaian Nama Mapset", kesesuaian or "-",
                         "green" if nilai_kesesuaian == 100 else "red")
            st.caption(f"Nilai: **{nilai_kesesuaian}**")

    # ── Hitung Skor Akhir (rumus persis dari old code) ────────────────────────
    skor = calculate_final_score(
        nilai_a=nilai_a,
        nilai_b=nilai_b,
        nilai_nama_tabel=nilai_kesesuaian,
        nilai_duplikat=nilai_duplikat,
        nilai_topologi=nilai_topo,
        nilai_upper_kolom=nilai_upper,
        nilai_timeliness=nilai_timeliness,
        hasil_kugi=hasil_kugi,
        persen_metadata=persen_metadata,
        nilai_commission=nilai_commission,
        nilai_omission=nilai_omission,
        compliance_code_val=compliance_val,
    )
    status, emoji = score_to_status(skor)

    # ── Tampilkan Scoring ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <h2 style="font-size:1.4rem; font-weight:800;">🏆 Hasil Scoring Akhir</h2>
    """, unsafe_allow_html=True)

    score_color = _score_color(skor)

    col_score, col_table = st.columns([1, 2])
    with col_score:
        st.markdown(f"""
        <div style="text-align:center; padding:1.5rem 0;">
            <div style="display:inline-flex; align-items:center; justify-content:center;
                        width:180px; height:180px; border-radius:50%;
                        border: 6px solid {score_color};
                        background: var(--surface2);
                        font-size:3.4rem; font-weight:900; color:{score_color};
                        box-shadow: 0 0 50px {score_color}30;">
                {skor}
            </div>
            <div style="font-size:1.2rem; font-weight:700; margin-top:1rem; color:{score_color};">
                {emoji} {status}
            </div>
            <div style="font-size:.8rem; color:var(--muted); margin-top:.3rem;">
                {layer_name}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_table:
        # Tentukan apakah nilai_b dan KUGI dipakai (compliance_val == 'true')
        dipakai_b = "✅" if compliance_val == "true" else "—"
        dipakai_kugi = "✅" if compliance_val == "true" else "—"

        kugi_disp = str(hasil_kugi)

        df_scores = pd.DataFrame({
            "Sub Elemen": [
                "Compliance Code", "Include With Dataset", "Format Nama Layer",
                "Duplikat Data", "Topologi/Point Check", "Nama Kolom (Kapital)",
                "Timeliness", "KUGI", "Metadata (Field Mandatory)",
                "Commission", "Omission",
            ],
            "Nilai": [
                str(nilai_a), str(nilai_b), str(nilai_kesesuaian),
                str(nilai_duplikat), str(nilai_topo), str(nilai_upper),
                str(nilai_timeliness), str(kugi_disp), str(persen_metadata),
                str(nilai_commission), str(nilai_omission),
            ],
            "Dipakai": [
                "✅", dipakai_b, "✅", "✅", "✅", "✅",
                "✅", dipakai_kugi, "✅", "✅", "✅",
            ],
        })
        st.dataframe(df_scores, use_container_width=True, hide_index=True)

    if status == "Perlu Diperbaiki":
        rekomendasi = (f"Mapset {layer_name} perlu diperbaiki untuk memenuhi standar "
                       "kualitas data geospasial minimum agar dapat digunakan oleh Stakeholder.")
        st.error(f"❌ **Rekomendasi:** {rekomendasi}")
    else:
        rekomendasi = ""
        st.success(f"✅ Data memenuhi standar kualitas — Status: **{status}**")

    # ── Generate & Download PDF ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📄 Download Laporan PDF")

    report_data = {
        **{k: v for k, v in mapset_data.items()},
        # Fields template
        "kolom_huruf_besar": hasil_upper,
        "comformity_1":  _bool_label(compliance_val),
        "comformity_2":  _bool_label(included_val) if url_metadata else "—",
        "comformity_3":  kesesuaian,
        "commission":    hasil_commission,
        "omission":      hasil_omission,
        "metadata":      persen_metadata,
        "keterisian":    str(hasil_kugi),
        "tahun_data":    timeliness_label,
        "duplikat_data": hasil_duplikat,
        "topology_check": hasil_topo,
        "mapset":        layer_name,
        "nilai":         str(skor),
        "Status":        status,
        "rekomendasi":   rekomendasi,
        # Nilai numerik per elemen untuk tabel PDF
        "_n_comformity_1":  nilai_a,
        "_n_comformity_2":  nilai_b,
        "_n_comformity_3":  nilai_kesesuaian,
        "_n_duplikat":      nilai_duplikat,
        "_n_topologi":      nilai_topo,
        "_n_upper_kolom":   nilai_upper,
        "_n_timeliness":    nilai_timeliness,
        "_n_kugi":          kugi_disp,
        "_n_commission":    nilai_commission,
        "_n_omission":      nilai_omission,
    }

    try:
        with st.spinner("🔄 Generating laporan PDF..."):
            pdf_bytes = generate_pdf(report_data)

        safe_name = layer_name.replace(" ", "_").replace("/", "-")
        st.download_button(
            label="📥  Download Laporan PDF",
            data=pdf_bytes,
            file_name=f"kualitas_{safe_name}_{tanggal_str()}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=False,
        )
        st.success("✅ Laporan PDF berhasil digenerate!")
    except Exception as e:
        st.error(f"❌ Gagal generate PDF: {e}")
        st.info("💡 Pastikan `reportlab` terinstall: `pip install reportlab`")

    # ── Simpan ke history (persistent + session state) ───────────────────────
    history_entry = {
        "layer_name":    layer_name,
        "organisasi":    mapset_data.get("Nama Organisasi", "-"),
        "skor":          skor,
        "status":        status,
        "tanggal":       mapset_data.get("Tanggal Penilaian", datetime.now().strftime("%d-%m-%Y")),
        "penanggung_jawab": mapset_data.get("Nama Penanggung Jawab", "-"),
        "report_data":   report_data,
        "pdf_bytes":     pdf_bytes if "pdf_bytes" in dir() else None,
        # Detail sub-elemen
        "nilai_compliance_code":     nilai_a,
        "nilai_included":            nilai_b,
        "nilai_nama_mapset":         nilai_kesesuaian,
        "nilai_duplikat":            nilai_duplikat,
        "nilai_topologi":            nilai_topo,
        "nilai_upper_kolom":         nilai_upper,
        "nilai_timeliness":          nilai_timeliness,
        "nilai_kugi":                kugi_disp,
        "nilai_metadata":            persen_metadata,
        "nilai_commission":          nilai_commission,
        "nilai_omission":            nilai_omission,
    }
    # Load dari file, upsert, simpan kembali ke file & session_state
    if "scoring_history" not in st.session_state or not st.session_state["scoring_history"]:
        st.session_state["scoring_history"] = load_history()
    st.session_state["scoring_history"] = upsert_entry(
        st.session_state["scoring_history"], history_entry
    )
    save_history(st.session_state["scoring_history"])
    st.info("💾 Hasil penilaian **tersimpan permanen** ke Scoring Kualitas Data.")


def tanggal_str():
    return datetime.now().strftime("%Y%m%d")


def _metric_pill(label: str, value: str, color: str = "cyan"):
    color_map = {
        "cyan":   ("rgba(0,212,255,.15)", "#00D4FF"),
        "green":  ("rgba(0,230,118,.15)", "#00E676"),
        "amber":  ("rgba(255,183,77,.15)", "#FFB74D"),
        "red":    ("rgba(255,82,82,.15)", "#FF5252"),
        "purple": ("rgba(206,147,216,.15)", "#CE93D8"),
    }
    bg, fg = color_map.get(color, color_map["cyan"])
    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {fg}40; border-radius:10px;
                padding:.85rem 1rem; margin:.4rem 0; display:inline-block; min-width:180px;">
        <div style="font-size:.7rem; color:{fg}; text-transform:uppercase; letter-spacing:.06em; font-weight:700;">{label}</div>
        <div style="font-size:1.1rem; font-weight:800; color:{fg}; margin-top:.2rem;">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def _score_color(skor: float) -> str:
    if skor > 90:    return "#00E676"
    elif skor > 75:  return "#00D4FF"
    elif skor >= 60: return "#FFB74D"
    else:            return "#FF5252"