"""
Halaman Scoring Kualitas Data — Rekap semua hasil penilaian dari session state.
Fitur: lihat rekap, download PDF per item, penilaian ulang, filter & statistik.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.pdf_generator import generate_pdf
from utils.history_store import load_history, save_history


def _score_badge(skor: float) -> str:
    if skor > 90:    return "🌟 Sangat Baik"
    elif skor > 75:  return "🟢 Baik"
    elif skor >= 60: return "🟡 Cukup"
    else:            return "🔴 Perlu Diperbaiki"


def _score_color(skor: float) -> str:
    if skor > 90:    return "#00E676"
    elif skor > 75:  return "#00D4FF"
    elif skor >= 60: return "#FFB74D"
    else:            return "#FF5252"


def render(user: dict):
    st.markdown("""
    <div style="margin-bottom:1rem;">
        <h1 style="font-size:1.7rem; font-weight:800; margin:0;">
            📊 Scoring Kualitas Data Geospasial
        </h1>
        <p style="color:var(--muted); margin:.4rem 0 0; font-size:.875rem;">
            Rekap semua hasil penilaian kualitas data yang telah dilakukan.
            Download laporan PDF atau lakukan penilaian ulang dari sini.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Load dari persistent file kalau session_state kosong (setelah refresh)
    if "scoring_history" not in st.session_state or not st.session_state["scoring_history"]:
        st.session_state["scoring_history"] = load_history()
    history: list = st.session_state.get("scoring_history", [])

    # ── EMPTY STATE ───────────────────────────────────────────────────────────
    if not history:
        st.markdown("""
        <div style="text-align:center; padding:4rem 2rem;
                    background:var(--surface); border:1px dashed var(--border2);
                    border-radius:var(--radius);">
            <div style="font-size:3.5rem; margin-bottom:1rem;">📭</div>
            <div style="font-size:1.2rem; font-weight:700; color:var(--muted); margin-bottom:.5rem;">
                Belum ada data penilaian
            </div>
            <div style="font-size:.875rem; color:var(--muted2);">
                Lakukan Topology Check terlebih dahulu untuk melihat rekap di sini.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔬  Mulai Topology Check", width="content"):
            st.session_state["nav_override"] = "topology"
            st.rerun()
        return

    # ── SUMMARY METRICS ───────────────────────────────────────────────────────
    total = len(history)
    scores = [h["skor"] for h in history]
    avg   = round(sum(scores)/total, 1)
    sangat_baik   = sum(1 for s in scores if s > 90)
    baik          = sum(1 for s in scores if 75 < s <= 90)
    cukup         = sum(1 for s in scores if 60 <= s <= 75)
    perlu         = sum(1 for s in scores if s < 60)

    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-box">
            <div class="mval c-cyan">{total}</div>
            <div class="mlbl">Total Penilaian</div>
        </div>
        <div class="metric-box">
            <div class="mval" style="color:{_score_color(avg)};">{avg}</div>
            <div class="mlbl">Rata-rata Skor</div>
        </div>
        <div class="metric-box">
            <div class="mval c-green">{sangat_baik}</div>
            <div class="mlbl">🌟 Sangat Baik</div>
        </div>
        <div class="metric-box">
            <div class="mval c-cyan">{baik}</div>
            <div class="mlbl">🟢 Baik</div>
        </div>
        <div class="metric-box">
            <div class="mval c-amber">{cukup}</div>
            <div class="mlbl">🟡 Cukup</div>
        </div>
        <div class="metric-box">
            <div class="mval c-red">{perlu}</div>
            <div class="mlbl">🔴 Perlu Diperbaiki</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── VISUALISASI DISTRIBUSI ────────────────────────────────────────────────
    with st.expander("📈 Visualisasi Distribusi Skor", expanded=False):
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("**Distribusi Status**")
            dist_df = pd.DataFrame({
                "Status": ["Sangat Baik (>90)", "Baik (76-90)", "Cukup (60-75)", "Perlu Diperbaiki (<60)"],
                "Jumlah": [sangat_baik, baik, cukup, perlu]
            })
            st.bar_chart(dist_df.set_index("Status"))

        with col_chart2:
            st.markdown("**Skor per Mapset (terbaru)**")
            last_10 = history[-10:]
            score_df = pd.DataFrame({
                "Mapset": [h["layer_name"][:25] + "..." if len(h["layer_name"]) > 25 else h["layer_name"] for h in last_10],
                "Skor":   [h["skor"] for h in last_10]
            })
            st.bar_chart(score_df.set_index("Mapset"))

    # ── FILTER ────────────────────────────────────────────────────────────────
    st.markdown("### 🔍 Filter & Cari")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_status = st.multiselect(
            "Filter Status",
            ["🌟 Sangat Baik", "🟢 Baik", "🟡 Cukup", "🔴 Perlu Diperbaiki"],
            default=[],
            placeholder="Semua status"
        )
    with col_f2:
        orgs = sorted(set(h.get("organisasi", "-") for h in history))
        filter_org = st.multiselect("Filter Organisasi", orgs, default=[], placeholder="Semua organisasi")
    with col_f3:
        search_text = st.text_input("🔎 Cari nama mapset", placeholder="Ketik nama...")

    # Apply filter
    filtered = history.copy()
    if filter_status:
        filtered = [h for h in filtered if _score_badge(h["skor"]) in filter_status]
    if filter_org:
        filtered = [h for h in filtered if h.get("organisasi", "-") in filter_org]
    if search_text:
        filtered = [h for h in filtered if search_text.lower() in h["layer_name"].lower()]

    st.markdown(f"**Menampilkan {len(filtered)} dari {len(history)} penilaian**")
    st.markdown("---")

    # ── TABEL REKAP + AKSI ────────────────────────────────────────────────────
    st.markdown("### 📋 Daftar Hasil Penilaian")

    if not filtered:
        st.info("ℹ️ Tidak ada data yang sesuai dengan filter.")
        return

    # Tampilkan setiap item sebagai card
    for idx, h in enumerate(reversed(filtered)):
        real_idx = len(history) - 1 - history.index(h) if h in history else idx
        skor      = h["skor"]
        status    = h["status"]
        sc        = _score_color(skor)
        badge     = _score_badge(skor)

        with st.container():
            st.markdown(f"""
            <div class="gis-card" style="border-left: 4px solid {sc}; margin-bottom:.75rem;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:.5rem;">
                    <div style="flex:1; min-width:200px;">
                        <div style="font-size:1rem; font-weight:700; color:var(--text);">{h['layer_name']}</div>
                        <div style="font-size:.78rem; color:var(--muted); margin:.2rem 0;">
                            🏢 {h.get('organisasi','-')} &nbsp;·&nbsp; 📅 {h.get('tanggal','-')} &nbsp;·&nbsp; 👤 {h.get('penanggung_jawab','-')}
                        </div>
                    </div>
                    <div style="text-align:right; flex-shrink:0;">
                        <div style="font-size:2rem; font-weight:900; color:{sc}; line-height:1;">{skor}</div>
                        <div style="font-size:.75rem; color:{sc}; font-weight:700;">{badge}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Sub-scores expander
            with st.expander(f"📐 Detail Sub-Elemen — {h['layer_name']}", expanded=False):
                sub_df = pd.DataFrame({
                    "Sub Elemen": [
                        "Compliance Code", "Include With Dataset", "Format Nama Layer",
                        "Duplikat Data", "Topologi", "Nama Kolom (Kapital)",
                        "Timeliness", "KUGI", "Metadata", "Commission", "Omission",
                    ],
                    "Nilai": [
                        str(h.get("nilai_compliance_code", "-")),
                        str(h.get("nilai_included", "-")),
                        str(h.get("nilai_nama_mapset", "-")),
                        str(h.get("nilai_duplikat", "-")),
                        str(h.get("nilai_topologi", "-")),
                        str(h.get("nilai_upper_kolom", "-")),
                        str(h.get("nilai_timeliness", "-")),
                        str(h.get("nilai_kugi", "-")),
                        str(h.get("nilai_metadata", "-")),
                        str(h.get("nilai_commission", "-")),
                        str(h.get("nilai_omission", "-")),
                    ],
                })
                st.dataframe(sub_df, use_container_width=True, hide_index=True)

            # Action buttons
            col_dl, col_ulang, col_hapus, _ = st.columns([1.2, 1.2, 1, 3])

            with col_dl:
                # Download PDF
                try:
                    if h.get("report_data"):
                        with st.spinner("Generating PDF..."):
                            pdf_b = generate_pdf(h["report_data"])
                        safe_name = h["layer_name"].replace(" ", "_").replace("/", "-")
                        st.download_button(
                            label="📥  Download PDF",
                            data=pdf_b,
                            file_name=f"kualitas_{safe_name}_{h.get('tanggal','').replace('-','')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}_{h['layer_name'][:10]}",
                        )
                    else:
                        st.button("📥  Download PDF", disabled=True,
                                  key=f"dl_pdf_dis_{idx}", help="Data laporan tidak tersedia")
                except Exception as e:
                    st.button("📥  PDF Error", disabled=True, key=f"dl_err_{idx}",
                              help=str(e))

            with col_ulang:
                if st.button("🔄  Nilai Ulang", key=f"ulang_{idx}_{h['layer_name'][:10]}",
                             help="Arahkan ke Topology Check untuk penilaian ulang"):
                    # Simpan layer yang akan di-recheck ke session
                    st.session_state["recheck_layer"] = h["layer_name"]
                    st.info("ℹ️ Buka halaman **Topology Check** dan pilih mapset yang sama untuk melakukan penilaian ulang.")

            with col_hapus:
                if st.button("🗑️  Hapus", key=f"hapus_{idx}_{h['layer_name'][:10]}",
                             help="Hapus hasil penilaian ini dari rekap"):
                    if h in st.session_state["scoring_history"]:
                        st.session_state["scoring_history"].remove(h)
                        save_history(st.session_state["scoring_history"])
                    st.rerun()

            st.markdown("")

    # ── EXPORT SEMUA ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📤 Export Semua Data")

    col_exp1, col_exp2, _ = st.columns([1.5, 1.5, 3])
    with col_exp1:
        # Export CSV
        export_rows = []
        for h in filtered:
            export_rows.append({
                "Mapset":             h["layer_name"],
                "Organisasi":         h.get("organisasi", "-"),
                "Skor":               h["skor"],
                "Status":             h["status"],
                "Tanggal":            h.get("tanggal", "-"),
                "Penanggung Jawab":   h.get("penanggung_jawab", "-"),
                "Compliance Code":    h.get("nilai_compliance_code", "-"),
                "Include With Dataset": h.get("nilai_included", "-"),
                "Format Nama Layer":  h.get("nilai_nama_mapset", "-"),
                "Duplikat Data":      h.get("nilai_duplikat", "-"),
                "Topologi":           h.get("nilai_topologi", "-"),
                "Upper Kolom":        h.get("nilai_upper_kolom", "-"),
                "Timeliness":         h.get("nilai_timeliness", "-"),
                "KUGI":               h.get("nilai_kugi", "-"),
                "Metadata":           h.get("nilai_metadata", "-"),
                "Commission":         h.get("nilai_commission", "-"),
                "Omission":           h.get("nilai_omission", "-"),
            })
        if export_rows:
            csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8")
            st.download_button(
                "📊  Export CSV (semua)",
                data=csv_bytes,
                file_name=f"rekap_scoring_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with col_exp2:
        # Hapus semua
        if st.button("🗑️  Hapus Semua Rekap", width="stretch"):
            st.session_state["scoring_history"] = []
            save_history([])
            st.rerun()
