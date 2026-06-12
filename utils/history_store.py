"""
Persistent history store — menyimpan hasil penilaian ke file JSON di server.
Sehingga data tidak hilang saat Streamlit di-refresh.

File disimpan di: {project_root}/data/scoring_history.json
"""
import os
import json
import logging
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "..", "data")
_HISTORY_FILE = os.path.join(_DATA_DIR, "scoring_history.json")


def _ensure_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def load_history() -> list:
    """Load history dari file JSON. Return list (kosong jika belum ada)."""
    _ensure_dir()
    if not os.path.exists(_HISTORY_FILE):
        return []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # pdf_bytes tidak di-serialize (bytes tidak JSON-serializable)
            for item in data:
                item.pop("pdf_bytes", None)
            return data
    except Exception as e:
        logging.warning(f"Gagal load history: {e}")
        return []


def save_history(history: list):
    """Simpan history ke file JSON. pdf_bytes dibuang (tidak serializable)."""
    _ensure_dir()
    try:
        safe = []
        for item in history:
            entry = {k: v for k, v in item.items()
                     if k != "pdf_bytes" and _is_json_serializable(v)}
            safe.append(entry)
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(safe, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logging.warning(f"Gagal simpan history: {e}")


def _is_json_serializable(v) -> bool:
    try:
        json.dumps(v, default=str)
        return True
    except Exception:
        return False


def upsert_entry(history: list, entry: dict) -> list:
    """
    Tambah atau update entry berdasarkan layer_name + tanggal.
    Return list history yang sudah diupdate.
    """
    key = (entry.get("layer_name", ""), entry.get("tanggal", ""))
    for i, h in enumerate(history):
        if (h.get("layer_name", ""), h.get("tanggal", "")) == key:
            history[i] = entry
            return history
    history.append(entry)
    return history
