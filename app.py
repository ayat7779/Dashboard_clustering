"""Dashboard BI interaktif untuk transaksi PKB dan BBNKB."""

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from src.data_loader import get_last_sync, load_local_cache, sync_from_csv


NAVY = "#0B1F3A"
EMERALD = "#047857"
CHART_COLORS = [EMERALD, "#0F766E", "#0EA5A4", "#1D4ED8", "#F59E0B"]

load_dotenv()
st.set_page_config(page_title="BI PKB & BBNKB", page_icon="📊", layout="wide")

# CSS kustom untuk styling metric, termasuk metric card khusus dengan warna berbeda
st.markdown(f"""
<style>
.stApp {{background:#F8FAFC}} 
[data-testid="stMetric"] {{
    background: white;
    border-top: 4px solid {EMERALD};
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(15,23,42,.08);
}}
/* Desain khusus untuk card jumlah transaksi (Warna Biru Aksen) */
[data-testid="stMetric"].metric-custom-transaksi {{
    background: #EFF6FF !important;
    border-top: 4px solid #1D4ED8 !important;
}}
/* Desain khusus untuk card Total Loket Pembayaran (Warna Kuning/Amber Gelap Aksen) */
[data-testid="stMetric"].metric-custom-loket {{
    background: #FEFCE8 !important;
    border-top: 4px solid #CA8A04 !important;
}}
/* Desain khusus untuk card Total BBN (Warna Oranye/Amber Aksen) */
[data-testid="stMetric"].metric-custom-bbn {{
    background: #FFFBEB !important;
    border-top: 4px solid #F59E0B !important;
}}
/* Desain khusus untuk card Jumlah Kabupaten/Kota (Warna Indigo Aksen) */
[data-testid="stMetric"].metric-custom-kabkota {{
    background: #EEF2FF !important;
    border-top: 4px solid #4F46E5 !important;
}}
/* Desain khusus untuk card Total Denda BBNKB (Warna Ungu/Purple Aksen) */
[data-testid="stMetric"].metric-custom-dendabbn {{
    background: #FAF5FF !important;
    border-top: 4px solid #7C3AED !important;
}}
/* Desain khusus untuk card Total SWDKLJJ (Warna Rose/Pink Aksen) */
[data-testid="stMetric"].metric-custom-swdklijj {{
    background: #FFF1F2 !important;
    border-top: 4px solid #E11D48 !important;
}}
/* Desain khusus untuk card Total Opsen BBNKB (Warna Cyan/Teal Aksen) */
[data-testid="stMetric"].metric-custom-opsenbbn {{
    background: #ECFEFF !important;
    border-top: 4px solid #0891B2 !important;
}}
/* Desain khusus untuk card Total PNBP Kepolisian (Warna Lime/Green-Yellow Aksen) */
[data-testid="stMetric"].metric-custom-pnbp {{
    background: #F7FEE7 !important;
    border-top: 4px solid #65A30D !important;
}}
h1, h2, h3 {{color: {NAVY}}}
</style>
""", unsafe_allow_html=True)

local_database_url = os.getenv("LOCAL_DATABASE_URL", "")


@st.cache_data(ttl=300, show_spinner="Membaca cache database lokal...")
def get_local_data(database_url: str) -> pd.DataFrame:
    return load_local_cache(database_url)


def first_existing_column(data: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(column).strip().casefold(): column for column in data.columns}
    return next((normalized[name.casefold()] for name in candidates if name.casefold() in normalized), None)


def sum_columns_with_prefix(data: pd.DataFrame, prefix: str) -> pd.Series:
    columns = [column for column in data.columns if str(column).casefold().startswith(prefix.casefold())]
    return data[columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) if columns else pd.Series(0.0, index=data.index)


def vehicle_group(value: object) -> str:
    label = str(value).upper()
    if any(token in label for token in ("R2", "RODA 2", "SEPEDA MOTOR", "MOTOR")):
        return "R2 / Sepeda Motor"
    if any(token in label for token in ("R4", "RODA 4", "MINIBUS", "MOBIL")):
        return "R4 / Mobil"
    return "Lainnya"


def format_indo_date(date_obj) -> str:
    """Format tanggal ke bentuk dd mmmm yyyy dalam bahasa Indonesia."""
    months = {
        1: "januari", 2: "februari", 3: "maret", 4: "april",
        5: "mei", 6: "juni", 7: "juli", 8: "agustus",
        9: "september", 10: "oktober", 11: "november", 12: "desember"
    }
    day = date_obj.strftime("%d")
    month = months.get(date_obj.month, "")
    year = date_obj.strftime("%Y")
    return f"{day} {month} {year}"


def build_bi_dataset(data: pd.DataFrame) -> pd.DataFrame:
    """Standarkan variasi nama kolom ekspor transaksi untuk visual BI."""
    result = data.copy()
    date_column = first_existing_column(result, ["periode", "TglDaftar", "TglCetakSKPD"])
    region_column = first_existing_column(result, ["NamaWilayah", "UPT", "Lokasi_Bayar", "wilayah"])
    loket_column = first_existing_column(result, ["Lokasi_Bayar", "LokasiBayar", "Loket"])
    vehicle_column = first_existing_column(result, ["Jenis_Kendaraan", "JenisKendaraan", "Jenis Kendaraan"])
    registration_column = first_existing_column(result, ["Jenis_Pendaftaran", "JenisPendaftaran", "Jenis Pendaftaran"])
    plate_column = first_existing_column(result, ["Nopol", "NoPol", "No_Polisi", "Nomor_Polisi"])
    brand_column = first_existing_column(result, ["Merk", "Merek"])
    model_column = first_existing_column(result, ["Model", "Tipe"])
    
    pokok_pkb_columns = [
        column
        for name in ("PokokPKB", "PokokPKBT1", "PokokPKBT2", "PokokPKBT3", "PokokPKBT4", "PokokPKBT5")
        if (column := first_existing_column(result, [name]))
    ]
    denda_pkb_columns = [
        column
        for name in ("DendaPKB", "DendaPKBT1", "DendaPKBT2", "DendaPKBT3", "DendaPKBT4", "DendaPKBT5", "DendaKasPKB")
        if (column := first_existing_column(result, [name]))
    ]
    
    # Kolom Opsen PKB
    opsen_pkb_columns = [
        column
        for name in (
            "PokokPKB_Opsen", "PokokPKB_OpsenT1", "PokokPKB_OpsenT2", "PokokPKB_OpsenT3", "PokokPKB_OpsenT4", "PokokPKB_OpsenT5",
            "DendaPKB_Opsen", "DendaPKB_OpsenT1", "DendaPKB_OpsenT2", "DendaPKB_OpsenT3", "DendaPKB_OpsenT4", "DendaPKB_OpsenT5"
        )
        if (column := first_existing_column(result, [name]))
    ]

    # Kolom Pokok BBN
    pokok_bbn_columns = [
        column
        for name in ("PokokBBN", "PokokBBNT1", "PokokBBNT2", "PokokBBNT3", "PokokBBNT4", "PokokBBNT5")
        if (column := first_existing_column(result, [name]))
    ]

    # Kolom Denda BBNKB
    denda_bbnkb_columns = [
        column
        for name in ("DendaBBN", "DendaBBNT1", "DendaBBNT2", "DendaBBNT3", "DendaBBNT4", "DendaBBNT5", "DendaKasBBN")
        if (column := first_existing_column(result, [name]))
    ]

    # Kolom Opsen BBNKB (PokokBBN_Opsen + DendaBBN_Opsen beserta variasinya jika ada)
    opsen_bbn_columns = [
        column
        for name in ("PokokBBN_Opsen", "DendaBBN_Opsen")
        if (column := first_existing_column(result, [name]))
    ]

    # Kolom SWDKLJJ
    swdkljj_columns = [
        column
        for name in (
            "PokokSWDK", "PokokSWDKT1", "PokokSWDKT2", "PokokSWDKT3", "PokokSWDKT4", "PokokSWDKT5",
            "DendaSWDK", "DendaSWDKT1", "DendaSWDKT2", "DendaSWDKT3", "DendaSWDKT4", "DendaSWDKT5"
        )
        if (column := first_existing_column(result, [name]))
    ]

    # Kolom PNBP Kepolisian (TNKB + STNK + PNBPPengesahan)
    pnbp_columns = [
        column
        for name in ("TNKB", "STNK", "PNBPPengesahan")
        if (column := first_existing_column(result, [name]))
    ]

    total_column = first_existing_column(result, ["Total"])
    result["tgl_daftar"] = pd.to_datetime(result[date_column], errors="coerce")
    result["upt"] = result[region_column].fillna("Tidak diketahui").astype(str)
    result["lokasi_bayar"] = result[loket_column].fillna("Tidak diketahui").astype(str) if loket_column else "Tidak tersedia"
    result["jenis_kendaraan"] = result[vehicle_column].fillna("Lainnya").map(vehicle_group) if vehicle_column else "Tidak tersedia"
    result["jenis_pendaftaran"] = result[registration_column].fillna("Tidak diketahui").astype(str) if registration_column else "Tidak tersedia"
    result["nopol"] = result[plate_column].astype("string") if plate_column else pd.NA
    
    if brand_column or model_column:
        brand = result[brand_column].fillna("").astype(str) if brand_column else ""
        model = result[model_column].fillna("").astype(str) if model_column else ""
        result["merk_model"] = (brand + " " + model).str.strip().replace("", "Tidak diketahui")
    else:
        result["merk_model"] = "Tidak tersedia"
        
    result["total"] = (
        pd.to_numeric(result[total_column], errors="coerce").fillna(0)
        if total_column
        else pd.Series(0.0, index=result.index)
    )
    result["pokok_pkb"] = (
        result[pokok_pkb_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if pokok_pkb_columns
        else pd.Series(0.0, index=result.index)
    )
    result["denda_pkb"] = (
        result[denda_pkb_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if denda_pkb_columns
        else pd.Series(0.0, index=result.index)
    )
    result["opsen_pkb"] = (
        result[opsen_pkb_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if opsen_pkb_columns
        else pd.Series(0.0, index=result.index)
    )
    result["pokok_bbn"] = (
        result[pokok_bbn_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if pokok_bbn_columns
        else pd.Series(0.0, index=result.index)
    )
    result["denda_bbnkb"] = (
        result[denda_bbnkb_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if denda_bbnkb_columns
        else pd.Series(0.0, index=result.index)
    )
    result["opsen_bbn"] = (
        result[opsen_bbn_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if opsen_bbn_columns
        else pd.Series(0.0, index=result.index)
    )
    result["swdkljj"] = (
        result[swdkljj_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if swdkljj_columns
        else pd.Series(0.0, index=result.index)
    )
    result["pnbp_kepolisian"] = (
        result[pnbp_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        if pnbp_columns
        else pd.Series(0.0, index=result.index)
    )
    result["denda_bbn"] = sum_columns_with_prefix(result, "DendaBBN")
    result["total_denda"] = result["denda_pkb"] + result["denda_bbn"]
    result["total_pokok"] = result["total"].clip(lower=0)
    return result.dropna(subset=["tgl_daftar"])


def rupiah(value: float) -> str:
    return f"Rp{value:,.0f}".replace(",", ".")


def chart_layout(figure, title: str):
    return figure.update_layout(title=title, template="plotly_white", colorway=CHART_COLORS, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="white", plot_bgcolor="white", font=dict(color=NAVY))


st.title("Dashboard BI Transaksi PKB & BBNKB")
period_caption = st.empty()
filter_container = st.container()
with st.sidebar:
    st.header("Unggah & Simpan Data")
    uploaded_file = st.file_uploader("CSV transaksi PKB/BBNKB", type="csv")
    if st.button("Simpan ke database lokal", type="primary", disabled=uploaded_file is None):
        progress_text, progress_bar = st.empty(), st.progress(0)
        def update_save_progress(saved_records: int, total_records: int) -> None:
            percent = int(saved_records / total_records * 100) if total_records else 0
            progress_bar.progress(percent)
            progress_text.caption(f"Menyimpan: {percent}% ({saved_records:,}/{total_records:,} baris)")
        try:
            progress_text.caption("Memvalidasi file CSV...")
            records = sync_from_csv(uploaded_file, local_database_url, update_save_progress)
            get_local_data.clear()
            progress_bar.progress(100)
            progress_text.caption(f"Penyimpanan selesai: 100% ({records:,} baris).")
            st.success(f"Data berhasil disimpan: {records:,} baris.")
        except (ValueError, SQLAlchemyError) as error:
            progress_bar.empty(); progress_text.empty()
            st.error(f"Sinkronisasi gagal: {error}")

try:
    raw_data, last_sync = get_local_data(local_database_url), get_last_sync(local_database_url)
except (ValueError, SQLAlchemyError) as error:
    st.warning("Cache lokal belum tersedia.")
    st.markdown("Lengkapi `.env`, aktifkan MySQL lokal, unggah CSV, lalu klik **Simpan ke database lokal**.")
    st.caption(str(error)); st.stop()

data = build_bi_dataset(raw_data)
if data.empty:
    st.warning("Tidak ada data transaksi dengan tanggal valid untuk ditampilkan."); st.stop()
if last_sync:
    st.caption(f"Cache terakhir diperbarui: {last_sync:%d-%m-%Y %H:%M:%S}")

with filter_container:
    st.markdown("#### Filter Global")
    min_date, max_date = data["tgl_daftar"].min().date(), data["tgl_daftar"].max().date()
    start_filter, end_filter, upt_filter, vehicle_filter = st.columns(4)
    start_date = start_filter.date_input("Tanggal Awal Daftar", min_date, min_value=min_date, max_value=max_date)
    end_date = end_filter.date_input("Tanggal Akhir Daftar", max_date, min_value=min_date, max_value=max_date)
    selected_upt = upt_filter.multiselect("Nama Wilayah / UPT", sorted(data["upt"].unique()))
    vehicle_options = sorted(data.loc[data["jenis_kendaraan"] != "Tidak tersedia", "jenis_kendaraan"].unique())
    selected_vehicle = vehicle_filter.multiselect("Jenis Kendaraan", vehicle_options)

start_date_str = format_indo_date(start_date)
end_date_str = format_indo_date(end_date)

period_caption.caption(
    "Monitoring pendapatan, transaksi, kepatuhan, dan kinerja wilayah • "
    f"periode {start_date_str} hingga {end_date_str}"
)

filtered = data.copy()
if start_date > end_date:
    st.error("TglAwal tidak boleh lebih besar dari TglAkhir."); st.stop()
filtered = filtered[filtered["tgl_daftar"].dt.date.between(start_date, end_date)]
if selected_upt: filtered = filtered[filtered["upt"].isin(selected_upt)]
if selected_vehicle: filtered = filtered[filtered["jenis_kendaraan"].isin(selected_vehicle)]
if filtered.empty:
    st.info("Tidak ada transaksi yang sesuai dengan filter."); st.stop()

st.subheader("Ringkasan Eksekutif")
total_revenue, total_pokok_pkb, total_denda_pkb, total_opsen_pkb, total_bbn, total_denda_bbnkb, total_opsen_bbn, total_swdkljj, total_pnbp = (
    filtered["total"].sum(), 
    filtered["pokok_pkb"].sum(), 
    filtered["denda_pkb"].sum(), 
    filtered["opsen_pkb"].sum(),
    filtered["pokok_bbn"].sum(),
    filtered["denda_bbnkb"].sum(),
    filtered["opsen_bbn"].sum(),
    filtered["swdkljj"].sum(),
    filtered["pnbp_kepolisian"].sum()
)

total_rows_count = len(filtered)
total_loket_count = filtered["lokasi_bayar"].nunique(dropna=True) if "lokasi_bayar" in filtered else 0
total_kabkota_count = filtered["upt"].nunique(dropna=True) if "upt" in filtered else 0

# Layout KPI Card (4 kolom utama)
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Pendapatan Pajak", rupiah(total_revenue))
    # Card Jumlah Transaksi di bawah Total Pendapatan Pajak
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-transaksi" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Jumlah Transaksi</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{total_rows_count:,}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    # Card Total Loket Pembayaran di bawah Card Jumlah Transaksi pada kolom 1
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-loket" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total Loket Pembayaran</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{total_loket_count:,}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with col2:
    st.metric("Total PKB", rupiah(total_pokok_pkb))
    # Card Total BBN di bawah Total PKB
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-bbn" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total BBNKB</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{rupiah(total_bbn)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    # Card Jumlah Kabupaten/Kota di bawah Card Total BBNKB pada kolom 2
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-kabkota" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Jumlah Kabupaten/Kota</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{total_kabkota_count:,}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with col3:
    st.metric("Total Denda PKB", rupiah(total_denda_pkb))
    # Card Total Denda BBNKB di bawah Total Denda PKB
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-dendabbn" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total Denda BBNKB</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{rupiah(total_denda_bbnkb)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    # Card Total SWDKLJJ di bawah Total Denda BBNKB pada kolom 3
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-swdklijj" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total SWDKLJJ</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{rupiah(total_swdkljj)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

with col4:
    st.metric("Total Opsen PKB", rupiah(total_opsen_pkb))
    # Card Total Opsen BBNKB di bawah Total Opsen PKB
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-opsenbbn" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total Opsen BBNKB</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{rupiah(total_opsen_bbn)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    # Card Total PNBP Kepolisian di bawah Total Opsen BBNKB pada kolom 4
    st.markdown(
        f'<div data-testid="stMetric" class="metric-custom-pnbp" style="margin-top: 16px;">'
        f'<label style="color: #475569; font-size: 14px;">Total PNBP Kepolisian</label>'
        f'<div style="font-size: 24px; font-weight: 600; color: #0F172A;">{rupiah(total_pnbp)}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

st.subheader("Analisis Tren & Waktu")
granularity = st.radio("Granularitas tren", ["Harian", "Bulanan"], horizontal=True)
trend_data = filtered.copy()
trend_data["periode_tren"] = trend_data["tgl_daftar"].dt.to_period("D" if granularity == "Harian" else "M").dt.to_timestamp()
trend_data = trend_data.groupby("periode_tren", as_index=False)["total"].sum()

# Konversi nilai total ke dalam satuan Juta Rupiah
trend_data["total_juta"] = trend_data["total"] / 1_000_000

trend = px.line(
    trend_data, 
    x="periode_tren", 
    y="total_juta", 
    markers=True, 
    labels={"periode_tren": "Tanggal", "total_juta": "Pendapatan (Juta Rp)"}
)
trend.update_traces(hovertemplate="Tanggal: %{x|%d-%m-%Y}<br>Pendapatan: Rp %{y:,.2f} Juta<extra></extra>")
st.plotly_chart(chart_layout(trend, f"Tren Penerimaan Pajak {granularity} (dalam Juta Rp)"), use_container_width=True)

st.subheader("Komposisi Objek Pajak")
composition_col, brand_col = st.columns(2)
with composition_col:
    vehicle_data = filtered[filtered["jenis_kendaraan"] != "Tidak tersedia"].groupby("jenis_kendaraan", as_index=False).size()
    if vehicle_data.empty: st.info("Kolom Jenis_Kendaraan belum tersedia pada CSV.")
    else:
        fig_pie = px.pie(vehicle_data, names="jenis_kendaraan", values="size", hole=.58, color_discrete_sequence=["#EF4444", "#22C55E", "#3B82F6"])
        st.plotly_chart(chart_layout(fig_pie, "Proporsi Jenis Kendaraan"), use_container_width=True)
with brand_col:
    brand_data = filtered[filtered["merk_model"] != "Tidak tersedia"].groupby("merk_model", as_index=False)["total"].sum().nlargest(5, "total")
    if brand_data.empty: st.info("Kolom Merk/Merek atau Model belum tersedia pada CSV.")
    else:
        brand_data["total_juta"] = brand_data["total"] / 1_000_000
        fig_bar_brand = px.bar(
            brand_data.sort_values("total_juta"), 
            x="total_juta", 
            y="merk_model", 
            orientation="h", 
            labels={"total_juta": "Pendapatan (Juta Rp)", "merk_model": "Merk / Model"}
        )
        fig_bar_brand.update_traces(hovertemplate="Merk / Model: %{y}<br>Pendapatan: Rp %{x:,.2f} Juta<extra></extra>")
        st.plotly_chart(chart_layout(fig_bar_brand, "Top 5 Merk / Model (dalam Juta Rp)"), use_container_width=True)

left_col, right_col = st.columns(2)
with left_col:
    st.subheader("Kinerja Wilayah & Pembayaran")
    region_data = filtered.groupby("upt", as_index=False)["total"].sum().sort_values("total")
    region_data["total_juta"] = region_data["total"] / 1_000_000
    fig_bar_region = px.bar(
        region_data, 
        x="total_juta", 
        y="upt", 
        orientation="h", 
        labels={"total_juta": "Pendapatan (Juta Rp)", "upt": "Nama Wilayah / UPT"}
    )
    fig_bar_region.update_traces(hovertemplate="Wilayah / UPT: %{y}<br>Pendapatan: Rp %{x:,.2f} Juta<extra></extra>")
    st.plotly_chart(chart_layout(fig_bar_region, "Pendapatan per Wilayah / Lokasi Bayar (dalam Juta Rp)"), use_container_width=True)

with right_col:
    st.subheader("Kepatuhan & Pendapatan Lainnya")
    registration_data = filtered[filtered["jenis_pendaftaran"] != "Tidak tersedia"].groupby("jenis_pendaftaran", as_index=False).size()
    if registration_data.empty: st.info("Kolom Jenis_Pendaftaran belum tersedia pada CSV.")
    else: st.plotly_chart(chart_layout(px.pie(registration_data, names="jenis_pendaftaran", values="size", hole=.5), "Proporsi Jenis Pendaftaran"), use_container_width=True)
    
    denda_summary = pd.DataFrame({
        "Komponen": ["Denda PKB", "Denda BBN"],
        "Nominal Juta": [filtered["denda_pkb"].sum() / 1_000_000, filtered["denda_bbn"].sum() / 1_000_000]
    })
    st.dataframe(denda_summary, hide_index=True, use_container_width=True, column_config={"Nominal Juta": st.column_config.NumberColumn("Nominal (Juta Rp)", format="Rp %.2f Juta")})

st.subheader("Detail Transaksi")
detail_columns = [column for column in ["tgl_daftar","upt","nopol","jenis_kendaraan","merk_model","jenis_pendaftaran","total_pokok","denda_pkb","denda_bbn","total"] if column in filtered]

detail_df = filtered[detail_columns].sort_values("tgl_daftar", ascending=False).copy()
for col in ["total_pokok", "denda_pkb", "denda_bbn", "total"]:
    if col in detail_df.columns:
        detail_df[f"{col}_juta"] = detail_df[col] / 1_000_000

display_detail_cols = ["tgl_daftar", "upt", "nopol", "jenis_kendaraan", "merk_model", "jenis_pendaftaran", "total_pokok_juta", "denda_pkb_juta", "denda_bbn_juta", "total_juta"]
available_display_cols = [c for c in display_detail_cols if c in detail_df.columns]

st.dataframe(
    detail_df[available_display_cols], 
    use_container_width=True, 
    hide_index=True, 
    column_config={
        "tgl_daftar": "TglDaftar",
        "upt": "Wilayah / UPT",
        "total_pokok_juta": st.column_config.NumberColumn("Pokok (Jt)", format="Rp %.2f Jt"),
        "denda_pkb_juta": st.column_config.NumberColumn("Denda PKB (Jt)", format="Rp %.2f Jt"),
        "denda_bbn_juta": st.column_config.NumberColumn("Denda BBN (Jt)", format="Rp %.2f Jt"),
        "total_juta": st.column_config.NumberColumn("Total (Jt)", format="Rp %.2f Jt")
    }
)