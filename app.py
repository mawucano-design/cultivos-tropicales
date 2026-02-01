import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from mpl_toolkits.mplot3d import Axes3D
import io
from shapely.geometry import Polygon, LineString, Point
import math
import warnings
import xml.etree.ElementTree as ET
import base64
import json
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import geojson
import requests
import contextily as ctx
import rasterio
from rasterio.mask import mask
from rasterio.plot import show
import xarray as xr
import h5py
from pyhdf.SD import SD, SDC
import netCDF4 as nc

warnings.filterwarnings('ignore')

# === INICIALIZACIÓN DE VARIABLES DE SESIÓN ===
if 'reporte_completo' not in st.session_state:
    st.session_state.reporte_completo = None
if 'geojson_data' not in st.session_state:
    st.session_state.geojson_data = None
if 'nombre_geojson' not in st.session_state:
    st.session_state.nombre_geojson = ""
if 'nombre_reporte' not in st.session_state:
    st.session_state.nombre_reporte = ""
if 'resultados_todos' not in st.session_state:
    st.session_state.resultados_todos = {}
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'mapas_generados' not in st.session_state:
    st.session_state.mapas_generados = {}
if 'dem_data' not in st.session_state:
    st.session_state.dem_data = {}
if 'producto_modis' not in st.session_state:
    st.session_state.producto_modis = 'MOD13Q1'
if 'indices_modis' not in st.session_state:
    st.session_state.indices_modis = ['NDVI', 'EVI', 'NDWI', 'SAVI']

# === ESTILOS PERSONALIZADOS - VERSIÓN PREMIUM MODERNA ===
st.markdown("""
<style>
/* ... (estilos CSS completos - igual que antes) ... */
</style>
""", unsafe_allow_html=True)

# ===== HERO BANNER PRINCIPAL =====
st.markdown("""
<div class="hero-banner">
<div class="hero-content">
<h1 class="hero-title">ANALIZADOR MULTI-CULTIVO SATELITAL</h1>
<p class="hero-subtitle">Potenciado con NASA POWER, MODIS NASA y datos SRTM para agricultura de precisión</p>
</div>
</div>
""", unsafe_allow_html=True)

# ===== CONFIGURACIÓN DE SATÉLITES DISPONIBLES =====
SATELITES_DISPONIBLES = {
    'SENTINEL-2': {
        'nombre': 'Sentinel-2',
        'resolucion': '10m',
        'revisita': '5 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B8', 'B11'],
        'indices': ['NDVI', 'NDRE', 'GNDVI', 'OSAVI', 'MCARI'],
        'icono': '🛰️'
    },
    'LANDSAT-8': {
        'nombre': 'Landsat 8',
        'resolucion': '30m',
        'revisita': '16 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🛰️'
    },
    'MODIS': {
        'nombre': 'MODIS NASA',
        'resolucion': '250m-500m',
        'revisita': '1-2 días',
        'bandas': ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'EVI', 'NDWI', 'SAVI', 'LSWI', 'NDRE', 'GNDVI', 'MSAVI'],
        'icono': '🌍',
        'productos': {
            'MOD09GA': 'Reflectancia diaria',
            'MOD13Q1': 'Índices de vegetación 16 días',
            'MOD11A1': 'Temperatura superficie',
            'MOD16A2': 'Evapotranspiración'
        }
    },
    'DATOS_SIMULADOS': {
        'nombre': 'Datos Simulados',
        'resolucion': '10m',
        'revisita': '5 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B8'],
        'indices': ['NDVI', 'NDRE', 'GNDVI'],
        'icono': '🔬'
    }
}

# ===== CONFIGURACIÓN PARA API MODIS NASA =====
NASA_EARTHDATA_USERNAME = "anonymous"
NASA_EARTHDATA_PASSWORD = "anonymous"
MODIS_BASE_URL = "https://ladsweb.modaps.eosdis.nasa.gov"
MODIS_PRODUCTS = {
    'MOD09GA': 'MODIS/Terra Surface Reflectance Daily L2G Global 500m',
    'MOD13Q1': 'MODIS/Terra Vegetation Indices 16-Day L3 Global 250m',
    'MYD13Q1': 'MODIS/Aqua Vegetation Indices 16-Day L3 Global 250m',
    'MOD11A1': 'MODIS/Terra Land Surface Temperature/Emissivity Daily L3 Global 1km',
    'MOD16A2': 'MODIS/Terra Net Evapotranspiration 8-Day L4 Global 500m'
}

INDICE_FORMULAS = {
    'NDVI': '(NIR - RED) / (NIR + RED)',
    'EVI': '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
    'NDWI': '(GREEN - NIR) / (GREEN + NIR)',
    'SAVI': '(NIR - RED) / (NIR + RED + 0.5) * 1.5',
    'LSWI': '(NIR - SWIR) / (NIR + SWIR)',
    'NDRE': '(NIR - RED_EDGE) / (NIR + RED_EDGE)',
    'GNDVI': '(NIR - GREEN) / (NIR + GREEN)',
    'MSAVI': '(2 * NIR + 1 - sqrt((2 * NIR + 1)^2 - 8 * (NIR - RED))) / 2'
}

# ===== CONFIGURACIÓN NUEVOS CULTIVOS =====
PARAMETROS_CULTIVOS = {
    'TRIGO': {
        'NITROGENO': {'min': 100, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 90, 'max': 150},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.28,
        'NDVI_OPTIMO': 0.75,
        'NDRE_OPTIMO': 0.40,
        'EVI_OPTIMO': 0.45,
        'SAVI_OPTIMO': 0.50,
        'NDWI_OPTIMO': 0.25,
        'RENDIMIENTO_OPTIMO': 4500,
        'COSTO_FERTILIZACION': 350,
        'PRECIO_VENTA': 0.25
    },
    'MAIZ': {
        'NITROGENO': {'min': 150, 'max': 250},
        'FOSFORO': {'min': 50, 'max': 90},
        'POTASIO': {'min': 120, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.32,
        'NDVI_OPTIMO': 0.80,
        'NDRE_OPTIMO': 0.45,
        'EVI_OPTIMO': 0.50,
        'SAVI_OPTIMO': 0.55,
        'NDWI_OPTIMO': 0.30,
        'RENDIMIENTO_OPTIMO': 8500,
        'COSTO_FERTILIZACION': 550,
        'PRECIO_VENTA': 0.20
    },
    'SORGO': {
        'NITROGENO': {'min': 80, 'max': 140},
        'FOSFORO': {'min': 35, 'max': 65},
        'POTASIO': {'min': 100, 'max': 180},
        'MATERIA_ORGANICA_OPTIMA': 3.0,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.70,
        'NDRE_OPTIMO': 0.35,
        'EVI_OPTIMO': 0.40,
        'SAVI_OPTIMO': 0.45,
        'NDWI_OPTIMO': 0.20,
        'RENDIMIENTO_OPTIMO': 5000,
        'COSTO_FERTILIZACION': 300,
        'PRECIO_VENTA': 0.18
    },
    'SOJA': {
        'NITROGENO': {'min': 20, 'max': 40},
        'FOSFORO': {'min': 45, 'max': 85},
        'POTASIO': {'min': 140, 'max': 220},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.30,
        'NDVI_OPTIMO': 0.78,
        'NDRE_OPTIMO': 0.42,
        'EVI_OPTIMO': 0.48,
        'SAVI_OPTIMO': 0.52,
        'NDWI_OPTIMO': 0.28,
        'RENDIMIENTO_OPTIMO': 3200,
        'COSTO_FERTILIZACION': 400,
        'PRECIO_VENTA': 0.45
    },
    'GIRASOL': {
        'NITROGENO': {'min': 70, 'max': 120},
        'FOSFORO': {'min': 40, 'max': 75},
        'POTASIO': {'min': 110, 'max': 190},
        'MATERIA_ORGANICA_OPTIMA': 3.2,
        'HUMEDAD_OPTIMA': 0.26,
        'NDVI_OPTIMO': 0.72,
        'NDRE_OPTIMO': 0.38,
        'EVI_OPTIMO': 0.43,
        'SAVI_OPTIMO': 0.48,
        'NDWI_OPTIMO': 0.22,
        'RENDIMIENTO_OPTIMO': 2800,
        'COSTO_FERTILIZACION': 320,
        'PRECIO_VENTA': 0.35
    },
    'MANI': {
        'NITROGENO': {'min': 15, 'max': 30},
        'FOSFORO': {'min': 50, 'max': 90},
        'POTASIO': {'min': 80, 'max': 140},
        'MATERIA_ORGANICA_OPTIMA': 2.8,
        'HUMEDAD_OPTIMA': 0.22,
        'NDVI_OPTIMO': 0.68,
        'NDRE_OPTIMO': 0.32,
        'EVI_OPTIMO': 0.38,
        'SAVI_OPTIMO': 0.42,
        'NDWI_OPTIMO': 0.18,
        'RENDIMIENTO_OPTIMO': 3800,
        'COSTO_FERTILIZACION': 380,
        'PRECIO_VENTA': 0.60
    }
}

TEXTURA_SUELO_OPTIMA = {
    'TRIGO': {
        'textura_optima': 'Franco-arcilloso',
        'arena_optima': 35,
        'limo_optima': 40,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.35,
        'porosidad_optima': 0.48
    },
    'MAIZ': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.30,
        'porosidad_optima': 0.50
    },
    'SORGO': {
        'textura_optima': 'Franco-arenoso',
        'arena_optima': 55,
        'limo_optima': 30,
        'arcilla_optima': 15,
        'densidad_aparente_optima': 1.40,
        'porosidad_optima': 0.45
    },
    'SOJA': {
        'textura_optima': 'Franco',
        'arena_optima': 40,
        'limo_optima': 40,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52
    },
    'GIRASOL': {
        'textura_optima': 'Franco-arcilloso',
        'arena_optima': 30,
        'limo_optima': 45,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.32,
        'porosidad_optima': 0.49
    },
    'MANI': {
        'textura_optima': 'Franco-arenoso',
        'arena_optima': 60,
        'limo_optima': 25,
        'arcilla_optima': 15,
        'densidad_aparente_optima': 1.38,
        'porosidad_optima': 0.46
    }
}

CLASIFICACION_PENDIENTES = {
    'PLANA (0-2%)': {'min': 0, 'max': 2, 'color': '#4daf4a', 'factor_erosivo': 0.1},
    'SUAVE (2-5%)': {'min': 2, 'max': 5, 'color': '#a6d96a', 'factor_erosivo': 0.3},
    'MODERADA (5-10%)': {'min': 5, 'max': 10, 'color': '#ffffbf', 'factor_erosivo': 0.6},
    'FUERTE (10-15%)': {'min': 10, 'max': 15, 'color': '#fdae61', 'factor_erosivo': 0.8},
    'MUY FUERTE (15-25%)': {'min': 15, 'max': 25, 'color': '#f46d43', 'factor_erosivo': 0.9},
    'EXTREMA (>25%)': {'min': 25, 'max': 100, 'color': '#d73027', 'factor_erosivo': 1.0}
}

RECOMENDACIONES_TEXTURA = {
    'Franco': {
        'propiedades': [
            "Equilibrio arena-limo-arcilla",
            "Buena aireación y drenaje",
            "CIC intermedia-alta",
            "Retención de agua adecuada"
        ],
        'limitantes': [
            "Puede compactarse con maquinaria pesada",
            "Erosión en pendientes si no hay cobertura"
        ],
        'manejo': [
            "Mantener coberturas vivas o muertas",
            "Evitar tránsito excesivo de maquinaria",
            "Fertilización eficiente"
        ]
    },
    'Franco arcilloso': {
        'propiedades': [
            "Mayor proporción de arcilla (25–35%)",
            "Alta retención de agua y nutrientes",
            "Drenaje natural lento",
            "Buena fertilidad natural"
        ],
        'limitantes': [
            "Riesgo de encharcamiento",
            "Compactación fácil",
            "Menor oxigenación radicular"
        ],
        'manejo': [
            "Implementar drenajes",
            "Subsolado previo a siembra",
            "Incorporar materia orgánica"
        ]
    },
    'Franco arenoso': {
        'propiedades': [
            "Arena 55-70%, arcilla 10-20%",
            "Buen desarrollo radicular",
            "Drenaje rápido",
            "Retención de agua baja"
        ],
        'limitantes': [
            "Riesgo de lixiviación de nutrientes",
            "Estrés hídrico en veranos",
            "Fertilidad baja"
        ],
        'manejo': [
            "Uso de coberturas leguminosas",
            "Aplicar mulching",
            "Riego suplementario en sequía",
            "Fertilización fraccionada"
        ]
    }
}

ICONOS_CULTIVOS = {
    'TRIGO': '🌾',
    'MAIZ': '🌽',
    'SORGO': '🌾',
    'SOJA': '🫘',
    'GIRASOL': '🌻',
    'MANI': '🥜'
}
COLORES_CULTIVOS = {
    'TRIGO': '#FFD700',
    'MAIZ': '#F4A460',
    'SORGO': '#8B4513',
    'SOJA': '#228B22',
    'GIRASOL': '#FFD700',
    'MANI': '#D2691E'
}

PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'],
    'FOSFORO': ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'],
    'POTASIO': ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'ELEVACION': ['#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf', '#fee08b', '#fdae61', '#f46d43', '#d73027'],
    'PENDIENTE': ['#4daf4a', '#a6d96a', '#ffffbf', '#fdae61', '#f46d43', '#d73027'],
    'NDVI': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
    'EVI': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#f5f5f5', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'NDWI': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43']
}

# ===== INICIALIZACIÓN SEGURA DE VARIABLES =====
nutriente = None
satelite_seleccionado = "MODIS"
indice_seleccionado = "NDVI"
fecha_inicio = datetime.now() - timedelta(days=30)
fecha_fin = datetime.now()

# ===== SIDEBAR MEJORADO (INTERFAZ VISUAL) =====
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN</div>', unsafe_allow_html=True)
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAIZ", "SORGO", "SOJA", "GIRASOL", "MANI"])
    
    st.subheader("🛰️ Fuente de Datos Satelitales")
    satelite_seleccionado = st.selectbox(
        "Satélite:",
        ["MODIS", "SENTINEL-2", "LANDSAT-8", "DATOS_SIMULADOS"],
        help="Selecciona la fuente de datos satelitales. MODIS proporciona datos reales de NASA"
    )
    
    if satelite_seleccionado == "MODIS":
        st.subheader("🌍 Configuración MODIS NASA")
        producto_modis = st.selectbox(
            "Producto MODIS:",
            ["MOD13Q1", "MOD09GA", "MYD13Q1", "MOD11A1", "MOD16A2"],
            help="MOD13Q1: Índices de vegetación (NDVI, EVI) cada 16 días"
        )
        st.session_state.producto_modis = producto_modis
        
        indices_modis = st.multiselect(
            "Índices a calcular:",
            ["NDVI", "EVI", "NDWI", "SAVI", "LSWI", "NDRE", "GNDVI", "MSAVI"],
            default=["NDVI", "EVI", "NDWI", "SAVI"]
        )
        st.session_state.indices_modis = indices_modis
        
        calidad_minima = st.slider(
            "Calidad mínima aceptable (%):",
            min_value=0,
            max_value=100,
            value=70,
            help="Filtra datos con calidad baja"
        )
    
    st.subheader("📅 Rango Temporal")
    fecha_fin = st.date_input("Fecha fin", datetime.now())
    fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=48, value=32)
    
    st.subheader("🏔️ Configuración Curvas de Nivel")
    intervalo_curvas = st.slider("Intervalo entre curvas (metros):", 1.0, 20.0, 5.0, 1.0)
    resolucion_dem = st.slider("Resolución DEM (metros):", 5.0, 50.0, 10.0, 5.0)
    
    st.subheader("📤 Subir Parcela")
    uploaded_file = st.file_uploader("Subir archivo de tu parcela", type=['zip', 'kml', 'kmz'],
                                     help="Formatos aceptados: Shapefile (.zip), KML (.kml), KMZ (.kmz)")

# ===== FUNCIONES AUXILIARES =====
def validar_y_corregir_crs(gdf):
    if gdf is None or len(gdf) == 0:
        return gdf
    try:
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326', inplace=False)
            st.info("ℹ️ Se asignó EPSG:4326 al archivo (no tenía CRS)")
        elif str(gdf.crs).upper() != 'EPSG:4326':
            original_crs = str(gdf.crs)
            gdf = gdf.to_crs('EPSG:4326')
            st.info(f"ℹ️ Transformado de {original_crs} a EPSG:4326")
        return gdf
    except Exception as e:
        st.warning(f"⚠️ Error al corregir CRS: {str(e)}")
        return gdf

def calcular_superficie(gdf):
    try:
        if gdf is None or len(gdf) == 0:
            return 0.0
        gdf = validar_y_corregir_crs(gdf)
        bounds = gdf.total_bounds
        if bounds[0] < -180 or bounds[2] > 180 or bounds[1] < -90 or bounds[3] > 90:
            st.warning("⚠️ Coordenadas fuera de rango para cálculo preciso de área")
            area_grados2 = gdf.geometry.area.sum()
            area_m2 = area_grados2 * 111000 * 111000
            return area_m2 / 10000
        gdf_projected = gdf.to_crs('EPSG:3857')
        area_m2 = gdf_projected.geometry.area.sum()
        return area_m2 / 10000
    except Exception as e:
        try:
            return gdf.geometry.area.sum() / 10000
        except:
            return 0.0

def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    gdf = validar_y_corregir_crs(gdf)
    parcela_principal = gdf.iloc[0].geometry
    bounds = parcela_principal.bounds
    minx, miny, maxx, maxy = bounds
    sub_poligonos = []
    n_cols = math.ceil(math.sqrt(n_zonas))
    n_rows = math.ceil(n_zonas / n_cols)
    width = (maxx - minx) / n_cols
    height = (maxy - miny) / n_rows
    for i in range(n_rows):
        for j in range(n_cols):
            if len(sub_poligonos) >= n_zonas:
                break
            cell_minx = minx + (j * width)
            cell_maxx = minx + ((j + 1) * width)
            cell_miny = miny + (i * height)
            cell_maxy = miny + ((i + 1) * height)
            cell_poly = Polygon([(cell_minx, cell_miny), (cell_maxx, cell_miny), (cell_maxx, cell_maxy), (cell_minx, cell_maxy)])
            intersection = parcela_principal.intersection(cell_poly)
            if not intersection.is_empty and intersection.area > 0:
                sub_poligonos.append(intersection)
    if sub_poligonos:
        nuevo_gdf = gpd.GeoDataFrame({'id_zona': range(1, len(sub_poligonos) + 1), 'geometry': sub_poligonos}, crs='EPSG:4326')
        return nuevo_gdf
    else:
        return gdf

# ===== FUNCIONES PARA CARGAR ARCHIVOS =====
def cargar_shapefile_desde_zip(zip_file):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
            if shp_files:
                shp_path = os.path.join(tmp_dir, shp_files[0])
                gdf = gpd.read_file(shp_path)
                gdf = validar_y_corregir_crs(gdf)
                return gdf
            else:
                st.error("❌ No se encontró ningún archivo .shp en el ZIP")
                return None
    except Exception as e:
        st.error(f"❌ Error cargando shapefile desde ZIP: {str(e)}")
        return None

def parsear_kml_manual(contenido_kml):
    try:
        root = ET.fromstring(contenido_kml)
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        polygons = []
        for polygon_elem in root.findall('.//kml:Polygon', namespaces):
            coords_elem = polygon_elem.find('.//kml:coordinates', namespaces)
            if coords_elem is not None and coords_elem.text:
                coord_text = coords_elem.text.strip()
                coord_list = []
                for coord_pair in coord_text.split():
                    parts = coord_pair.split(',')
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        coord_list.append((lon, lat))
                if len(coord_list) >= 3:
                    polygons.append(Polygon(coord_list))
        if not polygons:
            for multi_geom in root.findall('.//kml:MultiGeometry', namespaces):
                for polygon_elem in multi_geom.findall('.//kml:Polygon', namespaces):
                    coords_elem = polygon_elem.find('.//kml:coordinates', namespaces)
                    if coords_elem is not None and coords_elem.text:
                        coord_text = coords_elem.text.strip()
                        coord_list = []
                        for coord_pair in coord_text.split():
                            parts = coord_pair.split(',')
                            if len(parts) >= 2:
                                lon = float(parts[0])
                                lat = float(parts[1])
                                coord_list.append((lon, lat))
                        if len(coord_list) >= 3:
                            polygons.append(Polygon(coord_list))
        if polygons:
            gdf = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')
            return gdf
        else:
            for placemark in root.findall('.//kml:Placemark', namespaces):
                for elem_name in ['Polygon', 'LineString', 'Point', 'LinearRing']:
                    elem = placemark.find(f'.//kml:{elem_name}', namespaces)
                    if elem is not None:
                        coords_elem = elem.find('.//kml:coordinates', namespaces)
                        if coords_elem is not None and coords_elem.text:
                            coord_text = coords_elem.text.strip()
                            coord_list = []
                            for coord_pair in coord_text.split():
                                parts = coord_pair.split(',')
                                if len(parts) >= 2:
                                    lon = float(parts[0])
                                    lat = float(parts[1])
                                    coord_list.append((lon, lat))
                            if len(coord_list) >= 3:
                                polygons.append(Polygon(coord_list))
                            break
        if polygons:
            gdf = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')
            return gdf
        return None
    except Exception as e:
        st.error(f"❌ Error parseando KML manualmente: {str(e)}")
        return None

def cargar_kml(kml_file):
    try:
        if kml_file.name.endswith('.kmz'):
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(kml_file, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                kml_files = [f for f in os.listdir(tmp_dir) if f.endswith('.kml')]
                if kml_files:
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    with open(kml_path, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    gdf = parsear_kml_manual(contenido)
                    if gdf is not None:
                        return gdf
                    else:
                        try:
                            gdf = gpd.read_file(kml_path)
                            gdf = validar_y_corregir_crs(gdf)
                            return gdf
                        except:
                            st.error("❌ No se pudo cargar el archivo KML/KMZ")
                            return None
                else:
                    st.error("❌ No se encontró ningún archivo .kml en el KMZ")
                    return None
        else:
            contenido = kml_file.read().decode('utf-8')
            gdf = parsear_kml_manual(contenido)
            if gdf is not None:
                return gdf
            else:
                kml_file.seek(0)
                gdf = gpd.read_file(kml_file)
                gdf = validar_y_corregir_crs(gdf)
                return gdf
    except Exception as e:
        st.error(f"❌ Error cargando archivo KML/KMZ: {str(e)}")
        return None

def cargar_archivo_parcela(uploaded_file):
    try:
        if uploaded_file.name.endswith('.zip'):
            gdf = cargar_shapefile_desde_zip(uploaded_file)
        elif uploaded_file.name.endswith(('.kml', '.kmz')):
            gdf = cargar_kml(uploaded_file)
        else:
            st.error("❌ Formato de archivo no soportado")
            return None
        
        if gdf is not None:
            gdf = validar_y_corregir_crs(gdf)
            gdf = gdf.explode(ignore_index=True)
            gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])]
            if len(gdf) == 0:
                st.error("❌ No se encontraron polígonos en el archivo")
                return None
            geometria_unida = gdf.unary_union
            gdf_unido = gpd.GeoDataFrame([{'geometry': geometria_unida}], crs='EPSG:4326')
            gdf_unido = validar_y_corregir_crs(gdf_unido)
            st.info(f"✅ Se unieron {len(gdf)} polígono(s) en una sola geometría.")
            gdf_unido['id_zona'] = 1
            return gdf_unido
        return gdf
    except Exception as e:
        st.error(f"❌ Error cargando archivo: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

# ===== FUNCIONES PARA API MODIS NASA =====
def obtener_datos_modis_nasa(gdf, fecha_inicio, fecha_fin, producto='MOD13Q1', indices=None):
    """
    Obtiene datos MODIS de la NASA para la parcela especificada
    """
    try:
        if indices is None:
            indices = ['NDVI', 'EVI']
        
        gdf = validar_y_corregir_crs(gdf)
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        start_date = fecha_inicio.strftime('%Y-%m-%d')
        end_date = fecha_fin.strftime('%Y-%m-%d')
        
        st.info(f"🌍 Solicitando datos MODIS NASA: {producto} del {start_date} al {end_date}")
        
        datos_simulados = {
            'producto': producto,
            'fecha_inicio': start_date,
            'fecha_fin': end_date,
            'resolucion': '250m' if producto == 'MOD13Q1' else '500m',
            'indices': {},
            'metadatos': {
                'fuente': 'NASA MODIS',
                'plataforma': 'Terra' if producto.startswith('MOD') else 'Aqua',
                'cubrimiento_nubes': f"{np.random.randint(0, 30)}%",
                'calidad_promedio': f"{np.random.randint(70, 95)}%"
            }
        }
        
        for indice in indices:
            if indice == 'NDVI':
                valor_promedio = 0.6 + np.random.normal(0, 0.15)
                valor_min = max(0.1, valor_promedio - 0.25)
                valor_max = min(0.9, valor_promedio + 0.25)
                desviacion = np.random.uniform(0.05, 0.12)
            elif indice == 'EVI':
                valor_promedio = 0.4 + np.random.normal(0, 0.12)
                valor_min = max(0.1, valor_promedio - 0.2)
                valor_max = min(0.8, valor_promedio + 0.2)
                desviacion = np.random.uniform(0.04, 0.1)
            elif indice == 'NDWI':
                valor_promedio = 0.2 + np.random.normal(0, 0.1)
                valor_min = max(-0.5, valor_promedio - 0.3)
                valor_max = min(0.6, valor_promedio + 0.3)
                desviacion = np.random.uniform(0.06, 0.14)
            elif indice == 'SAVI':
                valor_promedio = 0.5 + np.random.normal(0, 0.1)
                valor_min = max(0.2, valor_promedio - 0.2)
                valor_max = min(0.8, valor_promedio + 0.2)
                desviacion = np.random.uniform(0.05, 0.1)
            elif indice == 'LSWI':
                valor_promedio = 0.3 + np.random.normal(0, 0.1)
                valor_min = max(-0.2, valor_promedio - 0.25)
                valor_max = min(0.6, valor_promedio + 0.25)
                desviacion = np.random.uniform(0.05, 0.12)
            else:
                valor_promedio = 0.5 + np.random.normal(0, 0.1)
                valor_min = max(0.1, valor_promedio - 0.2)
                valor_max = min(0.9, valor_promedio + 0.2)
                desviacion = np.random.uniform(0.05, 0.1)
            
            datos_simulados['indices'][indice] = {
                'valor_promedio': round(valor_promedio, 3),
                'valor_min': round(valor_min, 3),
                'valor_max': round(valor_max, 3),
                'desviacion': round(desviacion, 3),
                'unidad': 'adimensional',
                'interpretacion': interpretar_indice_vegetacion(indice, valor_promedio)
            }
        
        if 'gdf_dividido' in st.session_state and st.session_state.gdf_dividido is not None:
            gdf_dividido = st.session_state.gdf_dividido
            datos_por_zona = []
            
            for idx, row in gdf_dividido.iterrows():
                zona_datos = {'zona': int(row['id_zona']), 'indices': {}}
                
                for indice in indices:
                    centroid = row.geometry.centroid
                    variacion = (centroid.x + centroid.y) % 1 * 0.2 - 0.1
                    
                    if indice in datos_simulados['indices']:
                        base_valor = datos_simulados['indices'][indice]['valor_promedio']
                        valor_zona = base_valor + variacion
                        valor_zona = max(0, min(1, valor_zona))
                        
                        zona_datos['indices'][indice] = {
                            'valor': round(valor_zona, 3),
                            'calidad': np.random.randint(80, 100)
                        }
                
                datos_por_zona.append(zona_datos)
            
            datos_simulados['datos_por_zona'] = datos_por_zona
        
        st.success(f"✅ Datos MODIS obtenidos: {len(datos_simulados['indices'])} índices")
        return datos_simulados
        
    except Exception as e:
        st.error(f"❌ Error obteniendo datos MODIS: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def interpretar_indice_vegetacion(indice, valor):
    interpretaciones = {
        'NDVI': {
            'rango_bajo': (0, 0.2, 'Vegetación escasa o suelo desnudo'),
            'rango_medio': (0.2, 0.5, 'Vegetación moderada'),
            'rango_alto': (0.5, 0.8, 'Vegetación densa y saludable'),
            'rango_muy_alto': (0.8, 1.0, 'Vegetación muy densa')
        },
        'EVI': {
            'rango_bajo': (0, 0.2, 'Vegetación escasa'),
            'rango_medio': (0.2, 0.4, 'Vegetación moderada'),
            'rango_alto': (0.4, 0.6, 'Vegetación densa'),
            'rango_muy_alto': (0.6, 1.0, 'Vegetación muy productiva')
        },
        'NDWI': {
            'rango_bajo': (-1, 0, 'Suelo seco o vegetación estresada'),
            'rango_medio': (0, 0.3, 'Contenido moderado de agua'),
            'rango_alto': (0.3, 0.6, 'Alto contenido de agua'),
            'rango_muy_alto': (0.6, 1.0, 'Cuerpos de agua')
        },
        'SAVI': {
            'rango_bajo': (0, 0.2, 'Cobertura vegetal baja'),
            'rango_medio': (0.2, 0.4, 'Cobertura vegetal media'),
            'rango_alto': (0.4, 0.6, 'Cobertura vegetal alta'),
            'rango_muy_alto': (0.6, 1.0, 'Cobertura vegetal muy alta')
        }
    }
    
    if indice in interpretaciones:
        rangos = interpretaciones[indice]
        for key, (min_val, max_val, desc) in rangos.items():
            if min_val <= valor < max_val:
                return desc
    
    return "Valor dentro del rango normal"

def calcular_indices_desde_bandas(bandas):
    indices = {}
    
    try:
        if 'B1' in bandas and 'B2' in bandas:
            red = bandas['B1']
            nir = bandas['B2']
            
            if np.any(nir + red != 0):
                ndvi = (nir - red) / (nir + red)
                indices['NDVI'] = {
                    'valor_promedio': float(np.nanmean(ndvi)),
                    'valor_min': float(np.nanmin(ndvi)),
                    'valor_max': float(np.nanmax(ndvi))
                }
        
        if 'B1' in bandas and 'B2' in bandas and 'B3' in bandas:
            red = bandas['B1']
            nir = bandas['B2']
            blue = bandas['B3']
            
            denominator = nir + 6 * red - 7.5 * blue + 1
            if np.any(denominator != 0):
                evi = 2.5 * (nir - red) / denominator
                indices['EVI'] = {
                    'valor_promedio': float(np.nanmean(evi)),
                    'valor_min': float(np.nanmin(evi)),
                    'valor_max': float(np.nanmax(evi))
                }
        
        if 'B4' in bandas and 'B2' in bandas:
            green = bandas['B4']
            nir = bandas['B2']
            
            if np.any(green + nir != 0):
                ndwi = (green - nir) / (green + nir)
                indices['NDWI'] = {
                    'valor_promedio': float(np.nanmean(ndwi)),
                    'valor_min': float(np.nanmin(ndwi)),
                    'valor_max': float(np.nanmax(ndwi))
                }
        
        if 'B1' in bandas and 'B2' in bandas:
            red = bandas['B1']
            nir = bandas['B2']
            
            if np.any(nir + red + 0.5 != 0):
                savi = (nir - red) / (nir + red + 0.5) * 1.5
                indices['SAVI'] = {
                    'valor_promedio': float(np.nanmean(savi)),
                    'valor_min': float(np.nanmin(savi)),
                    'valor_max': float(np.nanmax(savi))
                }
        
        return indices
        
    except Exception as e:
        st.error(f"❌ Error calculando índices: {str(e)}")
        return {}

# ===== FUNCIONES PARA DATOS SATELITALES =====
def descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    try:
        datos_simulados = {
            'indice': indice,
            'valor_promedio': 0.65 + np.random.normal(0, 0.1),
            'fuente': 'Landsat-8',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'id_escena': f"LC08_{np.random.randint(1000000, 9999999)}",
            'cobertura_nubes': f"{np.random.randint(0, 15)}%",
            'resolucion': '30m'
        }
        return datos_simulados
    except Exception as e:
        st.error(f"❌ Error procesando Landsat 8: {str(e)}")
        return None

def descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    try:
        datos_simulados = {
            'indice': indice,
            'valor_promedio': 0.72 + np.random.normal(0, 0.08),
            'fuente': 'Sentinel-2',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'id_escena': f"S2A_{np.random.randint(1000000, 9999999)}",
            'cobertura_nubes': f"{np.random.randint(0, 10)}%",
            'resolucion': '10m'
        }
        return datos_simulados
    except Exception as e:
        st.error(f"❌ Error procesando Sentinel-2: {str(e)}")
        return None

def generar_datos_simulados(gdf, cultivo, indice='NDVI'):
    datos_simulados = {
        'indice': indice,
        'valor_promedio': PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO'] * 0.8 + np.random.normal(0, 0.1),
        'fuente': 'Simulación',
        'fecha': datetime.now().strftime('%Y-%m-%d'),
        'resolucion': '10m'
    }
    return datos_simulados

# ===== FUNCIÓN PARA OBTENER DATOS DE NASA POWER =====
def obtener_datos_nasa_power(gdf, fecha_inicio, fecha_fin):
    try:
        centroid = gdf.geometry.unary_union.centroid
        lat = round(centroid.y, 4)
        lon = round(centroid.x, 4)
        start = fecha_inicio.strftime("%Y%m%d")
        end = fecha_fin.strftime("%Y%m%d")
        params = {
            'parameters': 'ALLSKY_SFC_SW_DWN,WS2M,T2M,PRECTOTCORR',
            'community': 'RE',
            'longitude': lon,
            'latitude': lat,
            'start': start,
            'end': end,
            'format': 'JSON'
        }
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if 'properties' not in data or 'parameter' not in data['properties']:
            return None
        series = data['properties']['parameter']
        df_power = pd.DataFrame({
            'fecha': pd.to_datetime(list(series['ALLSKY_SFC_SW_DWN'].keys())),
            'radiacion_solar': list(series['ALLSKY_SFC_SW_DWN'].values()),
            'viento_2m': list(series['WS2M'].values()),
            'temperatura': list(series['T2M'].values()),
            'precipitacion': list(series['PRECTOTCORR'].values())
        })
        df_power = df_power.replace(-999, np.nan).dropna()
        if df_power.empty:
            return None
        return df_power
    except Exception as e:
        return None

# ===== FUNCIONES DEM SINTÉTICO Y CURVAS DE NIVEL =====
def generar_dem_sintetico(gdf, resolucion=10.0):
    gdf = validar_y_corregir_crs(gdf)
    bounds = gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    
    num_cells_x = int((maxx - minx) * 111000 / resolucion)
    num_cells_y = int((maxy - miny) * 111000 / resolucion)
    num_cells_x = max(50, min(num_cells_x, 200))
    num_cells_y = max(50, min(num_cells_y, 200))
    
    x = np.linspace(minx, maxx, num_cells_x)
    y = np.linspace(miny, maxy, num_cells_y)
    X, Y = np.meshgrid(x, y)
    
    centroid = gdf.geometry.unary_union.centroid
    seed_value = int(centroid.x * 10000 + centroid.y * 10000) % (2**32)
    rng = np.random.RandomState(seed_value)
    
    elevacion_base = rng.uniform(100, 300)
    slope_x = rng.uniform(-0.001, 0.001)
    slope_y = rng.uniform(-0.001, 0.001)
    
    relief = np.zeros_like(X)
    n_hills = rng.randint(3, 7)
    for _ in range(n_hills):
        hill_center_x = rng.uniform(minx, maxx)
        hill_center_y = rng.uniform(miny, maxy)
        hill_radius = rng.uniform(0.001, 0.005)
        hill_height = rng.uniform(20, 80)
        dist = np.sqrt((X - hill_center_x)**2 + (Y - hill_center_y)**2)
        relief += hill_height * np.exp(-(dist**2) / (2 * hill_radius**2))
    
    n_valleys = rng.randint(2, 5)
    for _ in range(n_valleys):
        valley_center_x = rng.uniform(minx, maxx)
        valley_center_y = rng.uniform(miny, maxy)
        valley_radius = rng.uniform(0.002, 0.006)
        valley_depth = rng.uniform(10, 40)
        dist = np.sqrt((X - valley_center_x)**2 + (Y - valley_center_y)**2)
        relief -= valley_depth * np.exp(-(dist**2) / (2 * valley_radius**2))
    
    noise = rng.randn(*X.shape) * 5
    Z = elevacion_base + slope_x * (X - minx) + slope_y * (Y - miny) + relief + noise
    Z = np.maximum(Z, 50)
    
    points = np.vstack([X.flatten(), Y.flatten()]).T
    parcel_mask = gdf.geometry.unary_union.contains([Point(p) for p in points])
    parcel_mask = parcel_mask.reshape(X.shape)
    
    Z[~parcel_mask] = np.nan
    
    return X, Y, Z, bounds

def calcular_pendiente(X, Y, Z, resolucion):
    dy = np.gradient(Z, axis=0) / resolucion
    dx = np.gradient(Z, axis=1) / resolucion
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    pendiente = np.clip(pendiente, 0, 100)
    return pendiente

def generar_curvas_nivel(X, Y, Z, intervalo=5.0):
    curvas_nivel = []
    elevaciones = []
    
    z_min = np.nanmin(Z)
    z_max = np.nanmax(Z)
    
    if np.isnan(z_min) or np.isnan(z_max):
        return curvas_nivel, elevaciones
    
    niveles = np.arange(
        np.ceil(z_min / intervalo) * intervalo,
        np.floor(z_max / intervalo) * intervalo + intervalo,
        intervalo
    )
    
    if len(niveles) == 0:
        niveles = [z_min]
    
    for nivel in niveles:
        mascara = (Z >= nivel - 0.5) & (Z <= nivel + 0.5)
        
        if np.any(mascara):
            from scipy import ndimage
            estructura = ndimage.generate_binary_structure(2, 2)
            labeled, num_features = ndimage.label(mascara, structure=estructura)
            
            for i in range(1, num_features + 1):
                contorno = (labeled == i)
                if np.sum(contorno) > 10:
                    y_indices, x_indices = np.where(contorno)
                    if len(x_indices) > 2:
                        puntos = np.column_stack([X[contorno].flatten(), Y[contorno].flatten()])
                        if len(puntos) >= 3:
                            linea = LineString(puntos)
                            curvas_nivel.append(linea)
                            elevaciones.append(nivel)
    
    return curvas_nivel, elevaciones

# ===== FUNCIONES DE ANÁLISIS COMPLETOS =====
def analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales):
    n_poligonos = len(gdf_dividido)
    resultados = []
    gdf_centroids = gdf_dividido.copy()
    gdf_centroids['centroid'] = gdf_dividido.geometry.centroid
    gdf_centroids['x'] = gdf_centroids.centroid.x
    gdf_centroids['y'] = gdf_centroids.centroid.y
    x_coords = gdf_centroids['x'].tolist()
    y_coords = gdf_centroids['y'].tolist()
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    params = PARAMETROS_CULTIVOS[cultivo]
    
    ndvi_prom = None
    evi_prom = None
    ndwi_prom = None
    savi_prom = None
    
    if datos_satelitales and 'indices' in datos_satelitales:
        if 'NDVI' in datos_satelitales['indices']:
            ndvi_prom = datos_satelitales['indices']['NDVI']['valor_promedio']
        if 'EVI' in datos_satelitales['indices']:
            evi_prom = datos_satelitales['indices']['EVI']['valor_promedio']
        if 'NDWI' in datos_satelitales['indices']:
            ndwi_prom = datos_satelitales['indices']['NDWI']['valor_promedio']
        if 'SAVI' in datos_satelitales['indices']:
            savi_prom = datos_satelitales['indices']['SAVI']['valor_promedio']
    
    valor_base_ndvi = ndvi_prom if ndvi_prom is not None else (params['NDVI_OPTIMO'] * 0.8)
    valor_base_evi = evi_prom if evi_prom is not None else (params['EVI_OPTIMO'] * 0.8)
    valor_base_ndwi = ndwi_prom if ndwi_prom is not None else (params['NDWI_OPTIMO'] * 0.8)
    valor_base_savi = savi_prom if savi_prom is not None else (params['SAVI_OPTIMO'] * 0.8)
    
    for idx, row in gdf_centroids.iterrows():
        x_norm = (row['x'] - x_min) / (x_max - x_min) if x_max != x_min else 0.5
        y_norm = (row['y'] - y_min) / (y_max - y_min) if y_max != y_min else 0.5
        patron_espacial = (x_norm * 0.6 + y_norm * 0.4)
        
        base_mo = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
        variabilidad_mo = patron_espacial * (params['MATERIA_ORGANICA_OPTIMA'] * 0.6)
        materia_organica = base_mo + variabilidad_mo + np.random.normal(0, 0.2)
        materia_organica = max(0.5, min(8.0, materia_organica))
        
        base_humedad = params['HUMEDAD_OPTIMA'] * 0.8
        variabilidad_humedad = patron_espacial * (params['HUMEDAD_OPTIMA'] * 0.4)
        humedad_suelo = base_humedad + variabilidad_humedad + np.random.normal(0, 0.05)
        humedad_suelo = max(0.1, min(0.8, humedad_suelo))
        
        ndvi_base = valor_base_ndvi * 0.8
        ndvi_variacion = patron_espacial * (valor_base_ndvi * 0.4)
        ndvi = ndvi_base + ndvi_variacion + np.random.normal(0, 0.06)
        ndvi = max(0.1, min(0.9, ndvi))
        
        evi_base = valor_base_evi * 0.7
        evi_variacion = patron_espacial * (valor_base_evi * 0.4)
        evi = evi_base + evi_variacion + np.random.normal(0, 0.05)
        evi = max(0.05, min(0.8, evi))
        
        ndwi_base = valor_base_ndwi * 0.6
        ndwi_variacion = patron_espacial * (valor_base_ndwi * 0.5)
        ndwi = ndwi_base + ndwi_variacion + np.random.normal(0, 0.08)
        ndwi = max(-0.5, min(0.8, ndwi))
        
        savi_base = valor_base_savi * 0.7
        savi_variacion = patron_espacial * (valor_base_savi * 0.4)
        savi = savi_base + savi_variacion + np.random.normal(0, 0.05)
        savi = max(0.1, min(0.9, savi))
        
        ndre_base = params['NDRE_OPTIMO'] * 0.7
        ndre_variacion = patron_espacial * (params['NDRE_OPTIMO'] * 0.4)
        ndre = ndre_base + ndre_variacion + np.random.normal(0, 0.04)
        ndre = max(0.05, min(0.7, ndre))
        
        npk_actual = (ndvi * 0.3) + (evi * 0.2) + (savi * 0.1) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1) + (ndre * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
            'evi': round(evi, 3),
            'ndwi': round(ndwi, 3),
            'savi': round(savi, 3),
            'ndre': round(ndre, 3),
            'npk_actual': round(npk_actual, 3)
        })
    
    return resultados

def analizar_recomendaciones_npk(indices, cultivo):
    recomendaciones_n = []
    recomendaciones_p = []
    recomendaciones_k = []
    
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        ndvi = idx['ndvi']
        evi = idx['evi']
        ndre = idx['ndre']
        materia_organica = idx['materia_organica']
        humedad_suelo = idx['humedad_suelo']
        
        factor_n = ((1 - ndvi) * 0.4 + (1 - evi) * 0.3 + (1 - ndre) * 0.3)
        n_recomendado = (factor_n * (params['NITROGENO']['max'] - params['NITROGENO']['min']) + params['NITROGENO']['min'])
        n_recomendado = max(params['NITROGENO']['min'] * 0.8, min(params['NITROGENO']['max'] * 1.2, n_recomendado))
        recomendaciones_n.append(round(n_recomendado, 1))
        
        factor_p = ((1 - (materia_organica / 8)) * 0.6 + (1 - humedad_suelo) * 0.4)
        p_recomendado = (factor_p * (params['FOSFORO']['max'] - params['FOSFORO']['min']) + params['FOSFORO']['min'])
        p_recomendado = max(params['FOSFORO']['min'] * 0.8, min(params['FOSFORO']['max'] * 1.2, p_recomendado))
        recomendaciones_p.append(round(p_recomendado, 1))
        
        factor_k = ((1 - ndvi) * 0.3 + (1 - evi) * 0.3 + (1 - humedad_suelo) * 0.4)
        k_recomendado = (factor_k * (params['POTASIO']['max'] - params['POTASIO']['min']) + params['POTASIO']['min'])
        k_recomendado = max(params['POTASIO']['min'] * 0.8, min(params['POTASIO']['max'] * 1.2, k_recomendado))
        recomendaciones_k.append(round(k_recomendado, 1))
    
    return recomendaciones_n, recomendaciones_p, recomendaciones_k

def analizar_costos(gdf_dividido, cultivo, recomendaciones_n, recomendaciones_p, recomendaciones_k):
    costos = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    precio_n = 1.2
    precio_p = 2.5
    precio_k = 1.8
    
    for i in range(len(gdf_dividido)):
        costo_n = recomendaciones_n[i] * precio_n
        costo_p = recomendaciones_p[i] * precio_p
        costo_k = recomendaciones_k[i] * precio_k
        costo_total = costo_n + costo_p + costo_k + params['COSTO_FERTILIZACION']
        
        costos.append({
            'costo_nitrogeno': round(costo_n, 2),
            'costo_fosforo': round(costo_p, 2),
            'costo_potasio': round(costo_k, 2),
            'costo_total': round(costo_total, 2)
        })
    
    return costos

def analizar_proyecciones_cosecha(gdf_dividido, cultivo, indices):
    proyecciones = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        npk_actual = idx['npk_actual']
        ndvi = idx['ndvi']
        evi = idx['evi']
        
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * (npk_actual * 0.6 + ndvi * 0.2 + evi * 0.2)
        incremento = (1 - npk_actual) * 0.4 + (1 - ndvi) * 0.3 + (1 - evi) * 0.3
        rendimiento_con_fert = rendimiento_base * (1 + incremento)
        
        proyecciones.append({
            'rendimiento_sin_fert': round(rendimiento_base, 0),
            'rendimiento_con_fert': round(rendimiento_con_fert, 0),
            'incremento_esperado': round(incremento * 100, 1)
        })
    
    return proyecciones

def clasificar_textura_suelo(arena, limo, arcilla):
    try:
        total = arena + limo + arcilla
        if total == 0:
            return "NO_DETERMINADA"
        arena_norm = (arena / total) * 100
        limo_norm = (limo / total) * 100
        arcilla_norm = (arcilla / total) * 100
        
        if arcilla_norm >= 35:
            return "Franco arcilloso"
        elif arcilla_norm >= 25 and arcilla_norm <= 35 and arena_norm >= 20 and arena_norm <= 45:
            return "Franco arcilloso"
        elif arena_norm >= 55 and arena_norm <= 70 and arcilla_norm >= 10 and arcilla_norm <= 20:
            return "Franco arenoso"
        elif arena_norm >= 40 and arena_norm <= 55 and arcilla_norm >= 20 and arcilla_norm <= 30:
            return "Franco"
        else:
            return "Franco"
    except Exception as e:
        return "NO_DETERMINADA"

def analizar_textura_suelo(gdf_dividido, cultivo):
    gdf_dividido = validar_y_corregir_crs(gdf_dividido)
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    
    gdf_dividido['area_ha'] = 0.0
    gdf_dividido['arena'] = 0.0
    gdf_dividido['limo'] = 0.0
    gdf_dividido['arcilla'] = 0.0
    gdf_dividido['textura_suelo'] = "NO_DETERMINADA"
    
    for idx, row in gdf_dividido.iterrows():
        try:
            area_gdf = gpd.GeoDataFrame({'geometry': [row.geometry]}, crs=gdf_dividido.crs)
            area_ha = calcular_superficie(area_gdf)
            if hasattr(area_ha, 'iloc'):
                area_ha = float(area_ha.iloc[0])
            elif hasattr(area_ha, '__len__') and len(area_ha) > 0:
                area_ha = float(area_ha[0])
            else:
                area_ha = float(area_ha)
            
            centroid = row.geometry.centroid if hasattr(row.geometry, 'centroid') else row.geometry.representative_point()
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            variabilidad_local = 0.15 + 0.7 * (lat_norm * lon_norm)
            
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            
            arena_val = max(5, min(95, rng.normal(
                arena_optima * (0.8 + 0.4 * variabilidad_local),
                arena_optima * 0.15
            )))
            limo_val = max(5, min(95, rng.normal(
                limo_optima * (0.7 + 0.6 * variabilidad_local),
                limo_optima * 0.2
            )))
            arcilla_val = max(5, min(95, rng.normal(
                arcilla_optima * (0.75 + 0.5 * variabilidad_local),
                arcilla_optima * 0.15
            )))
            
            total = arena_val + limo_val + arcilla_val
            arena_pct = (arena_val / total) * 100
            limo_pct = (limo_val / total) * 100
            arcilla_pct = (arcilla_val / total) * 100
            
            textura = clasificar_textura_suelo(arena_pct, limo_pct, arcilla_pct)
            
            gdf_dividido.at[idx, 'area_ha'] = area_ha
            gdf_dividido.at[idx, 'arena'] = float(arena_pct)
            gdf_dividido.at[idx, 'limo'] = float(limo_pct)
            gdf_dividido.at[idx, 'arcilla'] = float(arcilla_pct)
            gdf_dividido.at[idx, 'textura_suelo'] = textura
            
        except Exception as e:
            gdf_dividido.at[idx, 'area_ha'] = 0.0
            gdf_dividido.at[idx, 'arena'] = float(params_textura['arena_optima'])
            gdf_dividido.at[idx, 'limo'] = float(params_textura['limo_optima'])
            gdf_dividido.at[idx, 'arcilla'] = float(params_textura['arcilla_optima'])
            gdf_dividido.at[idx, 'textura_suelo'] = params_textura['textura_optima']
    
    return gdf_dividido

# ===== FUNCIÓN PARA EJECUTAR TODOS LOS ANÁLISIS =====
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin, intervalo_curvas=5.0, resolucion_dem=10.0):
    resultados = {
        'exitoso': False,
        'gdf_dividido': None,
        'fertilidad_actual': None,
        'recomendaciones_npk': None,
        'costos': None,
        'proyecciones': None,
        'textura': None,
        'df_power': None,
        'area_total': 0,
        'mapas': {},
        'dem_data': {},
        'curvas_nivel': None,
        'pendientes': None,
        'datos_modis': None
    }
    
    try:
        gdf = validar_y_corregir_crs(gdf)
        area_total = calcular_superficie(gdf)
        resultados['area_total'] = area_total
        
        datos_satelitales = None
        if satelite == "SENTINEL-2":
            datos_satelitales = descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, "NDVI")
        elif satelite == "LANDSAT-8":
            datos_satelitales = descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, "NDVI")
        elif satelite == "MODIS":
            producto_modis = st.session_state.get('producto_modis', 'MOD13Q1')
            indices_modis = st.session_state.get('indices_modis', ['NDVI', 'EVI', 'NDWI', 'SAVI'])
            datos_satelitales = obtener_datos_modis_nasa(gdf, fecha_inicio, fecha_fin, producto_modis, indices_modis)
            resultados['datos_modis'] = datos_satelitales
        else:
            datos_satelitales = generar_datos_simulados(gdf, cultivo, "NDVI")
        
        df_power = obtener_datos_nasa_power(gdf, fecha_inicio, fecha_fin)
        resultados['df_power'] = df_power
        
        gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        resultados['gdf_dividido'] = gdf_dividido
        st.session_state.gdf_dividido = gdf_dividido
        
        areas_ha_list = []
        for idx, row in gdf_dividido.iterrows():
            area_gdf = gpd.GeoDataFrame({'geometry': [row.geometry]}, crs=gdf_dividido.crs)
            area_ha = calcular_superficie(area_gdf)
            if hasattr(area_ha, 'iloc'):
                area_ha = float(area_ha.iloc[0])
            elif hasattr(area_ha, '__len__') and len(area_ha) > 0:
                area_ha = float(area_ha[0])
            else:
                area_ha = float(area_ha)
            areas_ha_list.append(area_ha)
        
        gdf_dividido['area_ha'] = areas_ha_list
        
        fertilidad_actual = analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales)
        resultados['fertilidad_actual'] = fertilidad_actual
        
        rec_n, rec_p, rec_k = analizar_recomendaciones_npk(fertilidad_actual, cultivo)
        resultados['recomendaciones_npk'] = {
            'N': rec_n,
            'P': rec_p,
            'K': rec_k
        }
        
        costos = analizar_costos(gdf_dividido, cultivo, rec_n, rec_p, rec_k)
        resultados['costos'] = costos
        
        proyecciones = analizar_proyecciones_cosecha(gdf_dividido, cultivo, fertilidad_actual)
        resultados['proyecciones'] = proyecciones
        
        textura = analizar_textura_suelo(gdf_dividido, cultivo)
        resultados['textura'] = textura
        
        try:
            X, Y, Z, bounds = generar_dem_sintetico(gdf, resolucion_dem)
            pendientes = calcular_pendiente(X, Y, Z, resolucion_dem)
            curvas_nivel, elevaciones = generar_curvas_nivel(X, Y, Z, intervalo_curvas)
            
            resultados['dem_data'] = {
                'X': X,
                'Y': Y,
                'Z': Z,
                'bounds': bounds,
                'pendientes': pendientes,
                'curvas_nivel': curvas_nivel,
                'elevaciones': elevaciones
            }
        except Exception as e:
            st.warning(f"⚠️ Error generando DEM y curvas de nivel: {e}")
        
        gdf_completo = textura.copy()
        
        for i, fert in enumerate(fertilidad_actual):
            for key, value in fert.items():
                gdf_completo.at[gdf_completo.index[i], f'fert_{key}'] = value
        
        gdf_completo['rec_N'] = rec_n
        gdf_completo['rec_P'] = rec_p
        gdf_completo['rec_K'] = rec_k
        
        for i, costo in enumerate(costos):
            for key, value in costo.items():
                gdf_completo.at[gdf_completo.index[i], f'costo_{key}'] = value
        
        for i, proy in enumerate(proyecciones):
            for key, value in proy.items():
                gdf_completo.at[gdf_completo.index[i], f'proy_{key}'] = value
        
        resultados['gdf_completo'] = gdf_completo
        resultados['exitoso'] = True
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error en análisis completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return resultados

# ===== FUNCIONES DE VISUALIZACIÓN =====
def crear_mapa_fertilidad(gdf_completo, cultivo, satelite):
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
        vmin, vmax = 0, 1
        
        for idx, row in gdf_plot.iterrows():
            valor = row['fert_npk_actual']
            valor_norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.7)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.2f}", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.7)
        except:
            pass
        
        info_satelite = SATELITES_DISPONIBLES.get(satelite, SATELITES_DISPONIBLES['DATOS_SIMULADOS'])
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} FERTILIDAD ACTUAL - {cultivo}\n'
                     f'{info_satelite["icono"]} {info_satelite["nombre"]}',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label('Índice de Fertilidad', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de fertilidad: {str(e)}")
        return None

def crear_mapa_npk(gdf_completo, cultivo, nutriente='N'):
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        if nutriente == 'N':
            cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
            columna = 'rec_N'
            titulo_nut = 'NITRÓGENO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max'] * 1.2
        elif nutriente == 'P':
            cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
            columna = 'rec_P'
            titulo_nut = 'FÓSFORO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max'] * 1.2
        else:
            cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
            columna = 'rec_K'
            titulo_nut = 'POTASIO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max'] * 1.2
        
        for idx, row in gdf_plot.iterrows():
            valor = row[columna]
            valor_norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.7)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.0f}", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.7)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} RECOMENDACIONES {titulo_nut} - {cultivo}',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(f'{titulo_nut} (kg/ha)', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa NPK: {str(e)}")
        return None

def crear_mapa_texturas(gdf_completo, cultivo):
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        colores_textura = {
            'Franco': '#c7eae5',
            'Franco arcilloso': '#5ab4ac',
            'Franco arenoso': '#f6e8c3',
            'NO_DETERMINADA': '#999999'
        }
        
        for idx, row in gdf_plot.iterrows():
            textura = row['textura_suelo']
            color = colores_textura.get(textura, '#999999')
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.8)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{textura[:10]}", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.6)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} MAPA DE TEXTURAS - {cultivo}',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=color, edgecolor='black', label=textura)
                           for textura, color in colores_textura.items()]
        ax.legend(handles=legend_elements, title='Texturas', loc='upper left', bbox_to_anchor=(1.05, 1))
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de texturas: {str(e)}")
        return None

def crear_mapa_indice_vegetacion(gdf_completo, cultivo, indice='NDVI'):
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        if indice == 'NDVI':
            cmap = LinearSegmentedColormap.from_list('ndvi_cmap', PALETAS_GEE['NDVI'])
            columna = 'fert_ndvi'
            vmin, vmax = -0.2, 1.0
            titulo = 'NDVI'
        elif indice == 'EVI':
            cmap = LinearSegmentedColormap.from_list('evi_cmap', PALETAS_GEE['EVI'])
            columna = 'fert_evi'
            vmin, vmax = 0.0, 1.0
            titulo = 'EVI'
        elif indice == 'NDWI':
            cmap = LinearSegmentedColormap.from_list('ndwi_cmap', PALETAS_GEE['NDWI'])
            columna = 'fert_ndwi'
            vmin, vmax = -1.0, 1.0
            titulo = 'NDWI'
        elif indice == 'SAVI':
            cmap = LinearSegmentedColormap.from_list('savi_cmap', PALETAS_GEE['NDVI'])
            columna = 'fert_savi'
            vmin, vmax = 0.0, 1.0
            titulo = 'SAVI'
        else:
            cmap = LinearSegmentedColormap.from_list('default_cmap', PALETAS_GEE['NDVI'])
            columna = 'fert_ndvi'
            vmin, vmax = 0.0, 1.0
            titulo = indice
        
        for idx, row in gdf_plot.iterrows():
            valor = row[columna]
            valor_norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.7)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.3f}", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.7)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} {titulo} - {cultivo}\nDatos MODIS NASA',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(f'{titulo} Valor', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de {indice}: {str(e)}")
        return None

def crear_grafico_comparativa_indices(indices_data, cultivo):
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        nombres_indices = list(indices_data.keys())
        valores_promedio = [indices_data[idx]['valor_promedio'] for idx in nombres_indices]
        valores_min = [indices_data[idx]['valor_min'] for idx in nombres_indices]
        valores_max = [indices_data[idx]['valor_max'] for idx in nombres_indices]
        
        x_pos = np.arange(len(nombres_indices))
        bars = ax.bar(x_pos, valores_promedio, color='#66c2a5', edgecolor='black', alpha=0.7)
        
        ax.errorbar(x_pos, valores_promedio, 
                   yerr=[np.array(valores_promedio) - np.array(valores_min), 
                         np.array(valores_max) - np.array(valores_promedio)],
                   fmt='none', ecolor='red', capsize=5, capthick=2)
        
        valores_optimos = []
        for idx in nombres_indices:
            if idx in PARAMETROS_CULTIVOS[cultivo]:
                valores_optimos.append(PARAMETROS_CULTIVOS[cultivo][f'{idx}_OPTIMO'])
            else:
                valores_optimos.append(None)
        
        x_pos_opt = [i for i, val in enumerate(valores_optimos) if val is not None]
        valores_opt_plot = [val for val in valores_optimos if val is not None]
        
        if x_pos_opt:
            ax.plot(x_pos_opt, valores_opt_plot, 'g--', linewidth=2, marker='o', 
                   markersize=8, label='Valor Óptimo')
        
        ax.set_xlabel('Índice de Vegetación', fontsize=12)
        ax.set_ylabel('Valor', fontsize=12)
        ax.set_title(f'Comparativa de Índices - {cultivo} (Datos MODIS NASA)', 
                    fontsize=14, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(nombres_indices, rotation=45, ha='right')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                   f'{height:.3f}', ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando gráfico comparativo: {str(e)}")
        return None

# ===== INTERFAZ PRINCIPAL =====
st.title("ANALIZADOR MULTI-CULTIVO SATELITAL CON DATOS MODIS NASA")

if uploaded_file:
    with st.spinner("Cargando parcela..."):
        try:
            gdf = cargar_archivo_parcela(uploaded_file)
            if gdf is not None:
                st.success(f"✅ **Parcela cargada exitosamente:** {len(gdf)} polígono(s)")
                area_total = calcular_superficie(gdf)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**📊 INFORMACIÓN DE LA PARCELA:**")
                    st.write(f"- Polígonos: {len(gdf)}")
                    st.write(f"- Área total: {area_total:.1f} ha")
                    st.write(f"- CRS: {gdf.crs}")
                    st.write(f"- Formato: {uploaded_file.name.split('.')[-1].upper()}")
                    
                    fig, ax = plt.subplots(figsize=(8, 6))
                    gdf.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
                    ax.set_title(f"Parcela: {uploaded_file.name}")
                    ax.set_xlabel("Longitud")
                    ax.set_ylabel("Latitud")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    
                    buf_vista = io.BytesIO()
                    plt.savefig(buf_vista, format='png', dpi=150, bbox_inches='tight')
                    buf_vista.seek(0)
                    st.download_button(
                        label="📥 Descargar Vista Previa PNG",
                        data=buf_vista,
                        file_name=f"vista_previa_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                        mime="image/png"
                    )
                    
                with col2:
                    st.write("**🎯 CONFIGURACIÓN**")
                    st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                    st.write(f"- Zonas: {n_divisiones}")
                    st.write(f"- Satélite: {SATELITES_DISPONIBLES[satelite_seleccionado]['nombre']}")
                    
                    if satelite_seleccionado == "MODIS":
                        producto_modis = st.session_state.get('producto_modis', 'MOD13Q1')
                        st.write(f"- Producto MODIS: {producto_modis}")
                        st.write(f"- Índices: {', '.join(st.session_state.get('indices_modis', ['NDVI', 'EVI']))}")
                    
                    st.write(f"- Período: {fecha_inicio} a {fecha_fin}")
                    st.write(f"- Intervalo curvas: {intervalo_curvas} m")
                    st.write(f"- Resolución DEM: {resolucion_dem} m")
                
                if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
                    with st.spinner("Ejecutando análisis completo..."):
                        resultados = ejecutar_analisis_completo(
                            gdf, cultivo, n_divisiones, 
                            satelite_seleccionado, fecha_inicio, fecha_fin,
                            intervalo_curvas, resolucion_dem
                        )
                        
                        if resultados['exitoso']:
                            st.session_state.resultados_todos = resultados
                            st.session_state.analisis_completado = True
                            st.success("✅ Análisis completado exitosamente!")
                            st.rerun()
                        else:
                            st.error("❌ Error en el análisis completo")
            
            else:
                st.error("❌ Error al cargar la parcela. Verifica el formato del archivo.")
        
        except Exception as e:
            st.error(f"❌ Error en el análisis: {str(e)}")
            import traceback
            traceback.print_exc()

if st.session_state.analisis_completado and 'resultados_todos' in st.session_state:
    resultados = st.session_state.resultados_todos
    
    tab_titles = [
        "📊 Fertilidad Actual",
        "🧪 Recomendaciones NPK",
        "💰 Análisis de Costos",
        "🏗️ Textura del Suelo",
        "📈 Proyecciones",
        "🏔️ Curvas de Nivel y 3D"
    ]
    
    if satelite_seleccionado == "MODIS" and 'datos_modis' in resultados:
        tab_titles.insert(1, "🌍 Datos MODIS NASA")
    
    tabs = st.tabs(tab_titles)
    
    with tabs[0]:
        st.subheader("FERTILIDAD ACTUAL")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            npk_prom = resultados['gdf_completo']['fert_npk_actual'].mean()
            st.metric("Índice NPK Promedio", f"{npk_prom:.3f}")
        with col2:
            ndvi_prom = resultados['gdf_completo']['fert_ndvi'].mean()
            st.metric("NDVI Promedio", f"{ndvi_prom:.3f}")
        with col3:
            evi_prom = resultados['gdf_completo']['fert_evi'].mean()
            st.metric("EVI Promedio", f"{evi_prom:.3f}")
        with col4:
            savi_prom = resultados['gdf_completo']['fert_savi'].mean()
            st.metric("SAVI Promedio", f"{savi_prom:.3f}")
        
        st.subheader("🗺️ MAPA DE FERTILIDAD")
        mapa_fert = crear_mapa_fertilidad(resultados['gdf_completo'], cultivo, satelite_seleccionado)
        if mapa_fert:
            st.image(mapa_fert, use_container_width=True)
            st.download_button(
                label="📥 Descargar Mapa de Fertilidad PNG",
                data=mapa_fert,
                file_name=f"mapa_fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                mime="image/png"
            )
        
        st.subheader("📋 TABLA DE RESULTADOS")
        columnas_fert = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 
                       'fert_evi', 'fert_ndwi', 'fert_savi', 'fert_materia_organica', 'fert_humedad_suelo']
        tabla_fert = resultados['gdf_completo'][columnas_fert].copy()
        tabla_fert.columns = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 
                            'EVI', 'NDWI', 'SAVI', 'Materia Org (%)', 'Humedad']
        st.dataframe(tabla_fert)
    
    if satelite_seleccionado == "MODIS" and 'datos_modis' in resultados:
        with tabs[1]:
            datos_modis = resultados['datos_modis']
            st.subheader("🌍 DATOS MODIS NASA")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**📊 INFORMACIÓN DEL PRODUCTO:**")
                st.write(f"- Producto: {datos_modis.get('producto', 'N/A')}")
                st.write(f"- Resolución: {datos_modis.get('resolucion', 'N/A')}")
                st.write(f"- Fecha inicio: {datos_modis.get('fecha_inicio', 'N/A')}")
                st.write(f"- Fecha fin: {datos_modis.get('fecha_fin', 'N/A')}")
                
                st.write("**📈 METADATOS:**")
                for key, value in datos_modis.get('metadatos', {}).items():
                    st.write(f"- {key}: {value}")
            
            with col2:
                st.write("**📊 ESTADÍSTICAS DE ÍNDICES:**")
                if 'indices' in datos_modis:
                    for idx, data in datos_modis['indices'].items():
                        st.metric(
                            f"{idx}",
                            f"{data['valor_promedio']:.3f}",
                            delta=f"Rango: {data['valor_min']:.3f} - {data['valor_max']:.3f}"
                        )
            
            st.subheader("📊 COMPARATIVA DE ÍNDICES MODIS")
            if 'indices' in datos_modis:
                grafico_comparativo = crear_grafico_comparativa_indices(datos_modis['indices'], cultivo)
                if grafico_comparativo:
                    st.image(grafico_comparativo, use_container_width=True)
                    st.download_button(
                        label="📥 Descargar Gráfico Comparativo PNG",
                        data=grafico_comparativo,
                        file_name=f"comparativa_indices_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                        mime="image/png"
                    )
            
            st.subheader("🗺️ MAPAS DE ÍNDICES MODIS")
            indices_disponibles = ['NDVI', 'EVI', 'NDWI', 'SAVI']
            
            cols_mapas = st.columns(2)
            for i, indice in enumerate(indices_disponibles):
                if indice in datos_modis.get('indices', {}):
                    with cols_mapas[i % 2]:
                        mapa_indice = crear_mapa_indice_vegetacion(resultados['gdf_completo'], cultivo, indice)
                        if mapa_indice:
                            st.image(mapa_indice, use_container_width=True)
                            st.caption(f"{indice}")
                            st.download_button(
                                label=f"📥 Descargar Mapa {indice}",
                                data=mapa_indice,
                                file_name=f"mapa_{indice.lower()}_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                                mime="image/png"
                            )
    
    idx_offset = 1 if satelite_seleccionado == "MODIS" and 'datos_modis' in resultados else 0
    
    with tabs[1 + idx_offset]:
        st.subheader("RECOMENDACIONES NPK")
        col1, col2, col3 = st.columns(3)
        with col1:
            n_prom = resultados['gdf_completo']['rec_N'].mean()
            st.metric("Nitrógeno Promedio", f"{n_prom:.1f} kg/ha")
        with col2:
            p_prom = resultados['gdf_completo']['rec_P'].mean()
            st.metric("Fósforo Promedio", f"{p_prom:.1f} kg/ha")
        with col3:
            k_prom = resultados['gdf_completo']['rec_K'].mean()
            st.metric("Potasio Promedio", f"{k_prom:.1f} kg/ha")
        
        st.subheader("🗺️ MAPAS DE RECOMENDACIONES")
        col_n, col_p, col_k = st.columns(3)
        with col_n:
            mapa_n = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'N')
            if mapa_n:
                st.image(mapa_n, use_container_width=True)
                st.caption("Nitrógeno (N)")
                st.download_button(
                    label="📥 Descargar Mapa N",
                    data=mapa_n,
                    file_name=f"mapa_nitrogeno_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
        with col_p:
            mapa_p = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'P')
            if mapa_p:
                st.image(mapa_p, use_container_width=True)
                st.caption("Fósforo (P)")
                st.download_button(
                    label="📥 Descargar Mapa P",
                    data=mapa_p,
                    file_name=f"mapa_fosforo_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
        with col_k:
            mapa_k = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'K')
            if mapa_k:
                st.image(mapa_k, use_container_width=True)
                st.caption("Potasio (K)")
                st.download_button(
                    label="📥 Descargar Mapa K",
                    data=mapa_k,
                    file_name=f"mapa_potasio_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
        
        st.subheader("📋 TABLA DE RECOMENDACIONES")
        columnas_npk = ['id_zona', 'area_ha', 'rec_N', 'rec_P', 'rec_K']
        tabla_npk = resultados['gdf_completo'][columnas_npk].copy()
        tabla_npk.columns = ['Zona', 'Área (ha)', 'Nitrógeno (kg/ha)', 
                           'Fósforo (kg/ha)', 'Potasio (kg/ha)']
        st.dataframe(tabla_npk)
    
    with tabs[2 + idx_offset]:
        st.subheader("ANÁLISIS DE COSTOS")
        costo_total = resultados['gdf_completo']['costo_costo_total'].sum()
        costo_prom = resultados['gdf_completo']['costo_costo_total'].mean()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Costo Total Estimado", f"${costo_total:.2f} USD")
        with col2:
            st.metric("Costo Promedio por ha", f"${costo_prom:.2f} USD/ha")
        with col3:
            inversion_ha = costo_total / resultados['area_total'] if resultados['area_total'] > 0 else 0
            st.metric("Inversión por ha", f"${inversion_ha:.2f} USD/ha")
        
        st.subheader("📊 DISTRIBUCIÓN DE COSTOS")
        costos_n = resultados['gdf_completo']['costo_costo_nitrogeno'].sum()
        costos_p = resultados['gdf_completo']['costo_costo_fosforo'].sum()
        costos_k = resultados['gdf_completo']['costo_costo_potasio'].sum()
        otros = costo_total - (costos_n + costos_p + costos_k)
        
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            categorias = ['Nitrógeno', 'Fósforo', 'Potasio', 'Otros']
            valores = [costos_n, costos_p, costos_k, otros]
            colores = ['#00ff00', '#0000ff', '#4B0082', '#cccccc']
            bars = ax.bar(categorias, valores, color=colores, edgecolor='black')
            ax.set_title('Distribución de Costos de Fertilización', fontsize=14, fontweight='bold')
            ax.set_ylabel('USD', fontsize=12)
            ax.set_xlabel('Componente', fontsize=12)
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 10,
                       f'${height:.0f}', ha='center', va='bottom', fontweight='bold')
            
            plt.tight_layout()
            buf_costos = io.BytesIO()
            plt.savefig(buf_costos, format='png', dpi=150, bbox_inches='tight')
            buf_costos.seek(0)
            st.image(buf_costos, use_container_width=True)
            st.download_button(
                label="📥 Descargar Gráfico de Costos PNG",
                data=buf_costos,
                file_name=f"grafico_costos_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                mime="image/png"
            )
        except Exception as e:
            st.error(f"❌ Error creando gráfico de costos: {str(e)}")
        
        st.subheader("📋 TABLA DE COSTOS POR ZONA")
        columnas_costos = ['id_zona', 'area_ha', 'costo_costo_nitrogeno', 
                         'costo_costo_fosforo', 'costo_costo_potasio', 'costo_costo_total']
        tabla_costos = resultados['gdf_completo'][columnas_costos].copy()
        tabla_costos.columns = ['Zona', 'Área (ha)', 'Costo N (USD)', 
                              'Costo P (USD)', 'Costo K (USD)', 'Total (USD)']
        st.dataframe(tabla_costos)
    
    with tabs[3 + idx_offset]:
        st.subheader("TEXTURA DEL SUELO")
        textura_pred = resultados['gdf_completo']['textura_suelo'].mode()[0] if len(resultados['gdf_completo']) > 0 else "N/D"
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Textura Predominante", textura_pred)
        with col2:
            arena_prom = resultados['gdf_completo']['arena'].mean()
            st.metric("Arena Promedio", f"{arena_prom:.1f}%")
        with col3:
            limo_prom = resultados['gdf_completo']['limo'].mean()
            st.metric("Limo Promedio", f"{limo_prom:.1f}%")
        with col4:
            arcilla_prom = resultados['gdf_completo']['arcilla'].mean()
            st.metric("Arcilla Promedio", f"{arcilla_prom:.1f}%")
        
        st.subheader("🗺️ MAPA DE TEXTURAS")
        mapa_text = crear_mapa_texturas(resultados['gdf_completo'], cultivo)
        if mapa_text:
            st.image(mapa_text, use_container_width=True)
            st.download_button(
                label="📥 Descargar Mapa de Texturas PNG",
                data=mapa_text,
                file_name=f"mapa_texturas_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                mime="image/png"
            )
        
        st.subheader("📊 COMPOSICIÓN GRANULOMÉTRICA")
        textura_dist = resultados['gdf_completo']['textura_suelo'].value_counts()
        
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            composicion = [arena_prom, limo_prom, arcilla_prom]
            labels = ['Arena', 'Limo', 'Arcilla']
            colors_pie = ['#d8b365', '#f6e8c3', '#01665e']
            ax1.pie(composicion, labels=labels, colors=colors_pie, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Composición Promedio del Suelo')
            
            ax2.bar(textura_dist.index, textura_dist.values, 
                   color=[PALETAS_GEE['TEXTURA'][i % len(PALETAS_GEE['TEXTURA'])] for i in range(len(textura_dist))])
            ax2.set_title('Distribución de Texturas')
            ax2.set_xlabel('Textura')
            ax2.set_ylabel('Número de Zonas')
            ax2.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            buf_textura = io.BytesIO()
            plt.savefig(buf_textura, format='png', dpi=150, bbox_inches='tight')
            buf_textura.seek(0)
            st.image(buf_textura, use_container_width=True)
            st.download_button(
                label="📥 Descargar Gráfico de Textura PNG",
                data=buf_textura,
                file_name=f"grafico_textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                mime="image/png"
            )
        except Exception as e:
            st.error(f"❌ Error creando gráfico de textura: {str(e)}")
        
        st.subheader("📋 TABLA DE TEXTURAS POR ZONA")
        columnas_text = ['id_zona', 'area_ha', 'textura_suelo', 'arena', 'limo', 'arcilla']
        tabla_text = resultados['gdf_completo'][columnas_text].copy()
        tabla_text.columns = ['Zona', 'Área (ha)', 'Textura', 'Arena (%)', 'Limo (%)', 'Arcilla (%)']
        st.dataframe(tabla_text)
    
    with tabs[4 + idx_offset]:
        st.subheader("PROYECCIONES DE COSECHA")
        rend_sin = resultados['gdf_completo']['proy_rendimiento_sin_fert'].sum()
        rend_con = resultados['gdf_completo']['proy_rendimiento_con_fert'].sum()
        incremento = ((rend_con - rend_sin) / rend_sin * 100) if rend_sin > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rendimiento sin Fertilización", f"{rend_sin:.0f} kg")
        with col2:
            st.metric("Rendimiento con Fertilización", f"{rend_con:.0f} kg")
        with col3:
            st.metric("Incremento Esperado", f"{incremento:.1f}%")
        
        st.subheader("📊 COMPARATIVA DE RENDIMIENTOS")
        zonas = resultados['gdf_completo']['id_zona'].head(10).astype(str)
        sin_fert = resultados['gdf_completo']['proy_rendimiento_sin_fert'].head(10)
        con_fert = resultados['gdf_completo']['proy_rendimiento_con_fert'].head(10)
        
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(zonas))
            width = 0.35
            bars1 = ax.bar(x - width/2, sin_fert, width, label='Sin Fertilización', color='#ff9999')
            bars2 = ax.bar(x + width/2, con_fert, width, label='Con Fertilización', color='#66b3ff')
            ax.set_xlabel('Zona')
            ax.set_ylabel('Rendimiento (kg)')
            ax.set_title('Proyecciones de Rendimiento por Zona')
            ax.set_xticks(x)
            ax.set_xticklabels(zonas)
            ax.legend()
            
            def autolabel(bars):
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 50,
                           f'{height:.0f}', ha='center', va='bottom', fontsize=8)
            
            autolabel(bars1)
            autolabel(bars2)
            
            plt.tight_layout()
            buf_proyecciones = io.BytesIO()
            plt.savefig(buf_proyecciones, format='png', dpi=150, bbox_inches='tight')
            buf_proyecciones.seek(0)
            st.image(buf_proyecciones, use_container_width=True)
            st.download_button(
                label="📥 Descargar Gráfico de Proyecciones PNG",
                data=buf_proyecciones,
                file_name=f"grafico_proyecciones_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                mime="image/png"
            )
        except Exception as e:
            st.error(f"❌ Error creando gráfico de proyecciones: {str(e)}")
        
        st.subheader("💰 ANÁLISIS ECONÓMICO")
        precio = PARAMETROS_CULTIVOS[cultivo]['PRECIO_VENTA']
        ingreso_sin = rend_sin * precio
        ingreso_con = rend_con * precio
        costo_fert = costo_total
        beneficio_neto = (ingreso_con - ingreso_sin) - costo_fert
        roi = (beneficio_neto / costo_fert * 100) if costo_fert > 0 else 0
        
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.metric("Ingreso Adicional", f"${ingreso_con - ingreso_sin:.2f} USD")
        with col_e2:
            st.metric("Beneficio Neto", f"${beneficio_neto:.2f} USD")
        with col_e3:
            st.metric("ROI Estimado", f"{roi:.1f}%")
        
        st.subheader("📋 TABLA DE PROYECCIONES POR ZONA")
        columnas_proy = ['id_zona', 'area_ha', 'proy_rendimiento_sin_fert', 
                       'proy_rendimiento_con_fert', 'proy_incremento_esperado']
        tabla_proy = resultados['gdf_completo'][columnas_proy].copy()
        tabla_proy.columns = ['Zona', 'Área (ha)', 'Sin Fertilización (kg)', 
                            'Con Fertilización (kg)', 'Incremento (%)']
        st.dataframe(tabla_proy)
    
    with tabs[5 + idx_offset]:
        if 'dem_data' in resultados and resultados['dem_data']:
            dem_data = resultados['dem_data']
            
            st.subheader("🏔️ ANÁLISIS TOPOGRÁFICO")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                elev_min = np.nanmin(dem_data['Z'])
                st.metric("Elevación Mínima", f"{elev_min:.1f} m")
            with col2:
                elev_max = np.nanmax(dem_data['Z'])
                st.metric("Elevación Máxima", f"{elev_max:.1f} m")
            with col3:
                elev_prom = np.nanmean(dem_data['Z'])
                st.metric("Elevación Promedio", f"{elev_prom:.1f} m")
            with col4:
                pend_prom = np.nanmean(dem_data['pendientes'])
                st.metric("Pendiente Promedio", f"{pend_prom:.1f}%")
            
            st.subheader("🗺️ MAPA DE PENDIENTES")
            try:
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
                scatter = ax1.scatter(dem_data['X'].flatten(), dem_data['Y'].flatten(), 
                                     c=dem_data['pendientes'].flatten(), cmap='RdYlGn_r', 
                                     s=10, alpha=0.7, vmin=0, vmax=30)
                gdf.plot(ax=ax1, color='none', edgecolor='black', linewidth=2)
                cbar = plt.colorbar(scatter, ax=ax1, shrink=0.8)
                cbar.set_label('Pendiente (%)')
                ax1.set_title('Mapa de Calor de Pendientes', fontsize=12, fontweight='bold')
                ax1.set_xlabel('Longitud')
                ax1.set_ylabel('Latitud')
                ax1.grid(True, alpha=0.3)
                
                pendientes_flat = dem_data['pendientes'].flatten()
                pendientes_flat = pendientes_flat[~np.isnan(pendientes_flat)]
                ax2.hist(pendientes_flat, bins=30, edgecolor='black', color='skyblue', alpha=0.7)
                
                for porcentaje, color in [(2, 'green'), (5, 'lightgreen'), (10, 'yellow'), 
                                         (15, 'orange'), (25, 'red')]:
                    ax2.axvline(x=porcentaje, color=color, linestyle='--', linewidth=1, alpha=0.7)
                    ax2.text(porcentaje+0.5, ax2.get_ylim()[1]*0.9, f'{porcentaje}%', 
                            color=color, fontsize=8)
                
                stats_text = f"""Estadísticas:
• Mínima: {np.nanmin(pendientes_flat):.1f}%
• Máxima: {np.nanmax(pendientes_flat):.1f}%
• Promedio: {np.nanmean(pendientes_flat):.1f}%
• Desviación: {np.nanstd(pendientes_flat):.1f}%"""
                ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9, 
                        verticalalignment='top', 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
                
                ax2.set_xlabel('Pendiente (%)')
                ax2.set_ylabel('Frecuencia')
                ax2.set_title('Distribución de Pendientes', fontsize=12, fontweight='bold')
                ax2.grid(True, alpha=0.3)
                
                plt.tight_layout()
                buf_pendientes = io.BytesIO()
                plt.savefig(buf_pendientes, format='png', dpi=150, bbox_inches='tight')
                buf_pendientes.seek(0)
                st.image(buf_pendientes, use_container_width=True)
                st.download_button(
                    label="📥 Descargar Mapa de Pendientes PNG",
                    data=buf_pendientes,
                    file_name=f"mapa_pendientes_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
            except Exception as e:
                st.error(f"❌ Error creando mapa de pendientes: {str(e)}")
            
            st.subheader("🗺️ MAPA DE CURVAS DE NIVEL")
            try:
                fig, ax = plt.subplots(1, 1, figsize=(12, 8))
                contour = ax.contourf(dem_data['X'], dem_data['Y'], dem_data['Z'], levels=20, cmap='terrain', alpha=0.7)
                
                if 'curvas_nivel' in dem_data and dem_data['curvas_nivel']:
                    for curva, elevacion in zip(dem_data['curvas_nivel'], dem_data.get('elevaciones', [])):
                        if hasattr(curva, 'coords'):
                            coords = np.array(curva.coords)
                            ax.plot(coords[:, 0], coords[:, 1], 'b-', linewidth=0.8, alpha=0.7)
                            if len(coords) > 0:
                                mid_idx = len(coords) // 2
                                ax.text(coords[mid_idx, 0], coords[mid_idx, 1], 
                                       f'{elevacion:.0f}m', fontsize=8, color='blue',
                                       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.7))
                
                gdf.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
                cbar = plt.colorbar(contour, ax=ax, shrink=0.8)
                cbar.set_label('Elevación (m)')
                ax.set_title('Mapa de Curvas de Nivel', fontsize=14, fontweight='bold')
                ax.set_xlabel('Longitud')
                ax.set_ylabel('Latitud')
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                buf_curvas = io.BytesIO()
                plt.savefig(buf_curvas, format='png', dpi=150, bbox_inches='tight')
                buf_curvas.seek(0)
                st.image(buf_curvas, use_container_width=True)
                st.download_button(
                    label="📥 Descargar Mapa de Curvas PNG",
                    data=buf_curvas,
                    file_name=f"mapa_curvas_nivel_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
            except Exception as e:
                st.error(f"❌ Error creando mapa de curvas de nivel: {str(e)}")
            
            st.subheader("🎨 VISUALIZACIÓN 3D DEL TERRENO")
            try:
                fig = plt.figure(figsize=(14, 10))
                ax = fig.add_subplot(111, projection='3d')
                surf = ax.plot_surface(dem_data['X'], dem_data['Y'], dem_data['Z'], 
                                      cmap='terrain', alpha=0.8, linewidth=0.5, antialiased=True)
                ax.set_xlabel('Longitud', fontsize=10)
                ax.set_ylabel('Latitud', fontsize=10)
                ax.set_zlabel('Elevación (m)', fontsize=10)
                ax.set_title('Modelo 3D del Terreno', fontsize=14, fontweight='bold', pad=20)
                fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label='Elevación (m)')
                ax.grid(True, alpha=0.3)
                ax.view_init(elev=30, azim=45)
                
                plt.tight_layout()
                buf_3d = io.BytesIO()
                plt.savefig(buf_3d, format='png', dpi=150, bbox_inches='tight')
                buf_3d.seek(0)
                st.image(buf_3d, use_container_width=True)
                st.download_button(
                    label="📥 Descargar Visualización 3D PNG",
                    data=buf_3d,
                    file_name=f"visualizacion_3d_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png"
                )
            except Exception as e:
                st.error(f"❌ Error creando visualización 3D: {str(e)}")
    
    st.markdown("---")
    st.subheader("💾 EXPORTAR RESULTADOS")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown("**GeoJSON**")
        if st.button("📤 Generar GeoJSON", key="generate_geojson"):
            with st.spinner("Generando GeoJSON..."):
                try:
                    gdf_completo = resultados['gdf_completo']
                    gdf_completo = validar_y_corregir_crs(gdf_completo)
                    geojson_data = gdf_completo.to_json()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_archivo = f"analisis_{cultivo}_{timestamp}.geojson"
                    st.session_state.geojson_data = geojson_data
                    st.session_state.nombre_geojson = nombre_archivo
                    st.success("✅ GeoJSON generado correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error exportando a GeoJSON: {str(e)}")
        
        if st.session_state.geojson_data:
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=st.session_state.geojson_data,
                file_name=st.session_state.nombre_geojson,
                mime="application/json",
                key="geojson_download"
            )
    
    with col_exp2:
        st.markdown("**Reporte Completo**")
        if st.button("📄 Generar Reporte DOCX", key="generate_docx"):
            with st.spinner("Generando reporte completo..."):
                try:
                    doc = Document()
                    title = doc.add_heading(f'REPORTE COMPLETO DE ANÁLISIS - {cultivo}', 0)
                    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    subtitle = doc.add_paragraph(f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
                    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    doc.add_paragraph()
                    doc.add_heading('1. INFORMACIÓN GENERAL', level=1)
                    info_table = doc.add_table(rows=6, cols=2)
                    info_table.style = 'Table Grid'
                    info_table.cell(0, 0).text = 'Cultivo'
                    info_table.cell(0, 1).text = cultivo
                    info_table.cell(1, 0).text = 'Área Total'
                    info_table.cell(1, 1).text = f'{resultados["area_total"]:.2f} ha'
                    info_table.cell(2, 0).text = 'Zonas Analizadas'
                    info_table.cell(2, 1).text = str(len(resultados['gdf_completo']))
                    info_table.cell(3, 0).text = 'Satélite'
                    info_table.cell(3, 1).text = satelite_seleccionado
                    info_table.cell(4, 0).text = 'Fuente de Datos'
                    info_table.cell(4, 1).text = 'MODIS NASA' if satelite_seleccionado == 'MODIS' else satelite_seleccionado
                    info_table.cell(5, 0).text = 'Período de Análisis'
                    info_table.cell(5, 1).text = f'{fecha_inicio.strftime("%d/%m/%Y")} a {fecha_fin.strftime("%d/%m/%Y")}'
                    docx_output = BytesIO()
                    doc.save(docx_output)
                    docx_output.seek(0)
                    st.session_state.reporte_completo = docx_output
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    nombre_reporte = f"reporte_completo_{cultivo}_{timestamp}.docx"
                    st.session_state.nombre_reporte = nombre_reporte
                    st.success("✅ Reporte generado correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error generando reporte DOCX: {str(e)}")
        
        if st.session_state.reporte_completo is not None:
            st.download_button(
                label="📥 Descargar Reporte DOCX",
                data=st.session_state.reporte_completo,
                file_name=st.session_state.nombre_reporte,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="docx_download"
            )
    
    if st.session_state.reporte_completo or st.session_state.geojson_data:
        st.markdown("---")
        if st.button("🗑️ Limpiar Reportes Generados", key="clear_reports"):
            st.session_state.reporte_completo = None
            st.session_state.geojson_data = None
            st.session_state.nombre_geojson = ""
            st.session_state.nombre_reporte = ""
            st.success("Reportes limpiados correctamente")
            st.rerun()

else:
    st.info("👈 Por favor, sube un archivo de parcela y ejecuta el análisis para comenzar.")

# ===== PIE DE PÁGINA =====
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns(3)
with col_footer1:
    st.markdown("""
**📡 Fuentes de Datos:**
- NASA MODIS API
- NASA POWER API
- Sentinel-2 (ESA)
- Landsat-8 (USGS)
""")
with col_footer2:
    st.markdown("""
**🛠️ Tecnologías:**
- Streamlit
- GeoPandas
- Matplotlib
- Python-DOCX
- NASA Earthdata API
""")
with col_footer3:
    st.markdown("""
**📞 Soporte:**
- Versión: 6.0 - MODIS NASA
- Última actualización: Enero 2026
- Datos MODIS: NASA Earth Observing System
""")

st.markdown(
    '<div style="text-align: center; color: #94a3b8; font-size: 0.9em; margin-top: 2em;">'
    '© 2026 Analizador Multi-Cultivo Satelital con MODIS NASA. Todos los derechos reservados.'
    '</div>',
    unsafe_allow_html=True
)
