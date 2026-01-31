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

# Importar Sentinel Hub si está disponible
try:
    from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, \
        MimeType, BBox, CRS, bbox_to_dimensions, Geometry
    SENTINEL_HUB_AVAILABLE = True
except ImportError:
    SENTINEL_HUB_AVAILABLE = False
    st.warning("⚠️ Sentinel Hub no está instalado. Para usar datos satelitales reales, instala con: pip install sentinelhub")

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
if 'sh_config' not in st.session_state:
    st.session_state.sh_config = None
if 'sentinel_authenticated' not in st.session_state:
    st.session_state.sentinel_authenticated = False
if 'sh_client_id' not in st.session_state:
    st.session_state.sh_client_id = ''
if 'sh_client_secret' not in st.session_state:
    st.session_state.sh_client_secret = ''
if 'sh_instance_id' not in st.session_state:
    st.session_state.sh_instance_id = ''

# === CONFIGURACIÓN DE SENTINEL HUB CON CREDENCIALES INCLUIDAS ===
def configurar_sentinel_hub_predefinido():
    """Configurar Sentinel Hub con credenciales incluidas en el código"""
    if not SENTINEL_HUB_AVAILABLE:
        return None
    
    try:
        config = SHConfig()
        
        # ⚠️ ⚠️ ⚠️ IMPORTANTE: REEMPLAZA ESTAS CREDENCIALES CON LAS TUS ⚠️ ⚠️ ⚠️
        # ⚠️ Obtén tus credenciales de: https://apps.sentinel-hub.com/dashboard/
        
        # Client ID de Sentinel Hub
        config.sh_client_id = 854eeebf-f870-484a-96f4-d23d49b5f071
        
        # Client Secret de Sentinel Hub
        config.sh_client_secret = 23729a0d-75f6-478b-8304-c8bb2bfbe71d
        
        # Instance ID de Sentinel Hub
        config.instance_id = PLAK91bbe43a22834a5ca2c6cee7ebd97105
        
        # Verificar que las credenciales no sean las de ejemplo
        if (config.sh_client_id == 'TU_CLIENT_ID_AQUI' or 
            config.sh_client_secret == 'TU_CLIENT_SECRET_AQUI' or
            config.instance_id == 'TU_INSTANCE_ID_AQUI'):
            st.warning("⚠️ Credenciales de Sentinel Hub no configuradas. Usa tus credenciales reales.")
            return None
        
        return config
    except Exception as e:
        st.error(f"❌ Error configurando Sentinel Hub: {str(e)}")
        return None

# === ESTILOS PERSONALIZADOS - VERSIÓN PREMIUM MODERNA ===
st.markdown("""
<style>
/* === FONDO GENERAL OSCURO ELEGANTE === */
.stApp {
background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
color: #ffffff !important;
font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
/* === SIDEBAR: FONDO BLANCO CON TEXTO NEGRO === */
[data-testid="stSidebar"] {
background: #ffffff !important;
border-right: 1px solid #e5e7eb !important;
box-shadow: 5px 0 25px rgba(0, 0, 0, 0.1) !important;
}
/* Texto general del sidebar en NEGRO */
[data-testid="stSidebar"] *,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stText,
[data-testid="stSidebar"] .stTitle,
[data-testid="stSidebar"] .stSubheader {
color: #000000 !important;
text-shadow: none !important;
}
/* Título del sidebar elegante */
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
/* Widgets del sidebar con estilo glassmorphism */
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stDateInput,
[data-testid="stSidebar"] .stSlider {
background: rgba(255, 255, 255, 0.9) !important;
backdrop-filter: blur(10px);
border-radius: 12px;
padding: 12px;
margin: 8px 0;
border: 1px solid #d1d5db !important;
}
/* Labels de los widgets en negro */
[data-testid="stSidebar"] .stSelectbox div,
[data-testid="stSidebar"] .stDateInput div,
[data-testid="stSidebar"] .stSlider label {
color: #000000 !important;
font-weight: 600;
font-size: 0.95em;
}
/* Inputs y selects - fondo blanco con texto negro */
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
background-color: #ffffff !important;
border: 1px solid #d1d5db !important;
color: #000000 !important;
border-radius: 8px;
}
/* Slider - colores negro */
[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
color: #000000 !important;
}
/* Date Input - fondo blanco con texto negro */
[data-testid="stSidebar"] .stDateInput [data-baseweb="input"] {
background-color: #ffffff !important;
border: 1px solid #d1d5db !important;
color: #000000 !important;
border-radius: 8px;
}
/* Placeholder en gris */
[data-testid="stSidebar"] .stDateInput [data-baseweb="input"]::placeholder {
color: #6b7280 !important;
}
/* Botones premium */
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
/* === HERO BANNER PRINCIPAL CON IMAGEN === */
.hero-banner {
background: linear-gradient(rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.95)),
url('https://images.unsplash.com/photo-1597981309443-6e2d2a4d9c3f?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=2070&q=80') !important;
background-size: cover !important;
background-position: center 40% !important;
padding: 3.5em 2em !important;
border-radius: 24px !important;
margin-bottom: 2.5em !important;
box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4) !important;
border: 1px solid rgba(59, 130, 246, 0.2) !important;
position: relative !important;
overflow: hidden !important;
}
.hero-banner::before {
content: '' !important;
position: absolute !important;
top: 0 !important;
left: 0 !important;
right: 0 !important;
bottom: 0 !important;
background: linear-gradient(45deg, rgba(59, 130, 246, 0.1), rgba(29, 78, 216, 0.05)) !important;
z-index: 1 !important;
}
.hero-content {
position: relative !important;
z-index: 2 !important;
text-align: center !important;
}
.hero-title {
color: #ffffff !important;
font-size: 3.2em !important;
font-weight: 900 !important;
margin-bottom: 0.3em !important;
text-shadow: 0 4px 12px rgba(0, 0, 0, 0.6) !important;
letter-spacing: -0.5px !important;
background: linear-gradient(135deg, #ffffff 0%, #93c5fd 100%) !important;
-webkit-background-clip: text !important;
-webkit-text-fill-color: transparent !important;
background-clip: text !important;
}
.hero-subtitle {
color: #cbd5e1 !important;
font-size: 1.3em !important;
font-weight: 400 !important;
max-width: 800px !important;
margin: 0 auto !important;
line-height: 1.6 !important;
}
/* === PESTAÑAS PRINCIPALES (fuera del sidebar) - SIN CAMBIOS === */
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
/* === PESTAÑAS DEL SIDEBAR: FONDO BLANCO + TEXTO NEGRO === */
[data-testid="stSidebar"] .stTabs [data-baseweb="tab-list"] {
background: #ffffff !important;
border: 1px solid #e2e8f0 !important;
padding: 8px !important;
border-radius: 12px !important;
gap: 6px !important;
}
[data-testid="stSidebar"] .stTabs [data-baseweb="tab"] {
color: #000000 !important;
background: transparent !important;
border-radius: 8px !important;
padding: 8px 16px !important;
font-weight: 600 !important;
border: 1px solid transparent !important;
}
[data-testid="stSidebar"] .stTabs [data-baseweb="tab"]:hover {
background: #f1f5f9 !important;
color: #000000 !important;
border-color: #cbd5e1 !important;
}
/* Pestaña activa en el sidebar: blanco con texto negro */
[data-testid="stSidebar"] .stTabs [aria-selected="true"] {
background: #ffffff !important;
color: #000000 !important;
font-weight: 700 !important;
border: 1px solid #3b82f6 !important;
}
/* === MÉTRICAS PREMIUM === */
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
div[data-testid="metric-container"] label,
div[data-testid="metric-container"] div,
div[data-testid="metric-container"] [data-testid="stMetricValue"],
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
color: #ffffff !important;
font-weight: 600 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
font-size: 2.5em !important;
font-weight: 800 !important;
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
-webkit-background-clip: text !important;
-webkit-text-fill-color: transparent !important;
background-clip: text !important;
}
/* === GRÁFICOS CON ESTILO OSCURO === */
.stPlotlyChart, .stPyplot {
background: rgba(15, 23, 42, 0.8) !important;
backdrop-filter: blur(10px) !important;
border-radius: 20px !important;
padding: 20px !important;
box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
border: 1px solid rgba(59, 130, 246, 0.2) !important;
}
/* === EXPANDERS ELEGANTES === */
.streamlit-expanderHeader {
color: #ffffff !important;
background: rgba(30, 41, 59, 0.8) !important;
backdrop-filter: blur(10px) !important;
border-radius: 16px !important;
font-weight: 700 !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
padding: 16px 20px !important;
margin-bottom: 10px !important;
}
.streamlit-expanderContent {
background: rgba(15, 23, 42, 0.6) !important;
border-radius: 0 0 16px 16px !important;
padding: 20px !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
border-top: none !important;
}
/* === TEXTOS GENERALES === */
h1, h2, h3, h4, h5, h6 {
color: #ffffff !important;
font-weight: 800 !important;
margin-top: 1.5em !important;
}
p, div, span, label, li {
color: #cbd5e1 !important;
line-height: 1.7 !important;
}
/* === DATA FRAMES TABLAS ELEGANTES === */
.dataframe {
background: rgba(15, 23, 42, 0.8) !important;
backdrop-filter: blur(10px) !important;
border-radius: 16px !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
color: #ffffff !important;
}
.dataframe th {
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
color: #ffffff !important;
font-weight: 700 !important;
padding: 16px !important;
}
.dataframe td {
color: #cbd5e1 !important;
padding: 14px 16px !important;
border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
}
/* === ALERTS Y MENSAJES === */
.stAlert {
border-radius: 16px !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
backdrop-filter: blur(10px) !important;
}
/* === SCROLLBAR PERSONALIZADA === */
::-webkit-scrollbar {
width: 10px !important;
height: 10px !important;
}
::-webkit-scrollbar-track {
background: rgba(15, 23, 42, 0.8) !important;
border-radius: 10px !important;
}
::-webkit-scrollbar-thumb {
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
border-radius: 10px !important;
}
::-webkit-scrollbar-thumb:hover {
background: linear-gradient(135deg, #4f8df8 0%, #2d5fe8 100%) !important;
}
/* === TARJETAS DE CULTIVOS === */
.cultivo-card {
background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)) !important;
border-radius: 20px !important;
padding: 25px !important;
border: 1px solid rgba(59, 130, 246, 0.2) !important;
box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
transition: all 0.3s ease !important;
height: 100% !important;
}
.cultivo-card:hover {
transform: translateY(-8px) !important;
box-shadow: 0 20px 40px rgba(59, 130, 246, 0.2) !important;
border-color: rgba(59, 130, 246, 0.4) !important;
}
/* === TABLERO DE CONTROL === */
.dashboard-grid {
display: grid !important;
grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
gap: 25px !important;
margin: 30px 0 !important;
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
/* === STATS BADGES === */
.stats-badge {
display: inline-block !important;
padding: 6px 14px !important;
border-radius: 50px !important;
font-size: 0.85em !important;
font-weight: 700 !important;
margin: 2px !important;
}
.badge-success {
background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
color: white !important;
}
.badge-warning {
background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
color: white !important;
}
.badge-danger {
background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
color: white !important;
}
.badge-info {
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ===== HERO BANNER PRINCIPAL =====
st.markdown("""
<div class="hero-banner">
<div class="hero-content">
<h1 class="hero-title">ANALIZADOR MULTI-CULTIVO SATELITAL</h1>
<p class="hero-subtitle">Potenciado con NASA POWER, Sentinel Hub y datos SRTM para agricultura de precisión</p>
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
'SENTINEL-2_REAL': {
'nombre': 'Sentinel-2 (Real)',
'resolucion': '10m',
'revisita': '5 días',
'bandas': ['B02', 'B03', 'B04', 'B05', 'B08', 'B11'],
'indices': ['NDVI', 'NDRE', 'GNDVI', 'OSAVI', 'MCARI'],
'icono': '🌍',
'requerimiento': 'Sentinel Hub'
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

# ===== CONFIGURACIÓN VARIEDADES ARGENTINAS =====
VARIEDADES_ARGENTINA = {
    'TRIGO': [
        'ACA 303', 'ACA 315', 'Baguette Premium 11', 'Baguette Premium 13', 
        'Biointa 1005', 'Biointa 2004', 'Klein Don Enrique', 'Klein Guerrero', 
        'Buck Meteoro', 'Buck Poncho', 'SY 110', 'SY 200'
    ],
    'MAIZ': [
        'DK 72-10', 'DK 73-20', 'Pioneer 30F53', 'Pioneer 30F35', 
        'Syngenta AG 6800', 'Syngenta AG 8088', 'Dow 2A610', 'Dow 2B710', 
        'Nidera 8710', 'Nidera 8800', 'Morgan 360', 'Morgan 390'
    ],
    'SORGO': [
        'Advanta AS 5405', 'Advanta AS 5505', 'Pioneer 84G62', 'Pioneer 85G96', 
        'DEKALB 53-67', 'DEKALB 55-00', 'MACER S-10', 'MACER S-15', 
        'Sorgocer 105', 'Sorgocer 110', 'Río IV 100', 'Río IV 110'
    ],
    'SOJA': [
        'DM 53i52', 'DM 58i62', 'Nidera 49X', 'Nidera 52X', 
        'Don Mario 49X', 'Don Mario 52X', 'SYNGENTA 4.9i', 'SYNGENTA 5.2i', 
        'Biosoys 4.9', 'Biosoys 5.2', 'ACA 49', 'ACA 52'
    ],
    'GIRASOL': [
        'ACA 884', 'ACA 887', 'Nidera 7120', 'Nidera 7150', 
        'Syngenta 390', 'Syngenta 410', 'Pioneer 64A15', 'Pioneer 65A25', 
        'Advanta G 100', 'Advanta G 110', 'Biosun 400', 'Biosun 420'
    ],
    'MANI': [
        'ASEM 400', 'ASEM 500', 'Granoleico', 'Guasu', 
        'Florman INTA', 'Elena', 'Colorado Irradiado', 'Overo Colorado', 
        'Runner 886', 'Runner 890', 'Tegua', 'Virginia 98R'
    ]
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
'PENDIENTE': ['#4daf4a', '#a6d96a', '#ffffbf', '#fdae61', '#f46d43', '#d73027']
}

# ===== FUNCIÓN PARA MOSTRAR INFORMACIÓN DEL CULTIVO =====
def mostrar_info_cultivo(cultivo):
    """Muestra información específica del cultivo seleccionado"""
    if cultivo in PARAMETROS_CULTIVOS:
        params = PARAMETROS_CULTIVOS[cultivo]
        
        st.markdown(f"""
        <div class="cultivo-card">
            <h3>{ICONOS_CULTIVOS[cultivo]} {cultivo} - Información Argentina</h3>
            <p><strong>Zonas principales:</strong> {', '.join(params.get('ZONAS_ARGENTINA', []))}</p>
            <p><strong>Variedades comunes:</strong></p>
            <ul>
        """, unsafe_allow_html=True)
        
        for variedad in params.get('VARIEDADES', [])[:5]:  # Mostrar solo las primeras 5
            st.markdown(f"<li>{variedad}</li>", unsafe_allow_html=True)
        
        if len(params.get('VARIEDADES', [])) > 5:
            st.markdown(f"<li>... y {len(params.get('VARIEDADES', [])) - 5} más</li>", unsafe_allow_html=True)
        
        st.markdown("""
            </ul>
        </div>
        """, unsafe_allow_html=True)

# ===== FUNCIONES SENTINEL HUB =====
def configurar_sentinel_hub(client_id=None, client_secret=None, instance_id=None):
    """Configurar Sentinel Hub con credenciales (manual o automática)"""
    if not SENTINEL_HUB_AVAILABLE:
        return None
    
    try:
        config = SHConfig()
        
        # Si se proporcionan credenciales manualmente, usarlas
        if client_id and client_secret and instance_id:
            config.sh_client_id = client_id
            config.sh_client_secret = client_secret
            config.instance_id = instance_id
        else:
            # Usar las credenciales predefinidas
            config_predefinido = configurar_sentinel_hub_predefinido()
            if config_predefinido:
                return config_predefinido
            else:
                return None
                
        return config
    except Exception as e:
        st.error(f"❌ Error configurando Sentinel Hub: {str(e)}")
        return None

def verificar_autenticacion_sentinel_hub(config):
    """Verificar si las credenciales de Sentinel Hub son válidas"""
    if not SENTINEL_HUB_AVAILABLE or config is None:
        return False
    
    try:
        # Intentar una solicitud simple para verificar las credenciales
        bbox = BBox(bbox=[-58.5, -34.6, -58.4, -34.5], crs=CRS.WGS84)
        size = bbox_to_dimensions(bbox, resolution=10)
        
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["B02", "B03", "B04"],
                output: { bands: 3 }
            };
        }
        function evaluatePixel(sample) {
            return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
        }
        """
        
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=("2023-01-01", "2023-01-02"),
                    maxcc=0.1  # Máximo 10% de nubes
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
            bbox=bbox,
            size=size,
            config=config
        )
        
        # Intentar obtener datos (puede fallar si las credenciales son inválidas)
        data = request.get_data()
        
        # Si llegamos aquí sin excepciones, la autenticación es exitosa
        return True
    except Exception as e:
        # Mostrar error más específico
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
            st.error("❌ Error de autenticación: Credenciales inválidas o expiradas")
        elif "403" in error_msg or "Forbidden" in error_msg:
            st.error("❌ Error de permisos: Verifica tu instance_id y permisos")
        elif "404" in error_msg:
            st.error("❌ Recurso no encontrado: Verifica tu configuración")
        else:
            st.error(f"❌ Error de conexión con Sentinel Hub: {error_msg[:200]}")
        return False

def obtener_datos_sentinel2_real(gdf, fecha_inicio, fecha_fin, config, indice='NDVI'):
    """Obtener datos reales de Sentinel-2 usando Sentinel Hub"""
    if not SENTINEL_HUB_AVAILABLE or config is None:
        return None
    
    try:
        # Obtener bounding box de la parcela
        bounds = gdf.total_bounds
        bbox = BBox(bbox=bounds, crs=CRS.WGS84)
        
        # Configurar tamaño de imagen
        resolution = 10  # 10 metros
        size = bbox_to_dimensions(bbox, resolution=resolution)
        
        # Definir evalscript según el índice
        if indice == 'NDVI':
            evalscript = """
            //VERSION=3
            function setup() {
                return {
                    input: [{
                        bands: ["B04", "B08"],
                        units: "REFLECTANCE"
                    }],
                    output: {
                        bands: 1,
                        sampleType: "FLOAT32"
                    }
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
                    input: [{
                        bands: ["B05", "B08"],
                        units: "REFLECTANCE"
                    }],
                    output: {
                        bands: 1,
                        sampleType: "FLOAT32"
                    }
                };
            }
            function evaluatePixel(sample) {
                let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
                return [ndre];
            }
            """
        else:
            evalscript = """
            //VERSION=3
            function setup() {
                return {
                    input: [{
                        bands: ["B02", "B03", "B04", "B05", "B08", "B11"],
                        units: "REFLECTANCE"
                    }],
                    output: {
                        bands: 1,
                        sampleType: "FLOAT32"
                    }
                };
            }
            function evaluatePixel(sample) {
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                return [ndvi];
            }
            """
        
        # Crear solicitud
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(fecha_inicio.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")),
                    maxcc=0.3  # Máximo 30% de nubes
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            bbox=bbox,
            size=size,
            config=config
        )
        
        # Obtener datos
        datos = request.get_data()
        
        if datos and len(datos) > 0:
            # Procesar datos para obtener estadísticas
            datos_array = np.array(datos[0])
            datos_validos = datos_array[~np.isnan(datos_array)]
            
            if len(datos_validos) > 0:
                valor_promedio = float(np.mean(datos_validos))
                valor_min = float(np.min(datos_validos))
                valor_max = float(np.max(datos_validos))
                valor_std = float(np.std(datos_validos))
                
                return {
                    'indice': indice,
                    'valor_promedio': valor_promedio,
                    'valor_min': valor_min,
                    'valor_max': valor_max,
                    'valor_std': valor_std,
                    'fuente': 'Sentinel-2 (Sentinel Hub)',
                    'fecha_descarga': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'resolucion': f'{resolution}m',
                    'estado': 'exitosa',
                    'datos_brutos': datos_array.tolist() if datos_array.size < 1000 else None
                }
        
        return None
        
    except Exception as e:
        st.error(f"❌ Error obteniendo datos de Sentinel Hub: {str(e)}")
        return None

def descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, config=None, indice='NDVI'):
    """Descargar datos de Sentinel-2 (real o simulado)"""
    # Intentar obtener datos reales si hay configuración
    if config is not None and SENTINEL_HUB_AVAILABLE:
        datos_reales = obtener_datos_sentinel2_real(gdf, fecha_inicio, fecha_fin, config, indice)
        if datos_reales:
            return datos_reales
        else:
            st.warning("⚠️ No se pudieron obtener datos reales. Usando datos simulados.")
    
    # Datos simulados como fallback
    return descargar_datos_sentinel2_simulado(gdf, fecha_inicio, fecha_fin, indice)

def descargar_datos_sentinel2_simulado(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Datos simulados de Sentinel-2"""
    try:
        # Generar datos simulados basados en ubicación y fecha
        centroid = gdf.geometry.unary_union.centroid
        lat = centroid.y
        lon = centroid.x
        
        # Variación estacional
        mes = fecha_inicio.month
        if mes in [12, 1, 2]:  # Verano (hemisferio sur)
            base_ndvi = 0.7
        elif mes in [3, 4, 5]:  # Otoño
            base_ndvi = 0.6
        elif mes in [6, 7, 8]:  # Invierno
            base_ndvi = 0.4
        else:  # Primavera
            base_ndvi = 0.8
        
        # Variación por latitud
        lat_factor = 1.0 - abs(lat) / 90 * 0.2
        
        # Ruido aleatorio
        np.random.seed(int(lat * 10000 + lon * 10000))
        ruido = np.random.normal(0, 0.1)
        
        valor_promedio = max(0.1, min(0.9, base_ndvi * lat_factor + ruido))
        
        datos_simulados = {
            'indice': indice,
            'valor_promedio': valor_promedio,
            'valor_min': max(0.05, valor_promedio - 0.2),
            'valor_max': min(0.95, valor_promedio + 0.2),
            'valor_std': 0.08,
            'fuente': 'Sentinel-2 (Simulado)',
            'fecha_descarga': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'resolucion': '10m',
            'estado': 'simulado',
            'nota': 'Datos simulados para demostración. Para datos reales, configure Sentinel Hub.'
        }
        return datos_simulados
    except Exception as e:
        st.error(f"❌ Error generando datos simulados: {str(e)}")
        return None

def descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Datos simulados de Landsat-8"""
    try:
        datos_simulados = {
            'indice': indice,
            'valor_promedio': 0.65 + np.random.normal(0, 0.1),
            'fuente': 'Landsat-8 (Simulado)',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'id_escena': f"LC08_{np.random.randint(1000000, 9999999)}",
            'cobertura_nubes': f"{np.random.randint(0, 15)}%",
            'resolucion': '30m',
            'estado': 'simulado'
        }
        return datos_simulados
    except Exception as e:
        st.error(f"❌ Error procesando Landsat 8: {str(e)}")
        return None

def generar_datos_simulados(gdf, cultivo, indice='NDVI'):
    """Generar datos simulados para demostración"""
    datos_simulados = {
        'indice': indice,
        'valor_promedio': PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO'] * 0.8 + np.random.normal(0, 0.1),
        'fuente': 'Simulación',
        'fecha': datetime.now().strftime('%Y-%m-%d'),
        'resolucion': '10m',
        'estado': 'simulado'
    }
    return datos_simulados

# ===== INICIALIZACIÓN SEGURA DE VARIABLES =====
nutriente = None
satelite_seleccionado = "SENTINEL-2_REAL" if SENTINEL_HUB_AVAILABLE else "SENTINEL-2"
indice_seleccionado = "NDVI"
fecha_inicio = datetime.now() - timedelta(days=30)
fecha_fin = datetime.now()

# ===== SIDEBAR MEJORADO (INTERFAZ VISUAL) =====
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN</div>', unsafe_allow_html=True)
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAIZ", "SORGO", "SOJA", "GIRASOL", "MANI"])
    
    # Mostrar información del cultivo
    mostrar_info_cultivo(cultivo)
    
    # Selector de variedad
    variedades = VARIEDADES_ARGENTINA.get(cultivo, [])
    if variedades:
        variedad = st.selectbox(
            "Variedad/Cultivar:",
            ["No especificada"] + variedades,
            help="Selecciona la variedad o cultivar específico"
        )
    else:
        variedad = "No especificada"
    
    # Configuración Sentinel Hub - Versión simplificada
    if SENTINEL_HUB_AVAILABLE:
        with st.expander("🔐 Configuración Sentinel Hub"):
            
            # Mostrar estado actual
            if st.session_state.sentinel_authenticated:
                st.success("✅ Sentinel Hub autenticado")
                if st.button("🗑️ Limpiar autenticación", key="clear_sentinel_auth"):
                    st.session_state.sh_config = None
                    st.session_state.sentinel_authenticated = False
                    st.session_state.sh_client_id = ''
                    st.session_state.sh_client_secret = ''
                    st.session_state.sh_instance_id = ''
                    st.success("Autenticación limpiada")
                    st.rerun()
            else:
                st.info("Credenciales configuradas en el código. Haz clic en 'Autenticar' para conectar.")
                
                # Botón para autenticar con credenciales predefinidas
                if st.button("🔑 Autenticar con Credenciales Predefinidas", key="auth_predefined", type="primary"):
                    with st.spinner("Autenticando con Sentinel Hub..."):
                        config = configurar_sentinel_hub_predefinido()
                        if config:
                            autenticado = verificar_autenticacion_sentinel_hub(config)
                            if autenticado:
                                st.session_state.sh_config = config
                                st.session_state.sentinel_authenticated = True
                                st.success("✅ Autenticación exitosa!")
                                st.rerun()
                            else:
                                st.error("❌ Error de autenticación. Verifica las credenciales en el código.")
                        else:
                            st.error("❌ Error configurando Sentinel Hub. Verifica las credenciales.")
                
                # Instrucciones para configurar credenciales
                st.markdown("---")
                st.markdown("**📝 Para configurar tus credenciales:**")
                st.markdown("""
                1. Ve a: https://apps.sentinel-hub.com/dashboard/
                2. Crea una cuenta o inicia sesión
                3. Obtén tu **Client ID**, **Client Secret** e **Instance ID**
                4. Reemplaza las credenciales en el archivo `app.py`:
                """)
                st.code("""
# En la función configurar_sentinel_hub_predefinido():
config.sh_client_id = 'TU_CLIENT_ID_REAL'       # ⚠️ Reemplazar
config.sh_client_secret = 'TU_CLIENT_SECRET_REAL' # ⚠️ Reemplazar
config.instance_id = 'TU_INSTANCE_ID_REAL'     # ⚠️ Reemplazar
                """, language="python")
                
                # Opción para ingresar credenciales manualmente (alternativa)
                st.markdown("---")
                st.markdown("**O ingresa credenciales manualmente:**")
                
                sh_client_id = st.text_input("Client ID", type="password")
                sh_client_secret = st.text_input("Client Secret", type="password")
                sh_instance_id = st.text_input("Instance ID", type="password")
                
                col_auth1, col_auth2 = st.columns(2)
                with col_auth1:
                    if st.button("🔑 Autenticar Manualmente", key="auth_manual"):
                        if sh_client_id and sh_client_secret and sh_instance_id:
                            with st.spinner("Autenticando con Sentinel Hub..."):
                                config = configurar_sentinel_hub(sh_client_id, sh_client_secret, sh_instance_id)
                                if config:
                                    autenticado = verificar_autenticacion_sentinel_hub(config)
                                    if autenticado:
                                        st.session_state.sh_config = config
                                        st.session_state.sentinel_authenticated = True
                                        st.session_state.sh_client_id = sh_client_id
                                        st.session_state.sh_client_secret = sh_client_secret
                                        st.session_state.sh_instance_id = sh_instance_id
                                        st.success("✅ Autenticación manual exitosa!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error de autenticación. Verifica tus credenciales.")
                                else:
                                    st.error("❌ Error configurando Sentinel Hub")
                        else:
                            st.warning("⚠️ Por favor, completa todos los campos")
                
                with col_auth2:
                    if st.button("🗑️ Limpiar Campos", key="clear_fields"):
                        st.session_state.sh_client_id = ''
                        st.session_state.sh_client_secret = ''
                        st.session_state.sh_instance_id = ''
                        st.rerun()
    
    else:
        st.warning("⚠️ Sentinel Hub no disponible. Instala con: pip install sentinelhub")
    
    st.subheader("🛰️ Fuente de Datos Satelitales")
    
    # Opciones de satélites disponibles
    opciones_satelites = []
    if SENTINEL_HUB_AVAILABLE:
        opciones_satelites.append("SENTINEL-2_REAL")
    opciones_satelites.extend(["SENTINEL-2", "LANDSAT-8", "DATOS_SIMULADOS"])
    
    # Si Sentinel-2 Real está seleccionado pero no hay autenticación, mostrar advertencia
    if satelite_seleccionado == "SENTINEL-2_REAL" and not st.session_state.sentinel_authenticated:
        st.warning("⚠️ Para usar Sentinel-2 Real, primero autentícate con Sentinel Hub")
        # Cambiar a datos simulados por defecto
        satelite_seleccionado = "SENTINEL-2"
    
    satelite_seleccionado = st.selectbox(
        "Satélite:",
        opciones_satelites,
        help="Selecciona la fuente de datos satelitales",
        index=opciones_satelites.index(satelite_seleccionado) if satelite_seleccionado in opciones_satelites else 0
    )
    
    # Mostrar información del satélite seleccionado
    if satelite_seleccionado in SATELITES_DISPONIBLES:
        info_satelite = SATELITES_DISPONIBLES[satelite_seleccionado]
        st.caption(f"{info_satelite['icono']} {info_satelite['nombre']} - {info_satelite['resolucion']}")
    
    # Selector de índice
    st.subheader("📊 Índice de Vegetación")
    if satelite_seleccionado in SATELITES_DISPONIBLES:
        indices_disponibles = SATELITES_DISPONIBLES[satelite_seleccionado]['indices']
        indice_seleccionado = st.selectbox("Índice:", indices_disponibles)
    
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

# ===== FUNCIONES AUXILIARES - CORREGIDAS PARA EPSG:4326 =====
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

# ===== FUNCIÓN PARA OBTENER DATOS DE NASA POWER =====
def obtener_datos_nasa_power(gdf, fecha_inicio, fecha_fin):
    """
    Obtiene datos meteorológicos diarios de NASA POWER para el centroide de la parcela.
    """
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
    """Genera un DEM sintético para análisis de terreno"""
    gdf = validar_y_corregir_crs(gdf)
    bounds = gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    
    # Crear grid
    num_cells_x = int((maxx - minx) * 111000 / resolucion)  # 1 grado ≈ 111km
    num_cells_y = int((maxy - miny) * 111000 / resolucion)
    num_cells_x = max(50, min(num_cells_x, 200))
    num_cells_y = max(50, min(num_cells_y, 200))
    
    x = np.linspace(minx, maxx, num_cells_x)
    y = np.linspace(miny, maxy, num_cells_y)
    X, Y = np.meshgrid(x, y)
    
    # Generar terreno sintético
    centroid = gdf.geometry.unary_union.centroid
    seed_value = int(centroid.x * 10000 + centroid.y * 10000) % (2**32)
    rng = np.random.RandomState(seed_value)
    
    # Elevación base
    elevacion_base = rng.uniform(100, 300)
    
    # Pendiente general
    slope_x = rng.uniform(-0.001, 0.001)
    slope_y = rng.uniform(-0.001, 0.001)
    
    # Relieve
    relief = np.zeros_like(X)
    n_hills = rng.randint(3, 7)
    for _ in range(n_hills):
        hill_center_x = rng.uniform(minx, maxx)
        hill_center_y = rng.uniform(miny, maxy)
        hill_radius = rng.uniform(0.001, 0.005)
        hill_height = rng.uniform(20, 80)
        dist = np.sqrt((X - hill_center_x)**2 + (Y - hill_center_y)**2)
        relief += hill_height * np.exp(-(dist**2) / (2 * hill_radius**2))
    
    # Valles
    n_valleys = rng.randint(2, 5)
    for _ in range(n_valleys):
        valley_center_x = rng.uniform(minx, maxx)
        valley_center_y = rng.uniform(miny, maxy)
        valley_radius = rng.uniform(0.002, 0.006)
        valley_depth = rng.uniform(10, 40)
        dist = np.sqrt((X - valley_center_x)**2 + (Y - valley_center_y)**2)
        relief -= valley_depth * np.exp(-(dist**2) / (2 * valley_radius**2))
    
    # Ruido
    noise = rng.randn(*X.shape) * 5
    
    Z = elevacion_base + slope_x * (X - minx) + slope_y * (Y - miny) + relief + noise
    Z = np.maximum(Z, 50)  # Evitar valores negativos
    
    # Aplicar máscara de la parcela
    points = np.vstack([X.flatten(), Y.flatten()]).T
    parcel_mask = gdf.geometry.unary_union.contains([Point(p) for p in points])
    parcel_mask = parcel_mask.reshape(X.shape)
    
    Z[~parcel_mask] = np.nan
    
    return X, Y, Z, bounds

def calcular_pendiente(X, Y, Z, resolucion):
    """Calcula pendiente a partir del DEM"""
    # Calcular gradientes
    dy = np.gradient(Z, axis=0) / resolucion
    dx = np.gradient(Z, axis=1) / resolucion
    
    # Calcular pendiente en porcentaje
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    pendiente = np.clip(pendiente, 0, 100)
    
    return pendiente

def generar_curvas_nivel(X, Y, Z, intervalo=5.0):
    """Genera curvas de nivel a partir del DEM"""
    curvas_nivel = []
    elevaciones = []
    
    # Calcular valores únicos de elevación para las curvas
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
    
    # Generar curvas de nivel
    for nivel in niveles:
        # Crear máscara para el nivel
        mascara = (Z >= nivel - 0.5) & (Z <= nivel + 0.5)
        
        if np.any(mascara):
            # Encontrar contornos
            from scipy import ndimage
            estructura = ndimage.generate_binary_structure(2, 2)
            labeled, num_features = ndimage.label(mascara, structure=estructura)
            
            for i in range(1, num_features + 1):
                # Extraer contorno
                contorno = (labeled == i)
                if np.sum(contorno) > 10:  # Filtrar contornos muy pequeños
                    # Obtener coordenadas del contorno
                    y_indices, x_indices = np.where(contorno)
                    if len(x_indices) > 2:
                        # Crear línea de contorno
                        puntos = np.column_stack([X[contorno].flatten(), Y[contorno].flatten()])
                        if len(puntos) >= 3:
                            linea = LineString(puntos)
                            curvas_nivel.append(linea)
                            elevaciones.append(nivel)
    
    return curvas_nivel, elevaciones

# ===== FUNCIONES DE ANÁLISIS COMPLETOS =====
def analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales):
    """Análisis de fertilidad actual"""
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
    """Análisis de recomendaciones NPK"""
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
    """Análisis de costos de fertilización"""
    costos = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    precio_n = 1.2  # USD/kg N
    precio_p = 2.5  # USD/kg P2O5
    precio_k = 1.8  # USD/kg K2O
    
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
    """Análisis de proyecciones de cosecha con y sin fertilización"""
    proyecciones = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        npk_actual = idx['npk_actual']
        ndvi = idx['ndvi']
        
        # Rendimiento base sin fertilización
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * npk_actual * 0.7
        
        # Incremento esperado con fertilización
        incremento = (1 - npk_actual) * 0.4 + (1 - ndvi) * 0.2
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
    """Análisis de textura del suelo"""
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
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin, 
                              intervalo_curvas=5.0, resolucion_dem=10.0, config_sentinel_hub=None):
    """Ejecuta todos los análisis y guarda los resultados"""
    
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
        'datos_satelitales': None
    }
    
    try:
        # Cargar y preparar datos
        gdf = validar_y_corregir_crs(gdf)
        area_total = calcular_superficie(gdf)
        resultados['area_total'] = area_total
        
        # Obtener datos satelitales
        datos_satelitales = None
        if satelite == "SENTINEL-2_REAL" or satelite == "SENTINEL-2":
            datos_satelitales = descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, config_sentinel_hub, indice_seleccionado)
        elif satelite == "LANDSAT-8":
            datos_satelitales = descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, indice_seleccionado)
        else:
            datos_satelitales = generar_datos_simulados(gdf, cultivo, indice_seleccionado)
        
        resultados['datos_satelitales'] = datos_satelitales
        
        # Obtener datos meteorológicos
        df_power = obtener_datos_nasa_power(gdf, fecha_inicio, fecha_fin)
        resultados['df_power'] = df_power
        
        # Dividir parcela
        gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        resultados['gdf_dividido'] = gdf_dividido
        
        # Calcular áreas
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
        
        # 1. Análisis de fertilidad actual
        fertilidad_actual = analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales)
        resultados['fertilidad_actual'] = fertilidad_actual
        
        # 2. Análisis de recomendaciones NPK
        rec_n, rec_p, rec_k = analizar_recomendaciones_npk(fertilidad_actual, cultivo)
        resultados['recomendaciones_npk'] = {
            'N': rec_n,
            'P': rec_p,
            'K': rec_k
        }
        
        # 3. Análisis de costos
        costos = analizar_costos(gdf_dividido, cultivo, rec_n, rec_p, rec_k)
        resultados['costos'] = costos
        
        # 4. Análisis de proyecciones
        proyecciones = analizar_proyecciones_cosecha(gdf_dividido, cultivo, fertilidad_actual)
        resultados['proyecciones'] = proyecciones
        
        # 5. Análisis de textura
        textura = analizar_textura_suelo(gdf_dividido, cultivo)
        resultados['textura'] = textura
        
        # 6. Análisis DEM y curvas de nivel
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
        
        # Combinar todos los resultados en un solo GeoDataFrame
        gdf_completo = textura.copy()
        
        # Añadir fertilidad
        for i, fert in enumerate(fertilidad_actual):
            for key, value in fert.items():
                gdf_completo.at[gdf_completo.index[i], f'fert_{key}'] = value
        
        # Añadir recomendaciones NPK
        gdf_completo['rec_N'] = rec_n
        gdf_completo['rec_P'] = rec_p
        gdf_completo['rec_K'] = rec_k
        
        # Añadir costos
        for i, costo in enumerate(costos):
            for key, value in costo.items():
                gdf_completo.at[gdf_completo.index[i], f'costo_{key}'] = value
        
        # Añadir proyecciones
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

# ===== FUNCIONES DE VISUALIZACIÓN CON BOTONES DESCARGA =====
def crear_mapa_fertilidad(gdf_completo, cultivo, satelite):
    """Crear mapa de fertilidad actual"""
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
    """Crear mapa de recomendaciones NPK"""
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
    """Crear mapa de texturas"""
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

def crear_grafico_distribucion_costos(costos_n, costos_p, costos_k, otros, costo_total):
    """Crear gráfico de distribución de costos"""
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
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando gráfico de costos: {str(e)}")
        return None

def crear_grafico_composicion_textura(arena_prom, limo_prom, arcilla_prom, textura_dist):
    """Crear gráfico de composición granulométrica"""
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
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando gráfico de textura: {str(e)}")
        return None

def crear_grafico_proyecciones_rendimiento(zonas, sin_fert, con_fert):
    """Crear gráfico de proyecciones de rendimiento"""
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
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando gráfico de proyecciones: {str(e)}")
        return None

# ===== FUNCIONES PARA CURVAS DE NIVEL Y 3D =====
def crear_mapa_pendientes(X, Y, pendientes, gdf_original):
    """Crear mapa de pendientes"""
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Mapa de calor de pendientes
        scatter = ax1.scatter(X.flatten(), Y.flatten(), c=pendientes.flatten(), 
                             cmap='RdYlGn_r', s=10, alpha=0.7, vmin=0, vmax=30)
        
        gdf_original.plot(ax=ax1, color='none', edgecolor='black', linewidth=2)
        
        cbar = plt.colorbar(scatter, ax=ax1, shrink=0.8)
        cbar.set_label('Pendiente (%)')
        
        ax1.set_title('Mapa de Calor de Pendientes', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Longitud')
        ax1.set_ylabel('Latitud')
        ax1.grid(True, alpha=0.3)
        
        # Histograma de pendientes
        pendientes_flat = pendientes.flatten()
        pendientes_flat = pendientes_flat[~np.isnan(pendientes_flat)]
        
        ax2.hist(pendientes_flat, bins=30, edgecolor='black', color='skyblue', alpha=0.7)
        
        # Líneas de referencia
        for porcentaje, color in [(2, 'green'), (5, 'lightgreen'), (10, 'yellow'), 
                                 (15, 'orange'), (25, 'red')]:
            ax2.axvline(x=porcentaje, color=color, linestyle='--', linewidth=1, alpha=0.7)
            ax2.text(porcentaje+0.5, ax2.get_ylim()[1]*0.9, f'{porcentaje}%', 
                    color=color, fontsize=8)
        
        stats_text = f"""
Estadísticas:
• Mínima: {np.nanmin(pendientes_flat):.1f}%
• Máxima: {np.nanmax(pendientes_flat):.1f}%
• Promedio: {np.nanmean(pendientes_flat):.1f}%
• Desviación: {np.nanstd(pendientes_flat):.1f}%
"""
        ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9, 
                verticalalignment='top', 
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        
        ax2.set_xlabel('Pendiente (%)')
        ax2.set_ylabel('Frecuencia')
        ax2.set_title('Distribución de Pendientes', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        stats = {
            'min': float(np.nanmin(pendientes_flat)),
            'max': float(np.nanmax(pendientes_flat)),
            'mean': float(np.nanmean(pendientes_flat)),
            'std': float(np.nanstd(pendientes_flat))
        }
        
        return buf, stats
    except Exception as e:
        st.error(f"❌ Error creando mapa de pendientes: {str(e)}")
        return None, {}

def crear_mapa_curvas_nivel(X, Y, Z, curvas_nivel, elevaciones, gdf_original):
    """Crear mapa con curvas de nivel"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Mapa de elevación
        contour = ax.contourf(X, Y, Z, levels=20, cmap='terrain', alpha=0.7)
        
        # Curvas de nivel
        if curvas_nivel:
            for curva, elevacion in zip(curvas_nivel, elevaciones):
                if hasattr(curva, 'coords'):
                    coords = np.array(curva.coords)
                    ax.plot(coords[:, 0], coords[:, 1], 'b-', linewidth=0.8, alpha=0.7)
                    # Etiqueta de elevación
                    if len(coords) > 0:
                        mid_idx = len(coords) // 2
                        ax.text(coords[mid_idx, 0], coords[mid_idx, 1], 
                               f'{elevacion:.0f}m', fontsize=8, color='blue',
                               bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.7))
        
        gdf_original.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
        
        cbar = plt.colorbar(contour, ax=ax, shrink=0.8)
        cbar.set_label('Elevación (m)')
        
        ax.set_title('Mapa de Curvas de Nivel', fontsize=14, fontweight='bold')
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
        return None

def crear_visualizacion_3d(X, Y, Z):
    """Crear visualización 3D del terreno"""
    try:
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot superficie 3D
        surf = ax.plot_surface(X, Y, Z, cmap='terrain', alpha=0.8, 
                              linewidth=0.5, antialiased=True)
        
        # Configuración de ejes
        ax.set_xlabel('Longitud', fontsize=10)
        ax.set_ylabel('Latitud', fontsize=10)
        ax.set_zlabel('Elevación (m)', fontsize=10)
        ax.set_title('Modelo 3D del Terreno', fontsize=14, fontweight='bold', pad=20)
        
        # Colorbar
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label='Elevación (m)')
        
        # Estilo
        ax.grid(True, alpha=0.3)
        ax.view_init(elev=30, azim=45)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando visualización 3D: {str(e)}")
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
    """Generar reporte DOCX con todos los análisis"""
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
        info_table = doc.add_table(rows=6, cols=2)  # Aumentado a 6 filas
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
        
        # Información de datos satelitales
        if 'datos_satelitales' in resultados and resultados['datos_satelitales']:
            datos_sat = resultados['datos_satelitales']
            doc.add_paragraph()
            doc.add_heading('1.1. DATOS SATELITALES', level=2)
            doc.add_paragraph(f'Fuente: {datos_sat.get("fuente", "N/D")}')
            doc.add_paragraph(f'Índice: {datos_sat.get("indice", "N/D")}')
            doc.add_paragraph(f'Valor promedio: {datos_sat.get("valor_promedio", 0):.3f}')
            doc.add_paragraph(f'Estado: {datos_sat.get("estado", "N/D")}')
            if datos_sat.get("nota"):
                doc.add_paragraph(f'Nota: {datos_sat.get("nota")}')
        
        doc.add_paragraph()
        
        # 2. FERTILIDAD ACTUAL
        doc.add_heading('2. FERTILIDAD ACTUAL', level=1)
        doc.add_paragraph('Resumen de parámetros de fertilidad por zona:')
        
        # Tabla de fertilidad
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
        
        # Tabla de NPK
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
        
        # Tabla de costos
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
        
        # Resumen de costos totales
        doc.add_paragraph()
        costo_total = resultados['gdf_completo']['costo_costo_total'].sum()
        costo_promedio = resultados['gdf_completo']['costo_costo_total'].mean()
        doc.add_paragraph(f'Costo total estimado: ${costo_total:.2f} USD')
        doc.add_paragraph(f'Costo promedio por hectárea: ${costo_promedio:.2f} USD/ha')
        
        doc.add_paragraph()
        
        # 5. TEXTURA DEL SUELO
        doc.add_heading('5. TEXTURA DEL SUELO', level=1)
        doc.add_paragraph('Composición granulométrica por zona:')
        
        # Tabla de textura
        text_table = doc.add_table(rows=1, cols=5)
        text_table.style = 'Table Grid'
        text_headers = ['Zona', 'Textura', 'Arena (%)', 'Limo (%)', 'Arcilla (%)']
        for i, header in enumerate(text_headers):
            text_table.cell(0, i).text = header
        
        for i in range(min(10, len(resultados['gdf_completo']))):
            row = text_table.add_row().cells
            row[0].text = str(resultados['gdf_completo'].iloc[i]['id_zona'])
            row[1].text = str(resultados['gdf_completo'].iloc[i]['textura_suelo'])
            row[2].text = f"{resultados['gdf_completo'].iloc[i]['arena']:.1f}"
            row[3].text = f"{resultados['gdf_completo'].iloc[i]['limo']:.1f}"
            row[4].text = f"{resultados['gdf_completo'].iloc[i]['arcilla']:.1f}"
        
        doc.add_paragraph()
        
        # 6. PROYECCIONES DE COSECHA
        doc.add_heading('6. PROYECCIONES DE COSECHA', level=1)
        doc.add_paragraph('Proyecciones de rendimiento con y sin fertilización (kg/ha):')
        
        # Tabla de proyecciones
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
        
        # Resumen de proyecciones
        doc.add_paragraph()
        rend_sin_total = resultados['gdf_completo']['proy_rendimiento_sin_fert'].sum()
        rend_con_total = resultados['gdf_completo']['proy_rendimiento_con_fert'].sum()
        incremento_prom = resultados['gdf_completo']['proy_incremento_esperado'].mean()
        
        doc.add_paragraph(f'Rendimiento total sin fertilización: {rend_sin_total:.0f} kg')
        doc.add_paragraph(f'Rendimiento total con fertilización: {rend_con_total:.0f} kg')
        doc.add_paragraph(f'Incremento promedio esperado: {incremento_prom:.1f}%')
        
        doc.add_paragraph()
        
        # 7. TOPOGRAFÍA Y CURVAS DE NIVEL
        if 'dem_data' in resultados and resultados['dem_data']:
            doc.add_heading('7. TOPOGRAFÍA Y CURVAS DE NIVEL', level=1)
            
            dem_stats = {
                'Elevación mínima': f"{np.nanmin(resultados['dem_data']['Z']):.1f} m",
                'Elevación máxima': f"{np.nanmax(resultados['dem_data']['Z']):.1f} m",
                'Elevación promedio': f"{np.nanmean(resultados['dem_data']['Z']):.1f} m",
                'Pendiente promedio': f"{np.nanmean(resultados['dem_data']['pendientes']):.1f} %",
                'Número de curvas': f"{len(resultados['dem_data'].get('curvas_nivel', []))}"
            }
            
            for key, value in dem_stats.items():
                p = doc.add_paragraph()
                run_key = p.add_run(f'{key}: ')
                run_key.bold = True
                p.add_run(value)
        
        doc.add_paragraph()
        
        # 8. RECOMENDACIONES FINALES
        doc.add_heading('8. RECOMENDACIONES FINALES', level=1)
        
        recomendaciones = [
            f"Aplicar fertilización diferenciada por zonas según el análisis NPK",
            f"Priorizar zonas con índice de fertilidad inferior a 0.5",
            f"Considerar enmiendas orgánicas en zonas con materia orgánica < 2%",
            f"Implementar riego suplementario en zonas con humedad < 0.2",
            f"Realizar análisis de suelo de laboratorio para validar resultados",
            f"Considerar agricultura de precisión para aplicación variable de insumos"
        ]
        
        for rec in recomendaciones:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(rec)
        
        doc.add_paragraph()
        
        # 9. METADATOS TÉCNICOS
        doc.add_heading('9. METADATOS TÉCNICOS', level=1)
        metadatos = [
            ('Generado por', 'Analizador Multi-Cultivo Satellital'),
            ('Versión', '5.0 - Cultivos Extensivos'),
            ('Fecha de generación', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ('Sistema de coordenadas', 'EPSG:4326 (WGS84)'),
            ('Número de zonas', str(len(resultados['gdf_completo']))),
            ('Resolución satelital', SATELITES_DISPONIBLES[satelite]['resolucion']),
            ('Resolución DEM', f'{resolucion_dem} m'),
            ('Intervalo curvas de nivel', f'{intervalo_curvas} m')
        ]
        
        for key, value in metadatos:
            p = doc.add_paragraph()
            run_key = p.add_run(f'{key}: ')
            run_key.bold = True
            p.add_run(value)
        
        # Guardar documento
        docx_output = BytesIO()
        doc.save(docx_output)
        docx_output.seek(0)
        
        return docx_output
        
    except Exception as e:
        st.error(f"❌ Error generando reporte DOCX: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# ===== FUNCIÓN PARA DESCARGAR PNG =====
def crear_boton_descarga_png(buffer, nombre_archivo, texto_boton="📥 Descargar PNG"):
    """Crear botón de descarga para archivos PNG"""
    if buffer:
        st.download_button(
            label=texto_boton,
            data=buffer,
            file_name=nombre_archivo,
            mime="image/png"
        )

# ===== INTERFAZ PRINCIPAL =====
st.title("ANALIZADOR MULTI-CULTIVO SATELITAL")

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
                    
                    # Vista previa
                    fig, ax = plt.subplots(figsize=(8, 6))
                    gdf.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
                    ax.set_title(f"Parcela: {uploaded_file.name}")
                    ax.set_xlabel("Longitud")
                    ax.set_ylabel("Latitud")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    
                    # Botón descarga vista previa
                    buf_vista = io.BytesIO()
                    plt.savefig(buf_vista, format='png', dpi=150, bbox_inches='tight')
                    buf_vista.seek(0)
                    crear_boton_descarga_png(
                        buf_vista,
                        f"vista_previa_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                        "📥 Descargar Vista Previa PNG"
                    )
                    
                with col2:
                    st.write("**🎯 CONFIGURACIÓN**")
                    st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                    st.write(f"- Zonas: {n_divisiones}")
                    st.write(f"- Satélite: {SATELITES_DISPONIBLES[satelite_seleccionado]['nombre']}")
                    st.write(f"- Período: {fecha_inicio} a {fecha_fin}")
                    st.write(f"- Intervalo curvas: {intervalo_curvas} m")
                    st.write(f"- Resolución DEM: {resolucion_dem} m")
                
                if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
                    with st.spinner("Ejecutando análisis completo..."):
                        # Pasar la configuración de Sentinel Hub si está disponible
                        config_sentinel_hub = st.session_state.sh_config if st.session_state.sentinel_authenticated else None
                        
                        resultados = ejecutar_analisis_completo(
                            gdf, cultivo, n_divisiones, 
                            satelite_seleccionado, fecha_inicio, fecha_fin,
                            intervalo_curvas, resolucion_dem,
                            config_sentinel_hub=config_sentinel_hub
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

# Mostrar resultados si el análisis está completado
if st.session_state.analisis_completado and 'resultados_todos' in st.session_state:
    resultados = st.session_state.resultados_todos
    
    # Mostrar resultados en pestañas
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Fertilidad Actual",
        "🧪 Recomendaciones NPK",
        "💰 Análisis de Costos",
        "🏗️ Textura del Suelo",
        "📈 Proyecciones",
        "🏔️ Curvas de Nivel y 3D"
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
        
        # Mapa de fertilidad
        st.subheader("🗺️ MAPA DE FERTILIDAD")
        mapa_fert = crear_mapa_fertilidad(resultados['gdf_completo'], cultivo, satelite_seleccionado)
        if mapa_fert:
            st.image(mapa_fert, use_container_width=True)
            crear_boton_descarga_png(
                mapa_fert,
                f"mapa_fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Mapa de Fertilidad PNG"
            )
        
        # Tabla de resultados
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
        
        # Mapas NPK
        st.subheader("🗺️ MAPAS DE RECOMENDACIONES")
        col_n, col_p, col_k = st.columns(3)
        with col_n:
            mapa_n = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'N')
            if mapa_n:
                st.image(mapa_n, use_container_width=True)
                st.caption("Nitrógeno (N)")
                crear_boton_descarga_png(
                    mapa_n,
                    f"mapa_nitrogeno_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa N"
                )
        with col_p:
            mapa_p = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'P')
            if mapa_p:
                st.image(mapa_p, use_container_width=True)
                st.caption("Fósforo (P)")
                crear_boton_descarga_png(
                    mapa_p,
                    f"mapa_fosforo_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa P"
                )
        with col_k:
            mapa_k = crear_mapa_npk(resultados['gdf_completo'], cultivo, 'K')
            if mapa_k:
                st.image(mapa_k, use_container_width=True)
                st.caption("Potasio (K)")
                crear_boton_descarga_png(
                    mapa_k,
                    f"mapa_potasio_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa K"
                )
        
        # Tabla de recomendaciones
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
        
        # Gráfico de costos
        st.subheader("📊 DISTRIBUCIÓN DE COSTOS")
        costos_n = resultados['gdf_completo']['costo_costo_nitrogeno'].sum()
        costos_p = resultados['gdf_completo']['costo_costo_fosforo'].sum()
        costos_k = resultados['gdf_completo']['costo_costo_potasio'].sum()
        otros = costo_total - (costos_n + costos_p + costos_k)
        
        grafico_costos = crear_grafico_distribucion_costos(costos_n, costos_p, costos_k, otros, costo_total)
        if grafico_costos:
            st.image(grafico_costos, use_container_width=True)
            crear_boton_descarga_png(
                grafico_costos,
                f"grafico_costos_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Gráfico de Costos PNG"
            )
        
        # Tabla de costos
        st.subheader("📋 TABLA DE COSTOS POR ZONA")
        columnas_costos = ['id_zona', 'area_ha', 'costo_costo_nitrogeno', 
                         'costo_costo_fosforo', 'costo_costo_potasio', 'costo_costo_total']
        tabla_costos = resultados['gdf_completo'][columnas_costos].copy()
        tabla_costos.columns = ['Zona', 'Área (ha)', 'Costo N (USD)', 
                              'Costo P (USD)', 'Costo K (USD)', 'Total (USD)']
        st.dataframe(tabla_costos)
    
    with tab4:
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
        
        # Mapa de texturas
        st.subheader("🗺️ MAPA DE TEXTURAS")
        mapa_text = crear_mapa_texturas(resultados['gdf_completo'], cultivo)
        if mapa_text:
            st.image(mapa_text, use_container_width=True)
            crear_boton_descarga_png(
                mapa_text,
                f"mapa_texturas_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Mapa de Texturas PNG"
            )
        
        # Gráfico de composición
        st.subheader("📊 COMPOSICIÓN GRANULOMÉTRICA")
        textura_dist = resultados['gdf_completo']['textura_suelo'].value_counts()
        grafico_textura = crear_grafico_composicion_textura(arena_prom, limo_prom, arcilla_prom, textura_dist)
        if grafico_textura:
            st.image(grafico_textura, use_container_width=True)
            crear_boton_descarga_png(
                grafico_textura,
                f"grafico_textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Gráfico de Textura PNG"
            )
        
        # Tabla de texturas
        st.subheader("📋 TABLA DE TEXTURAS POR ZONA")
        columnas_text = ['id_zona', 'area_ha', 'textura_suelo', 'arena', 'limo', 'arcilla']
        tabla_text = resultados['gdf_completo'][columnas_text].copy()
        tabla_text.columns = ['Zona', 'Área (ha)', 'Textura', 'Arena (%)', 'Limo (%)', 'Arcilla (%)']
        st.dataframe(tabla_text)
    
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
        
        # Gráfico de proyecciones
        st.subheader("📊 COMPARATIVA DE RENDIMIENTOS")
        zonas = resultados['gdf_completo']['id_zona'].head(10).astype(str)
        sin_fert = resultados['gdf_completo']['proy_rendimiento_sin_fert'].head(10)
        con_fert = resultados['gdf_completo']['proy_rendimiento_con_fert'].head(10)
        
        grafico_proyecciones = crear_grafico_proyecciones_rendimiento(zonas, sin_fert, con_fert)
        if grafico_proyecciones:
            st.image(grafico_proyecciones, use_container_width=True)
            crear_boton_descarga_png(
                grafico_proyecciones,
                f"grafico_proyecciones_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "📥 Descargar Gráfico de Proyecciones PNG"
            )
        
        # Análisis económico
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
        
        # Tabla de proyecciones
        st.subheader("📋 TABLA DE PROYECCIONES POR ZONA")
        columnas_proy = ['id_zona', 'area_ha', 'proy_rendimiento_sin_fert', 
                       'proy_rendimiento_con_fert', 'proy_incremento_esperado']
        tabla_proy = resultados['gdf_completo'][columnas_proy].copy()
        tabla_proy.columns = ['Zona', 'Área (ha)', 'Sin Fertilización (kg)', 
                            'Con Fertilización (kg)', 'Incremento (%)']
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
            
            # Mapa de pendientes
            st.subheader("🗺️ MAPA DE PENDIENTES")
            mapa_pendientes, stats_pendientes = crear_mapa_pendientes(
                dem_data['X'], dem_data['Y'], dem_data['pendientes'], gdf
            )
            if mapa_pendientes:
                st.image(mapa_pendientes, use_container_width=True)
                crear_boton_descarga_png(
                    mapa_pendientes,
                    f"mapa_pendientes_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Mapa de Pendientes PNG"
                )
            
            # Mapa de curvas de nivel
            st.subheader("🗺️ MAPA DE CURVAS DE NIVEL")
            mapa_curvas = crear_mapa_curvas_nivel(
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
            
            # Visualización 3D
            st.subheader("🎨 VISUALIZACIÓN 3D DEL TERRENO")
            visualizacion_3d = crear_visualizacion_3d(dem_data['X'], dem_data['Y'], dem_data['Z'])
            if visualizacion_3d:
                st.image(visualizacion_3d, use_container_width=True)
                crear_boton_descarga_png(
                    visualizacion_3d,
                    f"visualizacion_3d_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "📥 Descargar Visualización 3D PNG"
                )
            
            # Análisis de riesgo de erosión
            st.subheader("⚠️ ANÁLISIS DE RIESGO DE EROSION")
            if stats_pendientes:
                riesgo_total = 0
                for categoria, params in CLASIFICACION_PENDIENTES.items():
                    mask = (dem_data['pendientes'].flatten() >= params['min']) & (dem_data['pendientes'].flatten() < params['max'])
                    porcentaje = np.sum(mask) / len(dem_data['pendientes'].flatten()) * 100
                    riesgo_total += porcentaje * params['factor_erosivo']
                
                riesgo_promedio = riesgo_total / 100
                
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    if riesgo_promedio < 0.3:
                        st.success("✅ **RIESGO BAJO**")
                        st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
                    elif riesgo_promedio < 0.6:
                        st.warning("⚠️ **RIESGO MODERADO**")
                        st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
                    else:
                        st.error("🚨 **RIESGO ALTO**")
                        st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
                
                with col_r2:
                    area_critica = resultados['area_total'] * (np.sum(dem_data['pendientes'].flatten() > 10) / len(dem_data['pendientes'].flatten()))
                    st.metric("Área Crítica (>10%)", f"{area_critica:.2f} ha")
                
                with col_r3:
                    area_manejable = resultados['area_total'] * (np.sum(dem_data['pendientes'].flatten() <= 10) / len(dem_data['pendientes'].flatten()))
                    st.metric("Área Manejable (≤10%)", f"{area_manejable:.2f} ha")
            
            # Tabla de datos DEM
            st.subheader("📊 DATOS TOPOGRÁFICOS")
            sample_points = []
            step = max(1, dem_data['X'].shape[0] // 20)
            for i in range(0, dem_data['X'].shape[0], step):
                for j in range(0, dem_data['X'].shape[1], step):
                    if not np.isnan(dem_data['Z'][i, j]):
                        sample_points.append({
                            'Latitud': dem_data['Y'][i, j],
                            'Longitud': dem_data['X'][i, j],
                            'Elevación (m)': dem_data['Z'][i, j],
                            'Pendiente (%)': dem_data['pendientes'][i, j]
                        })
            
            if sample_points:
                df_dem = pd.DataFrame(sample_points).head(20)
                st.dataframe(df_dem)
        else:
            st.warning("⚠️ No se generaron datos DEM. Intenta ejecutar el análisis nuevamente.")
    
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
    
    # Limpiar reportes
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
- NASA POWER API
- Sentinel-2 (ESA)
- Landsat-8 (USGS)
- Datos simulados
""")
with col_footer2:
    st.markdown("""
**🛠️ Tecnologías:**
- Streamlit
- GeoPandas
- Matplotlib
- Python-DOCX
""")
with col_footer3:
    st.markdown("""
**📞 Soporte:**
- Versión: 5.0 - Cultivos Extensivos
- Última actualización: Enero 2026
""")

st.markdown(
    '<div style="text-align: center; color: #94a3b8; font-size: 0.9em; margin-top: 2em;">'
    '© 2026 Analizador Multi-Cultivo Satelital. Todos los derechos reservados.'
    '</div>',
    unsafe_allow_html=True
)
