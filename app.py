# ============================================================
# 🌍 APP STREAMLIT CLOUD A4 FINAL
# GEE + NDVI Overlay + Clima + DEM SRTM + NPK + KML + DOCX
# ============================================================

import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import zipfile
import tempfile
import os
import json
import math
import requests

from shapely.geometry import Polygon
from datetime import datetime
from io import BytesIO

# DOCX
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Folium
import folium
from streamlit_folium import st_folium

# KML
import simplekml

# Earth Engine
import ee

# ============================================================
# CONFIG STREAMLIT
# ============================================================

st.set_page_config(
    page_title="🌱 Plataforma Agrícola A4 FINAL",
    layout="wide"
)

st.title("🌍 Plataforma Agrícola Completa A4 (FINAL)")
st.markdown("""
### Sentinel-2 NDVI Overlay + Clima + DEM SRTM + NPK + Export KML + Reporte DOCX
""")

# ============================================================
# 1. INICIALIZAR GOOGLE EARTH ENGINE (OBLIGATORIO)
# ============================================================

def inicializar_gee():
    if "GEE_SERVICE_ACCOUNT" not in st.secrets:
        st.error("❌ Falta el secret GEE_SERVICE_ACCOUNT en Streamlit Cloud")
        st.stop()

    try:
        credentials_info = json.loads(st.secrets["GEE_SERVICE_ACCOUNT"])

        credentials = ee.ServiceAccountCredentials(
            credentials_info["client_email"],
            key_data=json.dumps(credentials_info)
        )

        ee.Initialize(credentials)
        st.success("✅ Google Earth Engine inicializado correctamente")

    except Exception as e:
        st.error("❌ Error inicializando Earth Engine")
        st.exception(e)
        st.stop()


inicializar_gee()

# ============================================================
# 2. FUNCIONES GIS BÁSICAS
# ============================================================

def validar_crs(gdf):
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif str(gdf.crs) != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def calcular_area_ha(gdf):
    gdf_proj = gdf.to_crs(epsg=3857)
    return gdf_proj.geometry.area.sum() / 10000


def dividir_en_zonas(gdf, n_zonas):
    geom = gdf.iloc[0].geometry
    minx, miny, maxx, maxy = geom.bounds

    n_cols = math.ceil(math.sqrt(n_zonas))
    n_rows = math.ceil(n_zonas / n_cols)

    dx = (maxx - minx) / n_cols
    dy = (maxy - miny) / n_rows

    zonas = []
    zona_id = 1

    for r in range(n_rows):
        for c in range(n_cols):
            if zona_id > n_zonas:
                break

            x1 = minx + c * dx
            x2 = x1 + dx
            y1 = miny + r * dy
            y2 = y1 + dy

            poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
            inter = geom.intersection(poly)

            if not inter.is_empty:
                zonas.append({"id_zona": zona_id, "geometry": inter})

            zona_id += 1

    return gpd.GeoDataFrame(zonas, crs="EPSG:4326")


# ============================================================
# 3. SENTINEL-2 INDICES + NDVI TILE OVERLAY
# ============================================================

def obtener_indices_sentinel2(gdf, fecha_inicio, fecha_fin):
    geom = ee.Geometry.Polygon(list(gdf.iloc[0].geometry.exterior.coords))

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(str(fecha_inicio), str(fecha_fin))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    img = col.first()

    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")

    evi = img.expression(
        "2.5*((NIR-RED)/(NIR+6*RED-7.5*BLUE+1))",
        {
            "NIR": img.select("B8"),
            "RED": img.select("B4"),
            "BLUE": img.select("B2")
        }
    ).rename("EVI")

    ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")

    indices = ndvi.addBands(evi).addBands(ndwi)

    stats = indices.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        bestEffort=True
    ).getInfo()

    return stats, ndvi


def obtener_ndvi_tile(ndvi_img):
    """Convierte NDVI EE en tile overlay para Folium"""
    vis_params = {
        "min": 0,
        "max": 1,
        "palette": ["white", "green"]
    }

    map_id_dict = ee.Image(ndvi_img).getMapId(vis_params)

    return map_id_dict["tile_fetcher"].url_format


# ============================================================
# 4. DEM REAL SRTM + PENDIENTE
# ============================================================

def obtener_dem_srtm(gdf):
    geom = ee.Geometry.Polygon(list(gdf.iloc[0].geometry.exterior.coords))

    dem = ee.Image("USGS/SRTMGL1_003").clip(geom)
    slope = ee.Terrain.slope(dem)

    stats = dem.addBands(slope).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=30,
        bestEffort=True
    ).getInfo()

    return stats


# ============================================================
# 5. CLIMA NASA POWER
# ============================================================

def obtener_clima_nasa_power(gdf, fecha_inicio, fecha_fin):
    centroid = gdf.geometry.centroid.iloc[0]
    lat, lon = centroid.y, centroid.x

    start = fecha_inicio.strftime("%Y%m%d")
    end = fecha_fin.strftime("%Y%m%d")

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    params = {
        "parameters": "T2M,PRECTOTCORR,WS2M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON"
    }

    r = requests.get(url, params=params, timeout=20)
    data = r.json()

    series = data["properties"]["parameter"]

    df = pd.DataFrame({
        "fecha": pd.to_datetime(list(series["T2M"].keys())),
        "temp_C": list(series["T2M"].values()),
        "prec_mm": list(series["PRECTOTCORR"].values()),
        "viento": list(series["WS2M"].values())
    })

    return df


# ============================================================
# 6. NPK + COSTOS POR ZONA
# ============================================================

def estimar_npk_por_zona(zonas_gdf, ndvi_prom):
    resultados = []

    precio_urea = 550
    precio_map = 800
    precio_kcl = 650

    for _, row in zonas_gdf.iterrows():
        zona_id = row["id_zona"]

        if ndvi_prom < 0.3:
            N, P, K = 120, 60, 40
        elif ndvi_prom < 0.5:
            N, P, K = 80, 40, 30
        else:
            N, P, K = 50, 20, 15

        urea_kg = N / 0.46
        map_kg = P / 0.22
        kcl_kg = K / 0.50

        costo = (
            (urea_kg / 1000) * precio_urea +
            (map_kg / 1000) * precio_map +
            (kcl_kg / 1000) * precio_kcl
        )

        resultados.append({
            "Zona": zona_id,
            "N_kg_ha": N,
            "P_kg_ha": P,
            "K_kg_ha": K,
            "Costo_USD_ha": round(costo, 2)
        })

    return pd.DataFrame(resultados)


# ============================================================
# 7. EXPORTAR KML
# ============================================================

def exportar_kml(zonas_gdf):
    kml = simplekml.Kml()

    for _, row in zonas_gdf.iterrows():
        geom = row.geometry
        zona_id = row["id_zona"]

        coords = list(geom.exterior.coords)

        pol = kml.newpolygon(name=f"Zona {zona_id}")
        pol.outerboundaryis = coords

    buffer = BytesIO()
    kml.save(buffer)
    buffer.seek(0)
    return buffer


# ============================================================
# 8. REPORTE DOCX
# ============================================================

def generar_reporte(indices, dem_stats, clima_df, area_ha):
    doc = Document()

    title = doc.add_heading("REPORTE AGRÍCOLA A4 FINAL", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Fecha: {datetime.now()}")

    doc.add_heading("1. Índices Sentinel-2", level=1)
    for k, v in indices.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("2. DEM SRTM + Pendiente", level=1)
    for k, v in dem_stats.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("3. Área Total", level=1)
    doc.add_paragraph(f"{area_ha:.2f} ha")

    doc.add_heading("4. Clima NASA POWER", level=1)
    doc.add_paragraph(f"Temp media: {clima_df['temp_C'].mean():.2f} °C")
    doc.add_paragraph(f"Precip total: {clima_df['prec_mm'].sum():.2f} mm")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ============================================================
# 9. INTERFAZ STREAMLIT
# ============================================================

st.sidebar.header("📤 Subir Parcela")

uploaded = st.sidebar.file_uploader(
    "Subir ZIP shapefile o GeoJSON",
    type=["zip", "geojson"]
)

n_zonas = st.sidebar.slider("Número de zonas", 2, 20, 6)

fecha_inicio = st.sidebar.date_input("Fecha inicio", datetime(2024, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha fin", datetime(2024, 12, 31))

if uploaded:

    # Cargar shapefile ZIP
    if uploaded.name.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "file.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded.read())

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmpdir)

            shp_files = [f for f in os.listdir(tmpdir) if f.endswith(".shp")]
            shp_path = os.path.join(tmpdir, shp_files[0])

            gdf = gpd.read_file(shp_path)

    else:
        gdf = gpd.read_file(uploaded)

    gdf = validar_crs(gdf)
    area = calcular_area_ha(gdf)

    st.success(f"✅ Parcela cargada | Área: {area:.2f} ha")

    # Zonas
    zonas = dividir_en_zonas(gdf, n_zonas)

    # Sentinel-2 índices
    st.info("🌍 Calculando índices Sentinel-2...")
    indices, ndvi_img = obtener_indices_sentinel2(gdf, fecha_inicio, fecha_fin)

    ndvi_tile = obtener_ndvi_tile(ndvi_img)

    # DEM SRTM
    st.info("⛰️ Calculando DEM SRTM...")
    dem_stats = obtener_dem_srtm(gdf)

    # Clima
    st.info("🌦️ Descargando clima NASA POWER...")
    clima = obtener_clima_nasa_power(gdf, fecha_inicio, fecha_fin)

    # Tabla NPK
    tabla_npk = estimar_npk_por_zona(zonas, indices["NDVI"])

    # =====================================================
    # MAPA INTERACTIVO CON OVERLAY NDVI REAL
    # =====================================================

    st.write("## 🗺️ Mapa Interactivo con NDVI Overlay")

    centro = gdf.geometry.centroid.iloc[0]
    m = folium.Map(location=[centro.y, centro.x], zoom_start=13)

    # NDVI Overlay
    folium.TileLayer(
        tiles=ndvi_tile,
        attr="Google Earth Engine",
        name="NDVI Sentinel-2",
        overlay=True
    ).add_to(m)

    # Parcela
    folium.GeoJson(gdf, name="Parcela").add_to(m)

    # Zonas
    folium.GeoJson(zonas, name="Zonas").add_to(m)

    folium.LayerControl().add_to(m)

    st_folium(m, width=950, height=550)

    # =====================================================
    # RESULTADOS
    # =====================================================

    st.write("## 📊 Resultados")

    st.json(indices)
    st.json(dem_stats)

    st.write("### 🌾 Fertilización NPK + Costos por Zona")
    st.dataframe(tabla_npk)

    # Export KML
    st.write("### 📤 Exportar zonas en KML")
    kml_buffer = exportar_kml(zonas)

    st.download_button(
        "📥 Descargar zonas.kml",
        data=kml_buffer,
        file_name="zonas.kml",
        mime="application/vnd.google-earth.kml+xml"
    )

    # Reporte DOCX
    st.write("### 📄 Descargar Reporte Técnico DOCX")

    buffer_docx = generar_reporte(indices, dem_stats, clima, area)

    st.download_button(
        "📥 Descargar Reporte Completo",
        data=buffer_docx,
        file_name="reporte_agricola_A4.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
