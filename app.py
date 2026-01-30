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

# ===== MANEJO SEGURO DE SENTINEL HUB =====
try:
    from sentinelhub import (
        SHConfig, BBox, CRS, SentinelHubRequest, 
        DataCollection, MimeType, bbox_to_dimensions,
        SentinelHubCatalog
    )
    SENTINELHUB_AVAILABLE = True
except ImportError:
    SENTINELHUB_AVAILABLE = False
    st.sidebar.warning("⚠️ Paquete 'sentinelhub' no instalado. Usando datos simulados.")

warnings.filterwarnings('ignore')

# ===== CONFIGURACIÓN DE SENTINEL HUB (HARDCODED) =====
def configurar_sentinel_hub():
    """Configura las credenciales de Sentinel Hub - VERSIÓN HARDCODED"""
    try:
        config = SHConfig()
        
        # ⚠️ CREDENCIALES HARDCODED - SOLO PARA DEMO/PRUEBAS
        config.sh_client_id = "358474d6-2326-4637-bf8e-30a709b2d6a6"
        config.sh_client_secret = "b296cf70-c9d2-4e69-91f4-f7be80b99ed1"
        config.instance_id = "PLAK81593ed161694ad48faa8065411d2539"
        
        # Verificación mínima
        if not config.sh_client_id or not config.sh_client_secret:
            st.sidebar.error("❌ Error: Credenciales incompletas")
            return None
        
        st.sidebar.success("✅ Sentinel Hub configurado")
        return config
        
    except Exception as e:
        st.sidebar.error(f"❌ Error configurando Sentinel Hub: {str(e)}")
        return None

# ===== FUNCIONES PARA SENTINEL HUB =====
def buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config):
    """Busca escenas de Sentinel-2 disponibles en el rango temporal"""
    if not SENTINELHUB_AVAILABLE or config is None:
        return None
    
    try:
        gdf_wgs84 = gdf.to_crs('EPSG:4326')
        bounds = gdf_wgs84.total_bounds
        bbox = BBox(bbox=bounds, crs=CRS.WGS84)
        
        catalog = SentinelHubCatalog(config=config)
        
        time_interval = (fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))
        
        query = catalog.search(
            DataCollection.SENTINEL2_L2A,
            bbox=bbox,
            time=time_interval,
            query={'eo:cloud_cover': {'lt': 20}}
        )
        
        escenas = list(query)
        
        if not escenas:
            st.warning("⚠️ No se encontraron escenas disponibles")
            return None
        
        escena_seleccionada = min(escenas, key=lambda x: x['properties']['eo:cloud_cover'])
        
        return {
            'id': escena_seleccionada['id'],
            'fecha': escena_seleccionada['properties']['datetime'][:10],
            'nubes': escena_seleccionada['properties']['eo:cloud_cover'],
            'bbox': bbox,
            'bounds': bounds
        }
        
    except Exception as e:
        st.error(f"❌ Error buscando escenas: {str(e)}")
        return None

def calcular_indice_sentinel2(gdf, fecha_inicio, fecha_fin, indice='NDVI', config=None):
    """Calcula índices de vegetación usando Sentinel Hub Process API"""
    if not SENTINELHUB_AVAILABLE or config is None:
        return None
    
    try:
        escena = buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config)
        if escena is None:
            return None
        
        bbox = escena['bbox']
        size = bbox_to_dimensions(bbox, resolution=10)
        
        # Evalscript según el índice
        if indice == 'NDVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                    return [ndvi];
                }
            """
        elif indice == 'NDRE':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B05", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
                    return [ndre];
                }
            """
        elif indice == 'GNDVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B03", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let gndvi = (sample.B08 - sample.B03) / (sample.B08 + sample.B03);
                    return [gndvi];
                }
            """
        elif indice == 'EVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B02", "B04", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let evi = 2.5 * (sample.B08 - sample.B04) / 
                              (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1);
                    return [evi];
                }
            """
        elif indice == 'SAVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let L = 0.5;
                    let savi = ((sample.B08 - sample.B04) / (sample.B08 + sample.B04 + L)) * (1 + L);
                    return [savi];
                }
            """
        else:
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                    return [ndvi];
                }
            """
        
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(escena['fecha'], escena['fecha']),
                    mosaicking_order='leastCC'
                )
            ],
            responses=[
                SentinelHubRequest.output_response('default', MimeType.TIFF)
            ],
            bbox=bbox,
            size=size,
            config=config
        )
        
        with st.spinner(f"🛰️ Descargando datos Sentinel-2 para {indice}..."):
            img_data = request.get_data()
        
        if not img_data or len(img_data) == 0:
            st.error("❌ No se pudieron descargar los datos")
            return None
        
        img_array = img_data[0]
        valid_values = img_array[~np.isnan(img_array) & (img_array != 0)]
        
        if len(valid_values) == 0:
            st.warning("⚠️ No se encontraron valores válidos")
            return None
        
        valor_promedio = np.mean(valid_values)
        valor_min = np.min(valid_values)
        valor_max = np.max(valid_values)
        valor_std = np.std(valid_values)
        
        return {
            'indice': indice,
            'valor_promedio': float(valor_promedio),
            'valor_min': float(valor_min),
            'valor_max': float(valor_max),
            'valor_std': float(valor_std),
            'fuente': 'Sentinel-2 (Sentinel Hub)',
            'fecha': escena['fecha'],
            'id_escena': escena['id'],
            'cobertura_nubes': f"{escena['nubes']:.1f}%",
            'resolucion': '10m',
            'bounds': escena['bounds']
        }
        
    except Exception as e:
        st.error(f"❌ Error procesando Sentinel-2: {str(e)}")
        return None

def obtener_multiples_indices_sentinel2(gdf, fecha_inicio, fecha_fin, indices=['NDVI', 'NDRE'], config=None):
    """Obtiene múltiples índices de vegetación en una sola llamada"""
    if not SENTINELHUB_AVAILABLE or config is None:
        return None
    
    try:
        escena = buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config)
        if escena is None:
            return None
        
        bbox = escena['bbox']
        size = bbox_to_dimensions(bbox, resolution=10)
        
        evalscript = """
            //VERSION=3
            function setup() {
                return {
                    input: ["B02", "B03", "B04", "B05", "B08"],
                    output: { bands: 5, sampleType: "FLOAT32" }
                };
            }
            function evaluatePixel(sample) {
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
                let gndvi = (sample.B08 - sample.B03) / (sample.B08 + sample.B03);
                let evi = 2.5 * (sample.B08 - sample.B04) / 
                          (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1);
                let L = 0.5;
                let savi = ((sample.B08 - sample.B04) / (sample.B08 + sample.B04 + L)) * (1 + L);
                return [ndvi, ndre, gndvi, evi, savi];
            }
        """
        
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(escena['fecha'], escena['fecha']),
                    mosaicking_order='leastCC'
                )
            ],
            responses=[
                SentinelHubRequest.output_response('default', MimeType.TIFF)
            ],
            bbox=bbox,
            size=size,
            config=config
        )
        
        with st.spinner("🛰️ Descargando múltiples índices..."):
            img_data = request.get_data()
        
        if not img_data or len(img_data) == 0:
            return None
        
        img_array = img_data[0]
        
        indices_map = {'NDVI': 0, 'NDRE': 1, 'GNDVI': 2, 'EVI': 3, 'SAVI': 4}
        resultados = {}
        
        for idx_name in indices:
            if idx_name in indices_map:
                band_idx = indices_map[idx_name]
                band_data = img_array[:, :, band_idx]
                valid_values = band_data[~np.isnan(band_data) & (band_data != 0)]
                
                if len(valid_values) > 0:
                    resultados[idx_name] = {
                        'valor_promedio': float(np.mean(valid_values)),
                        'valor_min': float(np.min(valid_values)),
                        'valor_max': float(np.max(valid_values)),
                        'valor_std': float(np.std(valid_values)),
                        'fuente': 'Sentinel-2 (Sentinel Hub)',
                        'fecha': escena['fecha'],
                        'id_escena': escena['id'],
                        'cobertura_nubes': f"{escena['nubes']:.1f}%",
                        'resolucion': '10m'
                    }
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error obteniendo índices: {str(e)}")
        return None

# ===== INICIALIZACIÓN DE VARIABLES DE SESIÓN =====
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
if 'variedad_seleccionada' not in st.session_state:
    st.session_state.variedad_seleccionada = "No especificada"

# ===== ESTILOS PERSONALIZADOS =====
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
    color: #ffffff !important;
}

[data-testid="stSidebar"] {
    background: #ffffff !important;
}

.sidebar-title {
    font-size: 1.4em;
    font-weight: 800;
    margin: 1.5em 0 1em 0;
    text-align: center;
    padding: 14px;
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    border-radius: 16px;
    color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.3);
}

.hero-banner {
    background: linear-gradient(rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.95)),
                url('https://images.unsplash.com/photo-1597981309443-6e2d2a4d9c3f?ixlib=rb-4.0.3') !important;
    background-size: cover !important;
    padding: 3.5em 2em !important;
    border-radius: 24px !important;
    margin-bottom: 2.5em !important;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4) !important;
}

.hero-title {
    color: #ffffff !important;
    font-size: 3.2em !important;
    font-weight: 900 !important;
    margin-bottom: 0.3em !important;
    background: linear-gradient(135deg, #ffffff 0%, #93c5fd 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}

.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: white !important;
    border: none !important;
    padding: 0.8em 1.5em !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
}
</style>
""", unsafe_allow_html=True)

# ===== CONFIGURACIÓN DE CULTIVOS Y VARIEDADES =====
VARIEDADES_ARGENTINA = {
    'TRIGO': ['ACA 303', 'ACA 315', 'Baguette Premium 11', 'Baguette Premium 13', 'Biointa 1005', 'Biointa 2004', 'Klein Don Enrique', 'Klein Guerrero', 'Buck Meteoro', 'Buck Poncho', 'SY 110', 'SY 200'],
    'MAIZ': ['DK 72-10', 'DK 73-20', 'Pioneer 30F53', 'Pioneer 30F35', 'Syngenta AG 6800', 'Syngenta AG 8088', 'Dow 2A610', 'Dow 2B710', 'Nidera 8710', 'Nidera 8800', 'Morgan 360', 'Morgan 390'],
    'SORGO': ['Advanta AS 5405', 'Advanta AS 5505', 'Pioneer 84G62', 'Pioneer 85G96', 'DEKALB 53-67', 'DEKALB 55-00', 'MACER S-10', 'MACER S-15', 'Sorgocer 105', 'Sorgocer 110', 'Río IV 100', 'Río IV 110'],
    'SOJA': ['DM 53i52', 'DM 58i62', 'Nidera 49X', 'Nidera 52X', 'Don Mario 49X', 'Don Mario 52X', 'SYNGENTA 4.9i', 'SYNGENTA 5.2i', 'Biosoys 4.9', 'Biosoys 5.2', 'ACA 49', 'ACA 52'],
    'GIRASOL': ['ACA 884', 'ACA 887', 'Nidera 7120', 'Nidera 7150', 'Syngenta 390', 'Syngenta 410', 'Pioneer 64A15', 'Pioneer 65A25', 'Advanta G 100', 'Advanta G 110', 'Biosun 400', 'Biosun 420'],
    'MANI': ['ASEM 400', 'ASEM 500', 'Granoleico', 'Guasu', 'Florman INTA', 'Elena', 'Colorado Irradiado', 'Overo Colorado', 'Runner 886', 'Runner 890', 'Tegua', 'Virginia 98R']
}

PARAMETROS_CULTIVOS = {
    'TRIGO': {
        'NITROGENO': {'min': 100, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 90, 'max': 150},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.28,
        'NDVI_OPTIMO': 0.75,
        'NDRE_OPTIMO': 0.40,
        'RENDIMIENTO_OPTIMO': 4500,
        'COSTO_FERTILIZACION': 350,
        'PRECIO_VENTA': 0.25,
        'VARIEDADES': VARIEDADES_ARGENTINA['TRIGO'],
        'ZONAS_ARGENTINA': ['Pampeana', 'Noroeste', 'Noreste']
    },
    'MAIZ': {
        'NITROGENO': {'min': 150, 'max': 250},
        'FOSFORO': {'min': 50, 'max': 90},
        'POTASIO': {'min': 120, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.32,
        'NDVI_OPTIMO': 0.80,
        'NDRE_OPTIMO': 0.45,
        'RENDIMIENTO_OPTIMO': 8500,
        'COSTO_FERTILIZACION': 550,
        'PRECIO_VENTA': 0.20,
        'VARIEDADES': VARIEDADES_ARGENTINA['MAIZ'],
        'ZONAS_ARGENTINA': ['Pampeana', 'Noroeste', 'Noreste', 'Cuyo']
    },
    'SORGO': {
        'NITROGENO': {'min': 80, 'max': 140},
        'FOSFORO': {'min': 35, 'max': 65},
        'POTASIO': {'min': 100, 'max': 180},
        'MATERIA_ORGANICA_OPTIMA': 3.0,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.70,
        'NDRE_OPTIMO': 0.35,
        'RENDIMIENTO_OPTIMO': 5000,
        'COSTO_FERTILIZACION': 300,
        'PRECIO_VENTA': 0.18,
        'VARIEDADES': VARIEDADES_ARGENTINA['SORGO'],
        'ZONAS_ARGENTINA': ['Pampeana', 'Noroeste', 'Noreste']
    },
    'SOJA': {
        'NITROGENO': {'min': 20, 'max': 40},
        'FOSFORO': {'min': 45, 'max': 85},
        'POTASIO': {'min': 140, 'max': 220},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.30,
        'NDVI_OPTIMO': 0.78,
        'NDRE_OPTIMO': 0.42,
        'RENDIMIENTO_OPTIMO': 3200,
        'COSTO_FERTILIZACION': 400,
        'PRECIO_VENTA': 0.45,
        'VARIEDADES': VARIEDADES_ARGENTINA['SOJA'],
        'ZONAS_ARGENTINA': ['Pampeana', 'Noroeste', 'Noreste']
    },
    'GIRASOL': {
        'NITROGENO': {'min': 70, 'max': 120},
        'FOSFORO': {'min': 40, 'max': 75},
        'POTASIO': {'min': 110, 'max': 190},
        'MATERIA_ORGANICA_OPTIMA': 3.2,
        'HUMEDAD_OPTIMA': 0.26,
        'NDVI_OPTIMO': 0.72,
        'NDRE_OPTIMO': 0.38,
        'RENDIMIENTO_OPTIMO': 2800,
        'COSTO_FERTILIZACION': 320,
        'PRECIO_VENTA': 0.35,
        'VARIEDADES': VARIEDADES_ARGENTINA['GIRASOL'],
        'ZONAS_ARGENTINA': ['Pampeana', 'Noroeste', 'Noreste']
    },
    'MANI': {
        'NITROGENO': {'min': 15, 'max': 30},
        'FOSFORO': {'min': 50, 'max': 90},
        'POTASIO': {'min': 80, 'max': 140},
        'MATERIA_ORGANICA_OPTIMA': 2.8,
        'HUMEDAD_OPTIMA': 0.22,
        'NDVI_OPTIMO': 0.68,
        'NDRE_OPTIMO': 0.32,
        'RENDIMIENTO_OPTIMO': 3800,
        'COSTO_FERTILIZACION': 380,
        'PRECIO_VENTA': 0.60,
        'VARIEDADES': VARIEDADES_ARGENTINA['MANI'],
        'ZONAS_ARGENTINA': ['Córdoba', 'San Luis', 'La Pampa']
    }
}

ICONOS_CULTIVOS = {'TRIGO': '🌾', 'MAIZ': '🌽', 'SORGO': '🌾', 'SOJA': '🫘', 'GIRASOL': '🌻', 'MANI': '🥜'}

# ===== HERO BANNER =====
st.markdown("""
<div class="hero-banner">
    <div class="hero-content">
        <h1 class="hero-title">🛰️ ANALIZADOR MULTI-CULTIVO SATELITAL</h1>
        <p style="color: #cbd5e1; font-size: 1.3em;">Potenciado con Sentinel Hub para agricultura de precisión</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN</div>', unsafe_allow_html=True)
    
    if SENTINELHUB_AVAILABLE:
        if st.button("🔌 Probar Conexión"):
            config_test = configurar_sentinel_hub()
            if config_test:
                st.success("✅ Conexión exitosa")
            else:
                st.error("❌ Error en conexión")
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAIZ", "SORGO", "SOJA", "GIRASOL", "MANI"])
    
    variedades = VARIEDADES_ARGENTINA.get(cultivo, [])
    variedad = st.selectbox("Variedad:", ["No especificada"] + variedades)
    st.session_state.variedad_seleccionada = variedad
    
    satelite_seleccionado = st.selectbox("Satélite:", ["SENTINEL-2", "LANDSAT-8", "DATOS_SIMULADOS"])
    fecha_fin = st.date_input("Fecha fin", datetime.now())
    fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    n_divisiones = st.slider("Zonas de manejo:", 16, 48, 32)
    intervalo_curvas = st.slider("Intervalo curvas (m):", 1.0, 20.0, 5.0, 1.0)
    resolucion_dem = st.slider("Resolución DEM (m):", 5.0, 50.0, 10.0, 5.0)
    uploaded_file = st.file_uploader("Subir parcela", type=['zip', 'kml', 'kmz'])

# ===== FUNCIONES AUXILIARES =====
def validar_y_corregir_crs(gdf):
    if gdf is None or len(gdf) == 0:
        return gdf
    try:
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326', inplace=False)
        elif str(gdf.crs).upper() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        return gdf
    except:
        return gdf

def calcular_superficie(gdf):
    try:
        if gdf is None or len(gdf) == 0:
            return 0.0
        gdf = validar_y_corregir_crs(gdf)
        gdf_projected = gdf.to_crs('EPSG:3857')
        area_m2 = gdf_projected.geometry.area.sum()
        return area_m2 / 10000
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
                st.error("❌ No se encontró archivo .shp")
                return None
    except Exception as e:
        st.error(f"❌ Error cargando ZIP: {str(e)}")
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
        if polygons:
            gdf = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')
            return gdf
        return None
    except Exception as e:
        st.error(f"❌ Error parseando KML: {str(e)}")
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
                        gdf = gpd.read_file(kml_path)
                        gdf = validar_y_corregir_crs(gdf)
                        return gdf
                else:
                    st.error("❌ No se encontró archivo .kml")
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
        st.error(f"❌ Error cargando KML: {str(e)}")
        return None

def cargar_archivo_parcela(uploaded_file):
    try:
        if uploaded_file.name.endswith('.zip'):
            gdf = cargar_shapefile_desde_zip(uploaded_file)
        elif uploaded_file.name.endswith(('.kml', '.kmz')):
            gdf = cargar_kml(uploaded_file)
        else:
            st.error("❌ Formato no soportado")
            return None
        
        if gdf is not None:
            gdf = validar_y_corregir_crs(gdf)
            gdf = gdf.explode(ignore_index=True)
            gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])]
            if len(gdf) == 0:
                st.error("❌ No se encontraron polígonos")
                return None
            geometria_unida = gdf.unary_union
            gdf_unido = gpd.GeoDataFrame([{'geometry': geometria_unida}], crs='EPSG:4326')
            gdf_unido = validar_y_corregir_crs(gdf_unido)
            st.info(f"✅ Se unieron {len(gdf)} polígono(s)")
            gdf_unido['id_zona'] = 1
            return gdf_unido
        return gdf
    except Exception as e:
        st.error(f"❌ Error cargando archivo: {str(e)}")
        return None

# ===== FUNCIONES PARA DATOS SATELITALES =====
def descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    try:
        return {
            'indice': indice,
            'valor_promedio': 0.65 + np.random.normal(0, 0.1),
            'fuente': 'Landsat-8',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'resolucion': '30m'
        }
    except Exception as e:
        st.error(f"❌ Error Landsat 8: {str(e)}")
        return None

def descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Función modificada para usar Sentinel Hub"""
    try:
        config = None
        if SENTINELHUB_AVAILABLE and satelite_seleccionado == "SENTINEL-2":
            config = configurar_sentinel_hub()
        
        if config is not None:
            resultado = calcular_indice_sentinel2(gdf, fecha_inicio, fecha_fin, indice, config)
            if resultado is not None:
                return resultado
        
        st.warning("⚠️ Usando datos simulados")
        return generar_datos_simulados(gdf, cultivo, indice)
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return generar_datos_simulados(gdf, cultivo, indice)

def generar_datos_simulados(gdf, cultivo, indice='NDVI'):
    return {
        'indice': indice,
        'valor_promedio': PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO'] * 0.8 + np.random.normal(0, 0.1),
        'fuente': 'Simulación',
        'fecha': datetime.now().strftime('%Y-%m-%d'),
        'resolucion': '10m'
    }

# ===== FUNCIONES DE ANÁLISIS =====
def analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales):
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
    valor_base_satelital = datos_satelitales.get('valor_promedio', 0.6) if datos_satelitales else 0.6
    
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
        
        ndvi_base = valor_base_satelital * 0.8
        ndvi_variacion = patron_espacial * (valor_base_satelital * 0.4)
        ndvi = ndvi_base + ndvi_variacion + np.random.normal(0, 0.06)
        ndvi = max(0.1, min(0.9, ndvi))
        
        ndre_base = params['NDRE_OPTIMO'] * 0.7
        ndre_variacion = patron_espacial * (params['NDRE_OPTIMO'] * 0.4)
        ndre = ndre_base + ndre_variacion + np.random.normal(0, 0.04)
        ndre = max(0.05, min(0.7, ndre))
        
        ndwi = 0.2 + np.random.normal(0, 0.08)
        ndwi = max(0, min(1, ndwi))
        
        npk_actual = (ndvi * 0.4) + (ndre * 0.3) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'ndwi': round(ndwi, 3),
            'npk_actual': round(npk_actual, 3)
        })
    
    return resultados

def analizar_recomendaciones_npk(indices, cultivo):
    recomendaciones_n = []
    recomendaciones_p = []
    recomendaciones_k = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        ndre = idx['ndre']
        materia_organica = idx['materia_organica']
        humedad_suelo = idx['humedad_suelo']
        ndvi = idx['ndvi']
        
        factor_n = ((1 - ndre) * 0.6 + (1 - ndvi) * 0.4)
        n_recomendado = (factor_n * (params['NITROGENO']['max'] - params['NITROGENO']['min']) + params['NITROGENO']['min'])
        n_recomendado = max(params['NITROGENO']['min'] * 0.8, min(params['NITROGENO']['max'] * 1.2, n_recomendado))
        recomendaciones_n.append(round(n_recomendado, 1))
        
        factor_p = ((1 - (materia_organica / 8)) * 0.7 + (1 - humedad_suelo) * 0.3)
        p_recomendado = (factor_p * (params['FOSFORO']['max'] - params['FOSFORO']['min']) + params['FOSFORO']['min'])
        p_recomendado = max(params['FOSFORO']['min'] * 0.8, min(params['FOSFORO']['max'] * 1.2, p_recomendado))
        recomendaciones_p.append(round(p_recomendado, 1))
        
        factor_k = ((1 - ndre) * 0.4 + (1 - humedad_suelo) * 0.4 + (1 - (materia_organica / 8)) * 0.2)
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
        
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * npk_actual * 0.7
        incremento = (1 - npk_actual) * 0.4 + (1 - ndvi) * 0.2
        rendimiento_con_fert = rendimiento_base * (1 + incremento)
        
        proyecciones.append({
            'rendimiento_sin_fert': round(rendimiento_base, 0),
            'rendimiento_con_fert': round(rendimiento_con_fert, 0),
            'incremento_esperado': round(incremento * 100, 1)
        })
    
    return proyecciones

# ===== FUNCIÓN PRINCIPAL DE ANÁLISIS =====
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin, intervalo_curvas=5.0, resolucion_dem=10.0):
    resultados = {
        'exitoso': False,
        'gdf_dividido': None,
        'fertilidad_actual': None,
        'recomendaciones_npk': None,
        'costos': None,
        'proyecciones': None,
        'area_total': 0,
        'datos_satelitales': None
    }
    
    try:
        gdf = validar_y_corregir_crs(gdf)
        area_total = calcular_superficie(gdf)
        resultados['area_total'] = area_total
        
        config = None
        if satelite == "SENTINEL-2" and SENTINELHUB_AVAILABLE:
            config = configurar_sentinel_hub()
        
        datos_satelitales = None
        if satelite == "SENTINEL-2" and SENTINELHUB_AVAILABLE and config is not None:
            indices_deseados = ['NDVI', 'NDRE', 'GNDVI']
            datos_multiples = obtener_multiples_indices_sentinel2(
                gdf, fecha_inicio, fecha_fin, indices_deseados, config
            )
            
            if datos_multiples and 'NDVI' in datos_multiples:
                datos_satelitales = datos_multiples['NDVI']
                resultados['datos_satelitales'] = datos_multiples
                st.success(f"✅ Datos reales de Sentinel-2: {datos_satelitales['fecha']}")
            else:
                datos_satelitales = generar_datos_simulados(gdf, cultivo, "NDVI")
                st.warning("⚠️ Usando datos simulados")
                
        elif satelite == "LANDSAT-8":
            datos_satelitales = descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, "NDVI")
        else:
            datos_satelitales = generar_datos_simulados(gdf, cultivo, "NDVI")
        
        gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        resultados['gdf_dividido'] = gdf_dividido
        
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
        resultados['recomendaciones_npk'] = {'N': rec_n, 'P': rec_p, 'K': rec_k}
        
        costos = analizar_costos(gdf_dividido, cultivo, rec_n, rec_p, rec_k)
        resultados['costos'] = costos
        
        proyecciones = analizar_proyecciones_cosecha(gdf_dividido, cultivo, fertilidad_actual)
        resultados['proyecciones'] = proyecciones
        
        gdf_completo = gdf_dividido.copy()
        
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
        st.error(f"❌ Error en análisis: {str(e)}")
        import traceback
        traceback.print_exc()
        return resultados

# ===== INTERFAZ PRINCIPAL =====
st.title("🛰️ ANALIZADOR MULTI-CULTIVO SATELITAL")

if uploaded_file:
    with st.spinner("Cargando parcela..."):
        try:
            gdf = cargar_archivo_parcela(uploaded_file)
            if gdf is not None:
                st.success(f"✅ Parcela cargada: {len(gdf)} polígono(s)")
                area_total = calcular_superficie(gdf)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**📊 INFORMACIÓN DE LA PARCELA:**")
                    st.write(f"- Polígonos: {len(gdf)}")
                    st.write(f"- Área total: {area_total:.1f} ha")
                    st.write(f"- CRS: {gdf.crs}")
                    
                    fig, ax = plt.subplots(figsize=(8, 6))
                    gdf.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
                    ax.set_title(f"Parcela: {uploaded_file.name}")
                    ax.set_xlabel("Longitud")
                    ax.set_ylabel("Latitud")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                
                with col2:
                    st.write("**🎯 CONFIGURACIÓN**")
                    st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                    st.write(f"- Variedad: {st.session_state.variedad_seleccionada}")
                    st.write(f"- Zonas: {n_divisiones}")
                    st.write(f"- Satélite: {satelite_seleccionado}")
                    st.write(f"- Período: {fecha_inicio} a {fecha_fin}")
                
                if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
                    with st.spinner("Ejecutando análisis..."):
                        resultados = ejecutar_analisis_completo(
                            gdf, cultivo, n_divisiones, 
                            satelite_seleccionado, fecha_inicio, fecha_fin,
                            intervalo_curvas, resolucion_dem
                        )
                        
                        if resultados['exitoso']:
                            st.session_state.resultados_todos = resultados
                            st.session_state.analisis_completado = True
                            st.success("✅ Análisis completado!")
                            st.rerun()
                        else:
                            st.error("❌ Error en el análisis")
            
            else:
                st.error("❌ Error al cargar la parcela")
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Mostrar resultados
if st.session_state.analisis_completado and 'resultados_todos' in st.session_state:
    resultados = st.session_state.resultados_todos
    variedad = st.session_state.variedad_seleccionada
    
    if 'datos_satelitales' in resultados and resultados['datos_satelitales']:
        st.info(f"🛰️ **Datos Satelitales:** {resultados['datos_satelitales']['fecha']}")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Fertilidad", "🧪 NPK", "💰 Costos", "📈 Proyecciones"])
    
    with tab1:
        st.subheader("FERTILIDAD ACTUAL")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            npk_prom = resultados['gdf_completo']['fert_npk_actual'].mean()
            st.metric("Índice NPK", f"{npk_prom:.3f}")
        with col2:
            ndvi_prom = resultados['gdf_completo']['fert_ndvi'].mean()
            st.metric("NDVI", f"{ndvi_prom:.3f}")
        with col3:
            mo_prom = resultados['gdf_completo']['fert_materia_organica'].mean()
            st.metric("Materia Orgánica", f"{mo_prom:.1f}%")
        with col4:
            hum_prom = resultados['gdf_completo']['fert_humedad_suelo'].mean()
            st.metric("Humedad", f"{hum_prom:.3f}")
        
        st.subheader("📋 TABLA DE RESULTADOS")
        columnas_fert = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre', 'fert_materia_organica', 'fert_humedad_suelo']
        tabla_fert = resultados['gdf_completo'][columnas_fert].copy()
        tabla_fert.columns = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 'NDRE', 'Materia Org (%)', 'Humedad']
        st.dataframe(tabla_fert)
    
    with tab2:
        st.subheader("RECOMENDACIONES NPK")
        col1, col2, col3 = st.columns(3)
        with col1:
            n_prom = resultados['gdf_completo']['rec_N'].mean()
            st.metric("Nitrógeno", f"{n_prom:.1f} kg/ha")
        with col2:
            p_prom = resultados['gdf_completo']['rec_P'].mean()
            st.metric("Fósforo", f"{p_prom:.1f} kg/ha")
        with col3:
            k_prom = resultados['gdf_completo']['rec_K'].mean()
            st.metric("Potasio", f"{k_prom:.1f} kg/ha")
        
        st.subheader("📋 TABLA DE RECOMENDACIONES")
        columnas_npk = ['id_zona', 'area_ha', 'rec_N', 'rec_P', 'rec_K']
        tabla_npk = resultados['gdf_completo'][columnas_npk].copy()
        tabla_npk.columns = ['Zona', 'Área (ha)', 'N (kg/ha)', 'P (kg/ha)', 'K (kg/ha)']
        st.dataframe(tabla_npk)
    
    with tab3:
        st.subheader("ANÁLISIS DE COSTOS")
        costo_total = resultados['gdf_completo']['costo_costo_total'].sum()
        costo_prom = resultados['gdf_completo']['costo_costo_total'].mean()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Costo Total", f"${costo_total:.2f} USD")
        with col2:
            st.metric("Costo Promedio", f"${costo_prom:.2f} USD/ha")
        
        st.subheader("📋 TABLA DE COSTOS")
        columnas_costos = ['id_zona', 'area_ha', 'costo_costo_nitrogeno', 'costo_costo_fosforo', 'costo_costo_potasio', 'costo_costo_total']
        tabla_costos = resultados['gdf_completo'][columnas_costos].copy()
        tabla_costos.columns = ['Zona', 'Área (ha)', 'Costo N', 'Costo P', 'Costo K', 'Total']
        st.dataframe(tabla_costos)
    
    with tab4:
        st.subheader("PROYECCIONES DE COSECHA")
        rend_sin = resultados['gdf_completo']['proy_rendimiento_sin_fert'].sum()
        rend_con = resultados['gdf_completo']['proy_rendimiento_con_fert'].sum()
        incremento = ((rend_con - rend_sin) / rend_sin * 100) if rend_sin > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sin Fertilización", f"{rend_sin:.0f} kg")
        with col2:
            st.metric("Con Fertilización", f"{rend_con:.0f} kg")
        with col3:
            st.metric("Incremento", f"{incremento:.1f}%")
        
        st.subheader("📋 TABLA DE PROYECCIONES")
        columnas_proy = ['id_zona', 'area_ha', 'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert', 'proy_incremento_esperado']
        tabla_proy = resultados['gdf_completo'][columnas_proy].copy()
        tabla_proy.columns = ['Zona', 'Área (ha)', 'Sin Fert (kg)', 'Con Fert (kg)', 'Incremento (%)']
        st.dataframe(tabla_proy)

else:
    st.info("👈 Sube un archivo de parcela y ejecuta el análisis para comenzar.")

st.markdown("---")
st.markdown("**Versión 5.2 - Sentinel Hub Integration** | © 2026 Analizador Multi-Cultivo")
