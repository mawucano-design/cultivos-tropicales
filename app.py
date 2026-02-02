# ============================================================
# 🌍 APP STREAMLIT CLOUD A4 FINAL CORREGIDA
# GEE + NDVI Overlay + DEM SRTM + Clima + NPK + KML + DOCX
# SOPORTA: ZIP SHP + GEOJSON + KML + KMZ
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

# KML export
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
### Sentinel-2 NDVI Overlay + DEM SRTM + Clima + NPK + Export KML + Reporte DOCX
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
# 2. FUNCIÓN CLAVE: GeoPandas → Earth Engine Geometry
# ============================================================

def gdf_a_ee_geometry(gdf):
    """
    Convierte Polygon o MultiPolygon de GeoPandas
    en geometría válida Earth Engine
    """

    geom = gdf.iloc[0].geometry

    # Reparar geometría inválida
    if not geom.is_valid:
        geom = geom.buffer(0)

    # Si es MultiPolygon → usar el más grande
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda a: a.area)

    # Coordenadas
    coords = list(geom.exterior.coords)

    # Earth Engine requiere [[[lon,lat],...]]
    return ee.Geometry.Polygon([coords])


# ============================================================
# 3. FUNCIONES GIS
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

            poly = Polygon([(x1, y1), (x2, y1),
                            (x2, y2), (x1, y2)])

            inter = geom.intersection(poly)

            if not inter.is_empty:
                zonas.append({"id_zona": zona_id, "geometry": inter})

            zona_id += 1

    return gpd.GeoDataFrame(zonas, crs="EPSG:4326")


# ============================================================
# 4. CARGA DE ARCHIVOS: ZIP + GEOJSON + KML + KMZ
# ============================================================

def cargar_parcela(uploaded_file):
    """
    Soporta:
    - ZIP shapefile
    - GeoJSON
    - KML
    - KMZ
    """

    nombre = uploaded_file.name.lower()

    # ---- ZIP SHAPEFILE ----
    if nombre.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "file.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded_file.read())

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmpdir)

            shp_files = [f for f in os.listdir(tmpdir) if f.endswith(".shp")]
            shp_path = os.path.join(tmpdir, shp_files[0])

            gdf = gpd.read_file(shp_path)

    # ---- KMZ ----
    elif nombre.endswith(".kmz"):
        with tempfile.TemporaryDirectory() as tmpdir:
            kmz_path = os.path.join(tmpdir, "file.kmz")
            with open(kmz_path, "wb") as f:
                f.write(uploaded_file.read())

            with zipfile.ZipFile(kmz_path, "r") as z:
                z.extractall(tmpdir)

            kml_files = [f for f in os.listdir(tmpdir) if f.endswith(".kml")]
            kml_path = os.path.join(tmpdir, kml_files[0])

            gdf = gpd.read_file(kml_path)

    # ---- KML ----
    elif nombre.endswith(".kml"):
        gdf = gpd.read_file(uploaded_file)

    # ---- GEOJSON ----
    elif nombre.endswith(".geojson"):
        gdf = gpd.read_file(uploaded_file)

    else:
        st.error("❌ Formato no soportado")
        return None

    return validar_crs(gdf)


# ============================================================
# 5. SENTINEL-2 NDVI/EVI/NDWI + TILE OVERLAY
# ============================================================

def obtener_indices_sentinel2(gdf, fecha_inicio, fecha_fin):

    geom = gdf_a_ee_geometry(gdf)

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(str(fecha_inicio), str(fecha_fin))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    img = col.first()

    if img is None:
        return None, None

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

    vis_params = {
        "min": 0,
        "max": 1,
        "palette": ["red", "yellow", "green"]
    }

    map_id = ee.Image(ndvi_img).getMapId(vis_params)

    return map_id["tile_fetcher"].url_format


# ============================================================
# 6. DEM REAL SRTM + PENDIENTE
# ============================================================

def obtener_dem_srtm(gdf):

    geom = gdf_a_ee_geometry(gdf)

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
# 7. CLIMA NASA POWER
# ============================================================

def obtener_clima_nasa_power(gdf, fecha_inicio, fecha_fin):

    centroid = gdf.geometry.centroid.iloc[0]
    lat, lon = centroid.y, centroid.x

    start = fecha_inicio.strftime("%Y%m%d")
    end = fecha_fin.strftime("%Y%m%d")

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    params = {
        "parameters": "T2M,PRECTOTCORR",
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
        "prec_mm": list(series["PRECTOTCORR"].values())
    })

    return df


# ============================================================
# 8. NPK + COSTOS POR ZONA
# ============================================================

def estimar_npk_por_zona(zonas_gdf, ndvi_prom):

    resultados = []

    for _, row in zonas_gdf.iterrows():
        zona_id = row["id_zona"]

        if ndvi_prom < 0.3:
            N, P, K = 120, 60, 40
        elif ndvi_prom < 0.5:
            N, P, K = 80, 40, 30
        else:
            N, P, K = 50, 20, 15

        resultados.append({
            "Zona": zona_id,
            "N_kg_ha": N,
            "P_kg_ha": P,
            "K_kg_ha": K
        })

    return pd.DataFrame(resultados)


# ============================================================
# 9. EXPORTAR KML
# ============================================================

def exportar_kml(zonas_gdf):

    kml = simplekml.Kml()

    for _, row in zonas_gdf.iterrows():
        coords = list(row.geometry.exterior.coords)

        pol = kml.newpolygon(name=f"Zona {row['id_zona']}")
        pol.outerboundaryis = coords

    buffer = BytesIO()
    kml.save(buffer)
    buffer.seek(0)
    return buffer


# ============================================================
# 10. REPORTE DOCX
# ============================================================

def generar_reporte(indices, dem_stats, clima_df, area_ha):

    doc = Document()
    title = doc.add_heading("REPORTE AGRÍCOLA A4 FINAL", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Fecha: {datetime.now()}")

    doc.add_heading("1. Índices Sentinel-2", level=1)
    for k, v in indices.items():
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("2. DEM + Pendiente", level=1)
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
# 11. INTERFAZ STREAMLIT
# ============================================================

st.sidebar.header("📤 Subir Parcela")

uploaded = st.sidebar.file_uploader(
    "ZIP shapefile / GeoJSON / KML / KMZ",
    type=["zip", "geojson", "kml", "kmz"]
)

n_zonas = st.sidebar.slider("Número de zonas", 2, 20, 6)

fecha_inicio = st.sidebar.date_input("Fecha inicio", datetime(2024, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha fin", datetime(2024, 12, 31))

if uploaded:

    gdf = cargar_parcela(uploaded)

    if gdf is None:
        st.stop()

    st.write("Tipo geometría:", gdf.iloc[0].geometry.geom_type)
    st.write("Geometría válida:", gdf.iloc[0].geometry.is_valid)

    area = calcular_area_ha(gdf)
    st.success(f"✅ Parcela cargada | Área: {area:.2f} ha")

    zonas = dividir_en_zonas(gdf, n_zonas)

    # Índices Sentinel-2
    indices, ndvi_img = obtener_indices_sentinel2(gdf, fecha_inicio, fecha_fin)

    if indices is None:
        st.error("❌ No se encontró imagen Sentinel-2 válida")
        st.stop()

    # NDVI tile overlay
    ndvi_tile = obtener_ndvi_tile(ndvi_img)

    # DEM SRTM
    dem_stats = obtener_dem_srtm(gdf)

    # Clima
    clima = obtener_clima_nasa_power(gdf, fecha_inicio, fecha_fin)

    # NPK
    tabla_npk = estimar_npk_por_zona(zonas, indices["NDVI"])

    # =====================================================
    # MAPA INTERACTIVO
    # =====================================================

    st.write("## 🗺️ Mapa Interactivo NDVI Overlay")

    centro = gdf.geometry.centroid.iloc[0]

    m = folium.Map(location=[centro.y, centro.x], zoom_start=13)

    folium.TileLayer(
        tiles=ndvi_tile,
        name="NDVI Sentinel-2",
        overlay=True,
        attr="Google Earth Engine"
    ).add_to(m)

    folium.GeoJson(gdf, name="Parcela").add_to(m)
    folium.GeoJson(zonas, name="Zonas").add_to(m)

    folium.LayerControl().add_to(m)

    st_folium(m, width=950, height=550)

    # =====================================================
    # RESULTADOS
    # =====================================================

    st.write("## 📊 Resultados")
    st.json(indices)

    st.write("### ⛰️ DEM SRTM")
    st.json(dem_stats)

    st.write("### 🌾 NPK por Zona")
    st.dataframe(tabla_npk)

    # Export KML
    st.write("### 📤 Descargar zonas KML")
    kml_buffer = exportar_kml(zonas)

    st.download_button(
        "📥 Descargar zonas.kml",
        data=kml_buffer,
        file_name="zonas.kml",
        mime="application/vnd.google-earth.kml+xml"
    )

    # Reporte DOCX
    st.write("### 📄 Descargar Reporte DOCX")
    buffer_docx = generar_reporte(indices, dem_stats, clima, area)

    st.download_button(
        "📥 Descargar Reporte Completo",
        data=buffer_docx,
        file_name="reporte_agricola_A4.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
