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

# Ejecutar inicialización al inicio (ANTES de cualquier uso de ee.*)
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
    st.session_state.gee_project = ''
    if GEE_AVAILABLE:
        inicializar_gee()

# ===== CONFIGURACIÓN INICIAL DE LA APP =====
st.set_page_config(
    page_title="🌾 Análisis Multicultivo Satelital con GEE",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ===== CONFIGURACIÓN DE CULTIVOS MEJORADA =====
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
        'COSTO_FERTILIZACION': 380,
        'PRECIO_VENTA': 0.60,
        'icono': '🥜'
    }
}

# ===== FUNCIONES AUXILIARES MEJORADAS =====
def crear_mapa_interactivo(poligono=None, titulo="Mapa de la Parcela", zoom_start=14):
    """Crea un mapa interactivo con Esri World Imagery como base"""
    if poligono is not None:
        centroid = poligono.centroid
        lat, lon = centroid.y, centroid.x
    else:
        lat, lon = 4.6097, -74.0817  # Bogotá por defecto
    
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

def generar_dem_sintetico_mejorado(ancho=100, alto=100, complejidad=2):
    """Genera un DEM sintético más realista"""
    x = np.linspace(0, ancho, ancho)
    y = np.linspace(0, alto, alto)
    X, Y = np.meshgrid(x, y)
    
    # Base con pendiente general
    pendiente_base = np.random.uniform(1, 5)
    Z = pendiente_base * (X / ancho)
    
    # Agregar colinas y valles
    np.random.seed(42)
    n_colinas = np.random.randint(3, 7)
    for _ in range(n_colinas):
        centro_x = np.random.uniform(0, ancho)
        centro_y = np.random.uniform(0, alto)
        radio = np.random.uniform(10, 30)
        altura = np.random.uniform(5, 15)
        
        distancia = np.sqrt((X - centro_x)**2 + (Y - centro_y)**2)
        Z += altura * np.exp(-(distancia**2) / (2 * radio**2))
    
    # Agregar valles
    n_valles = np.random.randint(2, 5)
    for _ in range(n_valles):
        centro_x = np.random.uniform(0, ancho)
        centro_y = np.random.uniform(0, alto)
        radio = np.random.uniform(15, 35)
        profundidad = np.random.uniform(3, 10)
        
        distancia = np.sqrt((X - centro_x)**2 + (Y - centro_y)**2)
        Z -= profundidad * np.exp(-(distancia**2) / (2 * radio**2))
    
    # Ruido topográfico
    ruido = np.random.randn(alto, ancho) * complejidad
    Z += ruido
    
    # Normalizar
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

def crear_visualizacion_fertilidad(zonas, indices_fertilidad):
    """Crea visualización de fertilidad por zonas"""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Crear colormap para fertilidad
    cmap = plt.cm.viridis
    
    # Dibujar cada zona con su color según fertilidad
    for zona, idx in zip(zonas, indices_fertilidad):
        color = cmap(idx['indice_fertilidad'])
        
        # Obtener coordenadas del polígono
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.fill(x_coords, y_coords, color=color, alpha=0.7, edgecolor='black', linewidth=1)
        
        # Etiqueta con ID de zona y fertilidad
        centroid = zona['centroid']
        ax.text(centroid.x, centroid.y, f"Z{idx['id_zona']}\n{idx['indice_fertilidad']:.2f}",
                ha='center', va='center', fontsize=8, color='white',
                bbox=dict(boxstyle="round,pad=0.2", facecolor='black', alpha=0.5))
    
    ax.set_title('Mapa de Fertilidad por Zonas', fontsize=14, fontweight='bold')
    ax.set_xlabel('Longitud')
    ax.set_ylabel('Latitud')
    ax.grid(True, alpha=0.3)
    
    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label('Índice de Fertilidad', fontsize=12)
    
    plt.tight_layout()
    return fig

def crear_visualizacion_npk(zonas, recomendaciones_npk, nutriente='N'):
    """Crea visualización de recomendaciones NPK"""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Definir colormap según nutriente
    if nutriente == 'N':
        cmap = plt.cm.Greens
        titulo = 'Nitrógeno (N)'
        columna = 'N'
    elif nutriente == 'P':
        cmap = plt.cm.Blues
        titulo = 'Fósforo (P)'
        columna = 'P'
    else:
        cmap = plt.cm.Oranges
        titulo = 'Potasio (K)'
        columna = 'K'
    
    # Normalizar valores
    valores = [rec[columna] for rec in recomendaciones_npk]
    vmin, vmax = min(valores), max(valores)
    if vmin == vmax:
        vmin, vmax = 0, vmax * 1.1
    
    # Dibujar cada zona
    for zona, rec in zip(zonas, recomendaciones_npk):
        valor_norm = (rec[columna] - vmin) / (vmax - vmin)
        color = cmap(valor_norm)
        
        # Obtener coordenadas
        if hasattr(zona['geometry'], 'exterior'):
            coords = list(zona['geometry'].exterior.coords)
        else:
            coords = list(zona['geometry'].coords)
        
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        
        ax.fill(x_coords, y_coords, color=color, alpha=0.7, edgecolor='black', linewidth=1)
        
        # Etiqueta con valor
        centroid = zona['centroid']
        ax.text(centroid.x, centroid.y, f"{rec[columna]:.0f}",
                ha='center', va='center', fontsize=9, color='white',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
    
    ax.set_title(f'Recomendaciones de {titulo} (kg/ha)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Longitud')
    ax.set_ylabel('Latitud')
    ax.grid(True, alpha=0.3)
    
    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label(f'{titulo} (kg/ha)', fontsize=12)
    
    plt.tight_layout()
    return fig

# ===== FUNCIONES PARA CARGAR ARCHIVOS GEOGRÁFICOS =====
def procesar_kml(kml_bytes):
    """Procesa archivo KML"""
    try:
        # Guardar temporalmente el archivo
        with tempfile.NamedTemporaryFile(suffix='.kml', delete=False) as tmp_file:
            tmp_file.write(kml_bytes)
            tmp_file.flush()
            
            try:
                gdf = gpd.read_file(tmp_file.name, driver='KML')
            except:
                # Intentar con encoding diferente
                gdf = gpd.read_file(tmp_file.name, driver='KML', encoding='utf-8')
        
        # Limpiar archivo temporal
        os.unlink(tmp_file.name)
        
        if gdf.empty:
            st.warning("El archivo KML no contiene geometrías válidas")
            return None
        
        # Buscar polígonos en el GeoDataFrame
        for geom in gdf.geometry:
            if geom.geom_type == 'Polygon':
                return geom
            elif geom.geom_type == 'MultiPolygon':
                # Tomar el polígono más grande
                polygons = list(geom.geoms)
                return max(polygons, key=lambda p: p.area)
            elif geom.geom_type == 'GeometryCollection':
                # Buscar polígonos en la colección
                for subgeom in geom.geoms:
                    if subgeom.geom_type == 'Polygon':
                        return subgeom
        
        # Si no encuentra polígono, intentar crear uno a partir de puntos
        st.warning("No se encontraron polígonos en el KML. Creando polígono convexo...")
        puntos = []
        for geom in gdf.geometry:
            if geom.geom_type == 'Point':
                puntos.append((geom.x, geom.y))
            elif geom.geom_type == 'LineString':
                puntos.extend(list(geom.coords))
        
        if len(puntos) >= 3:
            from shapely.geometry import MultiPoint
            multipoint = MultiPoint(puntos)
            return multipoint.convex_hull
        
        return None
        
    except Exception as e:
        st.error(f"Error procesando KML: {str(e)}")
        return None

def procesar_kmz(kmz_bytes):
    """Procesa archivo KMZ (KML comprimido)"""
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix='.kmz', delete=False) as tmp_file:
            tmp_file.write(kmz_bytes)
            tmp_file.flush()
            
            # Descomprimir KMZ
            with zipfile.ZipFile(tmp_file.name, 'r') as kmz_zip:
                # Buscar archivos KML dentro del KMZ
                kml_files = [f for f in kmz_zip.namelist() if f.lower().endswith('.kml')]
                
                if not kml_files:
                    st.error("No se encontró archivo KML dentro del KMZ")
                    return None
                
                # Tomar el primer archivo KML
                kml_content = kmz_zip.read(kml_files[0])
                
                # Procesar como KML
                return procesar_kml(kml_content)
    
    except Exception as e:
        st.error(f"Error procesando KMZ: {str(e)}")
        return None
    finally:
        # Limpiar archivo temporal
        if 'tmp_file' in locals():
            os.unlink(tmp_file.name)

def procesar_shapefile_zip(zip_bytes):
    """Procesa Shapefile comprimido en ZIP"""
    try:
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Guardar ZIP
            zip_path = os.path.join(tmp_dir, 'shapefile.zip')
            with open(zip_path, 'wb') as f:
                f.write(zip_bytes)
            
            # Descomprimir
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # Buscar archivo .shp
            shp_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.shp')]
            
            if not shp_files:
                st.error("No se encontró archivo .shp en el ZIP")
                return None
            
            # Leer shapefile con geopandas
            shp_path = os.path.join(tmp_dir, shp_files[0])
            gdf = gpd.read_file(shp_path)
            
            if gdf.empty:
                st.warning("El Shapefile no contiene geometrías válidas")
                return None
            
            # Combinar todas las geometrías en un solo polígono
            poligonos = []
            for geom in gdf.geometry:
                if geom.geom_type == 'Polygon':
                    poligonos.append(geom)
                elif geom.geom_type == 'MultiPolygon':
                    poligonos.extend(list(geom.geoms))
            
            if not poligonos:
                st.warning("No se encontraron polígonos en el Shapefile")
                return None
            
            # Unir todos los polígonos
            if len(poligonos) == 1:
                poligono_final = poligonos[0]
            else:
                poligono_final = unary_union(poligonos)
            
            # Simplificar geometría si es necesario
            if poligono_final.geom_type == 'MultiPolygon':
                # Tomar el polígono más grande
                polygons = list(poligono_final.geoms)
                poligono_final = max(polygons, key=lambda p: p.area)
            
            # Reprojectar a WGS84 si es necesario
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf_wgs84 = gdf.to_crs(epsg=4326)
                poligono_final = gdf_wgs84.geometry.unary_union
            
            return poligono_final
            
    except Exception as e:
        st.error(f"Error procesando Shapefile: {str(e)}")
        return None

def procesar_archivo_geografico(archivo_subido):
    """Procesa archivos KML, KMZ o Shapefile (ZIP) y extrae polígonos"""
    
    try:
        # Leer el archivo cargado como bytes
        bytes_data = archivo_subido.getvalue()
        
        # Detectar tipo de archivo por extensión
        nombre_archivo = archivo_subido.name.lower()
        
        if nombre_archivo.endswith('.kml'):
            return procesar_kml(bytes_data)
        elif nombre_archivo.endswith('.kmz'):
            return procesar_kmz(bytes_data)
        elif nombre_archivo.endswith('.zip'):
            return procesar_shapefile_zip(bytes_data)
        else:
            st.error(f"Formato no soportado: {nombre_archivo}")
            return None
            
    except Exception as e:
        st.error(f"Error al procesar archivo: {str(e)}")
        return None

def cargar_poligono_desde_archivo():
    """Interfaz para cargar polígono desde archivo"""
    
    st.markdown("### 📁 Cargar Polígono desde Archivo")
    
    # Widget para subir archivo
    archivo_subido = st.file_uploader(
        "Seleccionar archivo",
        type=['kml', 'kmz', 'zip'],
        help="Formatos soportados: KML, KMZ, Shapefile (ZIP)"
    )
    
    if archivo_subido is not None:
        # Mostrar información del archivo
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(f"**Archivo:** {archivo_subido.name}")
        with col_info2:
            st.info(f"**Tamaño:** {archivo_subido.size / 1024:.1f} KB")
        
        # Procesar archivo
        with st.spinner("Procesando archivo..."):
            poligono = procesar_archivo_geografico(archivo_subido)
            
            if poligono is not None:
                st.success(f"✅ Polígono cargado exitosamente")
                
                # Calcular área aproximada
                gdf_temp = gpd.GeoDataFrame({'geometry': [poligono]}, crs='EPSG:4326')
                area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000
                
                st.metric("Área aproximada", f"{area_ha:.2f} ha")
                
                # Botón para usar este polígono
                if st.button("🗺️ Usar este Polígono en el Análisis", type="primary"):
                    st.session_state.poligono = poligono
                    st.rerun()
                
                # Mostrar vista previa en mapa pequeño
                st.markdown("**Vista previa:**")
                mapa_preview = crear_mapa_interactivo(poligono, zoom_start=12)
                st_folium(mapa_preview, width=400, height=300)
                
                return poligono
            else:
                st.error("No se pudo extraer un polígono válido del archivo")
    
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
    
    # Fechas
    fecha_fin = st.date_input("Fecha fin", datetime.now())
    fecha_inicio = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    
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

    # Carga de archivos geográficos
    st.markdown("---")
    st.markdown("### 📁 CARGAR POLÍGONO")
    
    # Opción para cargar desde archivo
    cargar_desde_archivo = st.checkbox("Cargar polígono desde archivo", value=False)

    if cargar_desde_archivo:
        poligono_cargado = cargar_poligono_desde_archivo()
        if poligono_cargado:
            st.session_state.poligono = poligono_cargado

# ===== SECCIÓN DE MAPA INTERACTIVO =====
st.markdown("## 🗺️ Mapa Interactivo de la Parcela")

# Inicializar polígono en session_state si no existe
if 'poligono' not in st.session_state:
    st.session_state.poligono = None

# Crear columnas para mapa y controles
col_mapa, col_controles = st.columns([3, 1])

with col_mapa:
    # Crear mapa
    mapa = crear_mapa_interactivo(st.session_state.poligono)
    
    # Mostrar mapa y capturar dibujos
    mapa_output = st_folium(
        mapa,
        width=800,
        height=500,
        key="mapa_parcela"
    )
    
    # Actualizar polígono si se dibujó uno nuevo
    if mapa_output and mapa_output.get('last_active_drawing'):
        drawing = mapa_output['last_active_drawing']
        if drawing['geometry']['type'] == 'Polygon':
            coords = drawing['geometry']['coordinates'][0]
            st.session_state.poligono = Polygon(coords)
            st.success("✅ Polígono actualizado desde el mapa")

with col_controles:
    st.markdown("### ✏️ Controles")
    
    # Botón para usar parcela de ejemplo
    if st.button("📍 Ejemplo Colombia", use_container_width=True):
        coords = [(-74.10, 4.65), (-74.05, 4.65), (-74.05, 4.60), (-74.10, 4.60)]
        st.session_state.poligono = Polygon(coords)
        st.rerun()
    
    # Botón para limpiar parcela
    if st.button("🗑️ Limpiar Parcela", use_container_width=True):
        st.session_state.poligono = None
        st.rerun()
    
    st.markdown("---")
    
    # Carga de archivos en la sección del mapa
    st.markdown("### 📤 Importar desde Archivo")
    archivo_subido = st.file_uploader(
        "Cargar KML/KMZ/Shapefile",
        type=['kml', 'kmz', 'zip'],
        help="Sube un archivo con la geometría de tu parcela",
        key="file_uploader_map"
    )

    if archivo_subido:
        with st.spinner("Procesando archivo..."):
            poligono = procesar_archivo_geografico(archivo_subido)
            if poligono:
                st.session_state.poligono = poligono
                st.success("✅ Polígono cargado exitosamente")
                st.rerun()
            else:
                st.error("❌ No se pudo procesar el archivo")
    
    st.markdown("---")
    st.markdown("**Información de la parcela:**")
    
    if st.session_state.poligono:
        # Calcular área
        gdf_temp = gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326')
        area_ha = gdf_temp.geometry.area.iloc[0] * 111000 * 111000 / 10000  # Aproximación
        
        st.metric("Área aproximada", f"{area_ha:.2f} ha")
        st.metric("Cultivo", cultivo_seleccionado)
        st.metric("Zonas", n_zonas)
    else:
        st.info("Dibuja un polígono en el mapa, usa el ejemplo o carga un archivo")

# ===== BOTÓN DE ANÁLISIS PRINCIPAL =====
st.markdown("---")
if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
    if st.session_state.poligono is None:
        st.error("❌ Por favor, dibuja o selecciona una parcela primero")
    else:
        with st.spinner("🔬 Realizando análisis completo..."):
            # Mostrar progreso
            progress_bar = st.progress(0)
            
            # Paso 1: Obtener datos satelitales
            progress_bar.progress(10)
            st.info("Paso 1/7: Obteniendo datos satelitales...")
            
            usar_gee = '_GEE' in satelite_seleccionado and st.session_state.gee_authenticated
            indices_satelitales = None
            
            if usar_gee:
                indices_satelitales = calcular_indices_satelitales_gee(
                    satelite_seleccionado,
                    st.session_state.poligono,
                    fecha_inicio,
                    fecha_fin
                )
                # Si no se obtuvieron datos de GEE, usar simulados
                if indices_satelitales is None:
                    st.warning("No se pudieron obtener datos de GEE. Usando datos simulados.")
                    usar_gee = False
            
            if not usar_gee:
                # Datos simulados si no hay GEE o si GEE falló
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
            indices_fertilidad = analizar_fertilidad_zonas(zonas, indices_satelitales, cultivo_seleccionado)
            
            # Paso 4: Calcular recomendaciones NPK
            progress_bar.progress(50)
            st.info("Paso 4/7: Calculando recomendaciones NPK...")
            recomendaciones_npk = calcular_recomendaciones_npk_mejorado(
                indices_fertilidad, 
                cultivo_seleccionado, 
                textura_suelo
            )
            
            # Paso 5: Calcular proyecciones de cosecha
            progress_bar.progress(65)
            st.info("Paso 5/7: Calculando proyecciones...")
            proyecciones = calcular_proyecciones_cosecha(indices_fertilidad, recomendaciones_npk, cultivo_seleccionado)
            
            # Paso 6: Generar DEM y análisis topográfico
            progress_bar.progress(80)
            st.info("Paso 6/7: Generando análisis topográfico...")
            X, Y, Z = generar_dem_sintetico_mejorado(100, 100, complejidad=2)
            pendientes = calcular_pendiente_mejorado(Z)
            
            # Paso 7: Preparar visualizaciones
            progress_bar.progress(95)
            st.info("Paso 7/7: Generando reportes...")
            
            # Guardar resultados en session_state
            st.session_state.resultados_analisis = {
                'indices_satelitales': indices_satelitales,
                'zonas': zonas,
                'indices_fertilidad': indices_fertilidad,
                'recomendaciones_npk': recomendaciones_npk,
                'proyecciones': proyecciones,
                'dem': {'X': X, 'Y': Y, 'Z': Z, 'pendientes': pendientes},
                'cultivo': cultivo_seleccionado,
                'textura_suelo': textura_suelo,
                'precipitacion': precipitacion,
                'area_total': gpd.GeoDataFrame({'geometry': [st.session_state.poligono]}, crs='EPSG:4326').geometry.area.iloc[0] * 111000 * 111000 / 10000
            }
            
            progress_bar.progress(100)
            st.success("✅ Análisis completado exitosamente!")

# ===== MOSTRAR RESULTADOS SI EXISTEN =====
if 'resultados_analisis' in st.session_state:
    resultados = st.session_state.resultados_analisis
    
    # Crear pestañas para diferentes secciones
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Resumen General",
        "🌿 Fertilidad",
        "🧪 Recomendaciones NPK",
        "📈 Proyecciones",
        "🏔️ Topografía",
        "📋 Reporte Completo"
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
            fuente = resultados['indices_satelitales'].get('fuente', 'No disponible')
            fecha = resultados['indices_satelitales'].get('fecha', 'No disponible')
            resolucion = resultados['indices_satelitales'].get('resolucion', 'N/A')
            
            st.markdown(f"""
            **🛰️ Fuente de datos:** {fuente}
            **📅 Fecha datos:** {fecha}
            **🎯 Resolución:** {resolucion}
            **🏜️ Textura suelo:** {resultados['textura_suelo']}
            """)
        
        # Mapa de ubicación
        st.markdown("### 🗺️ Ubicación de la Parcela")
        mapa_resumen = crear_mapa_interactivo(st.session_state.poligono, zoom_start=13)
        st_folium(mapa_resumen, width=800, height=400)
    
    with tab2:
        st.markdown("## 🌿 ANÁLISIS DE FERTILIDAD POR ZONAS")
        
        # Visualización de fertilidad
        st.markdown("### 🎨 Mapa de Fertilidad")
        fig_fert = crear_visualizacion_fertilidad(resultados['zonas'], resultados['indices_fertilidad'])
        st.pyplot(fig_fert)
        
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
        st.markdown("## 🧪 RECOMENDACIONES DE FERTILIZACIÓN NPK")
        
        # Mapas de recomendaciones
        st.markdown("### 🗺️ Mapas de Recomendaciones")
        
        col_n, col_p, col_k = st.columns(3)
        
        with col_n:
            st.markdown("#### **Nitrógeno (N)**")
            fig_n = crear_visualizacion_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'N')
            st.pyplot(fig_n)
        
        with col_p:
            st.markdown("#### **Fósforo (P)**")
            fig_p = crear_visualizacion_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'P')
            st.pyplot(fig_p)
        
        with col_k:
            st.markdown("#### **Potasio (K)**")
            fig_k = crear_visualizacion_npk(resultados['zonas'], resultados['recomendaciones_npk'], 'K')
            st.pyplot(fig_k)
        
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
    
    with tab4:
        st.markdown("## 📈 PROYECCIONES DE COSECHA")
        
        # Gráfico de proyecciones
        st.markdown("### 📊 Comparativa de Rendimientos")
        
        fig_proy, ax = plt.subplots(figsize=(10, 6))
        
        zonas_ids = [f"Z{idx['id_zona']}" for idx in resultados['indices_fertilidad']]
        rend_base = [proy['rendimiento_base'] for proy in resultados['proyecciones']]
        rend_fert = [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]
        
        x = np.arange(len(zonas_ids))
        width = 0.35
        
        ax.bar(x - width/2, rend_base, width, label='Sin Fertilización', color='#ff9999')
        ax.bar(x + width/2, rend_fert, width, label='Con Fertilización', color='#66b3ff')
        
        ax.set_xlabel('Zona')
        ax.set_ylabel('Rendimiento (kg/ha)')
        ax.set_title('Proyecciones de Rendimiento por Zona')
        ax.set_xticks(x)
        ax.set_xticklabels(zonas_ids, rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig_proy)
        
        # Análisis económico
        st.markdown("### 💰 Análisis Económico")
        
        precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
        rend_total_base = sum(rend_base) * resultados['area_total'] / len(rend_base)
        rend_total_fert = sum(rend_fert) * resultados['area_total'] / len(rend_fert)
        
        ingreso_base = rend_total_base * precio
        ingreso_fert = rend_total_fert * precio
        
        # Costos estimados de fertilización
        costo_n_kg = 1.2  # USD por kg de N
        costo_p_kg = 2.5  # USD por kg de P2O5
        costo_k_kg = 1.8  # USD por kg de K2O
        
        costo_total = (total_n * costo_n_kg + total_p * costo_p_kg + total_k * costo_k_kg)
        
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
    
    with tab5:
        st.markdown("## 🏔️ ANÁLISIS TOPOGRÁFICO")
        
        # DEM y pendientes
        st.markdown("### 🗺️ Modelo Digital de Elevaciones")
        
        fig_dem, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # DEM
        im1 = ax1.imshow(resultados['dem']['Z'], cmap='terrain', aspect='auto')
        ax1.set_title('Modelo Digital de Elevaciones')
        ax1.set_xlabel('X (m)')
        ax1.set_ylabel('Y (m)')
        plt.colorbar(im1, ax=ax1, label='Elevación (m)')
        
        # Pendientes
        im2 = ax2.imshow(resultados['dem']['pendientes'], cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=30)
        ax2.set_title('Mapa de Pendientes')
        ax2.set_xlabel('X (m)')
        ax2.set_ylabel('Y (m)')
        plt.colorbar(im2, ax=ax2, label='Pendiente (%)')
        
        plt.tight_layout()
        st.pyplot(fig_dem)
        
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
        
        # Curvas de nivel
        st.markdown("### 🗺️ Curvas de Nivel")
        
        fig_curvas, ax = plt.subplots(figsize=(10, 8))
        
        # Contour plot
        contour = ax.contour(resultados['dem']['X'], resultados['dem']['Y'], resultados['dem']['Z'], 
                            levels=10, colors='black', linewidths=0.5)
        ax.clabel(contour, inline=True, fontsize=8)
        
        # Fill contour
        ax.contourf(resultados['dem']['X'], resultados['dem']['Y'], resultados['dem']['Z'], 
                   levels=10, cmap='terrain', alpha=0.7)
        
        ax.set_title('Curvas de Nivel')
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig_curvas)
        
        # Recomendaciones topográficas
        st.markdown("### 💡 Recomendaciones Topográficas")
        
        if pendiente_prom < 5:
            st.success("""
            **✅ Condiciones óptimas para agricultura:**
            - Pendientes suaves (<5%) permiten buen drenaje sin riesgo significativo de erosión
            - Puedes implementar sistemas de riego convencionales
            - Mínima necesidad de obras de conservación de suelos
            """)
        elif pendiente_prom < 10:
            st.warning("""
            **⚠️ Pendientes moderadas (5-10%):**
            - Recomendado implementar cultivos en contorno
            - Considerar terrazas de base ancha para cultivos anuales
            - Mantener cobertura vegetal para prevenir erosión
            - Evitar labranza intensiva en dirección de la pendiente
            """)
        else:
            st.error("""
            **🚨 Pendientes pronunciadas (>10%):**
            - Alto riesgo de erosión - implementar medidas de conservación inmediatas
            - Recomendado: Terrazas, cultivos en fajas, barreras vivas
            - Considerar cultivos permanentes o agroforestería
            - Evitar cultivos anuales sin medidas de conservación
            - Consultar con especialista en conservación de suelos
            """)
    
    with tab6:
        st.markdown("## 📋 REPORTE COMPLETO")
        
        # Generar reporte ejecutivo
        st.markdown("### 📄 Reporte Ejecutivo")
        
        # Calcular ROI
        try:
            precio = PARAMETROS_CULTIVOS[resultados['cultivo']]['PRECIO_VENTA']
            rend_total_fert = sum([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]) * resultados['area_total'] / len(resultados['proyecciones'])
            costo_total = (total_n * 1.2 + total_p * 2.5 + total_k * 1.8) * resultados['area_total'] / len(resultados['recomendaciones_npk'])
            roi_estimado = ((rend_total_fert * precio) - costo_total) / costo_total * 100 if costo_total > 0 else 0
        except:
            roi_estimado = 0
        
        reporte_html = f"""
        <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)); 
                    border-radius: 20px; padding: 25px; border: 1px solid rgba(59, 130, 246, 0.2); 
                    margin-bottom: 20px;">
            <h2 style="color: #ffffff; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
                📋 REPORTE DE ANÁLISIS AGRÍCOLA
            </h2>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px;">
                <div>
                    <h3 style="color: #93c5fd;">📊 DATOS GENERALES</h3>
                    <p><strong>Cultivo:</strong> {resultados['cultivo']} {PARAMETROS_CULTIVOS[resultados['cultivo']]['icono']}</p>
                    <p><strong>Área total:</strong> {resultados['area_total']:.2f} ha</p>
                    <p><strong>Zonas de manejo:</strong> {len(resultados['zonas'])}</p>
                    <p><strong>Textura del suelo:</strong> {resultados['textura_suelo']}</p>
                    <p><strong>Precipitación:</strong> {resultados['precipitacion']} mm/año</p>
                </div>
                
                <div>
                    <h3 style="color: #93c5fd;">🛰️ DATOS SATELITALES</h3>
                    <p><strong>Fuente:</strong> {resultados['indices_satelitales'].get('fuente', 'No disponible')}</p>
                    <p><strong>Fecha:</strong> {resultados['indices_satelitales'].get('fecha', 'No disponible')}</p>
                    <p><strong>NDVI promedio:</strong> {np.mean([idx['ndvi'] for idx in resultados['indices_fertilidad']]):.3f}</p>
                    <p><strong>Fertilidad promedio:</strong> {np.mean([idx['indice_fertilidad'] for idx in resultados['indices_fertilidad']]):.3f}</p>
                </div>
            </div>
            
            <div style="margin-top: 30px;">
                <h3 style="color: #93c5fd;">🎯 RECOMENDACIONES PRINCIPALES</h3>
                <ul>
                    <li><strong>Fertilización diferenciada:</strong> Aplicar dosis variables según zona</li>
                    <li><strong>Manejo de pendientes:</strong> {"Implementar medidas de conservación" if np.mean(resultados['dem']['pendientes'].flatten()) > 10 else "Condiciones favorables"}</li>
                    <li><strong>Rendimiento esperado:</strong> {np.mean([proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']]):.0f} kg/ha</li>
                    <li><strong>ROI estimado:</strong> {roi_estimado:.1f}%</li>
                </ul>
            </div>
        </div>
        """
        
        st.markdown(reporte_html, unsafe_allow_html=True)
        
        # Opciones de exportación
        st.markdown("### 💾 Exportar Resultados")
        
        col_exp1, col_exp2, col_exp3 = st.columns(3)
        
        with col_exp1:
            # Crear DataFrame combinado
            df_completo = pd.DataFrame({
                'Zona': [f"Z{idx['id_zona']}" for idx in resultados['indices_fertilidad']],
                'Area_ha': [resultados['area_total'] / len(resultados['zonas'])] * len(resultados['zonas']),
                'Materia_Organica_%': [idx['materia_organica'] for idx in resultados['indices_fertilidad']],
                'Humedad': [idx['humedad'] for idx in resultados['indices_fertilidad']],
                'NDVI': [idx['ndvi'] for idx in resultados['indices_fertilidad']],
                'Indice_Fertilidad': [idx['indice_fertilidad'] for idx in resultados['indices_fertilidad']],
                'N_kg_ha': [rec['N'] for rec in resultados['recomendaciones_npk']],
                'P_kg_ha': [rec['P'] for rec in resultados['recomendaciones_npk']],
                'K_kg_ha': [rec['K'] for rec in resultados['recomendaciones_npk']],
                'Rendimiento_Base_kg_ha': [proy['rendimiento_base'] for proy in resultados['proyecciones']],
                'Rendimiento_Fert_kg_ha': [proy['rendimiento_fertilizado'] for proy in resultados['proyecciones']],
                'Incremento_%': [proy['incremento'] for proy in resultados['proyecciones']]
            })
            
            csv = df_completo.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"analisis_{resultados['cultivo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            # Generar PDF (simulado)
            if st.button("📄 Generar Reporte PDF", use_container_width=True):
                st.info("Función de generación de PDF en desarrollo. Por ahora, use CSV o tome capturas de pantalla.")
        
        with col_exp3:
            if st.button("🗑️ Limpiar Resultados", use_container_width=True):
                del st.session_state.resultados_analisis
                st.rerun()

# ===== PIE DE PÁGINA =====
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #94a3b8; padding: 20px;">
    <p><strong>🌾 Analizador Multicultivo Satelital con Google Earth Engine</strong></p>
    <p>Versión 3.0 | Desarrollado por Martin Ernesto Cano | Ingeniero Agrónomo</p>
    <p>📧 mawucano@gmail.com | 📱 +5493525 532313</p>
    <p>© 2024 - Todos los derechos reservados</p>
</div>
""", unsafe_allow_html=True)
