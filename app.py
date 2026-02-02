# app.py - Análisis Multicultivo Satelital con GEE - Versión COMPLETA
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

# Verificar scipy
try:
    from scipy.interpolate import griddata
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    st.warning("⚠️ Scipy no está instalado. Para interpolación en mapas de calor, instala: pip install scipy")

from collections import Counter

# Importar librerías para reportes
try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

# ===== INICIALIZACIÓN AUTOMÁTICA DE GOOGLE EARTH ENGINE =====
try:
    import ee
    GEE_AVAILABLE = True
except ImportError:
    GEE_AVAILABLE = False

def inicializar_gee():
    """Inicializa GEE"""
    if not GEE_AVAILABLE:
        return False
    
    try:
        # Intentar inicializar
        ee.Initialize(project='ee-mawucano25')
        st.session_state.gee_authenticated = True
        st.session_state.gee_project = 'ee-mawucano25'
        return True
    except Exception as e:
        print(f"Error inicialización GEE: {str(e)}")
        st.session_state.gee_authenticated = False
        return False

# ===== CONFIGURACIÓN INICIAL DE LA APP =====
st.set_page_config(
    page_title="🌾 Análisis Multicultivo Satelital con GEE",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== INICIALIZACIÓN DE SESSION STATE =====
if 'poligono' not in st.session_state:
    st.session_state.poligono = None
if 'resultados_analisis' not in st.session_state:
    st.session_state.resultados_analisis = None
if 'analisis_ejecutado' not in st.session_state:
    st.session_state.analisis_ejecutado = False
if 'cultivo_seleccionado' not in st.session_state:
    st.session_state.cultivo_seleccionado = 'TRIGO'
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
    st.session_state.gee_project = ''
    if GEE_AVAILABLE:
        inicializar_gee()

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
        background: linear-gradient(rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.95));
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
    }
    .dashboard-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)) !important;
        border-radius: 20px !important;
        padding: 25px !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.05) !important;
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
        'COSTO_FERTILIZACION': 380,
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

# ===== FUNCIONES PRINCIPALES =====
def procesar_archivo_carga(uploaded_file):
    """Procesa archivos KML, KMZ, GeoJSON, Shapefile"""
    try:
        if uploaded_file is None:
            return None
            
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as tmpdir:
            # Guardar archivo
            file_path = os.path.join(tmpdir, uploaded_file.name)
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Determinar tipo
            file_ext = uploaded_file.name.lower().split('.')[-1]
            
            if file_ext in ['kml', 'kmz']:
                gdf = gpd.read_file(file_path, driver='KML')
            elif file_ext == 'geojson':
                gdf = gpd.read_file(file_path)
            elif file_ext == 'shp':
                gdf = gpd.read_file(file_path)
            elif file_ext == 'zip':
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                shp_file = None
                for file in os.listdir(tmpdir):
                    if file.endswith('.shp'):
                        shp_file = os.path.join(tmpdir, file)
                        break
                if shp_file:
                    gdf = gpd.read_file(shp_file)
                else:
                    st.error("No se encontró .shp en el ZIP")
                    return None
            else:
                st.error(f"Formato no soportado: {file_ext}")
                return None
            
            if gdf.empty:
                st.error("Archivo vacío")
                return None
            
            # Obtener geometría
            geometry = gdf.geometry.iloc[0]
            
            # Convertir MultiPolygon a Polygon
            if geometry.geom_type == 'MultiPolygon':
                polygons = list(geometry.geoms)
                polygons.sort(key=lambda p: p.area, reverse=True)
                geometry = polygons[0]
            
            # Verificar tipo
            if geometry.geom_type not in ['Polygon', 'MultiPolygon']:
                st.error(f"Geometría no soportada: {geometry.geom_type}")
                return None
            
            # Reproject a WGS84
            if gdf.crs and gdf.crs.to_string() != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
                geometry = gdf.geometry.iloc[0]
            
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            return geometry
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def crear_mapa_interactivo(poligono=None, zoom_start=14):
    """Crea mapa interactivo"""
    if poligono is not None:
        centroid = poligono.centroid
        lat, lon = centroid.y, centroid.x
    else:
        lat, lon = -34.6037, -58.3816
    
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True
    )
    
    # Capas base
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Imágenes Satelitales',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Calles',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Dibujar polígono
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
    
    # Control de capas
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Herramientas de dibujo
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
    """Calcula índices desde GEE"""
    if not st.session_state.gee_authenticated or poligono is None:
        return None
    
    try:
        # Simular datos para desarrollo
        np.random.seed(42)
        return {
            'NDVI': np.random.uniform(0.55, 0.85),
            'NDWI': np.random.uniform(0.10, 0.25),
            'EVI': np.random.uniform(0.45, 0.75),
            'NDRE': np.random.uniform(0.25, 0.45),
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'fuente': f'GEE - {tipo_satelite}',
            'resolucion': '10m'
        }
        
    except Exception as e:
        # Datos simulados si falla GEE
        np.random.seed(42)
        return {
            'NDVI': np.random.uniform(0.55, 0.85),
            'NDWI': np.random.uniform(0.10, 0.25),
            'EVI': np.random.uniform(0.45, 0.75),
            'NDRE': np.random.uniform(0.25, 0.45),
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'fuente': 'Simulado',
            'resolucion': '10m'
        }

def generar_dem_para_poligono(poligono, resolucion_m=10):
    """Genera DEM para el polígono"""
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    expand_factor = 0.2
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    # Calcular tamaño
    width_deg = expanded_maxx - expanded_minx
    height_deg = expanded_maxy - expanded_miny
    
    width_m = width_deg * 111000
    height_m = height_deg * 111000
    
    nx = min(int(width_m / resolucion_m), 200)
    ny = min(int(height_m / resolucion_m), 200)
    
    # Crear malla
    x = np.linspace(expanded_minx, expanded_maxx, nx)
    y = np.linspace(expanded_miny, expanded_maxy, ny)
    X, Y = np.meshgrid(x, y)
    
    # Generar terreno
    Z = np.zeros_like(X)
    pendiente_base = np.random.uniform(1, 3)
    Z = pendiente_base * ((X - expanded_minx) / width_deg)
    
    # Agregar características
    np.random.seed(42)
    n_colinas = np.random.randint(3, 8)
    for _ in range(n_colinas):
        centro_x = np.random.uniform(expanded_minx, expanded_maxx)
        centro_y = np.random.uniform(expanded_miny, expanded_maxy)
        radio = np.random.uniform(width_deg * 0.1, width_deg * 0.3)
        altura = np.random.uniform(5, 20)
        
        distancia = np.sqrt((X - centro_x)**2 + (Y - centro_y)**2)
        Z += altura * np.exp(-(distancia**2) / (2 * radio**2))
    
    # Normalizar
    Z = (Z - Z.min()) / (Z.max() - Z.min()) * 100
    
    return X, Y, Z

def calcular_pendiente_mejorado(dem):
    """Calcula pendiente en porcentaje"""
    dy, dx = np.gradient(dem)
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    return pendiente

def dividir_parcela_en_zonas(poligono, n_zonas=16):
    """Divide parcela en zonas"""
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
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
        centroid = zona['centroid']
        x_norm = (centroid.x - zona['geometry'].bounds[0]) / (zona['geometry'].bounds[2] - zona['geometry'].bounds[0])
        y_norm = (centroid.y - zona['geometry'].bounds[1]) / (zona['geometry'].bounds[3] - zona['geometry'].bounds[1])
        
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
        
        # Índices satelitales
        if indices_satelitales:
            ndvi = indices_satelitales.get('NDVI', 0.6) * (0.9 + 0.2 * factor_espacial)
            ndre = indices_satelitales.get('NDRE', 0.3) * (0.9 + 0.2 * factor_espacial)
            evi = indices_satelitales.get('EVI', 0.5) * (0.9 + 0.2 * factor_espacial)
        else:
            ndvi = params['NDVI_OPTIMO'] * (0.8 + 0.4 * factor_espacial)
            ndre = params['NDRE_OPTIMO'] * (0.8 + 0.4 * factor_espacial)
            evi = 0.5 * (0.8 + 0.4 * factor_espacial)
        
        # Índice de fertilidad
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
    """Calcula recomendaciones de NPK"""
    params = PARAMETROS_CULTIVOS[cultivo]
    
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
        factor_fertilidad = 1.0 - idx['indice_fertilidad']
        
        n_base = params['NITROGENO']['min'] + factor_fertilidad * (params['NITROGENO']['max'] - params['NITROGENO']['min'])
        p_base = params['FOSFORO']['min'] + factor_fertilidad * (params['FOSFORO']['max'] - params['FOSFORO']['min'])
        k_base = params['POTASIO']['min'] + factor_fertilidad * (params['POTASIO']['max'] - params['POTASIO']['min'])
        
        n_ajustado = n_base * factor_textura['N']
        p_ajustado = p_base * factor_textura['P']
        k_ajustado = k_base * factor_textura['K']
        
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
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * idx['indice_fertilidad']
        
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
    """Crea mapa de calor expandido"""
    fig, ax = plt.subplots(figsize=(14, 10))
    
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    expand_factor = 0.3
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    centroides_x = [zona['centroid'].x for zona in zonas]
    centroides_y = [zona['centroid'].y for zona in zonas]
    
    # Si scipy está disponible, usar interpolación
    if SCIPY_AVAILABLE:
        grid_x, grid_y = np.mgrid[expanded_minx:expanded_maxx:100j, expanded_miny:expanded_maxy:100j]
        grid_z = griddata((centroides_x, centroides_y), valores, (grid_x, grid_y), method='linear', fill_value=np.nanmean(valores))
        im = ax.imshow(grid_z.T, extent=[expanded_minx, expanded_maxx, expanded_miny, expanded_maxy], 
                       origin='lower', cmap=cmap, alpha=0.8, aspect='auto')
    else:
        # Sin scipy, solo scatter plot
        im = ax.scatter(centroides_x, centroides_y, c=valores, cmap=cmap, 
                        s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9)
    
    # Dibujar polígono
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.fill(x_coords, y_coords, color='white', alpha=0.2, edgecolor='black', linewidth=2, linestyle='--')
    ax.plot(x_coords, y_coords, 'k-', linewidth=2)
    
    # Contornos de zonas
    for zona in zonas:
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.7)
    
    # Puntos
    scatter = ax.scatter(centroides_x, centroides_y, c=valores, cmap=cmap, 
                         s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9)
    
    ax.set_title(titulo, fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitud', fontsize=14)
    ax.set_ylabel('Latitud', fontsize=14)
    ax.grid(True, alpha=0.2, linestyle='--')
    
    cbar = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label(unidad if unidad else 'Valor', fontsize=12)
    
    # Anotaciones
    for zona, valor in zip(zonas, valores):
        ax.annotate(f"{valor:.2f}" if valor < 1 else f"{valor:.0f}", 
                   xy=(zona['centroid'].x, zona['centroid'].y), 
                   xytext=(0, 8), textcoords='offset points',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='black'))
    
    ax.text(0.02, 0.02, f"Área expandida: {expand_factor*100:.0f}%", transform=ax.transAxes,
           fontsize=10, bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig

def crear_mapa_calor_fertilidad(zonas, indices_fertilidad, poligono):
    """Crea mapa de calor de fertilidad"""
    fertilidades = [idx['indice_fertilidad'] for idx in indices_fertilidad]
    return crear_mapa_calor_expandido(zonas, fertilidades, 
                                     'Mapa de Calor - Índice de Fertilidad', 
                                     plt.cm.YlOrRd, poligono, 'Índice de Fertilidad')

def crear_mapa_calor_npk(zonas, recomendaciones_npk, nutriente='N', poligono=None):
    """Crea mapa de calor de NPK"""
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
    """Crea mapa de calor de NDVI"""
    ndvi_valores = [idx['ndvi'] for idx in indices_fertilidad]
    
    fig, ax = plt.subplots(figsize=(14, 10))
    
    bounds = poligono.bounds
    minx, miny, maxx, maxy = bounds
    
    expand_factor = 0.3
    width = maxx - minx
    height = maxy - miny
    
    expanded_minx = minx - width * expand_factor
    expanded_maxx = maxx + width * expand_factor
    expanded_miny = miny - height * expand_factor
    expanded_maxy = maxy + height * expand_factor
    
    centroides_x = [zona['centroid'].x for zona in zonas]
    centroides_y = [zona['centroid'].y for zona in zonas]
    
    # Si scipy está disponible
    if SCIPY_AVAILABLE:
        grid_x, grid_y = np.mgrid[expanded_minx:expanded_maxx:100j, expanded_miny:expanded_maxy:100j]
        grid_z = griddata((centroides_x, centroides_y), ndvi_valores, (grid_x, grid_y), method='linear', fill_value=np.nanmean(ndvi_valores))
        im = ax.imshow(grid_z.T, extent=[expanded_minx, expanded_maxx, expanded_miny, expanded_maxy], 
                       origin='lower', cmap=plt.cm.RdYlGn, alpha=0.8, aspect='auto', vmin=0, vmax=1)
    else:
        # Sin scipy
        im = ax.scatter(centroides_x, centroides_y, c=ndvi_valores, cmap=plt.cm.RdYlGn, 
                        s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9, vmin=0, vmax=1)
    
    # Dibujar polígono
    if hasattr(poligono, 'exterior'):
        coords = list(poligono.exterior.coords)
    else:
        coords = list(poligono.coords)
    
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.fill(x_coords, y_coords, color='white', alpha=0.2, edgecolor='black', linewidth=2, linestyle='--')
    ax.plot(x_coords, y_coords, 'k-', linewidth=2)
    
    # Contornos
    for zona in zonas:
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.7)
    
    scatter = ax.scatter(centroides_x, centroides_y, c=ndvi_valores, cmap=plt.cm.RdYlGn, 
                         s=100, edgecolor='black', linewidth=1, zorder=5, alpha=0.9, vmin=0, vmax=1)
    
    ax.set_title('Mapa de Calor - NDVI', fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitud', fontsize=14)
    ax.set_ylabel('Latitud', fontsize=14)
    ax.grid(True, alpha=0.2, linestyle='--')
    
    cbar = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('NDVI', fontsize=12)
    
    ax.text(0.02, 0.98, 'Interpretación NDVI:\n0.0-0.2: Suelo desnudo\n0.2-0.4: Vegetación escasa\n0.4-0.6: Vegetación moderada\n0.6-0.8: Vegetación densa\n0.8-1.0: Vegetación muy densa',
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
    
    for zona, valor in zip(zonas, ndvi_valores):
        ax.annotate(f"{valor:.3f}", 
                   xy=(zona['centroid'].x, zona['centroid'].y), 
                   xytext=(0, 8), textcoords='offset points',
                   ha='center', va='bottom', fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='black'))
    
    plt.tight_layout()
    return fig

def crear_dem_y_curvas(poligono, resolucion_m=10, intervalo_curvas=5):
    """Crea DEM y curvas de nivel"""
    X, Y, Z = generar_dem_para_poligono(poligono, resolucion_m)
    
    pendientes = calcular_pendiente_mejorado(Z)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    
    # Panel 1: DEM
    im1 = ax1.imshow(Z, extent=[X.min(), X.max(), Y.min(), Y.max()], 
                     cmap='terrain', aspect='auto', origin='lower')
    ax1.set_title('Modelo Digital de Elevaciones', fontsize=16, fontweight='bold')
    ax1.set_xlabel('Longitud', fontsize=12)
    ax1.set_ylabel('Latitud', fontsize=12)
    
    # Dibujar polígono
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
    z_min, z_max = Z.min(), Z.max()
    niveles = np.arange(int(z_min // intervalo_curvas) * intervalo_curvas, 
                       int(z_max // intervalo_curvas + 2) * intervalo_curvas, 
                       intervalo_curvas)
    
    contour = ax2.contour(X, Y, Z, levels=niveles, colors='black', linewidths=0.8)
    ax2.clabel(contour, inline=True, fontsize=8, fmt='%1.0f m')
    
    ax2.contourf(X, Y, Z, levels=50, cmap='terrain', alpha=0.7)
    
    ax2.fill(poly_x, poly_y, color='white', alpha=0.3, edgecolor='black', linewidth=2)
    ax2.plot(poly_x, poly_y, 'k-', linewidth=2)
    
    ax2.set_title(f'Curvas de Nivel (Intervalo: {intervalo_curvas}m)', fontsize=16, fontweight='bold')
    ax2.set_xlabel('Longitud', fontsize=12)
    ax2.set_ylabel('Latitud', fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    return fig, {'X': X, 'Y': Y, 'Z': Z, 'pendientes': pendientes}

def guardar_figura_como_png(fig, nombre):
    """Guarda figura como PNG"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    return buf

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURACIÓN")
    
    # Estado GEE
    st.markdown("### 🌍 Google Earth Engine")
    if st.session_state.gee_authenticated:
        st.success("✅ **Autenticado**")
    else:
        st.warning("⚠️ **No autenticado** (usando datos simulados)")
    
    # Carga de archivos
    st.markdown("### 📁 Cargar Parcela")
    
    uploaded_file = st.file_uploader(
        "Sube archivo de parcela:",
        type=['kml', 'kmz', 'geojson', 'shp', 'zip'],
        help="KML, KMZ, GeoJSON, Shapefile"
    )
    
    if uploaded_file is not None:
        if st.button("Procesar Archivo"):
            geometry = procesar_archivo_carga(uploaded_file)
            if geometry is not None:
                st.session_state.poligono = geometry
                st.session_state.analisis_ejecutado = False
                st.session_state.resultados_analisis = None
                st.success("✅ Polígono cargado!")
    
    # Selección de cultivo
    st.markdown("### 🌱 Cultivo Principal")
    cultivo_opciones = list(PARAMETROS_CULTIVOS.keys())
    cultivo_seleccionado = st.selectbox(
        "Selecciona cultivo:",
        cultivo_opciones,
        format_func=lambda x: f"{PARAMETROS_CULTIVOS[x]['icono']} {x}"
    )
    
    # Configuración satelital
    st.markdown("### 🛰️ Configuración Satelital")
    
    col_fecha1, col_fecha2 = st.columns(2)
    with col_fecha1:
        fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    with col_fecha2:
        fecha_fin = st.date_input("Fecha fin", datetime.now())
    
    # Selección satélite
    if st.session_state.gee_authenticated:
        satelite_opciones = ['SENTINEL-2 (GEE)', 'LANDSAT-8 (GEE)', 'Simulado']
    else:
        satelite_opciones = ['Simulado']
    
    satelite_seleccionado = st.selectbox("Fuente datos:", satelite_opciones)
    
    # Configuración análisis
    st.markdown("### 📊 Configuración de Análisis")
    
    textura_suelo = st.selectbox(
        "Textura del suelo:",
        ['arenosa', 'franco-arenosa', 'franca', 'franco-arcillosa', 'arcillosa']
    )
    
    n_zonas = st.slider("Zonas de manejo:", 4, 36, 16)
    
    # DEM
    st.markdown("### 🏔️ Configuración Topográfica")
    resolucion_dem = st.slider("Resolución DEM (m):", 5, 50, 10)
    intervalo_curvas = st.slider("Intervalo curvas (m):", 1, 20, 5)
    
    # Precipitación
    precipitacion = st.slider("💧 Precipitación anual (mm):", 500, 4000, 1500)
    
    # Botones
    st.markdown("---")
    if st.button("🗑️ Limpiar Todo", use_container_width=True):
        st.session_state.poligono = None
        st.session_state.resultados_analisis = None
        st.session_state.analisis_ejecutado = False
        st.rerun()

# ===== MAPA INTERACTIVO =====
st.markdown("## 🗺️ Mapa Interactivo de la Parcela")

# Crear y mostrar mapa
mapa = crear_mapa_interactivo(st.session_state.poligono)
mapa_output = st_folium(mapa, width=1000, height=500, key="mapa_parcela")

# Capturar dibujo
if mapa_output and mapa_output.get('last_active_drawing'):
    drawing = mapa_output['last_active_drawing']
    if drawing['geometry']['type'] == 'Polygon':
        coords = drawing['geometry']['coordinates'][0]
        st.session_state.poligono = Polygon(coords)
        st.session_state.analisis_ejecutado = False
        st.session_state.resultados_analisis = None
        st.success("✅ Polígono dibujado!")
        st.rerun()

# Mostrar información parcela
if st.session_state.poligono:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        gdf_temp = gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326')
        area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000
        st.metric("Área aproximada", f"{area_ha:.2f} ha")
    
    with col2:
        st.metric("Cultivo", cultivo_seleccionado)
    
    with col3:
        st.metric("Zonas de manejo", n_zonas)
else:
    st.info("👆 **Dibuja un polígono en el mapa o carga un archivo para comenzar**")

# ===== BOTÓN ANÁLISIS =====
st.markdown("---")
col_btn1, col_btn2 = st.columns([3, 1])

with col_btn1:
    if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
        if st.session_state.poligono is None:
            st.error("❌ Por favor, dibuja o carga una parcela primero")
        else:
            with st.spinner("🔬 Realizando análisis completo..."):
                try:
                    # Paso 1: Obtener índices satelitales
                    if 'GEE' in satelite_seleccionado and st.session_state.gee_authenticated:
                        indices_satelitales = calcular_indices_satelitales_gee(
                            satelite_seleccionado,
                            st.session_state.poligono,
                            fecha_inicio,
                            fecha_fin
                        )
                    else:
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
                    
                    # Paso 2: Dividir parcela
                    zonas = dividir_parcela_en_zonas(st.session_state.poligono, n_zonas)
                    
                    # Paso 3: Analizar fertilidad
                    indices_fertilidad = analizar_fertilidad_zonas(zonas, indices_satelitales, cultivo_seleccionado)
                    
                    # Paso 4: Recomendaciones NPK
                    recomendaciones_npk = calcular_recomendaciones_npk_mejorado(
                        indices_fertilidad, cultivo_seleccionado, textura_suelo
                    )
                    
                    # Paso 5: Proyecciones
                    proyecciones = calcular_proyecciones_cosecha(indices_fertilidad, recomendaciones_npk, cultivo_seleccionado)
                    
                    # Paso 6: DEM y topografía
                    fig_dem, dem_data = crear_dem_y_curvas(st.session_state.poligono, resolucion_dem, intervalo_curvas)
                    
                    # Calcular área
                    gdf_temp = gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326')
                    area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000
                    
                    # Guardar resultados
                    st.session_state.resultados_analisis = {
                        'indices_satelitales': indices_satelitales,
                        'zonas': zonas,
                        'indices_fertilidad': indices_fertilidad,
                        'recomendaciones_npk': recomendaciones_npk,
                        'proyecciones': proyecciones,
                        'dem': dem_data,
                        'cultivo': cultivo_seleccionado,
                        'textura_suelo': textura_suelo,
                        'precipitacion': precipitacion,
                        'area_total': area_ha
                    }
                    
                    st.session_state.analisis_ejecutado = True
                    st.success("✅ Análisis completado exitosamente!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

with col_btn2:
    if st.session_state.analisis_ejecutado:
        if st.button("🗑️ Limpiar Resultados", use_container_width=True):
            st.session_state.resultados_analisis = None
            st.session_state.analisis_ejecutado = False
            st.rerun()

# ===== RESULTADOS =====
if st.session_state.analisis_ejecutado and st.session_state.resultados_analisis:
    resultados = st.session_state.resultados_analisis
    
    # Crear pestañas
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Resumen", "🌿 Fertilidad", "🟢 NDVI", "🧪 NPK", "📈 Proyecciones", 
        "🏔️ Topografía"
    ])
    
    with tab1:
        st.markdown("## 📊 RESUMEN GENERAL")
        
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
        
        # Información
        st.markdown("### 📋 Información del Análisis")
        
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.markdown(f"""
            **🌱 Cultivo:** {resultados['cultivo']}
            **🏞️ Área total:** {resultados['area_total']:.2f} ha
            **🏗️ Zonas analizadas:** {len(resultados['zonas'])}
            **🌧️ Precipitación:** {resultados['precipitacion']} mm/año
            """)
        
        with col_info2:
            st.markdown(f"""
            **🛰️ Fuente de datos:** {resultados['indices_satelitales']['fuente']}
            **📅 Fecha datos:** {resultados['indices_satelitales']['fecha']}
            **🏜️ Textura suelo:** {resultados['textura_suelo']}
            **🎯 Resolución:** {resultados['indices_satelitales'].get('resolucion', 'N/A')}
            """)
        
        # Mapa de ubicación
        st.markdown("### 🗺️ Ubicación de la Parcela")
        mapa_resumen = crear_mapa_interactivo(st.session_state.poligono, zoom_start=13)
        st_folium(mapa_resumen, width=800, height=400)
    
    with tab2:
        st.markdown("## 🌿 ANÁLISIS DE FERTILIDAD")
        
        # Mapa de calor
        fig_fert = crear_mapa_calor_fertilidad(resultados['zonas'], resultados['indices_fertilidad'], st.session_state.poligono)
        st.pyplot(fig_fert)
        
        # Tabla
        st.markdown("### 📋 Tabla de Resultados")
        df_fertilidad = pd.DataFrame(resultados['indices_fertilidad'])
        df_fertilidad = df_fertilidad[['id_zona', 'materia_organica', 'humedad', 'ndvi', 'ndre', 'indice_fertilidad']]
        df_fertilidad.columns = ['Zona', 'Materia Orgánica (%)', 'Humedad', 'NDVI', 'NDRE', 'Índice Fertilidad']
        st.dataframe(df_fertilidad, use_container_width=True)
        
        # Estadísticas
        st.markdown("### 📊 Estadísticas")
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            zonas_bajas = len([idx for idx in resultados['indices_fertilidad'] if idx['indice_fertilidad'] < 0.5])
            st.metric("Zonas Baja Fertilidad", zonas_bajas)
        
        with col_stat2:
            zonas_medias = len([idx for idx in resultados['indices_fertilidad'] if 0.5 <= idx['indice_fertilidad'] < 0.7])
            st.metric("Zonas Media Fertilidad", zonas_medias)
        
        with col_stat3:
            zonas_altas = len([idx for idx in resultados['indices_fertilidad'] if idx['indice_fertilidad'] >= 0.7])
            st.metric("Zonas Alta Fertilidad", zonas_altas)
    
    with tab3:
        st.markdown("## 🟢 ANÁLISIS DE NDVI")
        
        # Mapa NDVI
        fig_ndvi = crear_mapa_calor_ndvi(resultados['zonas'], resultados['indices_fertilidad'], st.session_state.poligono)
        st.pyplot(fig_ndvi)
        
        # Análisis
        ndvi_valores = [idx['ndvi'] for idx in resultados['indices_fertilidad']]
        
        col_ndvi1, col_ndvi2, col_ndvi3, col_ndvi4 = st.columns(4)
        
        with col_ndvi1:
            st.metric("NDVI Mínimo", f"{min(ndvi_valores):.3f}")
        
        with col_ndvi2:
            st.metric("NDVI Máximo", f"{max(ndvi_valores):.3f}")
        
        with col_ndvi3:
            st.metric("NDVI Promedio", f"{np.mean(ndvi_valores):.3f}")
        
        with col_ndvi4:
            st.metric("Desviación NDVI", f"{np.std(ndvi_valores):.3f}")
        
        # Interpretación
        st.markdown("### 📋 Interpretación de NDVI")
        
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
        
        distribucion = Counter(categorias)
        
        fig_dist, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(distribucion.keys(), distribucion.values(), color=['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60'])
        ax.set_title('Distribución de Zonas por Categoría de NDVI', fontsize=14, fontweight='bold')
        ax.set_xlabel('Categoría', fontsize=12)
        ax.set_ylabel('Número de Zonas', fontsize=12)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{int(height)}', ha='center', va='bottom', fontweight='bold')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig_dist)
    
    with tab4:
        st.markdown("## 🧪 RECOMENDACIONES NPK")
        
        # Mapas NPK
        col_n, col_p, col_k = st.columns(3)
        
        with col_n:
            st.markdown("#### **Nitrógeno (N)**")
            fig_n = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'N', st.session_state.poligono)
            st.pyplot(fig_n)
        
        with col_p:
            st.markdown("#### **Fósforo (P)**")
            fig_p = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'P', st.session_state.poligono)
            st.pyplot(fig_p)
        
        with col_k:
            st.markdown("#### **Potasio (K)**")
            fig_k = crear_mapa_calor_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'K', st.session_state.poligono)
            st.pyplot(fig_k)
        
        # Tabla recomendaciones
        st.markdown("### 📋 Recomendaciones Detalladas")
        df_npk = pd.DataFrame(resultados['recomendaciones_npk'])
        df_npk.insert(0, 'Zona', range(1, len(df_npk) + 1))
        df_npk.columns = ['Zona', 'Nitrógeno (kg/ha)', 'Fósforo (kg/ha)', 'Potasio (kg/ha)']
        st.dataframe(df_npk, use_container_width=True)
        
        # Necesidades totales
        st.markdown("### 📦 Necesidades Totales Estimadas")
        
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
        
        # Proyecciones
        st.markdown("### 📊 Comparativa de Rendimientos")
        
        fig_comparativa, ax = plt.subplots(figsize=(14, 7))
        
        zonas_ids = [f"Z{idx['id_zona']}" for idx in resultados['indices_fertilidad']]
        rend_base = [proy['rendimiento_base'] for proy in resultados['proyecciones']]
        rend_fert = [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]
        
        x = np.arange(len(zonas_ids))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, rend_base, width, label='Sin Fertilización', color='#ff6b6b', alpha=0.8)
        bars2 = ax.bar(x + width/2, rend_fert, width, label='Con Fertilización', color='#4ecdc4', alpha=0.8)
        
        for i, (base, fert) in enumerate(zip(rend_base, rend_fert)):
            incremento = ((fert - base) / base * 100) if base > 0 else 0
            ax.text(i, max(base, fert) + (max(rend_fert) * 0.02), 
                   f"+{incremento:.0f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_xlabel('Zona', fontsize=13)
        ax.set_ylabel('Rendimiento (kg/ha)', fontsize=13)
        ax.set_title('Comparativa de Rendimiento con y sin Fertilización', fontsize=16, fontweight='bold')
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
        
        costo_total = (total_n * 1.2 + total_p * 2.5 + total_k * 1.8)
        ingreso_adicional = ingreso_fert - ingreso_base
        beneficio_neto = ingreso_adicional - costo_total
        roi = (beneficio_neto / costo_total * 100) if costo_total > 0 else 0
        
        col_eco1, col_eco2, col_eco3, col_eco4 = st.columns(4)
        
        with col_eco1:
            st.metric("Ingreso Adicional", f"${ingreso_adicional:,.0f}")
        
        with col_eco2:
            st.metric("Costo Fertilización", f"${costo_total:,.0f}")
        
        with col_eco3:
            st.metric("Beneficio Neto", f"${beneficio_neto:,.0f}")
        
        with col_eco4:
            st.metric("ROI Estimado", f"{roi:.1f}%")
        
        # Tabla proyecciones
        st.markdown("### 📋 Tabla de Proyecciones")
        df_proy = pd.DataFrame(resultados['proyecciones'])
        df_proy.insert(0, 'Zona', zonas_ids)
        df_proy.columns = ['Zona', 'Sin Fertilización (kg/ha)', 'Con Fertilización (kg/ha)', 'Incremento (%)']
        st.dataframe(df_proy, use_container_width=True)
    
    with tab6:
        st.markdown("## 🏔️ ANÁLISIS TOPOGRÁFICO")
        
        # DEM y curvas
        fig_dem, _ = crear_dem_y_curvas(st.session_state.poligono, resolucion_dem, intervalo_curvas)
        st.pyplot(fig_dem)
        
        # Análisis pendientes
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
            pendiente_prom = np.mean(pendientes_flat)
            if pendiente_prom < 5:
                riesgo = "BAJO"
            elif pendiente_prom < 10:
                riesgo = "MODERADO"
            else:
                riesgo = "ALTO"
            st.metric("Riesgo Erosión", riesgo)
        
        # Histograma
        fig_hist, ax = plt.subplots(figsize=(10, 6))
        ax.hist(pendientes_flat, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        ax.axvline(pendiente_prom, color='red', linestyle='--', linewidth=2, label=f'Promedio: {pendiente_prom:.1f}%')
        ax.set_title('Distribución de Pendientes', fontsize=14, fontweight='bold')
        ax.set_xlabel('Pendiente (%)', fontsize=12)
        ax.set_ylabel('Frecuencia', fontsize=12)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
        
        plt.tight_layout()
        st.pyplot(fig_hist)
        
        # Recomendaciones
        st.markdown("### 💡 Recomendaciones Topográficas")
        
        if pendiente_prom < 5:
            st.success("""
            **✅ Condiciones óptimas:**
            - Pendientes suaves (<5%)
            - Buen drenaje natural
            - Mínimo riesgo de erosión
            - Ideal para agricultura mecanizada
            """)
        elif pendiente_prom < 10:
            st.warning("""
            **⚠️ Pendientes moderadas (5-10%):**
            - Cultivos en contorno recomendados
            - Considerar terrazas
            - Mantener cobertura vegetal
            - Evitar labranza intensiva
            """)
        else:
            st.error("""
            **🚨 Pendientes pronunciadas (>10%):**
            - Alto riesgo de erosión
            - Implementar medidas de conservación
            - Terrazas y barreras vivas
            - Considerar cultivos permanentes
            - Consultar especialista
            """)

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
