# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    # GDAL untuk geopandas
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    # Build tools
    gcc \
    g++ \
    # Curl untuk healthcheck
    curl \
    # Bersihkan cache
    && rm -rf /var/lib/apt/lists/*

# ── Set environment ───────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GDAL_CONFIG=/usr/bin/gdal-config

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────────────────────
COPY . .

# ── Buat direktori data (untuk scoring_history.json) ─────────────────────────
RUN mkdir -p /app/data

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 8501

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Run ───────────────────────────────────────────────────────────────────────
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]