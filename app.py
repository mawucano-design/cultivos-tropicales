import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation, LinearTriInterpolator
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize
from mpl_toolkits.mplot3d import Axes3D
import io
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
import math
import warnings
import xml.etree.ElementTree as ET
import json
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import geojson
import requests
import contextily as ctx
from scipy import ndimage

# ===== CONFIGURACIÓN DE GOOGLE EARTH ENGINE =====
try:
    import ee
    GEE_AVAILABLE = True
    
    # Intenta inicializar Google Earth Engine
    try:
        ee.Initialize(project='ee-multicultivo')
        st.sidebar.success("✅ Google Earth Engine inicializado")
    except ee.EEException:
        # Si no está inicializado, muestra instrucciones
        st.sidebar.warning("⚠️ GEE no inicializado. Necesitas autenticarte.")
        st.sidebar.info("Para autenticarte, ejecuta en tu terminal:")
        st.sidebar.code("earthengine authenticate")
        GEE_AVAILABLE = False
except ImportError:
    GEE_AVAILABLE = False
    st.sidebar.warning("⚠️ Paquete 'earthengine-api' no instalado. Usando datos simulados.")

warnings.filterwarnings('ignore')

# ===== FUNCIONES PARA GOOGLE EARTH ENGINE =====
def autenticar_gee():
    """Autenticar con Google Earth Engine"""
    try:
        if not GEE_AVAILABLE:
            return False
        
        # Verificar si ya está inicializado
        try:
            ee.Initialize(project='ee-multicultivo')
            return True
        except:
            # Intentar inicializar
            ee.Initialize()
            return True
            
    except Exception as e:
        st.sidebar.error(f"❌ Error autenticando GEE: {str(e)}")
        st.sidebar.info("""
        **Instrucciones para autenticar:**
        1. Instala: `pip install earthengine-api`
        2. Ejecuta en terminal: `earthengine authenticate`
        3. Sigue las instrucciones en el navegador
        """)
        return False

def calcular_indices_gee(gdf, fecha_inicio, fecha_fin, indices=['NDVI']):
    """Calcula índices de vegetación usando Google Earth Engine"""
    if not GEE_AVAILABLE:
        return None
    
    try:
        # Autenticar
        if not autenticar_gee():
            return None
        
        # Convertir GeoDataFrame a geometría de GEE
        gdf_wgs84 = gdf.to_crs('EPSG:4326')
        geometria = gdf_wgs84.geometry.unary_union
        
        # Crear polígono de GEE
        if geometria.geom_type == 'Polygon':
            coords = list(geometria.exterior.coords)
            ee_polygon = ee.Geometry.Polygon(coords)
        elif geometria.geom_type == 'MultiPolygon':
            polygons = []
            for poly in geometria.geoms:
                coords = list(poly.exterior.coords)
                polygons.append(coords)
            ee_polygon = ee.Geometry.MultiPolygon(polygons)
        else:
            st.error("❌ Tipo de geometría no soportado")
            return None
        
        # Definir período temporal
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        # Cargar colección de Sentinel-2
        coleccion = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterDate(fecha_inicio_str, fecha_fin_str) \
            .filterBounds(ee_polygon) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        # Seleccionar la imagen con menos nubes
        imagen = coleccion.sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        if imagen is None:
            st.warning("⚠️ No se encontraron imágenes Sentinel-2 sin nubes")
            return None
        
        # Función para calcular NDVI
        def calcular_ndvi(img):
            return img.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # Función para calcular NDRE
        def calcular_ndre(img):
            return img.normalizedDifference(['B8', 'B5']).rename('NDRE')
        
        # Función para calcular GNDVI
        def calcular_gndvi(img):
            return img.normalizedDifference(['B8', 'B3']).rename('GNDVI')
        
        # Función para calcular EVI
        def calcular_evi(img):
            evi = img.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': img.select('B8'),
                    'RED': img.select('B4'),
                    'BLUE': img.select('B2')
                }
            ).rename('EVI')
            return evi
        
        # Función para calcular SAVI
        def calcular_savi(img):
            L = 0.5
            savi = img.expression(
                '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
                {
                    'NIR': img.select('B8'),
                    'RED': img.select('B4')
                }
            ).rename('SAVI')
            return savi
        
        # Calcular índices solicitados
        resultados = {}
        
        for indice in indices:
            if indice == 'NDVI':
                img_indice = calcular_ndvi(imagen)
                nombre = 'NDVI'
            elif indice == 'NDRE':
                img_indice = calcular_ndre(imagen)
                nombre = 'NDRE'
            elif indice == 'GNDVI':
                img_indice = calcular_gndvi(imagen)
                nombre = 'GNDVI'
            elif indice == 'EVI':
                img_indice = calcular_evi(imagen)
                nombre = 'EVI'
            elif indice == 'SAVI':
                img_indice = calcular_savi(imagen)
                nombre = 'SAVI'
            else:
                continue
            
            # Obtener estadísticas de la región
            estadisticas = img_indice.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    reducer2=ee.Reducer.minMax().combine(
                        reducer2=ee.Reducer.stdDev(),
                        sharedInputs=True
                    ),
                    sharedInputs=True
                ),
                geometry=ee_polygon,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            # Información de la imagen
            fecha = imagen.date().format('YYYY-MM-dd').getInfo()
            id_imagen = imagen.id().getInfo()
            nubes = imagen.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
            
            resultados[nombre] = {
                'indice': nombre,
                'valor_promedio': estadisticas.get('mean', 0),
                'valor_min': estadisticas.get('min', 0),
                'valor_max': estadisticas.get('max', 0),
                'valor_std': estadisticas.get('stdDev', 0),
                'fuente': 'Sentinel-2 (Google Earth Engine)',
                'fecha': fecha,
                'id_escena': id_imagen,
                'cobertura_nubes': f"{nubes:.1f}%" if nubes else "Desconocido",
                'resolucion': '10m',
                'bounds': gdf_wgs84.total_bounds.tolist()
            }
        
        # Si no se calculó ningún índice, retornar NDVI por defecto
        if not resultados:
            img_indice = calcular_ndvi(imagen)
            estadisticas = img_indice.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    reducer2=ee.Reducer.minMax().combine(
                        reducer2=ee.Reducer.stdDev(),
                        sharedInputs=True
                    ),
                    sharedInputs=True
                ),
                geometry=ee_polygon,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            fecha = imagen.date().format('YYYY-MM-dd').getInfo()
            id_imagen = imagen.id().getInfo()
            nubes = imagen.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
            
            resultados['NDVI'] = {
                'indice': 'NDVI',
                'valor_promedio': estadisticas.get('mean', 0),
                'valor_min': estadisticas.get('min', 0),
                'valor_max': estadisticas.get('max', 0),
                'valor_std': estadisticas.get('stdDev', 0),
                'fuente': 'Sentinel-2 (Google Earth Engine)',
                'fecha': fecha,
                'id_escena': id_imagen,
                'cobertura_nubes': f"{nubes:.1f}%" if nubes else "Desconocido",
                'resolucion': '10m',
                'bounds': gdf_wgs84.total_bounds.tolist()
            }
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error calculando índices con GEE: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

def obtener_imagen_gee(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Obtiene una imagen de Google Earth Engine para visualización"""
    if not GEE_AVAILABLE:
        return None
    
    try:
        if not autenticar_gee():
            return None
        
        # Convertir GeoDataFrame a geometría de GEE
        gdf_wgs84 = gdf.to_crs('EPSG:4326')
        geometria = gdf_wgs84.geometry.unary_union
        
        # Crear polígono de GEE
        if geometria.geom_type == 'Polygon':
            coords = list(geometria.exterior.coords)
            ee_polygon = ee.Geometry.Polygon(coords)
        else:
            return None
        
        # Definir período temporal
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        # Cargar colección de Sentinel-2
        coleccion = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterDate(fecha_inicio_str, fecha_fin_str) \
            .filterBounds(ee_polygon) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
        
        # Seleccionar la imagen con menos nubes
        imagen = coleccion.sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        if imagen is None:
            return None
        
        # Calcular el índice seleccionado
        if indice == 'NDVI':
            img_indice = imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')
            viz_params = {
                'min': -0.2,
                'max': 0.8,
                'palette': ['blue', 'white', 'green']
            }
        elif indice == 'NDRE':
            img_indice = imagen.normalizedDifference(['B8', 'B5']).rename('NDRE')
            viz_params = {
                'min': -0.2,
                'max': 0.6,
                'palette': ['blue', 'white', 'darkgreen']
            }
        elif indice == 'GNDVI':
            img_indice = imagen.normalizedDifference(['B8', 'B3']).rename('GNDVI')
            viz_params = {
                'min': -0.2,
                'max': 0.7,
                'palette': ['brown', 'yellow', 'green']
            }
        else:
            img_indice = imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')
            viz_params = {
                'min': -0.2,
                'max': 0.8,
                'palette': ['blue', 'white', 'green']
            }
        
        # Obtener URL de la imagen
        map_id_dict = img_indice.getMapId(viz_params)
        
        return {
            'url': map_id_dict['tile_fetcher'].url_format,
            'bounds': gdf_wgs84.total_bounds.tolist(),
            'indice': indice
        }
        
    except Exception as e:
        st.error(f"❌ Error obteniendo imagen GEE: {str(e)}")
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
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False

# ===== ESTILOS PERSONALIZADOS =====
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
    color: #ffffff !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e5e7eb !important;
    box-shadow: 5px 0 25px rgba(0, 0, 0, 0.1) !important;
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
    border: 1px solid rgba(255, 255, 255, 0.2);
    letter-spacing: 0.5px;
}

.cultivo-card {
    background: white;
    border-radius: 12px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border-left: 4px solid #3b82f6;
}

.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: white !important;
    border: none !important;
    padding: 0.8em 1.5em !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 1em !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
    transition: all 0.3s ease !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

.stButton > button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 25px rgba(59, 130, 246, 0.6) !important;
    background: linear-gradient(135deg, #4f8df8 0%, #2d5fe8 100%) !important;
}

.hero-banner {
    background: linear-gradient(rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.95)),
                url('https://images.unsplash.com/photo-1597981309443-6e2d2a4d9c3f?ixlib=rb-4.0.3') !important;
    background-size: cover !important;
    padding: 3.5em 2em !important;
    border-radius: 24px !important;
    margin-bottom: 2.5em !important;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4) !important;
    border: 1px solid rgba(59, 130, 246, 0.2) !important;
    position: relative !important;
    overflow: hidden !important;
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

.hero-subtitle {
    color: #cbd5e1 !important;
    font-size: 1.3em !important;
    font-weight: 400 !important;
    max-width: 800px !important;
    margin: 0 auto !important;
    line-height: 1.6 !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(10px) !important;
    padding: 8px 16px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    margin-top: 1em !important;
    gap: 8px !important;
}

.stTabs [data-baseweb="tab"] {
    color: #94a3b8 !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    border-radius: 12px !important;
    background: transparent !important;
    transition: all 0.3s ease !important;
    border: 1px solid transparent !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background: rgba(59, 130, 246, 0.2) !important;
    border-color: rgba(59, 130, 246, 0.3) !important;
    transform: translateY(-2px) !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
}

div[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)) !important;
    backdrop-filter: blur(10px) !important;
    border-radius: 20px !important;
    padding: 24px !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
    border: 1px solid rgba(59, 130, 246, 0.2) !important;
    transition: all 0.3s ease !important;
}

div[data-testid="metric-container"]:hover {
    transform: translateY(-5px) !important;
    box-shadow: 0 15px 40px rgba(59, 130, 246, 0.2) !important;
    border-color: rgba(59, 130, 246, 0.4) !important;
}

.gee-info {
    background: linear-gradient(135deg, #0c4b33 0%, #1a936f 100%);
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    color: white;
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
        <p class="hero-subtitle">Potenciado con Google Earth Engine para agricultura de precisión con datos satelitales gratuitos</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ===== SIDEBAR CONFIGURACIÓN =====
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN</div>', unsafe_allow_html=True)
    
    # Configuración de Google Earth Engine
    st.markdown('<div class="gee-info">🌎 GOOGLE EARTH ENGINE</div>', unsafe_allow_html=True)
    
    if GEE_AVAILABLE:
        if st.button("🔑 Autenticar GEE"):
            with st.spinner("Autenticando con Google Earth Engine..."):
                if autenticar_gee():
                    st.session_state.gee_authenticated = True
                    st.success("✅ Autenticación exitosa!")
                    st.rerun()
                else:
                    st.error("❌ Error en autenticación")
        
        if st.session_state.get('gee_authenticated', False):
            st.success("✅ GEE Autenticado")
        else:
            st.warning("⚠️ GEE No autenticado")
            
        st.info("""
        **Satélites disponibles:**
        - Sentinel-2 (10m resolución)
        - Landsat 8/9 (30m resolución)
        - MODIS (250-500m)
        """)
    else:
        st.error("❌ GEE no disponible")
        st.info("""
        **Para instalar GEE:**
        1. `pip install earthengine-api`
        2. Ejecutar en terminal: `earthengine authenticate`
        3. Sigue las instrucciones en el navegador
        """)
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAIZ", "SORGO", "SOJA", "GIRASOL", "MANI"])
    
    variedades = VARIEDADES_ARGENTINA.get(cultivo, [])
    variedad = st.selectbox("Variedad:", ["No especificada"] + variedades)
    st.session_state.variedad_seleccionada = variedad
    
    satelite_seleccionado = st.selectbox("Satélite:", ["SENTINEL-2 (GEE)", "LANDSAT-8 (GEE)", "DATOS_SIMULADOS"])
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    with col2:
        fecha_fin = st.date_input("Fecha fin", datetime.now())
    
    n_divisiones = st.slider("Zonas de manejo:", 16, 48, 32)
    intervalo_curvas = st.slider("Intervalo curvas (m):", 1.0, 20.0, 5.0, 1.0)
    resolucion_dem = st.slider("Resolución DEM (m):", 5.0, 50.0, 10.0, 5.0)
    
    uploaded_file = st.file_uploader("Subir parcela", type=['zip', 'kml', 'kmz', 'geojson', 'shp'])
    
    # Selección de índices a calcular
    st.markdown("**📊 Índices a calcular:**")
    ndvi_check = st.checkbox("NDVI", value=True)
    ndre_check = st.checkbox("NDRE", value=True)
    gndvi_check = st.checkbox("GNDVI", value=False)
    evi_check = st.checkbox("EVI", value=False)
    savi_check = st.checkbox("SAVI", value=False)

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
        elif uploaded_file.name.endswith('.geojson'):
            contenido = uploaded_file.read().decode('utf-8')
            gdf = gpd.read_file(contenido, driver='GeoJSON')
            gdf = validar_y_corregir_crs(gdf)
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

# ===== FUNCIONES PARA DATOS SATELITALES CON GEE =====
def descargar_datos_gee(gdf, fecha_inicio, fecha_fin):
    """Descarga datos de Google Earth Engine"""
    try:
        # Determinar qué índices calcular según checkboxes
        indices_seleccionados = []
        if ndvi_check:
            indices_seleccionados.append('NDVI')
        if ndre_check:
            indices_seleccionados.append('NDRE')
        if gndvi_check:
            indices_seleccionados.append('GNDVI')
        if evi_check:
            indices_seleccionados.append('EVI')
        if savi_check:
            indices_seleccionados.append('SAVI')
        
        if not indices_seleccionados:
            indices_seleccionados = ['NDVI']  # Por defecto
        
        # Calcular índices con GEE
        resultados = calcular_indices_gee(gdf, fecha_inicio, fecha_fin, indices_seleccionados)
        
        if resultados:
            return resultados
        else:
            # Si GEE falla, usar datos simulados
            st.warning("⚠️ Usando datos simulados (GEE no disponible)")
            return generar_datos_simulados_multiples(gdf, cultivo, indices_seleccionados)
            
    except Exception as e:
        st.error(f"❌ Error GEE: {str(e)}")
        return generar_datos_simulados_multiples(gdf, cultivo, ['NDVI'])

def generar_datos_simulados_multiples(gdf, cultivo, indices):
    """Genera datos simulados para múltiples índices"""
    resultados = {}
    for indice in indices:
        resultados[indice] = {
            'indice': indice,
            'valor_promedio': PARAMETROS_CULTIVOS[cultivo].get(f'{indice}_OPTIMO', 0.7) * 0.8 + np.random.normal(0, 0.1),
            'valor_min': 0.3,
            'valor_max': 0.9,
            'valor_std': 0.1,
            'fuente': 'Simulación',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'resolucion': '10m'
        }
    return resultados

# ===== FUNCIONES DEM SINTÉTICO Y CURVAS DE NIVEL =====
def generar_dem_sintetico(gdf, resolucion=10.0):
    """Genera un DEM sintético para análisis de terreno"""
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
    """Calcula pendiente a partir del DEM"""
    dy = np.gradient(Z, axis=0) / resolucion
    dx = np.gradient(Z, axis=1) / resolucion
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    pendiente = np.clip(pendiente, 0, 100)
    return pendiente

def generar_curvas_nivel(X, Y, Z, intervalo=5.0):
    """Genera curvas de nivel a partir del DEM"""
    try:
        # Limpiar datos NaN
        Z_clean = np.where(np.isnan(Z), -9999, Z)
        
        # Niveles para las curvas
        z_min = np.min(Z_clean[Z_clean != -9999])
        z_max = np.max(Z_clean[Z_clean != -9999])
        
        if z_min == z_max:
            return [], []
        
        niveles = np.arange(
            np.floor(z_min / intervalo) * intervalo,
            np.ceil(z_max / intervalo) * intervalo + intervalo,
            intervalo
        )
        
        curvas_nivel = []
        elevaciones = []
        
        # Crear figura temporal para usar matplotlib's contour
        fig_temp = plt.figure(figsize=(1, 1))
        ax_temp = fig_temp.add_subplot(111)
        
        # Generar contornos
        CS = ax_temp.contour(X, Y, Z_clean, levels=niveles, colors='blue')
        
        plt.close(fig_temp)
        
        # Extraer las curvas de nivel
        for i, collection in enumerate(CS.collections):
            for path in collection.get_paths():
                if path.vertices.shape[0] > 2:  # Al menos 3 puntos
                    # Crear LineString a partir de los vértices
                    linea = LineString(path.vertices)
                    curvas_nivel.append(linea)
                    elevaciones.append(niveles[i] if i < len(niveles) else niveles[-1])
        
        return curvas_nivel, elevaciones
        
    except Exception as e:
        st.error(f"❌ Error generando curvas de nivel: {str(e)}")
        return [], []

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
    
    # Obtener valor NDVI de datos satelitales
    valor_base_satelital = 0.6  # Valor por defecto
    if datos_satelitales and 'NDVI' in datos_satelitales:
        valor_base_satelital = datos_satelitales['NDVI'].get('valor_promedio', 0.6)
    
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
        
        npk_actual = (ndvi * 0.4) + (ndre * 0.3) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
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

# ===== FUNCIONES DE VISUALIZACIÓN =====
def crear_mapa_fertilidad(gdf_completo, cultivo, satelite):
    """Crear mapa de fertilidad actual con mapa de calor"""
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        cmap = LinearSegmentedColormap.from_list('fertilidad_gee', ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'])
        vmin, vmax = 0, 1
        
        # Crear puntos para interpolación
        puntos = []
        valores = []
        for idx, row in gdf_plot.iterrows():
            centroid = row.geometry.centroid
            puntos.append([centroid.x, centroid.y])
            valores.append(row['fert_npk_actual'])
        
        puntos = np.array(puntos)
        valores = np.array(valores)
        
        # Crear grid para interpolación
        x_min, y_min, x_max, y_max = gdf_plot.total_bounds
        xi = np.linspace(x_min, x_max, 200)
        yi = np.linspace(y_min, y_max, 200)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolación
        triang = Triangulation(puntos[:, 0], puntos[:, 1])
        interpolator = LinearTriInterpolator(triang, valores)
        Zi = interpolator(Xi, Yi)
        
        # Si hay NaN en la interpolación, rellenar con valor más cercano
        if np.any(np.isnan(Zi)):
            Zi = np.nan_to_num(Zi, nan=np.nanmean(valores))
        
        # Plot mapa de calor
        heatmap = ax.contourf(Xi, Yi, Zi, levels=20, cmap=cmap, alpha=0.7)
        
        # Plot polígonos
        gdf_plot.boundary.plot(ax=ax, color='black', linewidth=1.5)
        
        # Añadir etiquetas
        for idx, row in gdf_plot.iterrows():
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{row['fert_npk_actual']:.2f}", (centroid.x, centroid.y),
                       xytext=(5, 5), textcoords="offset points",
                       fontsize=8, color='black', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.5)
        except:
            pass
        
        info_satelite = {'SENTINEL-2 (GEE)': 'Sentinel-2 (GEE)', 'LANDSAT-8 (GEE)': 'Landsat-8 (GEE)', 'DATOS_SIMULADOS': 'Simulados'}
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} MAPA DE CALOR - FERTILIDAD ACTUAL\n{cultivo} | {info_satelite.get(satelite, satelite)}',
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
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

def crear_mapa_npk_completo(gdf_completo, cultivo, nutriente='N'):
    """Crear mapa de recomendaciones NPK con mapa de calor"""
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        if nutriente == 'N':
            cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'])
            columna = 'rec_N'
            titulo_nut = 'NITRÓGENO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max'] * 1.2
        elif nutriente == 'P':
            cmap = LinearSegmentedColormap.from_list('fosforo_gee', ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'])
            columna = 'rec_P'
            titulo_nut = 'FÓSFORO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max'] * 1.2
        else:
            cmap = LinearSegmentedColormap.from_list('potasio_gee', ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8'])
            columna = 'rec_K'
            titulo_nut = 'POTASIO'
            vmin = PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min'] * 0.8
            vmax = PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max'] * 1.2
        
        # Crear puntos para interpolación
        puntos = []
        valores = []
        for idx, row in gdf_plot.iterrows():
            centroid = row.geometry.centroid
            puntos.append([centroid.x, centroid.y])
            valores.append(row[columna])
        
        puntos = np.array(puntos)
        valores = np.array(valores)
        
        # Crear grid para interpolación
        x_min, y_min, x_max, y_max = gdf_plot.total_bounds
        xi = np.linspace(x_min, x_max, 200)
        yi = np.linspace(y_min, y_max, 200)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolación
        triang = Triangulation(puntos[:, 0], puntos[:, 1])
        interpolator = LinearTriInterpolator(triang, valores)
        Zi = interpolator(Xi, Yi)
        
        # Si hay NaN en la interpolación
        if np.any(np.isnan(Zi)):
            Zi = np.nan_to_num(Zi, nan=np.nanmean(valores))
        
        # Plot mapa de calor
        heatmap = ax.contourf(Xi, Yi, Zi, levels=20, cmap=cmap, alpha=0.7)
        
        # Plot polígonos
        gdf_plot.boundary.plot(ax=ax, color='black', linewidth=1.5)
        
        # Añadir etiquetas
        for idx, row in gdf_plot.iterrows():
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{row[columna]:.0f}", (centroid.x, centroid.y),
                       xytext=(5, 5), textcoords="offset points",
                       fontsize=8, color='black', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.5)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} MAPA DE CALOR - RECOMENDACIONES {titulo_nut}\n{cultivo}',
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
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

def crear_mapa_pendientes_completo(X, Y, pendientes, gdf_original):
    """Crear mapa de pendientes con mapa de calor"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Filtrar valores NaN
        mask = ~np.isnan(pendientes)
        X_flat = X[mask].flatten()
        Y_flat = Y[mask].flatten()
        pend_flat = pendientes[mask].flatten()
        
        # Crear grid para interpolación
        xi = np.linspace(X_flat.min(), X_flat.max(), 300)
        yi = np.linspace(Y_flat.min(), Y_flat.max(), 300)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolación
        triang = Triangulation(X_flat, Y_flat)
        interpolator = LinearTriInterpolator(triang, pend_flat)
        Zi = interpolator(Xi, Yi)
        
        # Si hay NaN en la interpolación
        if np.any(np.isnan(Zi)):
            Zi = np.nan_to_num(Zi, nan=np.nanmean(pend_flat))
        
        # Plot mapa de calor de pendientes
        cmap_pend = LinearSegmentedColormap.from_list('pendiente_gee', ['#4daf4a', '#a6d96a', '#ffffbf', '#fdae61', '#f46d43', '#d73027'])
        heatmap = ax.contourf(Xi, Yi, Zi, levels=30, cmap=cmap_pend, alpha=0.8)
        
        # Plot parcela
        gdf_original.to_crs(epsg=3857).plot(ax=ax, color='none', edgecolor='black', linewidth=2.5)
        
        cbar = plt.colorbar(heatmap, ax=ax, shrink=0.8)
        cbar.set_label('Pendiente (%)', fontsize=12, fontweight='bold')
        
        ax.set_title('MAPA DE CALOR DE PENDIENTES', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.3)
        except:
            pass
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        # Calcular estadísticas
        pendientes_flat = pendientes.flatten()
        pendientes_flat = pendientes_flat[~np.isnan(pendientes_flat)]
        stats = {
            'min': float(np.nanmin(pendientes_flat)),
            'max': float(np.nanmax(pendientes_flat)),
            'mean': float(np.nanmean(pendientes_flat)),
            'std': float(np.nanstd(pendientes_flat))
        }
        
        return buf, stats
    except Exception as e:
        st.error(f"❌ Error creando mapa de pendientes: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None, {}

def crear_mapa_curvas_nivel_completo(X, Y, Z, curvas_nivel, elevaciones, gdf_original):
    """Crear mapa con curvas de nivel y relieve sombreado"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        
        # Crear relieve sombreado
        dx = np.gradient(Z, axis=1)
        dy = np.gradient(Z, axis=0)
        slope = np.arctan(np.sqrt(dx**2 + dy**2))
        aspect = np.arctan2(-dy, dx)
        azimuth = np.deg2rad(315)
        altitude = np.deg2rad(45)
        shaded = np.sin(altitude) * np.cos(slope) + np.cos(altitude) * np.sin(slope) * np.cos(azimuth - aspect)
        shaded = (shaded - shaded.min()) / (shaded.max() - shaded.min())
        
        # Plot relieve sombreado
        ax.imshow(shaded, extent=(X.min(), X.max(), Y.min(), Y.max()), 
                 cmap='gray', alpha=0.6, origin='lower')
        
        # Plot curvas de nivel
        if curvas_nivel:
            # Usar matplotlib.contour directamente para mejores resultados
            Z_filled = np.where(np.isnan(Z), np.nanmin(Z), Z)
            CS = ax.contour(X, Y, Z_filled, levels=np.arange(np.nanmin(Z), np.nanmax(Z), 5), 
                          colors='blue', linewidths=1.2, alpha=0.8)
            ax.clabel(CS, inline=True, fontsize=8, fmt='%1.0f m')
        
        # Plot parcela
        gdf_original.plot(ax=ax, color='none', edgecolor='red', linewidth=3)
        
        ax.set_title('MAPA TOPOGRÁFICO CON CURVAS DE NIVEL', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de curvas de nivel: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

def crear_visualizacion_3d_completa(X, Y, Z):
    """Crear visualización 3D del terreno con colores realistas"""
    try:
        fig = plt.figure(figsize=(16, 12))
        ax = fig.add_subplot(111, projection='3d')
        
        # Normalizar elevación para colores
        Z_normalized = (Z - np.nanmin(Z)) / (np.nanmax(Z) - np.nanmin(Z))
        
        # Crear superficie 3D con colores de terreno
        surf = ax.plot_surface(X, Y, Z, facecolors=plt.cm.terrain(Z_normalized), 
                              linewidth=0.5, antialiased=True, alpha=0.9)
        
        # Configuración de ejes
        ax.set_xlabel('Longitud', fontsize=12, labelpad=10)
        ax.set_ylabel('Latitud', fontsize=12, labelpad=10)
        ax.set_zlabel('Elevación (m)', fontsize=12, labelpad=10)
        ax.set_title('MODELO 3D DEL TERRENO', fontsize=18, fontweight='bold', pad=20)
        
        # Ajustar vista
        ax.view_init(elev=30, azim=45)
        ax.grid(True, alpha=0.3)
        
        # Añadir barra de colores
        m = plt.cm.ScalarMappable(cmap=plt.cm.terrain, 
                                norm=plt.Normalize(vmin=np.nanmin(Z), vmax=np.nanmax(Z)))
        m.set_array([])
        cbar = fig.colorbar(m, ax=ax, shrink=0.5, aspect=5, pad=0.1)
        cbar.set_label('Elevación (m)', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando visualización 3D: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

def crear_mapa_potencial_cosecha(gdf_completo, cultivo, variedad):
    """Crear mapa de potencial de cosecha con mapa de calor"""
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))
        
        # Mapa de rendimiento sin fertilización
        cmap_rend = LinearSegmentedColormap.from_list('rendimiento_gee', ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'])
        vmin_rend = gdf_completo['proy_rendimiento_sin_fert'].min()
        vmax_rend = gdf_completo['proy_rendimiento_sin_fert'].max()
        
        # Crear puntos para interpolación
        puntos = []
        valores = []
        for idx, row in gdf_plot.iterrows():
            centroid = row.geometry.centroid
            puntos.append([centroid.x, centroid.y])
            valores.append(row['proy_rendimiento_sin_fert'])
        
        puntos = np.array(puntos)
        valores = np.array(valores)
        
        # Crear grid para interpolación
        x_min, y_min, x_max, y_max = gdf_plot.total_bounds
        xi = np.linspace(x_min, x_max, 200)
        yi = np.linspace(y_min, y_max, 200)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolación
        triang = Triangulation(puntos[:, 0], puntos[:, 1])
        interpolator = LinearTriInterpolator(triang, valores)
        Zi = interpolator(Xi, Yi)
        
        # Si hay NaN en la interpolación
        if np.any(np.isnan(Zi)):
            Zi = np.nan_to_num(Zi, nan=np.nanmean(valores))
        
        # Plot mapa de calor
        heatmap1 = ax1.contourf(Xi, Yi, Zi, levels=20, cmap=cmap_rend, alpha=0.7)
        gdf_plot.boundary.plot(ax=ax1, color='black', linewidth=1.5)
        
        try:
            ctx.add_basemap(ax1, source=ctx.providers.Esri.WorldImagery, alpha=0.4)
        except:
            pass
        
        ax1.set_title(f'{ICONOS_CULTIVOS[cultivo]} POTENCIAL SIN FERTILIZACIÓN\n{cultivo} - {variedad}', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Longitud')
        ax1.set_ylabel('Latitud')
        ax1.grid(True, alpha=0.3)
        
        sm1 = plt.cm.ScalarMappable(cmap=cmap_rend, norm=plt.Normalize(vmin=vmin_rend, vmax=vmax_rend))
        sm1.set_array([])
        cbar1 = plt.colorbar(sm1, ax=ax1, shrink=0.8)
        cbar1.set_label('Rendimiento (kg/ha)', fontsize=11, fontweight='bold')
        
        # Mapa de rendimiento con fertilización
        vmin_rend_fert = gdf_completo['proy_rendimiento_con_fert'].min()
        vmax_rend_fert = gdf_completo['proy_rendimiento_con_fert'].max()
        
        # Crear puntos para interpolación
        valores_fert = []
        for idx, row in gdf_plot.iterrows():
            valores_fert.append(row['proy_rendimiento_con_fert'])
        
        valores_fert = np.array(valores_fert)
        
        # Interpolación
        interpolator_fert = LinearTriInterpolator(triang, valores_fert)
        Zi_fert = interpolator_fert(Xi, Yi)
        
        # Si hay NaN en la interpolación
        if np.any(np.isnan(Zi_fert)):
            Zi_fert = np.nan_to_num(Zi_fert, nan=np.nanmean(valores_fert))
        
        # Plot mapa de calor
        heatmap2 = ax2.contourf(Xi, Yi, Zi_fert, levels=20, cmap=cmap_rend, alpha=0.7)
        gdf_plot.boundary.plot(ax=ax2, color='black', linewidth=1.5)
        
        try:
            ctx.add_basemap(ax2, source=ctx.providers.Esri.WorldImagery, alpha=0.4)
        except:
            pass
        
        ax2.set_title(f'{ICONOS_CULTIVOS[cultivo]} POTENCIAL CON FERTILIZACIÓN\n{cultivo} - {variedad}', 
                     fontsize=14, fontweight='bold')
        ax2.set_xlabel('Longitud')
        ax2.set_ylabel('Latitud')
        ax2.grid(True, alpha=0.3)
        
        sm2 = plt.cm.ScalarMappable(cmap=cmap_rend, norm=plt.Normalize(vmin=vmin_rend_fert, vmax=vmax_rend_fert))
        sm2.set_array([])
        cbar2 = plt.colorbar(sm2, ax=ax2, shrink=0.8)
        cbar2.set_label('Rendimiento (kg/ha)', fontsize=11, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de potencial de cosecha: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

# ===== FUNCIONES DE EXPORTACIÓN =====
def exportar_a_geojson(gdf, nombre_base="parcela"):
    try:
        gdf = validar_y_corregir_crs(gdf)
        geojson_data = gdf.to_json()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_base}_{timestamp}.geojson"
        return geojson_data, nombre_archivo
    except Exception as e:
        st.error(f"❌ Error exportando a GeoJSON: {str(e)}")
        return None, None

def generar_reporte_completo(resultados, cultivo, variedad, satelite, fecha_inicio, fecha_fin):
    """Generar reporte DOCX con TODAS las secciones y análisis"""
    try:
        doc = Document()
        
        # Título
        title = doc.add_heading(f'REPORTE COMPLETO DE ANÁLISIS - {cultivo}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtítulo con variedad
        subtitle = doc.add_paragraph(f'Variedad: {variedad} | Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 1. INFORMACIÓN GENERAL
        doc.add_heading('1. INFORMACIÓN GENERAL', level=1)
        info_table = doc.add_table(rows=6, cols=2)
        info_table.style = 'Table Grid'
        info_table.cell(0, 0).text = 'Cultivo'
        info_table.cell(0, 1).text = cultivo
        info_table.cell(1, 0).text = 'Variedad/Cultivar'
        info_table.cell(1, 1).text = variedad
        info_table.cell(2, 0).text = 'Área Total'
        info_table.cell(2, 1).text = f'{resultados["area_total"]:.2f} ha'
        info_table.cell(3, 0).text = 'Zonas Analizadas'
        info_table.cell(3, 1).text = str(len(resultados['gdf_completo']))
        info_table.cell(4, 0).text = 'Satélite'
        info_table.cell(4, 1).text = satelite
        info_table.cell(5, 0).text = 'Período de Análisis'
        info_table.cell(5, 1).text = f'{fecha_inicio.strftime("%d/%m/%Y")} a {fecha_fin.strftime("%d/%m/%Y")}'
        
        doc.add_paragraph()
        
        # 2. FERTILIDAD ACTUAL
        doc.add_heading('2. FERTILIDAD ACTUAL', level=1)
        doc.add_paragraph('Resumen de parámetros de fertilidad por zona:')
        
        fert_table = doc.add_table(rows=1, cols=7)
        fert_table.style = 'Table Grid'
        headers = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 'NDRE', 'Materia Org (%)', 'Humedad']
        for i, header in enumerate(headers):
            fert_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = fert_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = f"{resultados['gdf_completo'].iloc[i]['area_ha']:.2f}"
            row[2].text = f"{resultados['gdf_completo'].iloc[i]['fert_npk_actual']:.3f}"
            row[3].text = f"{resultados['gdf_completo'].iloc[i]['fert_ndvi']:.3f}"
            row[4].text = f"{resultados['gdf_completo'].iloc[i]['fert_ndre']:.3f}"
            row[5].text = f"{resultados['gdf_completo'].iloc[i]['fert_materia_organica']:.1f}"
            row[6].text = f"{resultados['gdf_completo'].iloc[i]['fert_humedad_suelo']:.3f}"
        
        doc.add_paragraph()
        
        # 3. RECOMENDACIONES NPK
        doc.add_heading('3. RECOMENDACIONES NPK', level=1)
        doc.add_paragraph('Recomendaciones de fertilización por zona (kg/ha):')
        
        npk_table = doc.add_table(rows=1, cols=4)
        npk_table.style = 'Table Grid'
        npk_headers = ['Zona', 'Nitrógeno (N)', 'Fósforo (P)', 'Potasio (K)']
        for i, header in enumerate(npk_headers):
            npk_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = npk_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = f"{resultados['gdf_completo'].iloc[i]['rec_N']:.1f}"
            row[2].text = f"{resultados['gdf_completo'].iloc[i]['rec_P']:.1f}"
            row[3].text = f"{resultados['gdf_completo'].iloc[i]['rec_K']:.1f}"
        
        doc.add_paragraph()
        
        # 4. ANÁLISIS DE COSTOS
        doc.add_heading('4. ANÁLISIS DE COSTOS', level=1)
        doc.add_paragraph('Costos estimados de fertilización por zona (USD/ha):')
        
        costo_table = doc.add_table(rows=1, cols=5)
        costo_table.style = 'Table Grid'
        costo_headers = ['Zona', 'Costo N', 'Costo P', 'Costo K', 'Costo Total']
        for i, header in enumerate(costo_headers):
            costo_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = costo_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = f"{resultados['gdf_completo'].iloc[i]['costo_costo_nitrogeno']:.2f}"
            row[2].text = f"{resultados['gdf_completo'].iloc[i]['costo_costo_fosforo']:.2f}"
            row[3].text = f"{resultados['gdf_completo'].iloc[i]['costo_costo_potasio']:.2f}"
            row[4].text = f"{resultados['gdf_completo'].iloc[i]['costo_costo_total']:.2f}"
        
        doc.add_paragraph()
        costo_total = resultados['gdf_completo']['costo_costo_total'].sum()
        costo_promedio = resultados['gdf_completo']['costo_costo_total'].mean()
        doc.add_paragraph(f'Costo total estimado: ${costo_total:.2f} USD')
        doc.add_paragraph(f'Costo promedio por hectárea: ${costo_promedio:.2f} USD/ha')
        
        doc.add_paragraph()
        
        # 5. TEXTURA DEL SUELO
        doc.add_heading('5. TEXTURA DEL SUELO', level=1)
        doc.add_paragraph('Composición granulométrica por zona:')
        
        text_table = doc.add_table(rows=1, cols=5)
        text_table.style = 'Table Grid'
        text_headers = ['Zona', 'Textura', 'Arena (%)', 'Limo (%)', 'Arcilla (%)']
        for i, header in enumerate(text_headers):
            text_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = text_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = "Franco Arcilloso"  # Textura simulada
            row[2].text = f"{np.random.uniform(30, 50):.1f}"
            row[3].text = f"{np.random.uniform(20, 40):.1f}"
            row[4].text = f"{np.random.uniform(20, 40):.1f}"
        
        doc.add_paragraph()
        
        # 6. PROYECCIONES DE COSECHA
        doc.add_heading('6. PROYECCIONES DE COSECHA', level=1)
        doc.add_paragraph('Proyecciones de rendimiento con y sin fertilización (kg/ha):')
        
        proy_table = doc.add_table(rows=1, cols=4)
        proy_table.style = 'Table Grid'
        proy_headers = ['Zona', 'Sin Fertilización', 'Con Fertilización', 'Incremento (%)']
        for i, header in enumerate(proy_headers):
            proy_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = proy_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = f"{resultados['gdf_completo'].iloc[i]['proy_rendimiento_sin_fert']:.0f}"
            row[2].text = f"{resultados['gdf_completo'].iloc[i]['proy_rendimiento_con_fert']:.0f}"
            row[3].text = f"{resultados['gdf_completo'].iloc[i]['proy_incremento_esperado']:.1f}"
        
        doc.add_paragraph()
        rend_sin_total = resultados['gdf_completo']['proy_rendimiento_sin_fert'].sum()
        rend_con_total = resultados['gdf_completo']['proy_rendimiento_con_fert'].sum()
        incremento_prom = resultados['gdf_completo']['proy_incremento_esperado'].mean()
        doc.add_paragraph(f'Rendimiento total sin fertilización: {rend_sin_total:.0f} kg')
        doc.add_paragraph(f'Rendimiento total con fertilización: {rend_con_total:.0f} kg')
        doc.add_paragraph(f'Incremento promedio esperado: {incremento_prom:.1f}%')
        
        doc.add_paragraph()
        
        # 7. ANÁLISIS TOPOGRÁFICO
        if 'dem_data' in resultados and resultados['dem_data']:
            doc.add_heading('7. ANÁLISIS TOPOGRÁFICO', level=1)
            
            dem_stats = {
                'Elevación mínima': f"{np.nanmin(resultados['dem_data']['Z']):.1f} m",
                'Elevación máxima': f"{np.nanmax(resultados['dem_data']['Z']):.1f} m",
                'Elevación promedio': f"{np.nanmean(resultados['dem_data']['Z']):.1f} m",
                'Pendiente promedio': f"{np.nanmean(resultados['dem_data']['pendientes']):.1f} %",
                'Número de curvas de nivel': f"{len(resultados['dem_data'].get('curvas_nivel', []))}"
            }
            
            for key, value in dem_stats.items():
                p = doc.add_paragraph()
                run_key = p.add_run(f'{key}: ')
                run_key.bold = True
                p.add_run(value)
            
            doc.add_paragraph()
            
            # Riesgo de erosión
            doc.add_heading('8. ANÁLISIS DE RIESGO DE EROSIÓN', level=1)
            doc.add_paragraph('Clasificación de pendientes y factores de riesgo:')
            
            pendientes = resultados['dem_data']['pendientes'].flatten()
            pendientes = pendientes[~np.isnan(pendientes)]
            
            if len(pendientes) > 0:
                riesgo_total = 0
                for categoria, params in {
                    'PLANA (0-2%)': {'min': 0, 'max': 2, 'factor_erosivo': 0.1},
                    'SUAVE (2-5%)': {'min': 2, 'max': 5, 'factor_erosivo': 0.3},
                    'MODERADA (5-10%)': {'min': 5, 'max': 10, 'factor_erosivo': 0.6},
                    'FUERTE (10-15%)': {'min': 10, 'max': 15, 'factor_erosivo': 0.8},
                    'MUY FUERTE (15-25%)': {'min': 15, 'max': 25, 'factor_erosivo': 0.9},
                    'EXTREMA (>25%)': {'min': 25, 'max': 100, 'factor_erosivo': 1.0}
                }.items():
                    mask = (pendientes >= params['min']) & (pendientes < params['max'])
                    porcentaje = np.sum(mask) / len(pendientes) * 100
                    riesgo_total += porcentaje * params['factor_erosivo']
                
                riesgo_promedio = riesgo_total / 100
                
                if riesgo_promedio < 0.3:
                    nivel_riesgo = "BAJO"
                elif riesgo_promedio < 0.6:
                    nivel_riesgo = "MODERADO"
                else:
                    nivel_riesgo = "ALTO"
                
                doc.add_paragraph(f"Nivel de riesgo de erosión: {nivel_riesgo.upper()} (Factor: {riesgo_promedio:.2f})")
        
        doc.add_paragraph()
        
        # 9. RECOMENDACIONES FINALES
        doc.add_heading('9. RECOMENDACIONES FINALES', level=1)
        
        recomendaciones = [
            f"Aplicar fertilización diferenciada por zonas según el análisis NPK",
            f"Priorizar zonas con índice de fertilidad inferior a 0.5",
            f"Considerar enmiendas orgánicas en zonas con materia orgánica < 2%",
            f"Implementar riego suplementario en zonas con humedad < 0.2",
            f"Realizar análisis de suelo de laboratorio para validar resultados",
            f"Considerar agricultura de precisión para aplicación variable de insumos",
            f"Monitorear zonas con pendientes > 15% para prevención de erosión",
            f"Ajustar dosis de fertilizantes según variedad específica ({variedad})"
        ]
        
        for rec in recomendaciones:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(rec)
        
        doc.add_paragraph()
        
        # 10. METADATOS TÉCNICOS
        doc.add_heading('10. METADATOS TÉCNICOS', level=1)
        metadatos = [
            ('Generado por', 'Analizador Multi-Cultivo Satelital'),
            ('Versión', '6.0 - Google Earth Engine Integration'),
            ('Fecha de generación', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ('Sistema de coordenadas', 'EPSG:4326 (WGS84)'),
            ('Número de zonas', str(len(resultados['gdf_completo']))),
            ('Resolución satelital', '10m' if "SENTINEL" in satelite else '30m'),
            ('Resolución DEM', f'{resolucion_dem} m'),
            ('Intervalo curvas de nivel', f'{intervalo_curvas} m'),
            ('Variedad seleccionada', variedad),
            ('Google Earth Engine', 'Configurado' if GEE_AVAILABLE else 'No disponible')
        ]
        
        for key, value in metadatos:
            p = doc.add_paragraph()
            run_key = p.add_run(f'{key}: ')
            run_key.bold = True
            p.add_run(value)
        
        docx_output = BytesIO()
        doc.save(docx_output)
        docx_output.seek(0)
        
        return docx_output
        
    except Exception as e:
        st.error(f"❌ Error generando reporte DOCX: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def crear_boton_descarga_png(buffer, nombre_archivo, texto_boton="📥 Descargar PNG"):
    """Crear botón de descarga para archivos PNG"""
    if buffer:
        st.download_button(
            label=texto_boton,
            data=buffer,
            file_name=nombre_archivo,
            mime="image/png"
        )

# ===== FUNCIÓN PRINCIPAL DE ANÁLISIS =====
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin, intervalo_curvas=5.0, resolucion_dem=10.0):
    """Ejecuta todos los análisis y guarda los resultados"""
    resultados = {
        'exitoso': False,
        'gdf_dividido': None,
        'fertilidad_actual': None,
        'recomendaciones_npk': None,
        'costos': None,
        'proyecciones': None,
        'area_total': 0,
        'datos_satelitales': None,
        'dem_data': {}
    }
    
    try:
        gdf = validar_y_corregir_crs(gdf)
        area_total = calcular_superficie(gdf)
        resultados['area_total'] = area_total
        
        # Obtener datos satelitales según selección
        datos_satelitales = None
        if "GEE" in satelite and GEE_AVAILABLE:
            with st.spinner("🌎 Conectando a Google Earth Engine..."):
                datos_satelitales = descargar_datos_gee(gdf, fecha_inicio, fecha_fin)
                
            if datos_satelitales:
                st.success(f"✅ Datos satelitales obtenidos de Google Earth Engine")
                # Mostrar información de los índices obtenidos
                for idx_name, idx_data in datos_satelitales.items():
                    st.info(f"📊 {idx_name}: {idx_data.get('valor_promedio', 0):.3f} (Fecha: {idx_data.get('fecha', 'N/A')})")
            else:
                datos_satelitales = generar_datos_simulados_multiples(gdf, cultivo, ['NDVI', 'NDRE'])
                st.warning("⚠️ Usando datos simulados")
        else:
            datos_satelitales = generar_datos_simulados_multiples(gdf, cultivo, ['NDVI', 'NDRE'])
            st.info("ℹ️ Usando datos simulados")
        
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
        resultados['datos_satelitales'] = datos_satelitales
        resultados['exitoso'] = True
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error en análisis completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return resultados

# ===== INTERFAZ PRINCIPAL =====
st.title("🛰️ ANALIZADOR MULTI-CULTIVO SATELITAL CON GOOGLE EARTH ENGINE")

if uploaded_file:
    with st.spinner("Cargando parcela..."):
        try:
            gdf = cargar_archivo_parcela(uploaded_file)
            if gdf is not None:
                st.success(f"✅ Parcela cargada exitosamente: {len(gdf)} polígono(s)")
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
                    st.write(f"- Índices seleccionados: {', '.join([idx for idx, checked in [('NDVI', ndvi_check), ('NDRE', ndre_check), ('GNDVI', gndvi_check), ('EVI', evi_check), ('SAVI', savi_check)] if checked])}")
                
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
                st.error("❌ Error al cargar la parcela")
        
        except Exception as e:
            st.error(f"❌ Error en el análisis: {str(e)}")

# Mostrar resultados
if st.session_state.analisis_completado and 'resultados_todos' in st.session_state:
    resultados = st.session_state.resultados_todos
    variedad = st.session_state.variedad_seleccionada
    
    if 'datos_satelitales' in resultados and resultados['datos_satelitales']:
        st.markdown("---")
        st.subheader("🛰️ DATOS SATELITALES OBTENIDOS")
        
        datos_satelitales = resultados['datos_satelitales']
        cols = st.columns(min(3, len(datos_satelitales)))
        
        for idx, (indice_name, indice_data) in enumerate(datos_satelitales.items()):
            with cols[idx % 3]:
                st.metric(
                    label=f"{indice_name}",
                    value=f"{indice_data.get('valor_promedio', 0):.3f}",
                    help=f"Fuente: {indice_data.get('fuente', 'N/A')}\nFecha: {indice_data.get('fecha', 'N/A')}\nNubes: {indice_data.get('cobertura_nubes', 'N/A')}"
                )
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Fertilidad Actual",
        "🧪 Recomendaciones NPK",
        "💰 Análisis de Costos",
        "🏗️ Textura del Suelo",
        "📈 Proyecciones",
        "🏔️ Curvas de Nivel y 3D",
        "🌾 Potencial de Cosecha"
    ])
    
    with tab1:
        st.subheader("FERTILIDAD ACTUAL")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            npk_prom = resultados['gdf_completo']['fert_npk_actual'].mean()
            st.metric("Índice NPK Promedio", f"{npk_prom:.3f}")
        with col2:
            ndvi_prom = resultados['gdf_completo']['fert_ndvi'].mean()
            st.metric("NDVI Promedio", f"{ndvi_prom:.3f}")
        with col3:
            mo_prom = resultados['gdf_completo']['fert_materia_organica'].mean()
            st.metric("Materia Orgánica", f"{mo_prom:.1f}%")
        with col4:
            hum_prom = resultados['gdf_completo']['fert_humedad_suelo'].mean()
            st.metric("Humedad Suelo", f"{hum_prom:.3f}")
        
        st.subheader("🗺️ MAPA DE CALOR DE FERTILIDAD")
        mapa_fert = crear_mapa_fertilidad(resultados['gdf_completo'], cultivo, satelite_seleccionado)
        if mapa_fert:
            st.image(mapa_fert, use_container_width=True)
            crear_boton_descarga_png(
                mapa_fert,
                f"mapa_fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Mapa de Fertilidad PNG"
            )
        
        st.subheader("📋 TABLA DE RESULTADOS")
        columnas_fert = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 
                       'fert_ndre', 'fert_materia_organica', 'fert_humedad_suelo']
        tabla_fert = resultados['gdf_completo'][columnas_fert].copy()
        tabla_fert.columns = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 
                            'NDRE', 'Materia Org (%)', 'Humedad']
        st.dataframe(tabla_fert)
    
    with tab2:
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
        
        st.subheader("🗺️ MAPAS DE CALOR DE RECOMENDACIONES")
        col_n, col_p, col_k = st.columns(3)
        with col_n:
            mapa_n = crear_mapa_npk_completo(resultados['gdf_completo'], cultivo, 'N')
            if mapa_n:
                st.image(mapa_n, use_container_width=True)
                st.caption("Nitrógeno (N)")
                crear_boton_descarga_png(
                    mapa_n,
                    f"mapa_nitrogeno_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa N"
                )
        with col_p:
            mapa_p = crear_mapa_npk_completo(resultados['gdf_completo'], cultivo, 'P')
            if mapa_p:
                st.image(mapa_p, use_container_width=True)
                st.caption("Fósforo (P)")
                crear_boton_descarga_png(
                    mapa_p,
                    f"mapa_fosforo_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa P"
                )
        with col_k:
            mapa_k = crear_mapa_npk_completo(resultados['gdf_completo'], cultivo, 'K')
            if mapa_k:
                st.image(mapa_k, use_container_width=True)
                st.caption("Potasio (K)")
                crear_boton_descarga_png(
                    mapa_k,
                    f"mapa_potasio_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa K"
                )
        
        st.subheader("📋 TABLA DE RECOMENDACIONES")
        columnas_npk = ['id_zona', 'area_ha', 'rec_N', 'rec_P', 'rec_K']
        tabla_npk = resultados['gdf_completo'][columnas_npk].copy()
        tabla_npk.columns = ['Zona', 'Área (ha)', 'Nitrógeno (kg/ha)', 
                           'Fósforo (kg/ha)', 'Potasio (kg/ha)']
        st.dataframe(tabla_npk)
    
    with tab3:
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
        
        st.subheader("📋 TABLA DE COSTOS POR ZONA")
        columnas_costos = ['id_zona', 'area_ha', 'costo_costo_nitrogeno', 
                         'costo_costo_fosforo', 'costo_costo_potasio', 'costo_costo_total']
        tabla_costos = resultados['gdf_completo'][columnas_costos].copy()
        tabla_costos.columns = ['Zona', 'Área (ha)', 'Costo N (USD)', 
                              'Costo P (USD)', 'Costo K (USD)', 'Total (USD)']
        st.dataframe(tabla_costos)
    
    with tab4:
        st.subheader("TEXTURA DEL SUELO")
        st.info("⚠️ Análisis de textura simulado - Datos reales disponibles en versión premium.")
        
        # Datos simulados de textura del suelo
        texturas_disponibles = ["Franco Arcilloso", "Franco Limoso", "Franco Arenoso", "Arcilloso", "Arenoso"]
        textura_simulada = np.random.choice(texturas_disponibles)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Textura Predominante", textura_simulada)
        with col2:
            st.metric("Arena", f"{np.random.uniform(30, 50):.1f}%")
        with col3:
            st.metric("Arcilla", f"{np.random.uniform(20, 40):.1f}%")
        
        st.info("Para análisis de textura real, contacte con nuestro servicio de laboratorio de suelos.")
    
    with tab5:
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
        
        st.subheader("📋 TABLA DE PROYECCIONES POR ZONA")
        columnas_proy = ['id_zona', 'area_ha', 'proy_rendimiento_sin_fert', 
                       'proy_rendimiento_con_fert', 'proy_incremento_esperado']
        tabla_proy = resultados['gdf_completo'][columnas_proy].copy()
        tabla_proy.columns = ['Zona', 'Área (ha)', 'Sin Fert (kg)', 
                            'Con Fert (kg)', 'Incremento (%)']
        st.dataframe(tabla_proy)
    
    with tab6:
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
            
            st.subheader("🗺️ MAPA DE CALOR DE PENDIENTES")
            mapa_pendientes, stats_pendientes = crear_mapa_pendientes_completo(
                dem_data['X'], dem_data['Y'], dem_data['pendientes'], gdf
            )
            if mapa_pendientes:
                st.image(mapa_pendientes, use_container_width=True)
                crear_boton_descarga_png(
                    mapa_pendientes,
                    f"mapa_pendientes_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa de Pendientes PNG"
                )
            
            st.subheader("🗺️ MAPA TOPOGRÁFICO CON CURVAS DE NIVEL")
            mapa_curvas = crear_mapa_curvas_nivel_completo(
                dem_data['X'], dem_data['Y'], dem_data['Z'],
                dem_data.get('curvas_nivel', []), dem_data.get('elevaciones', []), gdf
            )
            if mapa_curvas:
                st.image(mapa_curvas, use_container_width=True)
                crear_boton_descarga_png(
                    mapa_curvas,
                    f"mapa_curvas_nivel_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa de Curvas PNG"
                )
            
            st.subheader("🎨 VISUALIZACIÓN 3D DEL TERRENO")
            visualizacion_3d = crear_visualizacion_3d_completa(dem_data['X'], dem_data['Y'], dem_data['Z'])
            if visualizacion_3d:
                st.image(visualizacion_3d, use_container_width=True)
                crear_boton_descarga_png(
                    visualizacion_3d,
                    f"visualizacion_3d_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Visualización 3D PNG"
                )
        else:
            st.warning("⚠️ No se generaron datos DEM. Intenta ejecutar el análisis nuevamente.")
    
    with tab7:
        st.subheader("POTENCIAL DE COSECHA")
        mapa_potencial = crear_mapa_potencial_cosecha(resultados['gdf_completo'], cultivo, variedad)
        if mapa_potencial:
            st.image(mapa_potencial, use_container_width=True)
            crear_boton_descarga_png(
                mapa_potencial,
                f"mapa_potencial_cosecha_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Mapa de Potencial PNG"
            )

else:
    st.info("👈 Sube un archivo de parcela y ejecuta el análisis para comenzar.")

# Sección de exportación
st.markdown("---")
st.subheader("💾 EXPORTAR RESULTADOS")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    st.markdown("**GeoJSON**")
    if st.button("📤 Generar GeoJSON", key="generate_geojson"):
        with st.spinner("Generando GeoJSON..."):
            geojson_data, nombre_geojson = exportar_a_geojson(
                resultados['gdf_completo'], 
                f"analisis_{cultivo}"
            )
            if geojson_data:
                st.session_state.geojson_data = geojson_data
                st.session_state.nombre_geojson = nombre_geojson
                st.success("✅ GeoJSON generado correctamente")
                st.rerun()
    
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
            reporte = generar_reporte_completo(
                resultados, 
                cultivo, 
                variedad,
                satelite_seleccionado,
                fecha_inicio,
                fecha_fin
            )
            if reporte:
                st.session_state.reporte_completo = reporte
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                nombre_reporte = f"reporte_completo_{cultivo}_{timestamp}.docx"
                st.session_state.nombre_reporte = nombre_reporte
                st.success("✅ Reporte generado correctamente")
                st.rerun()
    
    if st.session_state.reporte_completo is not None:
        st.download_button(
            label="📥 Descargar Reporte DOCX",
            data=st.session_state.reporte_completo,
            file_name=st.session_state.nombre_reporte,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="docx_download"
        )

# Información sobre Google Earth Engine
st.markdown("---")
st.markdown("""
### 🌎 Acerca de Google Earth Engine

**Google Earth Engine** es una plataforma de análisis geoespacial que combina:
- **Catálogo multi-petabyte** de imágenes satelitales
- **Procesamiento en la nube** a gran escala
- **Acceso gratuito** para investigación, educación y uso sin fines de lucro

**Satélites disponibles:**
- **Sentinel-2**: 10m resolución, cada 5 días
- **Landsat 8/9**: 30m resolución, cada 16 días
- **MODIS**: 250-500m resolución, diario
- **Y muchos más...**

**Para autenticar GEE:**
1. Instalar: `pip install earthengine-api`
2. Ejecutar en terminal: `earthengine authenticate`
3. Sigue las instrucciones en el navegador
""")

st.markdown("---")
st.markdown("**Versión 6.0 - Google Earth Engine Integration** | © 2026 Analizador Multi-Cultivo Satelital")
