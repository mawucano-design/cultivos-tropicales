# app.py - Análisis Multicultivo Satelital con GEE
import streamlit as st
import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import io
import json
import os
import tempfile
import zipfile
import math
from datetime import datetime, timedelta
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
import folium
from folium.plugins import Draw
import branca.colormap as cm
from streamlit_folium import st_folium
from matplotlib.tri import Triangulation
import warnings
warnings.filterwarnings('ignore')

# Importar librerías para reportes
try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ Para generar reportes DOCX, instala: pip install python-docx")

try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False
    st.warning("⚠️ Para exportar a XLSX, instala: pip install xlsxwriter")

# ===== INICIALIZACIÓN AUTOMÁTICA DE GOOGLE EARTH ENGINE =====
try:
    import ee
    GEE_AVAILABLE = True
except ImportError:
    GEE_AVAILABLE = False
    st.warning("⚠️ Google Earth Engine no está instalado. Para usar datos satelitales reales, instala: pip install earthengine-api")

def inicializar_gee():
    """Inicializa GEE con Service Account desde secrets de Streamlit Cloud o autenticación local"""
    if not GEE_AVAILABLE:
        return False
    
    try:
        # Intentar con secrets de Streamlit Cloud
        gee_secret = os.environ.get('GEE_SERVICE_ACCOUNT')
        if gee_secret:
            try:
                # Limpiar y parsear JSON
                credentials_info = json.loads(gee_secret.strip())
                credentials = ee.ServiceAccountCredentials(
                    credentials_info['client_email'],
                    key_data=json.dumps(credentials_info)
                )
                ee.Initialize(credentials, project='ee-mawucano25')
                st.session_state.gee_authenticated = True
                st.session_state.gee_project = 'ee-mawucano25'
                print("✅ GEE inicializado con Service Account")
                return True
            except Exception as e:
                print(f"⚠️ Error Service Account: {str(e)}")
        
        # Fallback: autenticación local (desarrollo)
        try:
            ee.Initialize(project='ee-mawucano25')
            st.session_state.gee_authenticated = True
            st.session_state.gee_project = 'ee-mawucano25'
            print("✅ GEE inicializado localmente")
            return True
        except Exception as e:
            print(f"⚠️ Error inicialización local: {str(e)}")
            
        st.session_state.gee_authenticated = False
        return False
        
    except Exception as e:
        st.session_state.gee_authenticated = False
        print(f"❌ Error crítico GEE: {str(e)}")
        return False

# ===== CONFIGURACIÓN INICIAL DE LA APP =====
st.set_page_config(
    page_title="🌾 Análisis Multicultivo Satelital con GEE",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== INICIALIZACIÓN DE VARIABLES DE SESIÓN =====
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
    st.session_state.gee_project = ''
    if GEE_AVAILABLE:
        inicializar_gee()

if 'poligono' not in st.session_state:
    st.session_state.poligono = None
if 'resultados_analisis' not in st.session_state:
    st.session_state.resultados_analisis = None
if 'cultivo_seleccionado' not in st.session_state:
    st.session_state.cultivo_seleccionado = 'TRIGO'
if 'analisis_ejecutado' not in st.session_state:
    st.session_state.analisis_ejecutado = False

# Estilos CSS premium
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
        color: white;
    }
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 0.8em 1.5em !important;
        font-weight: 700 !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 25px rgba(59, 130, 246, 0.6) !important;
    }
    .hero-banner {
        background: linear-gradient(rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.95)),
                    url('https://images.unsplash.com/photo-1597981309443-6e2d2a4d9c3f?ixlib=rb-4.0.3&auto=format&fit=crop&w=2070&q=80') !important;
        background-size: cover !important;
        background-position: center 40% !important;
        padding: 3.5em 2em !important;
        border-radius: 24px !important;
        margin-bottom: 2.5em !important;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
    .hero-title {
        background: linear-gradient(135deg, #ffffff 0%, #93c5fd 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        font-size: 3.2em !important;
        font-weight: 900 !important;
        text-shadow: 0 4px 12px rgba(0, 0, 0, 0.6) !important;
    }
    .dashboard-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)) !important;
        border-radius: 20px !important;
        padding: 25px !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    .dashboard-card:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0 20px 40px rgba(59, 130, 246, 0.2) !important;
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
</style>
""", unsafe_allow_html=True)

# ===== HERO BANNER =====
st.markdown("""
<div class="hero-banner">
    <div style="text-align: center;">
        <h1 class="hero-title">ANÁLISIS MULTICULTIVO SATELITAL CON GEE</h1>
        <p style="color: #cbd5e1; font-size: 1.3em; max-width: 800px; margin: 0 auto;">
            Potenciado con Google Earth Engine para agricultura de precisión en tiempo real
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ===== CONFIGURACIÓN DE CULTIVOS COMPLETA =====
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
        'icono': '🌾'
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
        'icono': '🌽'
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
        'icono': '🌾'
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
        'icono': '🫘'
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
        'icono': '🌻'
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
        'COSTO_FERTILizACION': 380,
        'PRECIO_VENTA': 0.60,
        'icono': '🥜'
    },
    'CACAO': {
        'NITROGENO': {'min': 120, 'max': 200},
        'FOSFORO': {'min': 45, 'max': 85},
        'POTASIO': {'min': 150, 'max': 250},
        'MATERIA_ORGANICA_OPTIMA': 4.2,
        'HUMEDAD_OPTIMA': 0.35,
        'NDVI_OPTIMO': 0.82,
        'NDRE_OPTIMO': 0.48,
        'RENDIMIENTO_OPTIMO': 1200,
        'COSTO_FERTILIZACION': 600,
        'PRECIO_VENTA': 3.50,
        'icono': '🍫'
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 280},
        'FOSFORO': {'min': 60, 'max': 100},
        'POTASIO': {'min': 300, 'max': 400},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.38,
        'NDVI_OPTIMO': 0.85,
        'NDRE_OPTIMO': 0.50,
        'RENDIMIENTO_OPTIMO': 40000,
        'COSTO_FERTILIZACION': 800,
        'PRECIO_VENTA': 0.30,
        'icono': '🍌'
    },
    'PALMA ACEITERA': {
        'NITROGENO': {'min': 100, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 200, 'max': 350},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.32,
        'NDVI_OPTIMO': 0.78,
        'NDRE_OPTIMO': 0.42,
        'RENDIMIENTO_OPTIMO': 20000,
        'COSTO_FERTILIZACION': 750,
        'PRECIO_VENTA': 0.18,
        'icono': '🌴'
    },
    'VID': {
        'NITROGENO': {'min': 60, 'max': 120},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 100, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 2.5,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.70,
        'NDRE_OPTIMO': 0.35,
        'RENDIMIENTO_OPTIMO': 15000,
        'COSTO_FERTILIZACION': 450,
        'PRECIO_VENTA': 0.80,
        'icono': '🍇'
    },
    'OLIVO': {
        'NITROGENO': {'min': 80, 'max': 150},
        'FOSFORO': {'min': 30, 'max': 60},
        'POTASIO': {'min': 120, 'max': 220},
        'MATERIA_ORGANICA_OPTIMA': 2.0,
        'HUMEDAD_OPTIMA': 0.20,
        'NDVI_OPTIMO': 0.65,
        'NDRE_OPTIMO': 0.30,
        'RENDIMIENTO_OPTIMO': 10000,
        'COSTO_FERTILIZACION': 400,
        'PRECIO_VENTA': 0.90,
        'icono': '🫒'
    }
}

# ===== FUNCIONES AUXILIARES MEJORADAS =====
def procesar_archivo_carga(uploaded_file):
    """Procesa archivos KML, KMZ, GeoJSON, Shapefile, etc."""
    try:
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as tmpdir:
            # Guardar el archivo subido
            file_path = os.path.join(tmpdir, uploaded_file.name)
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Determinar tipo de archivo por extensión
            file_ext = uploaded_file.name.lower().split('.')[-1]
            
            if file_ext in ['kml', 'kmz']:
                # Leer KML/KMZ
                gdf = gpd.read_file(file_path, driver='KML')
            elif file_ext == 'geojson':
                # Leer GeoJSON
                gdf = gpd.read_file(file_path)
            elif file_ext == 'shp':
                # Shapefile - ya es .shp
                gdf = gpd.read_file(file_path)
            elif file_ext == 'zip':
                # Shapefile comprimido
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                # Buscar archivo .shp en el directorio extraído
                shp_file = None
                for file in os.listdir(tmpdir):
                    if file.endswith('.shp'):
                        shp_file = os.path.join(tmpdir, file)
                        break
                if shp_file:
                    gdf = gpd.read_file(shp_file)
                else:
                    st.error("No se encontró archivo .shp en el ZIP")
                    return None
            else:
                st.error(f"Formato de archivo no soportado: {file_ext}")
                return None
            
            # Verificar que el GeoDataFrame no esté vacío
            if gdf.empty:
                st.error("El archivo no contiene geometrías válidas")
                return None
            
            # Obtener la primera geometría
            geometry = gdf.geometry.iloc[0]
            
            # Convertir a Polygon si es MultiPolygon
            if geometry.geom_type == 'MultiPolygon':
                # Tomar el polígono más grande
                polygons = list(geometry.geoms)
                polygons.sort(key=lambda p: p.area, reverse=True)
                geometry = polygons[0]
            
            # Verificar que sea un polígono válido
            if geometry.geom_type not in ['Polygon', 'MultiPolygon']:
                st.error(f"Tipo de geometría no soportado: {geometry.geom_type}. Se requiere Polygon o MultiPolygon.")
                return None
            
            # Reproject a WGS84 si es necesario
            if gdf.crs and gdf.crs.to_string() != 'EPSG:4326':
                gdf = gpd.to_crs('EPSG:4326')
                geometry = gdf.geometry.iloc[0]
            
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            st.info(f"Tipo de geometría: {geometry.geom_type}")
            
            return geometry
    
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {str(e)}")
        return None

def crear_mapa_interactivo(poligono=None, titulo="Mapa de la Parcela", zoom_start=14):
    """Crea un mapa interactivo con Esri World Imagery como base"""
    if poligono is not None:
        centroid = poligono.centroid
        lat, lon = centroid.y, centroid.x
    else:
        lat, lon = -34.6037, -58.3816  # Buenos Aires por defecto
    
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
        prefer_canvas=True
    )
    
    # Agregar Esri World Imagery
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri World Imagery',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Agregar capa de calles
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Límites y Nombres',
        overlay=True,
        control=True
    ).add_to(m)
    
    # Dibujar polígono si existe
    if poligono is not None:
        geojson = gpd.GeoSeries([poligono]).__geo_interface__
        folium.GeoJson(
            geojson,
            style_function=lambda x: {
                'fillColor': '#3e7d4c',
                'color': 'white',
                'weight': 2,
                'fillOpacity': 0.4,
            },
            name='Parcela'
        ).add_to(m)
    
    # Agregar control de capas
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Agregar herramientas de dibujo
    draw = Draw(
        export=True,
        position='topleft',
        draw_options={
            'polygon': True,
            'rectangle': True,
            'circle': False,
            'polyline': False,
            'marker': False
        }
    )
    draw.add_to(m)
    
    return m

def calcular_indices_satelitales_gee(tipo_satelite, poligono, fecha_inicio, fecha_fin):
    """Calcula índices satelitales desde Google Earth Engine"""
    if not st.session_state.gee_authenticated or poligono is None:
        return None
    
    try:
        # Convertir polígono a GeoJSON para GEE
        geojson = gpd.GeoSeries([poligono]).__geo_interface__['features'][0]['geometry']
        ee_poligono = ee.Geometry(geojson)
        
        # Formatear fechas
        fecha_inicio_ee = ee.Date(fecha_inicio.strftime('%Y-%m-%d'))
        fecha_fin_ee = ee.Date(fecha_fin.strftime('%Y-%m-%d'))
        
        if 'SENTINEL-2' in tipo_satelite:
            # Colección Sentinel-2 Surface Reflectance
            collection = ee.ImageCollection('COPERNICUS/S2_SR') \
                .filterBounds(ee_poligono) \
                .filterDate(fecha_inicio_ee, fecha_fin_ee) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                .sort('CLOUDY_PIXEL_PERCENTAGE')
            
            if collection.size().getInfo() == 0:
                st.warning("⚠️ No se encontraron imágenes Sentinel-2 sin nubes para el período seleccionado")
                return None
            
            imagen = collection.first()
            fecha = imagen.date().format('YYYY-MM-dd').getInfo()
            
            # Calcular índices
            ndvi = imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')
            ndwi = imagen.normalizedDifference(['B8', 'B11']).rename('NDWI')
            evi = imagen.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {'NIR': imagen.select('B8'), 'RED': imagen.select('B4'), 'BLUE': imagen.select('B2')}
            ).rename('EVI')
            ndre = imagen.normalizedDifference(['B8', 'B5']).rename('NDRE')
            
            # Extraer valores medios
            reducer = ee.Reducer.mean()
            stats_ndvi = ndvi.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=10, maxPixels=1e9).getInfo()
            stats_ndwi = ndwi.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=10, maxPixels=1e9).getInfo()
            stats_evi = evi.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=10, maxPixels=1e9).getInfo()
            stats_ndre = ndre.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=10, maxPixels=1e9).getInfo()
            
            return {
                'NDVI': stats_ndvi.get('NDVI', 0),
                'NDWI': stats_ndwi.get('NDWI', 0),
                'EVI': stats_evi.get('EVI', 0),
                'NDRE': stats_ndre.get('NDRE', 0),
                'fecha': fecha,
                'fuente': f'GEE - Sentinel-2 ({fecha})',
                'resolucion': '10m'
            }
            
        elif 'LANDSAT-8' in tipo_satelite or 'LANDSAT-9' in tipo_satelite:
            # Determinar colección según satélite
            if 'LANDSAT-8' in tipo_satelite:
                collection_id = 'LANDSAT/LC08/C02/T1_L2'
            else:
                collection_id = 'LANDSAT/LC09/C02/T1_L2'
            
            collection = ee.ImageCollection(collection_id) \
                .filterBounds(ee_poligono) \
                .filterDate(fecha_inicio_ee, fecha_fin_ee) \
                .filter(ee.Filter.lt('CLOUD_COVER', 20)) \
                .sort('CLOUD_COVER')
            
            if collection.size().getInfo() == 0:
                st.warning(f"⚠️ No se encontraron imágenes {tipo_satelite} sin nubes para el período seleccionado")
                return None
            
            imagen = collection.first()
            fecha = imagen.date().format('YYYY-MM-dd').getInfo()
            
            # Escalar bandas Landsat
            def scale_landsat(img):
                optical_bands = img.select('SR_B.').multiply(0.0000275).add(-0.2)
                return img.addBands(optical_bands, None, True)
            
            imagen = scale_landsat(imagen)
            
            # Calcular NDVI
            ndvi = imagen.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
            ndwi = imagen.normalizedDifference(['SR_B5', 'SR_B6']).rename('NDWI')
            
            # Extraer valores
            reducer = ee.Reducer.mean()
            stats_ndvi = ndvi.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=30, maxPixels=1e9).getInfo()
            stats_ndwi = ndwi.reduceRegion(reducer=reducer, geometry=ee_poligono, scale=30, maxPixels=1e9).getInfo()
            
            return {
                'NDVI': stats_ndvi.get('NDVI', 0),
                'NDWI': stats_ndwi.get('NDWI', 0),
                'EVI': 0,  # No calculado para Landsat
                'NDRE': 0,
                'fecha': fecha,
                'fuente': f'GEE - {tipo_satelite} ({fecha})',
                'resolucion': '30m'
            }
    
    except Exception as e:
        st.error(f"❌ Error al obtener datos de GEE: {str(e)[:200]}")
        return None

def generar_dem_para_poligono(poligono, resolucion_m=10):
    """Genera un DEM adaptado al polígono de la parcela"""
    # Obtener los límites del polígono
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    # Expandir los límites un 20% para tener un área más grande
    expand_factor = 0.2
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    # Calcular tamaño basado en resolución
    # Convertir grados a metros aproximados (1 grado ≈ 111,000 m)
    width_deg = expanded_maxx - expanded_minx
    height_deg = expanded_maxy - expanded_miny
    
    # Calcular número de puntos basado en resolución
    width_m = width_deg * 111000  # Aproximación
    height_m = height_deg * 111000
    
    nx = int(width_m / resolucion_m)
    ny = int(height_m / resolucion_m)
    
    # Limitar tamaño máximo
    nx = min(nx, 200)
    ny = min(ny, 200)
    
    # Crear malla
    x = np.linspace(expanded_minx, expanded_maxx, nx)
    y = np.linspace(expanded_miny, expanded_maxy, ny)
    X, Y = np.meshgrid(x, y)
    
    # Generar terreno realista
    Z = np.zeros_like(X)
    
    # Base con pendiente general
    pendiente_base = np.random.uniform(1, 3)
    Z = pendiente_base * ((X - expanded_minx) / width_deg)
    
    # Agregar colinas y valles aleatorios
    np.random.seed(42)
    n_colinas = np.random.randint(3, 8)
    for _ in range(n_colinas):
        centro_x = np.random.uniform(expanded_minx, expanded_maxx)
        centro_y = np.random.uniform(expanded_miny, expanded_maxy)
        radio = np.random.uniform(width_deg * 0.1, width_deg * 0.3)
        altura = np.random.uniform(5, 20)
        
        distancia = np.sqrt((X - centro_x)**2 + (Y - centro_y)**2)
        Z += altura * np.exp(-(distancia**2) / (2 * radio**2))
    
    # Agregar valles
    n_valles = np.random.randint(2, 6)
    for _ in range(n_valles):
        centro_x = np.random.uniform(expanded_minx, expanded_maxx)
        centro_y = np.random.uniform(expanded_miny, expanded_maxy)
        radio = np.random.uniform(width_deg * 0.15, width_deg * 0.35)
        profundidad = np.random.uniform(3, 12)
        
        distancia = np.sqrt((X - centro_x)**2 + (Y - centro_y)**2)
        Z -= profundidad * np.exp(-(distancia**2) / (2 * radio**2))
    
    # Ruido topográfico
    ruido = np.random.randn(ny, nx) * 2
    Z += ruido
    
    # Normalizar para que esté entre 0 y 100 metros
    Z = (Z - Z.min()) / (Z.max() - Z.min()) * 100
    
    return X, Y, Z

def calcular_pendiente_mejorado(dem):
    """Calcula pendiente en porcentaje"""
    dy, dx = np.gradient(dem)
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    return pendiente

def dividir_parcela_en_zonas(poligono, n_zonas=16):
    """Divide la parcela en zonas para análisis detallado"""
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    # Calcular número de filas y columnas
    n_cols = math.ceil(math.sqrt(n_zonas))
    n_rows = math.ceil(n_zonas / n_cols)
    
    width = (maxx - minx) / n_cols
    height = (maxy - miny) / n_rows
    
    zonas = []
    for i in range(n_rows):
        for j in range(n_cols):
            if len(zonas) >= n_zonas:
                break
                
            cell_minx = minx + (j * width)
            cell_maxx = minx + ((j + 1) * width)
            cell_miny = miny + (i * height)
            cell_maxy = miny + ((i + 1) * height)
            
            cell_poly = Polygon([
                (cell_minx, cell_miny),
                (cell_maxx, cell_miny),
                (cell_maxx, cell_maxy),
                (cell_minx, cell_maxy)
            ])
            
            intersection = poligono.intersection(cell_poly)
            if not intersection.is_empty and intersection.area > 0:
                zonas.append({
                    'id': len(zonas) + 1,
                    'geometry': intersection,
                    'centroid': intersection.centroid
                })
    
    return zonas

def analizar_fertilidad_zonas(zonas, indices_satelitales, cultivo):
    """Analiza fertilidad para cada zona"""
    params = PARAMETROS_CULTIVOS[cultivo]
    resultados = []
    
    for zona in zonas:
        # Generar datos sintéticos basados en posición
        centroid = zona['centroid']
        x_norm = (centroid.x - zona['geometry'].bounds[0]) / (zona['geometry'].bounds[2] - zona['geometry'].bounds[0])
        y_norm = (centroid.y - zona['geometry'].bounds[1]) / (zona['geometry'].bounds[3] - zona['geometry'].bounds[1])
        
        # Factor de variabilidad espacial
        factor_espacial = 0.5 + 0.5 * math.sin(x_norm * math.pi) * math.cos(y_norm * math.pi)
        
        # Materia orgánica
        mo_base = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
        materia_organica = mo_base + (factor_espacial * params['MATERIA_ORGANICA_OPTIMA'] * 0.3)
        materia_organica += np.random.normal(0, 0.2)
        materia_organica = max(1.0, min(8.0, materia_organica))
        
        # Humedad
        humedad_base = params['HUMEDAD_OPTIMA'] * 0.8
        humedad = humedad_base + (factor_espacial * params['HUMEDAD_OPTIMA'] * 0.2)
        humedad += np.random.normal(0, 0.05)
        humedad = max(0.1, min(0.8, humedad))
        
        # Índices satelitales ajustados por posición
        if indices_satelitales:
            ndvi = indices_satelitales.get('NDVI', 0.6) * (0.9 + 0.2 * factor_espacial)
            ndre = indices_satelitales.get('NDRE', 0.3) * (0.9 + 0.2 * factor_espacial)
            evi = indices_satelitales.get('EVI', 0.5) * (0.9 + 0.2 * factor_espacial)
        else:
            ndvi = params['NDVI_OPTIMO'] * (0.8 + 0.4 * factor_espacial)
            ndre = params['NDRE_OPTIMO'] * (0.8 + 0.4 * factor_espacial)
            evi = 0.5 * (0.8 + 0.4 * factor_espacial)
        
        # Calcular índice de fertilidad compuesto
        indice_fertilidad = (ndvi * 0.4 + ndre * 0.3 + (materia_organica / 8) * 0.2 + humedad * 0.1)
        
        resultados.append({
            'id_zona': zona['id'],
            'centroid': centroid,
            'materia_organica': round(materia_organica, 2),
            'humedad': round(humedad, 3),
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'evi': round(evi, 3),
            'indice_fertilidad': round(indice_fertilidad, 3)
        })
    
    return resultados

def calcular_recomendaciones_npk_mejorado(indices_fertilidad, cultivo, textura_suelo):
    """Calcula recomendaciones de NPK mejoradas"""
    params = PARAMETROS_CULTIVOS[cultivo]
    
    # Factores de ajuste
    factores_textura = {
        'arenosa': {'N': 1.2, 'P': 1.1, 'K': 1.3},
        'franco-arenosa': {'N': 1.1, 'P': 1.0, 'K': 1.1},
        'franca': {'N': 1.0, 'P': 1.0, 'K': 1.0},
        'franco-arcillosa': {'N': 0.9, 'P': 0.9, 'K': 0.9},
        'arcillosa': {'N': 0.8, 'P': 0.85, 'K': 0.85}
    }
    
    factor_textura = factores_textura.get(textura_suelo, factores_textura['franca'])
    
    recomendaciones = []
    for idx in indices_fertilidad:
        # Ajuste basado en fertilidad (menor fertilidad = mayor recomendación)
        factor_fertilidad = 1.0 - idx['indice_fertilidad']
        
        # Cálculo de recomendaciones
        n_base = params['NITROGENO']['min'] + factor_fertilidad * (params['NITROGENO']['max'] - params['NITROGENO']['min'])
        p_base = params['FOSFORO']['min'] + factor_fertilidad * (params['FOSFORO']['max'] - params['FOSFORO']['min'])
        k_base = params['POTASIO']['min'] + factor_fertilidad * (params['POTASIO']['max'] - params['POTASIO']['min'])
        
        # Aplicar ajuste por textura
        n_ajustado = n_base * factor_textura['N']
        p_ajustado = p_base * factor_textura['P']
        k_ajustado = k_base * factor_textura['K']
        
        # Variación aleatoria para simular diferencias entre zonas
        variacion = np.random.uniform(0.9, 1.1)
        
        recomendaciones.append({
            'N': round(n_ajustado * variacion, 1),
            'P': round(p_ajustado * variacion, 1),
            'K': round(k_ajustado * variacion, 1)
        })
    
    return recomendaciones

def calcular_proyecciones_cosecha(indices_fertilidad, recomendaciones_npk, cultivo):
    """Calcula proyecciones de cosecha"""
    params = PARAMETROS_CULTIVOS[cultivo]
    proyecciones = []
    
    for idx, rec in zip(indices_fertilidad, recomendaciones_npk):
        # Rendimiento base basado en fertilidad
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * idx['indice_fertilidad']
        
        # Efecto de la fertilización (asumir que optimiza rendimiento)
        efecto_fertilizacion = 1.0 + (rec['N'] + rec['P'] + rec['K']) / (params['NITROGENO']['max'] + params['FOSFORO']['max'] + params['POTASIO']['max']) * 0.5
        
        rendimiento_con_fert = rendimiento_base * efecto_fertilizacion
        incremento = ((rendimiento_con_fert - rendimiento_base) / rendimiento_base) * 100 if rendimiento_base > 0 else 0
        
        proyecciones.append({
            'rendimiento_base': round(rendimiento_base, 0),
            'rendimiento_fertilizado': round(rendimiento_con_fert, 0),
            'incremento': round(incremento, 1)
        })
    
    return proyecciones

def crear_mapa_calor_expandido(zonas, valores, titulo, cmap, poligono, unidad=''):
    """Crea mapa de calor expandido más allá del polígono"""
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Obtener límites del polígono
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    # Expandir los límites un 30% para el área de visualización
    expand_factor = 0.3
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    # Preparar datos para mapa de calor
    centroides_x = [zona['centroid'].x for zona in zonas]
    centroides_y = [zona['centroid'].y for zona in zonas]
    
    # Crear grilla para interpolación
    grid_x, grid_y = np.mgrid[expanded_minx:expanded_maxx:100j, expanded_miny:expanded_maxy:100j]
    
    # Interpolación lineal para suavizar
    from scipy.interpolate import griddata
    grid_z = griddata((centroides_x, centroides_y), valores, (grid_x, grid_y), method='linear', fill_value=np.nanmean(valores))
    
    # Mapa de calor con interpolación suavizada
    im = ax.imshow(grid_z.T, extent=[expanded_minx, expanded_maxx, expanded_miny, expanded_maxy], 
                   origin='lower', cmap=cmap, alpha=0.8, aspect='auto')
    
    # Dibujar el polígono principal
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.fill(x_coords, y_coords, color='white', alpha=0.2, edgecolor='black', linewidth=2, linestyle='--')
    ax.plot(x_coords, y_coords, 'k-', linewidth=2)
    
    # Dibujar contornos de zonas
    for zona in zonas:
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.7)
    
    # Añadir puntos de centroides
    scatter = ax.scatter(centroides_x, centroides_y, c=valores, cmap=cmap, 
                         s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9)
    
    # Etiquetas
    ax.set_title(titulo, fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitud', fontsize=14)
    ax.set_ylabel('Latitud', fontsize=14)
    ax.grid(True, alpha=0.2, linestyle='--')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label(unidad if unidad else 'Valor', fontsize=12)
    
    # Añadir anotaciones de valores en cada zona
    for zona, valor in zip(zonas, valores):
        ax.annotate(f"{valor:.2f}" if valor < 1 else f"{valor:.0f}", 
                   xy=(zona['centroid'].x, zona['centroid'].y), 
                   xytext=(0, 8), textcoords='offset points',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='black'))
    
    # Añadir escala
    ax.text(0.02, 0.02, f"Área expandida: {expand_factor*100:.0f}%", transform=ax.transAxes,
           fontsize=10, bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig

def crear_mapa_calor_fertilidad(zonas, indices_fertilidad, poligono):
    """Crea mapa de calor de fertilidad expandido"""
    fertilidades = [idx['indice_fertilidad'] for idx in indices_fertilidad]
    return crear_mapa_calor_expandido(zonas, fertilidades, 
                                     'Mapa de Calor - Índice de Fertilidad', 
                                     plt.cm.YlOrRd, poligono, 'Índice de Fertilidad')

def crear_mapa_calor_npk(zonas, recomendaciones_npk, nutriente='N', poligono=None):
    """Crea mapa de calor de NPK expandido"""
    # Preparar datos según nutriente
    if nutriente == 'N':
        valores = [rec['N'] for rec in recomendaciones_npk]
        titulo = 'Nitrógeno (N)'
        cmap = plt.cm.Greens
        unidad = 'kg/ha'
    elif nutriente == 'P':
        valores = [rec['P'] for rec in recomendaciones_npk]
        titulo = 'Fósforo (P)'
        cmap = plt.cm.Blues
        unidad = 'kg/ha'
    else:
        valores = [rec['K'] for rec in recomendaciones_npk]
        titulo = 'Potasio (K)'
        cmap = plt.cm.Oranges
        unidad = 'kg/ha'
    
    return crear_mapa_calor_expandido(zonas, valores, 
                                     f'Mapa de Calor - {titulo} ({unidad})', 
                                     cmap, poligono, unidad)

def crear_mapa_calor_ndvi(zonas, indices_fertilidad, poligono):
    """Crea mapa de calor de NDVI expandido"""
    ndvi_valores = [idx['ndvi'] for idx in indices_fertilidad]
    
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Obtener límites del polígono
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    # Expandir los límites un 30% para el área de visualización
    expand_factor = 0.3
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    # Preparar datos para mapa de calor
    centroides_x = [zona['centroid'].x for zona in zonas]
    centroides_y = [zona['centroid'].y for zona in zonas]
    
    # Crear grilla para interpolación
    grid_x, grid_y = np.mgrid[expanded_minx:expanded_maxx:100j, expanded_miny:expanded_maxy:100j]
    
    # Interpolación lineal para suavizar
    from scipy.interpolate import griddata
    grid_z = griddata((centroides_x, centroides_y), ndvi_valores, (grid_x, grid_y), method='linear', fill_value=np.nanmean(ndvi_valores))
    
    # Mapa de calor con colores específicos para NDVI
    cmap = plt.cm.RdYlGn  # Rojo-Amarillo-Verde para NDVI
    im = ax.imshow(grid_z.T, extent=[expanded_minx, expanded_maxx, expanded_miny, expanded_maxy], 
                   origin='lower', cmap=cmap, alpha=0.8, aspect='auto', vmin=0, vmax=1)
    
    # Dibujar el polígono principal
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.fill(x_coords, y_coords, color='white', alpha=0.2, edgecolor='black', linewidth=2, linestyle='--')
    ax.plot(x_coords, y_coords, 'k-', linewidth=2)
    
    # Dibujar contornos de zonas
    for zona in zonas:
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.7)
    
    # Añadir puntos de centroides
    scatter = ax.scatter(centroides_x, centroides_y, c=ndvi_valores, cmap=cmap, 
                         s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9, vmin=0, vmax=1)
    
    # Etiquetas
    ax.set_title('Mapa de Calor - NDVI (Índice de Vegetación de Diferencia Normalizada)', 
                fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitud', fontsize=14)
    ax.set_ylabel('Latitud', fontsize=14)
    ax.grid(True, alpha=0.2, linestyle='--')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('NDVI', fontsize=12)
    
    # Añadir leyenda de colores
    ax.text(0.02, 0.98, 'Interpretación NDVI:\n0.0-0.2: Suelo desnudo\n0.2-0.4: Vegetación escasa\n0.4-0.6: Vegetación moderada\n0.6-0.8: Vegetación densa\n0.8-1.0: Vegetación muy densa',
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
    
    # Añadir anotaciones de valores en cada zona
    for zona, valor in zip(zonas, ndvi_valores):
        ax.annotate(f"{valor:.3f}", 
                   xy=(zona['centroid'].x, zona['centroid'].y), 
                   xytext=(0, 8), textcoords='offset points',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='black'))
    
    plt.tight_layout()
    return fig

def crear_mapa_calor_rendimiento(zonas, proyecciones, tipo='base', poligono=None):
    """Crea mapa de calor de rendimiento expandido"""
    # Preparar datos según tipo
    if tipo == 'base':
        valores = [proy['rendimiento_base'] for proy in proyecciones]
        titulo = 'Rendimiento Sin Fertilización'
        cmap = plt.cm.RdYlGn_r  # Rojo-Amarillo-Verde (invertido)
    else:
        valores = [proy['rendimiento_fertilizado'] for proy in proyecciones]
        titulo = 'Rendimiento Con Fertilización'
        cmap = plt.cm.RdYlGn  # Verde-Amarillo-Rojo
    
    return crear_mapa_calor_expandido(zonas, valores, 
                                     f'Mapa de Calor - {titulo}', 
                                     cmap, poligono, 'kg/ha')

def crear_mapa_calor_diferencia(zonas, proyecciones, poligono):
    """Crea mapa de calor de diferencia de rendimiento expandido"""
    # Calcular diferencias
    diferencias = []
    porcentajes = []
    
    for proy in proyecciones:
        diferencia = proy['rendimiento_fertilizado'] - proy['rendimiento_base']
        porcentaje = proy['incremento']
        diferencias.append(diferencia)
        porcentajes.append(porcentaje)
    
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Obtener límites del polígono
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    # Expandir los límites un 30% para el área de visualización
    expand_factor = 0.3
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    # Preparar datos para mapa de calor
    centroides_x = [zona['centroid'].x for zona in zonas]
    centroides_y = [zona['centroid'].y for zona in zonas]
    
    # Crear grilla para interpolación
    grid_x, grid_y = np.mgrid[expanded_minx:expanded_maxx:100j, expanded_miny:expanded_maxy:100j]
    
    # Interpolación lineal para suavizar
    from scipy.interpolate import griddata
    grid_z = griddata((centroides_x, centroides_y), diferencias, (grid_x, grid_y), method='linear', fill_value=np.nanmean(diferencias))
    
    # Mapa de calor con colores divergentes
    cmap = plt.cm.RdBu  # Rojo-Azul (divergente)
    max_diff = max(abs(min(diferencias)), abs(max(diferencias)))
    im = ax.imshow(grid_z.T, extent=[expanded_minx, expanded_maxx, expanded_miny, expanded_maxy], 
                   origin='lower', cmap=cmap, alpha=0.8, aspect='auto', 
                   vmin=-max_diff, vmax=max_diff)
    
    # Dibujar el polígono principal
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.fill(x_coords, y_coords, color='white', alpha=0.2, edgecolor='black', linewidth=2, linestyle='--')
    ax.plot(x_coords, y_coords, 'k-', linewidth=2)
    
    # Dibujar contornos de zonas
    for zona in zonas:
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.7)
    
    # Añadir puntos de centroides
    scatter = ax.scatter(centroides_x, centroides_y, c=diferencias, cmap=cmap, 
                         s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9, 
                         vmin=-max_diff, vmax=max_diff)
    
    # Etiquetas
    ax.set_title('Mapa de Calor - Incremento por Fertilización', fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitud', fontsize=14)
    ax.set_ylabel('Latitud', fontsize=14)
    ax.grid(True, alpha=0.2, linestyle='--')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('Incremento (kg/ha)', fontsize=12)
    
    # Añadir anotaciones
    for i, (zona, proy, diff, pct) in enumerate(zip(zonas, proyecciones, diferencias, porcentajes)):
        color = 'green' if diff > 0 else 'red' if diff < 0 else 'gray'
        ax.annotate(f"+{diff:.0f}\n(+{pct:.0f}%)" if diff >= 0 else f"{diff:.0f}\n({pct:.0f}%)", 
                   xy=(zona['centroid'].x, zona['centroid'].y), 
                   xytext=(0, 8), textcoords='offset points',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8, edgecolor='black'))
    
    plt.tight_layout()
    return fig

def crear_dem_y_curvas(poligono, resolucion_m=10, intervalo_curvas=5):
    """Crea DEM y curvas de nivel consistentes"""
    # Generar DEM para el polígono
    X, Y, Z = generar_dem_para_poligono(poligono, resolucion_m)
    
    # Calcular pendientes
    pendientes = calcular_pendiente_mejorado(Z)
    
    # Crear figura con DEM y curvas
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    
    # Panel 1: DEM
    im1 = ax1.imshow(Z, extent=[X.min(), X.max(), Y.min(), Y.max()], 
                     cmap='terrain', aspect='auto', origin='lower')
    ax1.set_title('Modelo Digital de Elevaciones', fontsize=16, fontweight='bold')
    ax1.set_xlabel('Longitud', fontsize=12)
    ax1.set_ylabel('Latitud', fontsize=12)
    
    # Dibujar polígono sobre DEM
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    poly_x = [c[0] for c in coords]
    poly_y = [c[1] for c in coords]
    ax1.fill(poly_x, poly_y, color='white', alpha=0.3, edgecolor='black', linewidth=2)
    ax1.plot(poly_x, poly_y, 'k-', linewidth=2)
    
    plt.colorbar(im1, ax=ax1, label='Elevación (m)', shrink=0.8)
    
    # Panel 2: Curvas de nivel
    # Determinar niveles de curvas
    z_min, z_max = Z.min(), Z.max()
    niveles = np.arange(int(z_min // intervalo_curvas) * intervalo_curvas, 
                       int(z_max // intervalo_curvas + 2) * intervalo_curvas, 
                       intervalo_curvas)
    
    contour = ax2.contour(X, Y, Z, levels=niveles, colors='black', linewidths=0.8)
    ax2.clabel(contour, inline=True, fontsize=8, fmt='%1.0f m')
    
    # Fill contour
    ax2.contourf(X, Y, Z, levels=50, cmap='terrain', alpha=0.7)
    
    # Dibujar polígono sobre curvas
    ax2.fill(poly_x, poly_y, color='white', alpha=0.3, edgecolor='black', linewidth=2)
    ax2.plot(poly_x, poly_y, 'k-', linewidth=2)
    
    ax2.set_title(f'Curvas de Nivel (Intervalo: {intervalo_curvas}m)', fontsize=16, fontweight='bold')
    ax2.set_xlabel('Longitud', fontsize=12)
    ax2.set_ylabel('Latitud', fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    return fig, {'X': X, 'Y': Y, 'Z': Z, 'pendientes': pendientes}

def guardar_figura_como_png(fig, nombre):
    """Guarda una figura matplotlib como PNG en bytes"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    return buf

def generar_reporte_docx(resultados):
    """Genera un reporte completo en formato DOCX"""
    if not DOCX_AVAILABLE:
        st.error("python-docx no está instalado. Instala con: pip install python-docx")
        return None
    
    try:
        # Crear documento
        doc = Document()
        
        # Título principal
        title = doc.add_heading('REPORTE DE ANÁLISIS AGRÍCOLA', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Fecha
        doc.add_paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        doc.add_paragraph("")
        
        # Información general
        doc.add_heading('1. INFORMACIÓN GENERAL', level=1)
        
        info_table = doc.add_table(rows=5, cols=2)
        info_table.style = 'Light Grid'
        
        info_table.cell(0, 0).text = "Cultivo"
        info_table.cell(0, 1).text = resultados['cultivo']
        
        info_table.cell(1, 0).text = "Área Total"
        info_table.cell(1, 1).text = f"{resultados['area_total']:.2f} ha"
        
        info_table.cell(2, 0).text = "Zonas de Manejo"
        info_table.cell(2, 1).text = str(len(resultados['zonas']))
        
        info_table.cell(3, 0).text = "Textura del Suelo"
        info_table.cell(3, 1).text = resultados['textura_suelo']
        
        info_table.cell(4, 0).text = "Precipitación Anual"
        info_table.cell(4, 1).text = f"{resultados['precipitacion']} mm"
        
        doc.add_paragraph("")
        
        # Resultados de fertilidad
        doc.add_heading('2. ANÁLISIS DE FERTILIDAD', level=1)
        
        fert_table = doc.add_table(rows=len(resultados['indices_fertilidad'])+1, cols=6)
        fert_table.style = 'Light Grid'
        
        # Encabezados
        headers = ['Zona', 'Materia Orgánica (%)', 'Humedad', 'NDVI', 'NDRE', 'Índice Fertilidad']
        for i, header in enumerate(headers):
            fert_table.cell(0, i).text = header
        
        # Datos
        for i, idx in enumerate(resultados['indices_fertilidad']):
            fert_table.cell(i+1, 0).text = f"Z{idx['id_zona']}"
            fert_table.cell(i+1, 1).text = f"{idx['materia_organica']:.2f}"
            fert_table.cell(i+1, 2).text = f"{idx['humedad']:.3f}"
            fert_table.cell(i+1, 3).text = f"{idx['ndvi']:.3f}"
            fert_table.cell(i+1, 4).text = f"{idx['ndre']:.3f}"
            fert_table.cell(i+1, 5).text = f"{idx['indice_fertilidad']:.3f}"
        
        doc.add_paragraph("")
        
        # Recomendaciones de fertilización
        doc.add_heading('3. RECOMENDACIONES DE FERTILIZACIÓN', level=1)
        
        npk_table = doc.add_table(rows=len(resultados['recomendaciones_npk'])+1, cols=4)
        npk_table.style = 'Light Grid'
        
        npk_headers = ['Zona', 'Nitrógeno (kg/ha)', 'Fósforo (kg/ha)', 'Potasio (kg/ha)']
        for i, header in enumerate(npk_headers):
            npk_table.cell(0, i).text = header
        
        for i, rec in enumerate(resultados['recomendaciones_npk']):
            npk_table.cell(i+1, 0).text = f"Z{i+1}"
            npk_table.cell(i+1, 1).text = f"{rec['N']:.1f}"
            npk_table.cell(i+1, 2).text = f"{rec['P']:.1f}"
            npk_table.cell(i+1, 3).text = f"{rec['K']:.1f}"
        
        doc.add_paragraph("")
        
        # Proyecciones de cosecha
        doc.add_heading('4. PROYECCIONES DE COSECHA', level=1)
        
        proy_table = doc.add_table(rows=len(resultados['proyecciones'])+1, cols=4)
        proy_table.style = 'Light Grid'
        
        proy_headers = ['Zona', 'Sin Fertilización (kg/ha)', 'Con Fertilización (kg/ha)', 'Incremento (%)']
        for i, header in enumerate(proy_headers):
            proy_table.cell(0, i).text = header
        
        for i, proy in enumerate(resultados['proyecciones']):
            proy_table.cell(i+1, 0).text = f"Z{i+1}"
            proy_table.cell(i+1, 1).text = f"{proy['rendimiento_base']:.0f}"
            proy_table.cell(i+1, 2).text = f"{proy['rendimiento_fertilizado']:.0f}"
            proy_table.cell(i+1, 3).text = f"{proy['incremento']:.1f}"
        
        doc.add_paragraph("")
        
        # Análisis económico
        doc.add_heading('5. ANÁLISIS ECONÓMICO', level=1)
        
        # Calcular totales
        total_n = sum([rec['N'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        total_p = sum([rec['P'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        total_k = sum([rec['K'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        
        precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
        rend_total_base = sum([proy['rendimiento_base'] for proy in resultados['proyecciones']]) * resultados['area_total'] / len(resultados['proyecciones'])
        rend_total_fert = sum([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]) * resultados['area_total'] / len(resultados['proyecciones'])
        
        ingreso_base = rend_total_base * precio
        ingreso_fert = rend_total_fert * precio
        
        costo_total = (total_n * 1.2 + total_p * 2.5 + total_k * 1.8)
        ingreso_adicional = ingreso_fert - ingreso_base
        beneficio_neto = ingreso_adicional - costo_total
        roi = (beneficio_neto / costo_total * 100) if costo_total > 0 else 0
        
        eco_table = doc.add_table(rows=6, cols=2)
        eco_table.style = 'Light Grid'
        
        eco_data = [
            ("Ingreso sin fertilización", f"${ingreso_base:,.0f} USD"),
            ("Ingreso con fertilización", f"${ingreso_fert:,.0f} USD"),
            ("Ingreso adicional", f"${ingreso_adicional:,.0f} USD"),
            ("Costo fertilización", f"${costo_total:,.0f} USD"),
            ("Beneficio neto", f"${beneficio_neto:,.0f} USD"),
            ("ROI estimado", f"{roi:.1f}%")
        ]
        
        for i, (label, value) in enumerate(eco_data):
            eco_table.cell(i, 0).text = label
            eco_table.cell(i, 1).text = value
        
        # Recomendaciones finales
        doc.add_heading('6. RECOMENDACIONES FINALES', level=1)
        
        recomendaciones = [
            "Aplicar fertilización diferenciada según zonas de manejo",
            f"Priorizar zonas con índice de fertilidad menor a 0.5 ({len([idx for idx in resultados['indices_fertilidad'] if idx['indice_fertilidad'] < 0.5])} zonas)",
            "Monitorear humedad del suelo durante períodos críticos",
            "Realizar análisis de suelo para validar recomendaciones",
            "Considerar implementación de riego de precisión si la variabilidad de humedad es alta"
        ]
        
        for rec in recomendaciones:
            doc.add_paragraph(f"• {rec}", style='List Bullet')
        
        # Guardar en bytes
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
    
    except Exception as e:
        st.error(f"Error generando reporte DOCX: {str(e)}")
        return None

def exportar_tablas_xlsx(resultados):
    """Exporta todas las tablas a un archivo XLSX"""
    if not XLSX_AVAILABLE:
        st.error("xlsxwriter no está instalado. Instala con: pip install xlsxwriter")
        return None
    
    try:
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Hoja 1: Información general
            info_data = {
                'Parámetro': ['Cultivo', 'Área Total (ha)', 'Zonas de Manejo', 
                            'Textura del Suelo', 'Precipitación (mm)', 
                            'Fecha Análisis', 'Fuente de Datos'],
                'Valor': [
                    resultados['cultivo'],
                    f"{resultados['area_total']:.2f}",
                    len(resultados['zonas']),
                    resultados['textura_suelo'],
                    resultados['precipitacion'],
                    datetime.now().strftime('%d/%m/%Y %H:%M'),
                    resultados['indices_satelitales']['fuente']
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, sheet_name='Información General', index=False)
            
            # Hoja 2: Fertilidad
            fert_data = {
                'Zona': [f"Z{idx['id_zona']}" for idx in resultados['indices_fertilidad']],
                'Materia_Organica_%': [idx['materia_organica'] for idx in resultados['indices_fertilidad']],
                'Humedad': [idx['humedad'] for idx in resultados['indices_fertilidad']],
                'NDVI': [idx['ndvi'] for idx in resultados['indices_fertilidad']],
                'NDRE': [idx['ndre'] for idx in resultados['indices_fertilidad']],
                'EVI': [idx['evi'] for idx in resultados['indices_fertilidad']],
                'Indice_Fertilidad': [idx['indice_fertilidad'] for idx in resultados['indices_fertilidad']]
            }
            fert_df = pd.DataFrame(fert_data)
            fert_df.to_excel(writer, sheet_name='Fertilidad', index=False)
            
            # Hoja 3: Recomendaciones NPK
            npk_data = {
                'Zona': [f"Z{i+1}" for i in range(len(resultados['recomendaciones_npk']))],
                'Nitrogeno_kg_ha': [rec['N'] for rec in resultados['recomendaciones_npk']],
                'Fosforo_kg_ha': [rec['P'] for rec in resultados['recomendaciones_npk']],
                'Potasio_kg_ha': [rec['K'] for rec in resultados['recomendaciones_npk']]
            }
            npk_df = pd.DataFrame(npk_data)
            npk_df.to_excel(writer, sheet_name='Recomendaciones_NPK', index=False)
            
            # Hoja 4: Proyecciones
            proy_data = {
                'Zona': [f"Z{i+1}" for i in range(len(resultados['proyecciones']))],
                'Rendimiento_Base_kg_ha': [proy['rendimiento_base'] for proy in resultados['proyecciones']],
                'Rendimiento_Fertilizado_kg_ha': [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']],
                'Incremento_%': [proy['incremento'] for proy in resultados['proyecciones']]
            }
            proy_df = pd.DataFrame(proy_data)
            proy_df.to_excel(writer, sheet_name='Proyecciones', index=False)
            
            # Hoja 5: Resumen Económico
            # Calcular valores económicos
            total_n = sum([rec['N'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
            total_p = sum([rec['P'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
            total_k = sum([rec['K'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
            
            precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
            rend_total_base = sum([proy['rendimiento_base'] for proy in resultados['proyecciones']]) * resultados['area_total'] / len(resultados['proyecciones'])
            rend_total_fert = sum([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]) * resultados['area_total'] / len(resultados['proyecciones'])
            
            ingreso_base = rend_total_base * precio
            ingreso_fert = rend_total_fert * precio
            
            costo_total = (total_n * 1.2 + total_p * 2.5 + total_k * 1.8)
            ingreso_adicional = ingreso_fert - ingreso_base
            beneficio_neto = ingreso_adicional - costo_total
            roi = (beneficio_neto / costo_total * 100) if costo_total > 0 else 0
            
            eco_data = {
                'Concepto': [
                    'Ingreso sin fertilización',
                    'Ingreso con fertilización',
                    'Ingreso adicional',
                    'Costo fertilización',
                    'Beneficio neto',
                    'ROI (%)'
                ],
                'Valor_USD': [
                    ingreso_base,
                    ingreso_fert,
                    ingreso_adicional,
                    costo_total,
                    beneficio_neto,
                    roi
                ],
                'Comentario': [
                    'Basado en rendimiento promedio sin fertilización',
                    'Basado en rendimiento promedio con fertilización',
                    'Diferencia entre ingresos',
                    'Estimación basada en precios de mercado',
                    'Ingreso adicional menos costo de fertilización',
                    'Retorno sobre inversión en fertilización'
                ]
            }
            eco_df = pd.DataFrame(eco_data)
            eco_df.to_excel(writer, sheet_name='Análisis_Económico', index=False)
            
            # Ajustar anchos de columnas
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                worksheet.set_column('A:Z', 20)
        
        buffer.seek(0)
        return buffer
    
    except Exception as e:
        st.error(f"Error exportando a XLSX: {str(e)}")
        return None

def descargar_todas_visualizaciones(resultados, poligono):
    """Crea un archivo ZIP con todas las visualizaciones"""
    if 'resultados_analisis' not in st.session_state:
        return None
    
    try:
        # Crear archivo ZIP en memoria
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Mapa de calor de fertilidad
            fig_fert = crear_mapa_calor_fertilidad(resultados['zonas'], resultados['indices_fertilidad'], poligono)
            fert_buffer = guardar_figura_como_png(fig_fert, 'fertilidad')
            zip_file.writestr('01_Mapa_Calor_Fertilidad.png', fert_buffer.getvalue())
            
            # 2. Mapa de calor de NDVI
            fig_ndvi = crear_mapa_calor_ndvi(resultados['zonas'], resultados['indices_fertilidad'], poligono)
            ndvi_buffer = guardar_figura_como_png(fig_ndvi, 'ndvi')
            zip_file.writestr('02_Mapa_Calor_NDVI.png', ndvi_buffer.getvalue())
            
            # 3. Mapas de calor NPK
            for nutriente, nombre in [('N', 'Nitrogeno'), ('P', 'Fosforo'), ('K', 'Potasio')]:
                fig_npk = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], nutriente, poligono)
                npk_buffer = guardar_figura_como_png(fig_npk, f'npk_{nutriente}')
                zip_file.writestr(f'03_Mapa_Calor_{nombre}.png', npk_buffer.getvalue())
            
            # 4. Mapas de calor de rendimiento
            fig_rend_base = crear_mapa_calor_rendimiento(resultados['zonas'], resultados['proyecciones'], 'base', poligono)
            rend_base_buffer = guardar_figura_como_png(fig_rend_base, 'rendimiento_base')
            zip_file.writestr('04_Mapa_Calor_Rendimiento_Sin_Fertilizacion.png', rend_base_buffer.getvalue())
            
            fig_rend_fert = crear_mapa_calor_rendimiento(resultados['zonas'], resultados['proyecciones'], 'fert', poligono)
            rend_fert_buffer = guardar_figura_como_png(fig_rend_fert, 'rendimiento_fert')
            zip_file.writestr('05_Mapa_Calor_Rendimiento_Con_Fertilizacion.png', rend_fert_buffer.getvalue())
            
            # 5. Mapa de calor de diferencia
            fig_diff = crear_mapa_calor_diferencia(resultados['zonas'], resultados['proyecciones'], poligono)
            diff_buffer = guardar_figura_como_png(fig_diff, 'diferencia')
            zip_file.writestr('06_Mapa_Calor_Incremento_Fertilizacion.png', diff_buffer.getvalue())
            
            # 6. DEM y curvas de nivel
            fig_dem, dem_data = crear_dem_y_curvas(poligono, resolucion_m=10, intervalo_curvas=5)
            dem_buffer = io.BytesIO()
            fig_dem.savefig(dem_buffer, format='png', dpi=300, bbox_inches='tight')
            dem_buffer.seek(0)
            zip_file.writestr('07_DEM_y_Curvas_Nivel.png', dem_buffer.getvalue())
            
            plt.close('all')
        
        zip_buffer.seek(0)
        return zip_buffer
    
    except Exception as e:
        st.error(f"Error creando archivo ZIP: {str(e)}")
        return None

# ===== INTERFAZ DE USUARIO MEJORADA =====

# Sidebar - Configuración completa
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURACIÓN")
    
    # Estado de GEE
    st.markdown("### 🌍 Google Earth Engine")
    if st.session_state.gee_authenticated:
        st.success(f"✅ **Autenticado**\nProyecto: {st.session_state.gee_project}")
    else:
        st.error("❌ **No autenticado**")
        st.info("Para usar imágenes reales, configura GEE en Streamlit Cloud o ejecuta localmente.")
    
    # Carga de archivos KML/KMZ/Shapefile
    st.markdown("### 📁 Cargar Parcela desde Archivo")
    
    uploaded_file = st.file_uploader(
        "Sube un archivo de parcela:",
        type=['kml', 'kmz', 'geojson', 'shp', 'zip'],
        help="Formatos soportados: KML, KMZ, GeoJSON, Shapefile (.shp o .zip con shapefile)"
    )
    
    if uploaded_file is not None:
        geometry = procesar_archivo_carga(uploaded_file)
        if geometry is not None:
            st.session_state.poligono = geometry
            st.rerun()
    
    # Selección de cultivo
    st.markdown("### 🌱 Cultivo Principal")
    cultivo_opciones = list(PARAMETROS_CULTIVOS.keys())
    cultivo_seleccionado = st.selectbox(
        "Selecciona el cultivo:",
        cultivo_opciones,
        format_func=lambda x: f"{PARAMETROS_CULTIVOS[x]['icono']} {x}"
    )
    
    # Configuración satelital
    st.markdown("### 🛰️ Configuración Satelital")
    
    # Fechas - asegurar que fecha_inicio sea anterior
    fecha_fin = st.date_input("Fecha fin", datetime.now())
    fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    
    # Validación de fechas
    if fecha_inicio >= fecha_fin:
        st.warning("⚠️ La fecha de inicio debe ser anterior a la fecha de fin")
        fecha_inicio = fecha_fin - timedelta(days=30)
    
    # Selección de satélite
    if st.session_state.gee_authenticated:
        satelite_opciones = [
            'SENTINEL-2_GEE (10m, real)',
            'LANDSAT-8_GEE (30m, real)',
            'LANDSAT-9_GEE (30m, real)',
            '---',
            'SENTINEL-2 (simulado)',
            'LANDSAT-8 (simulado)',
            'LANDSAT-9 (simulado)'
        ]
    else:
        satelite_opciones = [
            'SENTINEL-2 (simulado)',
            'LANDSAT-8 (simulado)',
            'LANDSAT-9 (simulado)'
        ]
    
    satelite_seleccionado = st.selectbox("Fuente de datos:", satelite_opciones)
    
    # Configuración de análisis
    st.markdown("### 📊 Configuración de Análisis")
    textura_suelo = st.selectbox(
        "Textura del suelo:",
        ['arenosa', 'franco-arenosa', 'franca', 'franco-arcillosa', 'arcillosa']
    )
    
    n_zonas = st.slider("Número de zonas de manejo:", 4, 64, 16)
    
    # DEM y curvas de nivel
    st.markdown("### 🏔️ Configuración Topográfica")
    resolucion_dem = st.slider("Resolución DEM (metros):", 5, 50, 10)
    intervalo_curvas = st.slider("Intervalo curvas de nivel (m):", 1, 20, 5)
    
    # Precipitación
    precipitacion = st.slider("💧 Precipitación anual (mm):", 500, 4000, 1500)
    
    # Botón para limpiar parcela (solo en sidebar)
    st.markdown("---")
    if st.button("🗑️ Limpiar Parcela", use_container_width=True):
        if 'poligono' in st.session_state:
            st.session_state.poligono = None
        if 'resultados_analisis' in st.session_state:
            del st.session_state.resultados_analisis
        st.session_state.analisis_ejecutado = False
        st.rerun()

# ===== SECCIÓN DE MAPA INTERACTIVO =====
st.markdown("## 🗺️ Mapa Interactivo de la Parcela")

# Crear mapa
mapa = crear_mapa_interactivo(st.session_state.poligono)

# Mostrar mapa y capturar dibujos
mapa_output = st_folium(
    mapa,
    width=1000,
    height=600,
    key="mapa_parcela"
)

# Actualizar polígono si se dibujó uno nuevo
if mapa_output and mapa_output.get('last_active_drawing'):
    drawing = mapa_output['last_active_drawing']
    if drawing['geometry']['type'] == 'Polygon':
        coords = drawing['geometry']['coordinates'][0]
        st.session_state.poligono = Polygon(coords)
        st.success("✅ Polígono actualizado desde el mapa")

# Mostrar información de la parcela
if st.session_state.poligono:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Calcular área
        gdf_temp = gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326')
        area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000  # Aproximación
        st.metric("Área aproximada", f"{area_ha:.2f} ha")
    
    with col2:
        st.metric("Cultivo", cultivo_seleccionado)
    
    with col3:
        st.metric("Zonas de manejo", n_zonas)
else:
    st.info("👆 **Dibuja un polígono en el mapa o carga un archivo desde el sidebar para comenzar el análisis**")

# ===== BOTÓN DE ANÁLISIS PRINCIPAL =====
st.markdown("---")
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

with col_btn1:
    if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
        if st.session_state.poligono is None:
            st.error("❌ Por favor, dibuja o carga una parcela primero")
        else:
            # Guardar cultivo seleccionado en session_state
            st.session_state.cultivo_seleccionado = cultivo_seleccionado
            
            with st.spinner("🔬 Realizando análisis completo..."):
                try:
                    # Mostrar progreso
                    progress_bar = st.progress(0)
                    
                    # Paso 1: Obtener datos satelitales
                    progress_bar.progress(10)
                    st.info("Paso 1/7: Obteniendo datos satelitales...")
                    
                    usar_gee = '_GEE' in satelite_seleccionado and st.session_state.gee_authenticated
                    if usar_gee:
                        indices_satelitales = calcular_indices_satelitales_gee(
                            satelite_seleccionado,
                            st.session_state.poligono,
                            fecha_inicio,
                            fecha_fin
                        )
                    else:
                        # Datos simulados si no hay GEE
                        np.random.seed(42)
                        indices_satelitales = {
                            'NDVI': np.random.uniform(0.55, 0.85),
                            'NDWI': np.random.uniform(0.10, 0.25),
                            'EVI': np.random.uniform(0.45, 0.75),
                            'NDRE': np.random.uniform(0.25, 0.45),
                            'fecha': datetime.now().strftime('%Y-%m-%d'),
                            'fuente': 'Simulado',
                            'resolucion': '10m'
                        }
                    
                    # Paso 2: Dividir parcela en zonas
                    progress_bar.progress(20)
                    st.info("Paso 2/7: Dividiendo parcela en zonas...")
                    zonas = dividir_parcela_en_zonas(st.session_state.poligono, n_zonas)
                    
                    # Paso 3: Analizar fertilidad por zonas
                    progress_bar.progress(35)
                    st.info("Paso 3/7: Analizando fertilidad...")
                    indices_fertilidad = analizar_fertilidad_zonas(zonas, indices_satelitales, st.session_state.cultivo_seleccionado)
                    
                    # Paso 4: Calcular recomendaciones NPK
                    progress_bar.progress(50)
                    st.info("Paso 4/7: Calculando recomendaciones NPK...")
                    recomendaciones_npk = calcular_recomendaciones_npk_mejorado(
                        indices_fertilidad, 
                        st.session_state.cultivo_seleccionado, 
                        textura_suelo
                    )
                    
                    # Paso 5: Calcular proyecciones de cosecha
                    progress_bar.progress(65)
                    st.info("Paso 5/7: Calculando proyecciones...")
                    proyecciones = calcular_proyecciones_cosecha(indices_fertilidad, recomendaciones_npk, st.session_state.cultivo_seleccionado)
                    
                    # Paso 6: Generar DEM y análisis topográfico
                    progress_bar.progress(80)
                    st.info("Paso 6/7: Generando análisis topográfico...")
                    fig_dem, dem_data = crear_dem_y_curvas(st.session_state.poligono, resolucion_dem, intervalo_curvas)
                    pendientes = calcular_pendiente_mejorado(dem_data['Z'])
                    dem_data['pendientes'] = pendientes
                    
                    # Paso 7: Preparar visualizaciones
                    progress_bar.progress(95)
                    st.info("Paso 7/7: Generando reportes...")
                    
                    # Calcular área aproximada
                    gdf_temp = gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326')
                    area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000
                    
                    # Guardar resultados en session_state
                    st.session_state.resultados_analisis = {
                        'indices_satelitales': indices_satelitales,
                        'zonas': zonas,
                        'indices_fertilidad': indices_fertilidad,
                        'recomendaciones_npk': recomendaciones_npk,
                        'proyecciones': proyecciones,
                        'dem': dem_data,
                        'cultivo': st.session_state.cultivo_seleccionado,
                        'textura_suelo': textura_suelo,
                        'precipitacion': precipitacion,
                        'area_total': area_ha
                    }
                    
                    st.session_state.analisis_ejecutado = True
                    progress_bar.progress(100)
                    st.success("✅ Análisis completado exitosamente!")
                    st.rerun()  # Forzar recarga para mostrar resultados
                    
                except Exception as e:
                    st.error(f"❌ Error durante el análisis: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

with col_btn2:
    if st.session_state.resultados_analisis is not None:
        if st.button("📥 Descargar Mapas PNG", use_container_width=True):
            zip_buffer = descargar_todas_visualizaciones(st.session_state.resultados_analisis, st.session_state.poligono)
            if zip_buffer:
                st.download_button(
                    label="🗃️ Descargar ZIP",
                    data=zip_buffer,
                    file_name=f"mapas_{st.session_state.resultados_analisis['cultivo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )

with col_btn3:
    if st.session_state.resultados_analisis is not None:
        if st.button("🗑️ Limpiar Resultados", use_container_width=True):
            if 'resultados_analisis' in st.session_state:
                st.session_state.resultados_analisis = None
            st.session_state.analisis_ejecutado = False
            st.rerun()

# ===== MOSTRAR RESULTADOS SI EXISTEN =====
if st.session_state.resultados_analisis is not None and st.session_state.analisis_ejecutado:
    resultados = st.session_state.resultados_analisis
    
    # Crear pestañas para diferentes secciones
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Resumen General",
        "🌿 Fertilidad",
        "🟢 NDVI",
        "🧪 Recomendaciones NPK",
        "📈 Proyecciones",
        "🏔️ Topografía",
        "📋 Reporte Final"
    ])
    
    with tab1:
        st.markdown("## 📊 RESUMEN GENERAL DEL ANÁLISIS")
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            ndvi_prom = np.mean([idx['ndvi'] for idx in resultados['indices_fertilidad']])
            st.metric("NDVI Promedio", f"{ndvi_prom:.3f}")
        
        with col2:
            fert_prom = np.mean([idx['indice_fertilidad'] for idx in resultados['indices_fertilidad']])
            st.metric("Fertilidad Promedio", f"{fert_prom:.3f}")
        
        with col3:
            n_prom = np.mean([rec['N'] for rec in resultados['recomendaciones_npk']])
            st.metric("N Recomendado", f"{n_prom:.1f} kg/ha")
        
        with col4:
            rend_prom = np.mean([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']])
            st.metric("Rendimiento Estimado", f"{rend_prom:.0f} kg/ha")
        
        # Información del análisis
        st.markdown("### 📋 Información del Análisis")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.markdown(f"""
            **🌱 Cultivo:** {resultados['cultivo']} {PARAMETROS_CULTIVOS[resultados['cultivo']]['icono']}
            **🏞️ Área total:** {resultados['area_total']:.2f} ha
            **🏗️ Zonas analizadas:** {len(resultados['zonas'])}
            **🌧️ Precipitación:** {resultados['precipitacion']} mm/año
            """)
        
        with info_col2:
            st.markdown(f"""
            **🛰️ Fuente de datos:** {resultados['indices_satelitales']['fuente']}
            **📅 Fecha datos:** {resultados['indices_satelitales']['fecha']}
            **🎯 Resolución:** {resultados['indices_satelitales'].get('resolucion', 'N/A')}
            **🏜️ Textura suelo:** {resultados['textura_suelo']}
            """)
        
        # Mapa de ubicación
        st.markdown("### 🗺️ Ubicación de la Parcela")
        mapa_resumen = crear_mapa_interactivo(st.session_state.poligono, zoom_start=13)
        st_folium(mapa_resumen, width=800, height=400)
    
    with tab2:
        st.markdown("## 🌿 ANÁLISIS DE FERTILIDAD POR ZONAS")
        
        # Visualización de fertilidad
        st.markdown("### 🎨 Mapa de Calor de Fertilidad")
        fig_fert = crear_mapa_calor_fertilidad(resultados['zonas'], resultados['indices_fertilidad'], st.session_state.poligono)
        st.pyplot(fig_fert)
        
        # Botón para descargar
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            fert_buffer = guardar_figura_como_png(fig_fert, 'fertilidad')
            st.download_button(
                label="📥 Descargar Mapa PNG",
                data=fert_buffer,
                file_name=f"mapa_fertilidad_{resultados['cultivo']}.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Tabla de resultados
        st.markdown("### 📋 Tabla de Resultados por Zona")
        df_fertilidad = pd.DataFrame(resultados['indices_fertilidad'])
        df_fertilidad = df_fertilidad[['id_zona', 'materia_organica', 'humedad', 'ndvi', 'ndre', 'indice_fertilidad']]
        df_fertilidad.columns = ['Zona', 'Materia Orgánica (%)', 'Humedad', 'NDVI', 'NDRE', 'Índice Fertilidad']
        st.dataframe(df_fertilidad, use_container_width=True)
        
        # Análisis estadístico
        st.markdown("### 📊 Estadísticas de Fertilidad")
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("Materia Orgánica", f"{df_fertilidad['Materia Orgánica (%)'].mean():.2f}%")
        
        with col_stat2:
            st.metric("Humedad Promedio", f"{df_fertilidad['Humedad'].mean():.3f}")
        
        with col_stat3:
            zonas_bajas = len(df_fertilidad[df_fertilidad['Índice Fertilidad'] < 0.5])
            st.metric("Zonas Baja Fertilidad", zonas_bajas)
        
        with col_stat4:
            zonas_altas = len(df_fertilidad[df_fertilidad['Índice Fertilidad'] > 0.7])
            st.metric("Zonas Alta Fertilidad", zonas_altas)
    
    with tab3:
        st.markdown("## 🟢 ANÁLISIS DE NDVI")
        
        # Mapa de calor de NDVI
        st.markdown("### 🎨 Mapa de Calor de NDVI")
        fig_ndvi = crear_mapa_calor_ndvi(resultados['zonas'], resultados['indices_fertilidad'], st.session_state.poligono)
        st.pyplot(fig_ndvi)
        
        # Botón para descargar
        col_dl_ndvi1, col_dl_ndvi2 = st.columns(2)
        with col_dl_ndvi1:
            ndvi_buffer = guardar_figura_como_png(fig_ndvi, 'ndvi')
            st.download_button(
                label="📥 Descargar Mapa NDVI",
                data=ndvi_buffer,
                file_name=f"mapa_ndvi_{resultados['cultivo']}.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Análisis de NDVI
        st.markdown("### 📊 Estadísticas de NDVI")
        ndvi_valores = [idx['ndvi'] for idx in resultados['indices_fertilidad']]
        ndvi_min = min(ndvi_valores)
        ndvi_max = max(ndvi_valores)
        ndvi_prom = np.mean(ndvi_valores)
        ndvi_std = np.std(ndvi_valores)
        
        col_ndvi1, col_ndvi2, col_ndvi3, col_ndvi4 = st.columns(4)
        
        with col_ndvi1:
            st.metric("NDVI Mínimo", f"{ndvi_min:.3f}")
        
        with col_ndvi2:
            st.metric("NDVI Máximo", f"{ndvi_max:.3f}")
        
        with col_ndvi3:
            st.metric("NDVI Promedio", f"{ndvi_prom:.3f}")
        
        with col_ndvi4:
            st.metric("Desviación NDVI", f"{ndvi_std:.3f}")
        
        # Interpretación de NDVI
        st.markdown("### 📋 Interpretación de Valores NDVI")
        
        interpretacion_data = {
            'Rango NDVI': ['0.0 - 0.2', '0.2 - 0.4', '0.4 - 0.6', '0.6 - 0.8', '0.8 - 1.0'],
            'Estado Vegetación': ['Suelo desnudo/Baja vegetación', 'Vegetación escasa', 
                                 'Vegetación moderada', 'Vegetación densa', 'Vegetación muy densa'],
            'Recomendación': ['Fertilización intensiva', 'Fertilización moderada', 
                            'Fertilización equilibrada', 'Fertilización ligera', 
                            'Mantenimiento solamente']
        }
        
        df_interpretacion = pd.DataFrame(interpretacion_data)
        st.dataframe(df_interpretacion, use_container_width=True)
        
        # Distribución de zonas por categoría de NDVI
        st.markdown("### 📈 Distribución de Zonas por Categoría de NDVI")
        
        categorias = []
        for ndvi in ndvi_valores:
            if ndvi < 0.2:
                categorias.append('Suelo desnudo')
            elif ndvi < 0.4:
                categorias.append('Vegetación escasa')
            elif ndvi < 0.6:
                categorias.append('Vegetación moderada')
            elif ndvi < 0.8:
                categorias.append('Vegetación densa')
            else:
                categorias.append('Vegetación muy densa')
        
        from collections import Counter
        distribucion = Counter(categorias)
        
        fig_dist, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(distribucion.keys(), distribucion.values(), color=['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60'])
        ax.set_title('Distribución de Zonas por Categoría de NDVI', fontsize=14, fontweight='bold')
        ax.set_xlabel('Categoría de NDVI', fontsize=12)
        ax.set_ylabel('Número de Zonas', fontsize=12)
        
        # Añadir etiquetas
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{int(height)}', ha='center', va='bottom', fontweight='bold')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig_dist)
    
    with tab4:
        st.markdown("## 🧪 RECOMENDACIONES DE FERTILIZACIÓN NPK")
        
        # Mapas de calor de recomendaciones
        st.markdown("### 🗺️ Mapas de Calor - Recomendaciones")
        
        col_n, col_p, col_k = st.columns(3)
        
        with col_n:
            st.markdown("#### **Nitrógeno (N)**")
            fig_n = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'N', st.session_state.poligono)
            st.pyplot(fig_n)
            
            n_buffer = guardar_figura_como_png(fig_n, 'nitrogeno')
            st.download_button(
                label="📥 PNG",
                data=n_buffer,
                file_name="mapa_nitrogeno.png",
                mime="image/png",
                use_container_width=True
            )
        
        with col_p:
            st.markdown("#### **Fósforo (P)**")
            fig_p = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'P', st.session_state.poligono)
            st.pyplot(fig_p)
            
            p_buffer = guardar_figura_como_png(fig_p, 'fosforo')
            st.download_button(
                label="📥 PNG",
                data=p_buffer,
                file_name="mapa_fosforo.png",
                mime="image/png",
                use_container_width=True
            )
        
        with col_k:
            st.markdown("#### **Potasio (K)**")
            fig_k = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'K', st.session_state.poligono)
            st.pyplot(fig_k)
            
            k_buffer = guardar_figura_como_png(fig_k, 'potasio')
            st.download_button(
                label="📥 PNG",
                data=k_buffer,
                file_name="mapa_potasio.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Tabla de recomendaciones
        st.markdown("### 📋 Recomendaciones Detalladas por Zona")
        df_npk = pd.DataFrame(resultados['recomendaciones_npk'])
        df_npk.insert(0, 'Zona', range(1, len(df_npk) + 1))
        df_npk.columns = ['Zona', 'Nitrógeno (kg/ha)', 'Fósforo (kg/ha)', 'Potasio (kg/ha)']
        st.dataframe(df_npk, use_container_width=True)
        
        # Resumen de necesidades
        st.markdown("### 📦 Resumen de Necesidades Totales")
        
        total_n = df_npk['Nitrógeno (kg/ha)'].sum() * resultados['area_total'] / len(df_npk)
        total_p = df_npk['Fósforo (kg/ha)'].sum() * resultados['area_total'] / len(df_npk)
        total_k = df_npk['Potasio (kg/ha)'].sum() * resultados['area_total'] / len(df_npk)
        
        col_tot1, col_tot2, col_tot3 = st.columns(3)
        
        with col_tot1:
            st.metric("Nitrógeno Total", f"{total_n:.1f} kg")
        
        with col_tot2:
            st.metric("Fósforo Total", f"{total_p:.1f} kg")
        
        with col_tot3:
            st.metric("Potasio Total", f"{total_k:.1f} kg")
    
    with tab5:
        st.markdown("## 📈 PROYECCIONES DE COSECHA")
        
        # Mapas de calor de rendimiento
        st.markdown("### 🗺️ Mapas de Calor - Potencial de Cosecha")
        
        col_rend1, col_rend2 = st.columns(2)
        
        with col_rend1:
            st.markdown("#### **Sin Fertilización**")
            fig_rend_base = crear_mapa_calor_rendimiento(resultados['zonas'], resultados['proyecciones'], 'base', st.session_state.poligono)
            st.pyplot(fig_rend_base)
            
            base_buffer = guardar_figura_como_png(fig_rend_base, 'rendimiento_base')
            st.download_button(
                label="📥 PNG",
                data=base_buffer,
                file_name="rendimiento_sin_fertilizacion.png",
                mime="image/png",
                use_container_width=True
            )
        
        with col_rend2:
            st.markdown("#### **Con Fertilización**")
            fig_rend_fert = crear_mapa_calor_rendimiento(resultados['zonas'], resultados['proyecciones'], 'fert', st.session_state.poligono)
            st.pyplot(fig_rend_fert)
            
            fert_buffer = guardar_figura_como_png(fig_rend_fert, 'rendimiento_fert')
            st.download_button(
                label="📥 PNG",
                data=fert_buffer,
                file_name="rendimiento_con_fertilizacion.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Mapa de calor de diferencia
        st.markdown("### 🎯 Incremento por Fertilización")
        fig_diff = crear_mapa_calor_diferencia(resultados['zonas'], resultados['proyecciones'], st.session_state.poligono)
        st.pyplot(fig_diff)
        
        col_dl_diff, _ = st.columns([1, 3])
        with col_dl_diff:
            diff_buffer = guardar_figura_como_png(fig_diff, 'incremento')
            st.download_button(
                label="📥 Descargar Mapa de Incremento",
                data=diff_buffer,
                file_name="incremento_fertilizacion.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Gráfico de comparativa
        st.markdown("### 📊 Comparativa de Rendimientos por Zona")
        
        fig_comparativa, ax = plt.subplots(figsize=(14, 7))
        
        zonas_ids = [f"Z{idx['id_zona']}" for idx in resultados['indices_fertilidad']]
        rend_base = [proy['rendimiento_base'] for proy in resultados['proyecciones']]
        rend_fert = [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]
        
        x = np.arange(len(zonas_ids))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, rend_base, width, label='Sin Fertilización', color='#ff6b6b', alpha=0.8)
        bars2 = ax.bar(x + width/2, rend_fert, width, label='Con Fertilización', color='#4ecdc4', alpha=0.8)
        
        # Añadir etiquetas de incremento
        for i, (base, fert) in enumerate(zip(rend_base, rend_fert)):
            incremento = ((fert - base) / base * 100) if base > 0 else 0
            ax.text(i, max(base, fert) + (max(rend_fert) * 0.02), 
                   f"+{incremento:.0f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_xlabel('Zona', fontsize=13)
        ax.set_ylabel('Rendimiento (kg/ha)', fontsize=13)
        ax.set_title('Comparativa de Rendimiento con y sin Fertilización', fontsize=16, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(zonas_ids, rotation=45)
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        st.pyplot(fig_comparativa)
        
        # Análisis económico
        st.markdown("### 💰 Análisis Económico")
        
        precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
        rend_total_base = sum(rend_base) * resultados['area_total'] / len(rend_base)
        rend_total_fert = sum(rend_fert) * resultados['area_total'] / len(rend_fert)
        
        ingreso_base = rend_total_base * precio
        ingreso_fert = rend_total_fert * precio
        
        # Costos estimados de fertilización
        total_n = sum([rec['N'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        total_p = sum([rec['P'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        total_k = sum([rec['K'] for rec in resultados['recomendaciones_npk']]) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
        
        costo_total = (total_n * 1.2 + total_p * 2.5 + total_k * 1.8)
        
        ingreso_adicional = ingreso_fert - ingreso_base
        beneficio_neto = ingreso_adicional - costo_total
        roi = (beneficio_neto / costo_total * 100) if costo_total > 0 else 0
        
        col_eco1, col_eco2, col_eco3, col_eco4 = st.columns(4)
        
        with col_eco1:
            st.metric("Ingreso Adicional", f"${ingreso_adicional:,.0f} USD")
        
        with col_eco2:
            st.metric("Costo Fertilización", f"${costo_total:,.0f} USD")
        
        with col_eco3:
            st.metric("Beneficio Neto", f"${beneficio_neto:,.0f} USD")
        
        with col_eco4:
            st.metric("ROI Estimado", f"{roi:.1f}%")
        
        # Tabla de proyecciones
        st.markdown("### 📋 Tabla de Proyecciones por Zona")
        df_proy = pd.DataFrame(resultados['proyecciones'])
        df_proy.insert(0, 'Zona', zonas_ids)
        df_proy.columns = ['Zona', 'Sin Fertilización (kg/ha)', 'Con Fertilización (kg/ha)', 'Incremento (%)']
        st.dataframe(df_proy, use_container_width=True)
    
    with tab6:
        st.markdown("## 🏔️ ANÁLISIS TOPOGRÁFICO")
        
        # DEM y curvas de nivel consistentes
        st.markdown("### 🗺️ Modelo Digital de Elevaciones y Curvas de Nivel")
        
        fig_dem, _ = crear_dem_y_curvas(st.session_state.poligono, resolucion_dem, intervalo_curvas)
        st.pyplot(fig_dem)
        
        # Botones de descarga
        col_dl_dem, col_dl_pend = st.columns(2)
        with col_dl_dem:
            dem_buffer = guardar_figura_como_png(fig_dem, 'dem_curvas')
            st.download_button(
                label="📥 Descargar DEM y Curvas",
                data=dem_buffer,
                file_name="dem_curvas_nivel.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Análisis de pendientes
        st.markdown("### 📊 Análisis de Pendientes")
        
        pendientes_flat = resultados['dem']['pendientes'].flatten()
        
        col_pend1, col_pend2, col_pend3, col_pend4 = st.columns(4)
        
        with col_pend1:
            st.metric("Pendiente Mínima", f"{np.min(pendientes_flat):.1f}%")
        
        with col_pend2:
            st.metric("Pendiente Máxima", f"{np.max(pendientes_flat):.1f}%")
        
        with col_pend3:
            st.metric("Pendiente Promedio", f"{np.mean(pendientes_flat):.1f}%")
        
        with col_pend4:
            # Clasificación de riesgo
            pendiente_prom = np.mean(pendientes_flat)
            if pendiente_prom < 5:
                riesgo = "BAJO"
                color = "green"
            elif pendiente_prom < 10:
                riesgo = "MODERADO"
                color = "orange"
            else:
                riesgo = "ALTO"
                color = "red"
            st.metric("Riesgo Erosión", riesgo)
        
        # Histograma de pendientes
        st.markdown("### 📈 Distribución de Pendientes")
        
        fig_hist, ax = plt.subplots(figsize=(10, 6))
        ax.hist(pendientes_flat, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        ax.axvline(pendiente_prom, color='red', linestyle='--', linewidth=2, label=f'Promedio: {pendiente_prom:.1f}%')
        ax.set_title('Distribución de Pendientes en el Terreno', fontsize=14, fontweight='bold')
        ax.set_xlabel('Pendiente (%)', fontsize=12)
        ax.set_ylabel('Frecuencia', fontsize=12)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
        
        plt.tight_layout()
        st.pyplot(fig_hist)
        
        # Recomendaciones topográficas
        st.markdown("### 💡 Recomendaciones Topográficas")
        
        if pendiente_prom < 5:
            st.success("""
            **✅ Condiciones óptimas para agricultura:**
            - Pendientes suaves (<5%) permiten buen drenaje sin riesgo significativo de erosión
            - Puedes implementar sistemas de riego convencionales
            - Mínima necesidad de obras de conservación de suelos
            - Ideal para maquinaria agrícola convencional
            """)
        elif pendiente_prom < 10:
            st.warning("""
            **⚠️ Pendientes moderadas (5-10%):**
            - Recomendado implementar cultivos en contorno
            - Considerar terrazas de base ancha para cultivos anuales
            - Mantener cobertura vegetal para prevenir erosión
            - Evitar labranza intensiva en dirección de la pendiente
            - Considerar cultivos perennes en las áreas más inclinadas
            """)
        else:
            st.error("""
            **🚨 Pendientes pronunciadas (>10%):**
            - Alto riesgo de erosión - implementar medidas de conservación inmediatas
            - Recomendado: Terrazas, cultivos en fajas, barreras vivas
            - Considerar cultivos permanentes o agroforestería
            - Evitar cultivos anuales sin medidas de conservación
            - Consultar con especialista en conservación de suelos
            - Considerar cambio de uso del suelo si es económicamente inviable
            """)
    
    with tab7:
        st.markdown("## 📋 REPORTE FINAL COMPLETO")
        
        # Generar reportes
        st.markdown("### 📄 Generar Reportes Completos")
        
        col_report1, col_report2, col_report3 = st.columns(3)
        
        with col_report1:
            if DOCX_AVAILABLE:
                if st.button("📝 Generar Reporte DOCX", use_container_width=True):
                    docx_buffer = generar_reporte_docx(resultados)
                    if docx_buffer:
                        st.download_button(
                            label="📥 Descargar DOCX",
                            data=docx_buffer,
                            file_name=f"reporte_{resultados['cultivo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
            else:
                st.warning("python-docx no instalado")
        
        with col_report2:
            if XLSX_AVAILABLE:
                if st.button("📊 Exportar Tablas XLSX", use_container_width=True):
                    xlsx_buffer = exportar_tablas_xlsx(resultados)
                    if xlsx_buffer:
                        st.download_button(
                            label="📥 Descargar XLSX",
                            data=xlsx_buffer,
                            file_name=f"tablas_{resultados['cultivo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
            else:
                st.warning("xlsxwriter no instalado")
        
        with col_report3:
            if st.button("🗃️ Descargar Todos los Mapas", use_container_width=True):
                zip_buffer = descargar_todas_visualizaciones(resultados, st.session_state.poligono)
                if zip_buffer:
                    st.download_button(
                        label="📥 Descargar ZIP",
                        data=zip_buffer,
                        file_name=f"mapas_{resultados['cultivo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
        
        # Resumen ejecutivo
        st.markdown("### 📋 Resumen Ejecutivo")
        
        # Calcular valores para el resumen
        ndvi_prom = np.mean([idx['ndvi'] for idx in resultados['indices_fertilidad']])
        fert_prom = np.mean([idx['indice_fertilidad'] for idx in resultados['indices_fertilidad']])
        rend_prom_base = np.mean([proy['rendimiento_base'] for proy in resultados['proyecciones']])
        rend_prom_fert = np.mean([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']])
        incremento_prom = np.mean([proy['incremento'] for proy in resultados['proyecciones']])
        
        precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
        area = resultados['area_total']
        
        ingreso_base_total = rend_prom_base * area * precio
        ingreso_fert_total = rend_prom_fert * area * precio
        ingreso_adicional_total = ingreso_fert_total - ingreso_base_total
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)); 
                    border-radius: 20px; padding: 25px; border: 1px solid rgba(59, 130, 246, 0.2); 
                    margin-bottom: 20px;">
            <h3 style="color: #ffffff; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
                📈 RESUMEN EJECUTIVO
            </h3>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px;">
                <div>
                    <h4 style="color: #93c5fd;">📊 RESULTADOS TÉCNICOS</h4>
                    <p><strong>NDVI promedio:</strong> {ndvi_prom:.3f} (Óptimo: {PARAMETROS_CULTIVOS[resultados['cultivo']]['NDVI_OPTIMO']})</p>
                    <p><strong>Fertilidad promedio:</strong> {fert_prom:.3f}</p>
                    <p><strong>Rendimiento estimado:</strong> {rend_prom_base:.0f} → {rend_prom_fert:.0f} kg/ha</p>
                    <p><strong>Incremento promedio:</strong> +{incremento_prom:.1f}%</p>
                </div>
                
                <div>
                    <h4 style="color: #93c5fd;">💰 IMPACTO ECONÓMICO</h4>
                    <p><strong>Área cultivable:</strong> {area:.2f} ha</p>
                    <p><strong>Ingreso esperado:</strong> ${ingreso_base_total:,.0f} → ${ingreso_fert_total:,.0f} USD</p>
                    <p><strong>Ingreso adicional:</strong> ${ingreso_adicional_total:,.0f} USD</p>
                    <p><strong>ROI estimado:</strong> {((ingreso_adicional_total / (ingreso_adicional_total * 0.3)) * 100) if ingreso_adicional_total > 0 else 0:.1f}%</p>
                </div>
            </div>
            
            <div style="margin-top: 30px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 10px;">
                <h4 style="color: #93c5fd;">🎯 RECOMENDACIONES PRINCIPALES</h4>
                <ul style="color: #cbd5e1;">
                    <li><strong>Fertilización variable:</strong> Aplicar diferentes dosis de NPK según zonas de manejo</li>
                    <li><strong>Priorización:</strong> {len([idx for idx in resultados['indices_fertilidad'] if idx['indice_fertilidad'] < 0.5])} zonas requieren atención prioritaria</li>
                    <li><strong>Monitoreo:</strong> Seguimiento continuo de NDVI y humedad del suelo</li>
                    <li><strong>Validación:</strong> Realizar análisis de suelo para confirmar recomendaciones</li>
                    <li><strong>Topografía:</strong> {"Implementar medidas de conservación" if np.mean(resultados['dem']['pendientes'].flatten()) > 10 else "Condiciones topográficas favorables"}</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Tablas resumen
        st.markdown("### 📋 Tablas Resumen")
        
        col_sum1, col_sum2 = st.columns(2)
        
        with col_sum1:
            st.markdown("**Fertilidad por Zonas**")
            df_fert_sum = pd.DataFrame(resultados['indices_fertilidad'])[['id_zona', 'indice_fertilidad']]
            df_fert_sum.columns = ['Zona', 'Índice Fertilidad']
            df_fert_sum['Clasificación'] = pd.cut(df_fert_sum['Índice Fertilidad'], 
                                                 bins=[0, 0.3, 0.5, 0.7, 1.0],
                                                 labels=['Muy Baja', 'Baja', 'Media', 'Alta'])
            st.dataframe(df_fert_sum, use_container_width=True)
        
        with col_sum2:
            st.markdown("**Rendimiento por Zonas**")
            df_rend_sum = pd.DataFrame({
                'Zona': [f"Z{i+1}" for i in range(len(resultados['proyecciones']))],
                'Sin Fert (kg/ha)': [proy['rendimiento_base'] for proy in resultados['proyecciones']],
                'Con Fert (kg/ha)': [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']],
                'Incremento (%)': [proy['incremento'] for proy in resultados['proyecciones']]
            })
            st.dataframe(df_rend_sum, use_container_width=True)

# ===== PIE DE PÁGINA =====
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #94a3b8; padding: 20px;">
    <p><strong>🌾 Analizador Multicultivo Satelital con Google Earth Engine</strong></p>
    <p>Versión 3.2 | Desarrollado por Martin Ernesto Cano | Ingeniero Agrónomo</p>
    <p>📧 mawucano@gmail.com | 📱 +5493525 532313</p>
    <p>© 2024 - Todos los derechos reservados</p>
</div>
""", unsafe_allow_html=True)
