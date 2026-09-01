"""Sinkronisasi data penetapan Bapenda ke cache MySQL lokal."""

from datetime import datetime
import re
from collections.abc import Callable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CACHE_TABLE = "realisasi_pajak_cache"
SYNC_TABLE = "realisasi_pajak_sync_log"
REQUIRED_COLUMNS = {"periode", "wilayah", "realisasi_pkb", "realisasi_bbn", "opsen_pkb", "opsen_bbn"}
PKB_COLUMNS = ["PokokPKB", "PokokPKBT1", "PokokPKBT2", "PokokPKBT3", "PokokPKBT4", "PokokPKBT5", "DendaPKB", "DendaPKBT1", "DendaPKBT2", "DendaPKBT3", "DendaPKBT4", "DendaPKBT5", "DendaKasPKB"]
BBN_COLUMNS = ["PokokBBN", "PokokBBNT1", "PokokBBNT2", "PokokBBNT3", "PokokBBNT4", "PokokBBNT5", "DendaBBN", "DendaBBNT1", "DendaBBNT2", "DendaBBNT3", "DendaBBNT4", "DendaBBNT5", "DendaKasBBN"]
OPSEN_PKB_COLUMNS = ["PokokPKB_Opsen", "PokokPKB_OpsenT1", "PokokPKB_OpsenT2", "PokokPKB_OpsenT3", "PokokPKB_OpsenT4", "PokokPKB_OpsenT5", "DendaPKB_Opsen", "DendaPKB_OpsenT1", "DendaPKB_OpsenT2", "DendaPKB_OpsenT3", "DendaPKB_OpsenT4", "DendaPKB_OpsenT5"]
OPSEN_BBN_COLUMNS = ["PokokBBN_Opsen", "DendaBBN_Opsen"]


def _local_engine(local_database_url: str):
    if not local_database_url:
        raise ValueError("LOCAL_DATABASE_URL belum diisi pada berkas .env.")
    url = make_url(local_database_url)
    database_name = url.database
    if not database_name or not _IDENTIFIER.fullmatch(database_name):
        raise ValueError("Nama database lokal harus berupa identifier MySQL yang valid.")
    if not url.drivername.startswith("mysql"):
        raise ValueError("Database cache lokal harus menggunakan MySQL/MariaDB.")
    server_engine = create_engine(url.set(database=None), pool_pre_ping=True)
    try:
        with server_engine.begin() as connection:
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4"))
    finally:
        server_engine.dispose()
    return create_engine(local_database_url, pool_pre_ping=True)


def prepare_dashboard_data(data: pd.DataFrame) -> pd.DataFrame:
    """Pertahankan seluruh kolom CSV dan tambahkan kolom perhitungan dashboard."""
    data = data.copy()
    data.columns = data.columns.astype(str).str.strip().str.lstrip("\ufeff")
    if data.empty:
        raise ValueError("CSV tidak memiliki baris data.")
    if not REQUIRED_COLUMNS.issubset(data.columns):
        date_column = next((column for column in ("TglDaftar", "TglCetakSKPD") if column in data.columns), None)
        region_column = next(
            (column for column in ("NamaWilayah", "UPT", "Lokasi_Bayar") if column in data.columns), None
        )
        if not date_column or not region_column:
            raise ValueError(
                "CSV harus memiliki kolom ringkas atau kolom ekspor penetapan: "
                "periode/wilayah, atau TglDaftar/TglCetakSKPD dan NamaWilayah/UPT/Lokasi_Bayar"
            )

        def sum_columns(columns: list[str]) -> pd.Series:
            available = [column for column in columns if column in data.columns]
            if not available:
                return pd.Series(0, index=data.index, dtype="float64")
            return data[available].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)

        # Kolom asli CSV tetap disimpan; enam kolom ini ditambahkan untuk dashboard.
        data["periode"] = data[date_column]
        data["wilayah"] = data[region_column]
        data["realisasi_pkb"] = sum_columns(PKB_COLUMNS)
        data["realisasi_bbn"] = sum_columns(BBN_COLUMNS)
        data["opsen_pkb"] = sum_columns(OPSEN_PKB_COLUMNS)
        data["opsen_bbn"] = sum_columns(OPSEN_BBN_COLUMNS)
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Kolom wajib dari query belum tersedia: {', '.join(sorted(missing))}")
    raw_period = data["periode"].astype("string").str.strip()
    # Ekspor sumber menggunakan jam bertitik, mis. 02/01/2026 08.08
    # atau 2026-01-02 08.08.23. Ubah titik pada bagian waktu menjadi titik dua.
    raw_period = raw_period.str.replace(
        r"(\s\d{1,2})\.(\d{2})\.(\d{2})$", r"\1:\2:\3", regex=True
    )
    raw_period = raw_period.str.replace(r"(\s\d{1,2})\.(\d{2})$", r"\1:\2", regex=True)
    try:
        data["periode"] = pd.to_datetime(raw_period, format="mixed", dayfirst=True, errors="coerce")
    except (TypeError, ValueError):
        data["periode"] = pd.to_datetime(raw_period, dayfirst=True, errors="coerce")
    valid_period_count = data["periode"].notna().sum()
    if valid_period_count == 0:
        examples = ", ".join(map(str, raw_period.dropna().head(3).tolist())) or "kosong"
        raise ValueError(
            "Tidak ada tanggal yang dapat dibaca pada kolom periode/TglCetakSKPD. "
            f"Contoh nilai yang ditemukan: {examples}"
        )
    data = data.dropna(subset=["periode"])
    for column in ("realisasi_pkb", "realisasi_bbn", "opsen_pkb", "opsen_bbn"):
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    data["realisasi_pajak"] = data[["realisasi_pkb", "realisasi_bbn", "opsen_pkb", "opsen_bbn"]].sum(axis=1)
    data["wilayah"] = data["wilayah"].fillna("Tidak diketahui")
    return data


def sync_from_csv(
    uploaded_file,
    local_database_url: str,
    progress_callback: Callable[[int, int], None] | None = None,
    batch_size: int = 1_000,
) -> int:
    """Simpan data realisasi dari CSV sebagai snapshot cache lokal terbaru."""
    try:
        raw_data = pd.read_csv(uploaded_file, sep=None, engine="python")
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        raw_data = pd.read_csv(uploaded_file, sep=None, engine="python", encoding="latin1")
    data = prepare_dashboard_data(raw_data)
    if data.empty:
        raise ValueError("Tidak ada baris valid yang dapat disimpan dari CSV.")
    total_records = len(data)
    if progress_callback:
        progress_callback(0, total_records)

    local_engine = _local_engine(local_database_url)
    try:
        # Buat ulang snapshot terlebih dahulu, lalu masukkan data secara bertahap
        # agar antarmuka dapat menampilkan progres penyimpanan yang nyata.
        data.head(0).to_sql(CACHE_TABLE, local_engine, if_exists="replace", index=False)
        saved_records = 0
        for start in range(0, total_records, batch_size):
            batch = data.iloc[start : start + batch_size]
            batch.to_sql(CACHE_TABLE, local_engine, if_exists="append", index=False, method="multi")
            saved_records += len(batch)
            if progress_callback:
                progress_callback(saved_records, total_records)
        pd.DataFrame([{"synced_at": datetime.now(), "record_count": len(data)}]).to_sql(
            SYNC_TABLE, local_engine, if_exists="replace", index=False
        )
    finally:
        local_engine.dispose()
    return len(data)


def load_local_cache(local_database_url: str) -> pd.DataFrame:
    """Dashboard selalu membaca tabel cache lokal."""
    local_engine = _local_engine(local_database_url)
    try:
        with local_engine.connect() as connection:
            data = pd.read_sql(text(f"SELECT * FROM `{CACHE_TABLE}`"), connection)
    finally:
        local_engine.dispose()
    return prepare_dashboard_data(data)


def get_last_sync(local_database_url: str) -> pd.Timestamp | None:
    local_engine = _local_engine(local_database_url)
    try:
        with local_engine.connect() as connection:
            result = connection.execute(text(f"SELECT synced_at FROM `{SYNC_TABLE}` LIMIT 1")).scalar()
    finally:
        local_engine.dispose()
    return pd.to_datetime(result) if result else None
