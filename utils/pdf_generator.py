"""
PDF Generator — Generate PDF menggunakan ReportLab (pure Python).
100% portable, tidak butuh LibreOffice, berjalan di Streamlit Cloud.

Layout mengikuti template DOCX asli:
- Kop surat Diskominfo Jawa Barat (logo + teks)
- Garis pembatas
- Judul formulir
- Informasi Umum
- Hasil Penilaian (Conformity, Uniqueness, Consistency, Timelines, Completeness)
- Status Kualitas Data & Rekomendasi
"""
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_HERE         = os.path.dirname(os.path.abspath(__file__))
_ASSETS       = os.path.join(_HERE, "..", "assets")
_LOGO_PATH    = os.path.join(_ASSETS, "logo_diskominfo.png")
TEMPLATE_PATH = os.path.normpath(os.path.join(_HERE, "..", "data_template", "template_form_kualitas_data.docx"))

# ── Warna (mengikuti palette app) ─────────────────────────────────────────────
BLACK  = colors.black
WHITE  = colors.white
GRAY   = colors.HexColor("#555555")
LGRAY  = colors.HexColor("#AAAAAA")
BLUE   = colors.HexColor("#1A3A6B")   # biru Diskominfo
TEAL   = colors.HexColor("#00796B")
GREEN  = colors.HexColor("#2E7D32")
AMBER  = colors.HexColor("#E65100")
RED    = colors.HexColor("#B71C1C")
LBLUE  = colors.HexColor("#E3F0FF")   # bg header tabel
LGREEN = colors.HexColor("#E8F5E9")
LRED   = colors.HexColor("#FFEBEE")


# ── Styles ────────────────────────────────────────────────────────────────────
def _style(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=BLACK, spaceAfter=2, spaceBefore=2)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

ST_KOP_INST   = _style("kop_inst",  fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=TA_CENTER)
ST_KOP_DINAS  = _style("kop_dinas", fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=TA_CENTER)
ST_KOP_ADDR   = _style("kop_addr",  fontSize=8.5, leading=12, alignment=TA_CENTER, textColor=GRAY)

ST_TITLE      = _style("title",  fontName="Helvetica-Bold", fontSize=13, leading=17, alignment=TA_CENTER, spaceAfter=2)
ST_SUBTITLE   = _style("subtit", fontName="Helvetica-Bold", fontSize=12, leading=16, alignment=TA_CENTER, spaceAfter=6)

ST_SECTION    = _style("section", fontName="Helvetica-Bold", fontSize=11, leading=14,
                        textColor=BLUE, spaceBefore=8, spaceAfter=4)
ST_SUBSECTION = _style("subsect", fontName="Helvetica-Bold", fontSize=10, leading=13,
                        textColor=TEAL, spaceBefore=6, spaceAfter=3)

ST_LABEL      = _style("label",  fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=GRAY)
ST_VALUE      = _style("value",  fontSize=9.5, leading=13)
ST_BODY       = _style("body",   fontSize=10, leading=14, alignment=TA_JUSTIFY)
ST_BOLD_BODY  = _style("bbody",  fontName="Helvetica-Bold", fontSize=10, leading=14, alignment=TA_JUSTIFY)
ST_SMALL      = _style("small",  fontSize=8, leading=11, textColor=GRAY)


def _val(v):
    """Render nilai — ganti None/kosong dengan tanda strip."""
    s = str(v).strip() if v is not None else ""
    return s if s and s not in ("None", "nan", "-") else "—"


def _score_color(skor):
    try:
        s = float(str(skor).replace("%", ""))
    except Exception:
        return BLACK
    if s > 90:   return GREEN
    if s > 75:   return TEAL
    if s >= 60:  return AMBER
    return RED


def _score_bg(skor):
    try:
        s = float(str(skor).replace("%", ""))
    except Exception:
        return WHITE
    if s > 90:   return LGREEN
    if s > 75:   return colors.HexColor("#E0F2F1")
    if s >= 60:  return colors.HexColor("#FFF3E0")
    return LRED


# ── KOP SURAT ─────────────────────────────────────────────────────────────────
def _build_kop() -> Table:
    """Kop surat: logo kiri, teks kanan — persis seperti template DOCX."""
    # Logo
    if os.path.exists(_LOGO_PATH):
        logo = RLImage(_LOGO_PATH, width=1.8*cm, height=2.1*cm)
    else:
        logo = Paragraph("", ST_BODY)

    # Teks kop
    kop_content = [
        Paragraph("PEMERINTAH DAERAH PROVINSI JAWA BARAT", ST_KOP_INST),
        Paragraph("DINAS KOMUNIKASI DAN INFORMATIKA", ST_KOP_DINAS),
        Spacer(1, 2),
        Paragraph("Jalan Tamansari No. 55 Tlp. (022) 2502898 Faksimili (022) 2511505", ST_KOP_ADDR),
        Paragraph("Website: https://diskominfo.jabarprov.go.id  email: diskominfo@jabarprov.go.id", ST_KOP_ADDR),
        Paragraph("Bandung 40132", ST_KOP_ADDR),
    ]

    tbl = Table([[logo, kop_content]], colWidths=[2.5*cm, 14.5*cm])
    tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (0, 0), (0, 0),   "CENTER"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    return tbl


# ── INFO ROW (label : value) ───────────────────────────────────────────────────
def _info_row(label: str, value: str) -> Table:
    tbl = Table(
        [[Paragraph(label, ST_LABEL), Paragraph(_val(value), ST_VALUE)]],
        colWidths=[5.5*cm, 11.5*cm]
    )
    tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    return tbl


# ── PENILAIAN ROW ──────────────────────────────────────────────────────────────
def _penilaian_row(label: str, value: str, is_header=False) -> Table:
    if is_header:
        style = TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), LBLUE),
            ("TEXTCOLOR",     (0,0), (-1,-1), BLUE),
            ("FONTNAME",      (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("BOX",           (0,0), (-1,-1), 0.5, BLUE),
        ])
        cell = [Paragraph(label, _style("h", fontName="Helvetica-Bold", fontSize=10, textColor=BLUE))]
        tbl = Table([cell], colWidths=[17*cm])
    else:
        style = TableStyle([
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (0,-1),  24),  # indent label
            ("LEFTPADDING",   (1,0), (1,-1),  6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, colors.HexColor("#DDDDDD")),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ])
        tbl = Table(
            [[Paragraph(label, ST_LABEL), Paragraph(_val(value), ST_VALUE)]],
            colWidths=[6*cm, 11*cm]
        )
    tbl.setStyle(style)
    return tbl


# ── SCORE BOX ─────────────────────────────────────────────────────────────────
def _score_box(skor, status) -> Table:
    sc = _score_color(skor)
    bg = _score_bg(skor)
    skor_str = str(skor)
    data = [[
        Paragraph(
            f'<font color="#{sc.hexval()[2:]}"><b>{skor_str}</b></font>',
            _style("sc_num", fontSize=26, leading=30, alignment=TA_CENTER)
        ),
        Paragraph(
            f'<font color="#{sc.hexval()[2:]}"><b>{status}</b></font>',
            _style("sc_st", fontName="Helvetica-Bold", fontSize=14, leading=18, alignment=TA_CENTER)
        ),
    ]]
    tbl = Table(data, colWidths=[4*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), bg),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("BOX",           (0,0), (-1,-1), 1.5, sc),
        ("LINEBEFORE",    (0,0), (0,-1),  4, sc),
    ]))
    return tbl


# ── MAIN GENERATE ─────────────────────────────────────────────────────────────
def generate_pdf(data: dict, template_path: str = None) -> bytes:
    """
    Generate PDF laporan kualitas data menggunakan ReportLab.
    Mengikuti struktur template DOCX: kop surat, informasi umum,
    hasil penilaian per kategori, status & rekomendasi.

    Args:
        data: dict placeholder (key tanpa kurung siku).
        template_path: tidak digunakan (kept for API compatibility).

    Returns:
        bytes PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
        title=f"Laporan Kualitas Data - {data.get('mapset', 'Layer')}",
        author="GIS Quality Dashboard - Diskominfo Jawa Barat",
    )

    elems = []

    # ── KOP SURAT ─────────────────────────────────────────────────────────────
    elems.append(_build_kop())
    elems.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=BLUE, spaceAfter=8))

    # ── JUDUL ─────────────────────────────────────────────────────────────────
    elems.append(Paragraph("FORMULIR QUALITY CONTROL (QC)", ST_TITLE))
    elems.append(Paragraph("SCORING KUALITAS DATA GEOSPASIAL", ST_SUBTITLE))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=8))

    # ── INFORMASI UMUM ────────────────────────────────────────────────────────
    elems.append(Paragraph("Informasi Umum", ST_SECTION))

    info_fields = [
        ("Judul Mapset",         data.get("Judul Mapset")),
        ("SKPD / Organisasi",    data.get("Nama Organisasi")),
        ("Tipe Mapset",          data.get("Mapset Type")),
        ("Sumber Mapservice",    data.get("Sumber Mapservice")),
        ("Link Mapservice",      data.get("Mapservice Link")),
        ("Deskripsi",            data.get("Description")),
        ("Tanggal Penilaian",    data.get("Tanggal Penilaian")),
        ("Penanggung Jawab",     data.get("Nama Penanggung Jawab")),
    ]
    info_rows = [[Paragraph(l, ST_LABEL), Paragraph(_val(v), ST_VALUE)] for l, v in info_fields]

    info_tbl = Table(info_rows, colWidths=[5*cm, 12*cm])
    info_tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [colors.white, colors.HexColor("#F8F9FA")]),
        ("LINEBELOW",    (0,0), (-1,-2), 0.3, colors.HexColor("#E0E0E0")),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEBEFORE",   (0,0), (0,-1),  3, BLUE),
    ]))
    elems.append(info_tbl)
    elems.append(Spacer(1, 10))

    # ── HASIL PENILAIAN ───────────────────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=4))
    elems.append(Paragraph("Hasil Penilaian Kualitas Data", ST_SECTION))

    # Tabel penilaian
    penilaian_header = ["Sub Elemen Penilaian", "Keterangan / Hasil"]
    penilaian_data = [
        # Conformity
        ("CONFORMITY", None, True),
        ("Compliance Code Metadata",            data.get("comformity_1"), False),
        ("Included With Dataset Metadata",       data.get("comformity_2"), False),
        ("Format Penamaan Layer",               data.get("comformity_3"), False),
        # Uniqueness
        ("UNIQUENESS", None, True),
        ("Duplikat Data",                       data.get("duplikat_data"), False),
        # Consistency
        ("CONSISTENCY", None, True),
        ("Cek Topology",                        data.get("topology_check"), False),
        ("Nama Kolom Huruf Besar",              data.get("kolom_huruf_besar"), False),
        # Timelines
        ("TIMELINES", None, True),
        ("Keterbaruan Data",                    data.get("tahun_data"), False),
        # Completeness
        ("COMPLETENESS", None, True),
        ("Penilaian KUGI",                      data.get("keterisian"), False),
        ("Keterisian Field Mandatory Metadata", data.get("metadata"), False),
        ("Completeness Commission",             data.get("commission"), False),
        ("Completeness Omission",               data.get("omission"), False),
    ]

    tbl_header = [
        Paragraph(penilaian_header[0], _style("th0", fontName="Helvetica-Bold", fontSize=9.5,
                                               textColor=WHITE, alignment=TA_CENTER)),
        Paragraph(penilaian_header[1], _style("th1", fontName="Helvetica-Bold", fontSize=9.5,
                                               textColor=WHITE, alignment=TA_CENTER)),
    ]
    rows = [tbl_header]
    row_styles = [
        ("BACKGROUND",    (0,0), (-1,0), BLUE),
        ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",         (0,0), (-1,0), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, colors.HexColor("#E0E0E0")),
    ]

    for i, (label, value, is_hdr) in enumerate(penilaian_data):
        ri = i + 1  # row index (header is 0)
        if is_hdr:
            rows.append([
                Paragraph(label, _style(f"cat{i}", fontName="Helvetica-Bold", fontSize=9.5, textColor=BLUE)),
                Paragraph("", ST_BODY),
            ])
            row_styles += [
                ("BACKGROUND",    (0,ri), (-1,ri), LBLUE),
                ("TEXTCOLOR",     (0,ri), (-1,ri), BLUE),
                ("FONTNAME",      (0,ri), (-1,ri), "Helvetica-Bold"),
                ("SPAN",          (0,ri), (-1,ri)),
            ]
        else:
            rows.append([
                Paragraph(f"  {label}", _style(f"l{i}", fontSize=9.5, textColor=GRAY)),
                Paragraph(_val(value), ST_VALUE),
            ])
            if i % 2 == 0:
                row_styles.append(("BACKGROUND", (0,ri), (-1,ri), colors.HexColor("#F8F9FA")))

    pen_tbl = Table(rows, colWidths=[7*cm, 10*cm])
    pen_tbl.setStyle(TableStyle(row_styles))
    elems.append(pen_tbl)
    elems.append(Spacer(1, 12))

    # ── STATUS & SKOR ─────────────────────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=4))
    elems.append(Paragraph("Status Kualitas Data", ST_SECTION))

    skor   = data.get("nilai", "0")
    status = data.get("Status", "—")
    elems.append(_score_box(skor, status))
    elems.append(Spacer(1, 8))

    # Kalimat status (persis dari template)
    mapset = _val(data.get("mapset"))
    elems.append(Paragraph(
        f"Berdasarkan hasil penilaian, nilai mapset <b>{mapset}</b> adalah "
        f"<b>{skor}</b> dengan status kualitas data geospasial dinyatakan sebagai "
        f"<b>{status}</b>.",
        ST_BODY
    ))
    elems.append(Spacer(1, 8))

    # ── REKOMENDASI ───────────────────────────────────────────────────────────
    elems.append(Paragraph("Rekomendasi", ST_SUBSECTION))
    rekomendasi = _val(data.get("rekomendasi"))
    if rekomendasi == "—":
        rekomendasi = "Data telah memenuhi standar kualitas data geospasial yang ditetapkan."
    elems.append(Paragraph(rekomendasi, ST_BODY))
    elems.append(Spacer(1, 12))

    doc.build(elems)
    buf.seek(0)
    return buf.read()
