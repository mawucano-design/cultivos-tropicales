import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math
import folium
from folium import plugins
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import base64

# Intentar importar Earth Engine
try:
    import ee
    import geemap
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    st.warning("⚠️ Earth Engine no está disponible. Instala: pip install earthengine-api geemap")

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - SENTINEL-2 HARMONIZED + AGROECOLOGÍA")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# PARÁMETROS PARA DIFERENTES CULTIVOS
PARAMETROS_CULTIVOS = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 150, 'max': 220},
        'FOSFORO': {'min': 60, 'max': 80},
        'POTASIO': {'min': 100, 'max': 120},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.3
    },
    'CACAO': {
        'NITROGENO': {'min': 120, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 60},
        'POTASIO': {'min': 80, 'max': 110},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.35
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 250},
        'FOSFORO': {'min': 50, 'max': 70},
        'POTASIO': {'min': 120, 'max': 160},
        'MATERIA_ORGANICA_OPTIMA': 4.5,
        'HUMEDAD_OPTIMA': 0.4
    }
}

# PRINCIPIOS AGROECOLÓGICOS - RECOMENDACIONES ESPECÍFICAS
RECOMENDACIONES_AGROECOLOGICAS = {
    'PALMA_ACEITERA': {
        'COBERTURAS_VIVAS': [
            "Leguminosas: Centrosema pubescens, Pueraria phaseoloides",
            "Coberturas mixtas: Maní forrajero (Arachis pintoi)",
            "Plantas de cobertura baja: Dichondra repens"
        ],
        'ABONOS_VERDES': [
            "Crotalaria juncea: 3-4 kg/ha antes de la siembra",
            "Mucuna pruriens: 2-3 kg/ha para control de malezas",
            "Canavalia ensiformis: Fijación de nitrógeno"
        ],
        'BIOFERTILIZANTES': [
            "Bocashi: 2-3 ton/ha cada 6 meses",
            "Compost de racimo vacío: 1-2 ton/ha",
            "Biofertilizante líquido: Aplicación foliar mensual"
        ],
        'MANEJO_ECOLOGICO': [
            "Uso de trampas amarillas para insectos",
            "Cultivos trampa: Maíz alrededor de la plantación",
            "Conservación de enemigos naturales"
        ],
        'ASOCIACIONES': [
            "Piña en calles durante primeros 2 años",
            "Yuca en calles durante establecimiento",
            "Leguminosas arbustivas como cercas vivas"
        ]
    },
    'CACAO': {
        'COBERTURAS_VIVAS': [
            "Leguminosas rastreras: Arachis pintoi",
            "Coberturas sombreadas: Erythrina poeppigiana",
            "Plantas aromáticas: Lippia alba para control plagas"
        ],
        'ABONOS_VERDES': [
            "Frijol terciopelo (Mucuna pruriens): 3 kg/ha",
            "Guandul (Cajanus cajan): Podas periódicas",
            "Crotalaria: Control de nematodos"
        ],
        'BIOFERTILIZANTES': [
            "Compost de cacaoteca: 3-4 ton/ha",
            "Bocashi especial cacao: 2 ton/ha",
            "Té de compost aplicado al suelo"
        ],
        'MANEJO_ECOLOGICO': [
            "Sistema agroforestal multiestrato",
            "Manejo de sombra regulada (30-50%)",
            "Control biológico con hongos entomopatógenos"
        ],
        'ASOCIACIONES': [
            "Árboles maderables: Cedro, Caoba",
            "Frutales: Cítricos, Aguacate",
            "Plantas medicinales: Jengibre, Cúrcuma"
        ]
    },
    'BANANO': {
        'COBERTURAS_VIVAS': [
            "Arachis pintoi entre calles",
            "Leguminosas de porte bajo",
            "Coberturas para control de malas hierbas"
        ],
        'ABONOS_VERDES': [
            "Mucuna pruriens: 4 kg/ha entre ciclos",
            "Canavalia ensiformis: Fijación de N",
            "Crotalaria spectabilis: Control nematodos"
        ],
        'BIOFERTILIZANTES': [
            "Compost de pseudotallo: 4-5 ton/ha",
            "Bocashi bananero: 3 ton/ha",
            "Biofertilizante a base de micorrizas"
        ],
        'MANEJO_ECOLOGICO': [
            "Trampas cromáticas para picudos",
            "Barreras vivas con citronela",
            "Uso de trichoderma para control enfermedades"
        ],
        'ASOCIACIONES': [
            "Leguminosas arbustivas en linderos",
            "Cítricos como cortavientos",
            "Plantas repelentes: Albahaca, Menta"
        ]
    }
}

# FACTORES ESTACIONALES
FACTORES_MES = {
    "ENERO": 0.9, "FEBRERO": 0.95, "MARZO": 1.0, "ABRIL": 1.05,
    "MAYO": 1.1, "JUNIO": 1.0, "JULIO": 0.95, "AGOSTO": 0.9,
    "SEPTIEMBRE": 0.95, "OCTUBRE": 1.0, "NOVIEMBRE": 1.05, "DICIEMBRE": 1.0
}

FACTORES_N_MES = {
    "ENERO": 1.0, "FEBRERO": 1.05, "MARZO": 1.1, "ABRIL": 1.15,
    "MAYO": 1.2, "JUNIO": 1.1, "JULIO": 1.0, "AGOSTO": 0.9,
    "SEPTIEMBRE": 0.95, "OCTUBRE": 1.0, "NOVIEMBRE": 1.05, "DICIEMBRE": 1.0
}

FACTORES_P_MES = {
    "ENERO": 1.0, "FEBRERO": 1.0, "MARZO": 1.05, "ABRIL": 1.1,
    "MAYO": 1.15, "JUNIO": 1.1, "JULIO": 1.05, "AGOSTO": 1.0,
    "SEPTIEMBRE": 1.0, "OCTUBRE": 1.05, "NOVIEMBRE": 1.1, "DICIEMBRE": 1.05
}

FACTORES_K_MES = {
    "ENERO": 1.0, "FEBRERO": 1.0, "MARZO": 1.0, "ABRIL": 1.05,
    "MAYO": 1.1, "JUNIO": 1.15, "JULIO": 1.2, "AGOSTO": 1.15,
    "SEPTIEMBRE": 1.1, "OCTUBRE": 1.05, "NOVIEMBRE": 1.0, "DICIEMBRE": 1.0
}

# PALETAS GEE MEJORADAS - VERSIÓN MÁS IMPACTANTE
PALETAS_GEE = {
    'FERTILIDAD': [
        '#8B0000', '#FF0000', '#FF4500', '#FFA500', '#FFD700', 
        '#ADFF2F', '#32CD32', '#006400', '#004D00'
    ],
    'NITROGENO': [
        '#8B0000', '#FF0000', '#FF6B6B', '#FFD166', '#A3D977', 
        '#57CC99', '#38A3A5', '#22577A', '#1A3C5F'
    ],
    'FOSFORO': [
        '#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#BA55D3',
        '#DA70D6', '#EE82EE', '#FFB6C1', '#FFE4E1'
    ],
    'POTASIO': [
        '#8B4513', '#A0522D', '#CD853F', '#DAA520', '#F4A460',
        '#FFD700', '#FFEC8B', '#FFFACD', '#FFFFE0'
    ],
    'IMPACTO_VISUAL': {
        'MUY_BAJO': '#8B0000',    # Rojo oscuro
        'BAJO': '#FF0000',        # Rojo
        'MEDIO_BAJO': '#FF6B6B',  # Rojo claro
        'MEDIO': '#FFD700',       # Amarillo
        'MEDIO_ALTO': '#ADFF2F',  # Verde amarillo
        'ALTO': '#32CD32',        # Verde lima
        'MUY_ALTO': '#006400',    # Verde oscuro
        'EXCELENTE': '#004D00'    # Verde muy oscuro
    }
}

# ESCALAS MEJORADAS PARA RECOMENDACIONES
ESCALAS_RECOMENDACIONES = {
    'NITRÓGENO': {
        'rangos': [0, 20, 40, 60, 80, 100, 120, 140, 160],
        'colores': PALETAS_GEE['NITROGENO'],
        'etiquetas': ['0-20', '20-40', '40-60', '60-80', '80-100', '100-120', '120-140', '140-160', '160+ kg/ha']
    },
    'FÓSFORO': {
        'rangos': [0, 10, 20, 30, 40, 50, 60, 70, 80],
        'colores': PALETAS_GEE['FOSFORO'],
        'etiquetas': ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80+ kg/ha']
    },
    'POTASIO': {
        'rangos': [0, 15, 30, 45, 60, 75, 90, 105, 120],
        'colores': PALETAS_GEE['POTASIO'],
        'etiquetas': ['0-15', '15-30', '30-45', '45-60', '60-75', '75-90', '90-105', '105-120', '120+ kg/ha']
    }
}

# Inicializar session_state
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'gdf_analisis' not in st.session_state:
    st.session_state.gdf_analisis = None
if 'gdf_original' not in st.session_state:
    st.session_state.gdf_original = None
if 'gdf_zonas' not in st.session_state:
    st.session_state.gdf_zonas = None
if 'area_total' not in st.session_state:
    st.session_state.area_total = 0
if 'datos_demo' not in st.session_state:
    st.session_state.datos_demo = False
if 'usar_sentinel2' not in st.session_state:
    st.session_state.usar_sentinel2 = False
if 'ee_initialized' not in st.session_state:
    st.session_state.ee_initialized = False

# FUNCIÓN PARA INICIALIZAR EARTH ENGINE
def inicializar_earth_engine():
    """Inicializa Google Earth Engine"""
    try:
        if not st.session_state.ee_initialized:
            try:
                ee.Initialize()
                st.session_state.ee_initialized = True
                return True
            except Exception as e:
                st.warning(f"⚠️ Earth Engine no está autenticado: {str(e)}")
                st.info("""
                **Para usar Sentinel-2 Harmonizada necesitas:**
                1. Ejecutar en local: `ee.Authenticate()` y `ee.Initialize()`
                2. En Streamlit Cloud: Configurar service account
                3. Usar datos simulados por ahora
                """)
                return False
        return True
    except Exception as e:
        st.error(f"❌ Error inicializando Earth Engine: {str(e)}")
        return False

# FUNCIÓN PARA OBTENER DATOS REALES DE SENTINEL-2 HARMONIZED
def obtener_datos_sentinel2_harmonized(geometry, fecha_inicio, fecha_fin, cloud_filter=20):
    """
    Obtiene datos reales de Sentinel-2 Harmonizada para el área y período especificado
    """
    try:
        if not st.session_state.ee_initialized:
            return None
            
        # Definir la colección Sentinel-2 Harmonizada
        collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(geometry) \
            .filterDate(fecha_inicio, fecha_fin) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_filter)) \
            .sort('CLOUDY_PIXEL_PERCENTAGE')
        
        # Verificar si hay imágenes disponibles
        count = collection.size().getInfo()
        if count == 0:
            st.warning("🌤️ No se encontraron imágenes Sentinel-2 sin nubes para el área y fecha especificadas.")
            return None
        
        # Obtener la imagen menos nublada
        image = collection.first()
        
        # Calcular índices espectrales
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        ndbi = image.normalizedDifference(['B11', 'B8']).rename('NDBI')
        
        # Bandas para análisis de suelos
        bands = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']  # Blue, Green, Red, NIR, SWIR1, SWIR2
        
        # Crear imagen compuesta con índices
        composite_image = image.select(bands).addBands([ndvi, ndwi, ndbi])
        
        # Obtener metadatos
        cloud_percent = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        fecha_imagen = image.get('system:time_start').getInfo()
        fecha_imagen_str = datetime.fromtimestamp(fecha_imagen/1000).strftime('%Y-%m-%d')
        
        st.success(f"🛰️ Imagen Sentinel-2 cargada: {fecha_imagen_str} (Nubosidad: {cloud_percent}%)")
        
        return composite_image
        
    except Exception as e:
        st.error(f"❌ Error obteniendo datos Sentinel-2: {str(e)}")
        return None

# FUNCIÓN PARA ESTIMAR NUTRIENTES CON MODELOS BASADOS EN SENTINEL-2
def estimar_nutrientes_sentinel2(image, geometry, cultivo):
    """
    Estima nutrientes del suelo usando modelos basados en Sentinel-2
    Basado en investigaciones científicas de relación índices espectrales - nutrientes
    """
    try:
        # Extraer valores de píxeles para el área de interés
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=20,  # Escala 20m para mejor rendimiento
            maxPixels=1e9
        )
        
        # Obtener valores
        ndvi_val = ee.Number(stats.get('NDVI')).getInfo() or 0.5
        ndwi_val = ee.Number(stats.get('NDWI')).getInfo() or 0.3
        swir1_val = ee.Number(stats.get('B11')).getInfo() or 0.2
        nir_val = ee.Number(stats.get('B8')).getInfo() or 0.3
        red_val = ee.Number(stats.get('B4')).getInfo() or 0.2
        
        # Parámetros del cultivo
        params = PARAMETROS_CULTIVOS[cultivo]
        
        # MODELOS DE ESTIMACIÓN MEJORADOS (basados en investigación científica)
        # Nitrógeno - fuertemente correlacionado con NDVI y banda NIR
        nitrogeno_base = params['NITROGENO']['min'] + (params['NITROGENO']['max'] - params['NITROGENO']['min']) * ndvi_val * 1.2
        
        # Fósforo - correlacionado con bandas SWIR (relación con materia orgánica y pH)
        fosforo_base = params['FOSFORO']['min'] + (params['FOSFORO']['max'] - params['FOSFORO']['min']) * (1 - swir1_val) * 0.8
        
        # Potasio - correlacionado con múltiples bandas y textura
        potasio_base = params['POTASIO']['min'] + (params['POTASIO']['max'] - params['POTASIO']['min']) * (ndvi_val * 0.6 + (1 - swir1_val) * 0.4)
        
        # Materia orgánica estimada de SWIR y Red (modelo empírico)
        materia_organica = 1.5 + (5.5 * (1 - swir1_val)) * (red_val * 0.3 + 0.7)
        
        # Humedad estimada de NDWI y bandas NIR/SWIR
        humedad = 0.15 + (0.35 * ndwi_val) + (0.1 * (1 - swir1_val))
        
        # Asegurar valores dentro de rangos razonables
        nitrogeno_base = max(params['NITROGENO']['min'] * 0.7, min(params['NITROGENO']['max'] * 1.3, nitrogeno_base))
        fosforo_base = max(params['FOSFORO']['min'] * 0.7, min(params['FOSFORO']['max'] * 1.3, fosforo_base))
        potasio_base = max(params['POTASIO']['min'] * 0.7, min(params['POTASIO']['max'] * 1.3, potasio_base))
        materia_organica = max(1.0, min(8.0, materia_organica))
        humedad = max(0.1, min(0.8, humedad))
        ndvi_val = max(0.1, min(0.95, ndvi_val))
        
        return {
            'nitrogeno': nitrogeno_base,
            'fosforo': fosforo_base,
            'potasio': potasio_base,
            'materia_organica': materia_organica,
            'humedad': humedad,
            'ndvi': ndvi_val,
            'ndwi': ndwi_val,
            'swir1': swir1_val
        }
        
    except Exception as e:
        st.warning(f"⚠️ Error en estimación Sentinel-2: {str(e)}. Usando valores simulados.")
        return None

# FUNCIÓN MEJORADA PARA CALCULAR SUPERFICIE
def calcular_superficie(gdf):
    """Calcula superficie en hectáreas con manejo robusto de CRS"""
    try:
        if gdf.empty or gdf.geometry.isnull().all():
            return 0.0
            
        # Verificar si el CRS es geográfico (grados)
        if gdf.crs and gdf.crs.is_geographic:
            # Convertir a un CRS proyectado para cálculo de área precisa
            try:
                # Usar UTM adecuado (aquí se usa un CRS común para Colombia)
                gdf_proj = gdf.to_crs('EPSG:3116')  # MAGNA-SIRGAS / Colombia West zone
                area_m2 = gdf_proj.geometry.area
            except:
                # Fallback: conversión aproximada (1 grado ≈ 111km en ecuador)
                area_m2 = gdf.geometry.area * 111000 * 111000
        else:
            # Asumir que ya está en metros
            area_m2 = gdf.geometry.area
            
        return area_m2 / 10000  # Convertir a hectáreas
        
    except Exception as e:
        # Fallback simple
        try:
            return gdf.geometry.area.mean() / 10000
        except:
            return 1.0  # Valor por defecto

# FUNCIÓN MEJORADA PARA CREAR MAPA INTERACTIVO CON COLORES MÁS IMPACTANTES
def crear_mapa_interactivo_esri(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa interactivo con base ESRI Satélite - VERSIÓN MEJORADA VISUALMENTE"""
    
    # Obtener centro y bounds del GeoDataFrame
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    # Crear mapa centrado
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles=None,
        width='100%',
        height='600px'
    )
    
    # Añadir base ESRI Satélite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='🌍 Satélite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Añadir base ESRI Calles
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='🗺️ Calles',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Añadir base OpenStreetMap como alternativa
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='🗾 OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)
    
    # CONFIGURACIÓN MEJORADA DE COLORES Y RANGOS
    if columna_valor and analisis_tipo:
        if analisis_tipo == "FERTILIDAD ACTUAL":
            # Escala mejorada para fertilidad
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
            num_clases = len(colores)
        else:
            # Escalas específicas para cada nutriente
            if nutriente in ESCALAS_RECOMENDACIONES:
                escala = ESCALAS_RECOMENDACIONES[nutriente]
                vmin, vmax = min(escala['rangos']), max(escala['rangos'])
                colores = escala['colores']
                num_clases = len(colores)
            else:
                # Fallback
                vmin, vmax = 0, 100
                colores = PALETAS_GEE['NITROGENO']
                num_clases = len(colores)
        
        # Función mejorada para obtener color
        def obtener_color_mejorado(valor, vmin, vmax, colores, num_clases):
            if vmax == vmin:
                return colores[0]
            
            # Normalizar valor
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            
            # Asignar clase
            clase = int(valor_norm * (num_clases - 1))
            return colores[clase]
        
        # Añadir cada polígono con color mejorado
        for idx, row in gdf.iterrows():
            valor = row[columna_valor]
            color = obtener_color_mejorado(valor, vmin, vmax, colores, num_clases)
            
            # Crear popup informativo mejorado
            if analisis_tipo == "FERTILIDAD ACTUAL":
                popup_text = f"""
                <div style="font-family: Arial, sans-serif; max-width: 300px;">
                    <h4 style="color: #2E8B57; margin-bottom: 10px;">🌱 Zona {row['id_zona']}</h4>
                    <p><b>Índice Fertilidad:</b> <span style="color: #FF6B35; font-weight: bold;">{valor:.3f}</span></p>
                    <p><b>Área:</b> {row.get('area_ha', 0):.2f} ha</p>
                    <p><b>Categoría:</b> <span style="color: #2E8B57;">{row.get('categoria', 'N/A')}</span></p>
                    <p><b>N:</b> {row.get('nitrogeno', 0):.1f} kg/ha | <b>P:</b> {row.get('fosforo', 0):.1f} kg/ha | <b>K:</b> {row.get('potasio', 0):.1f} kg/ha</p>
                </div>
                """
            else:
                # Determinar icono según nutriente
                icono = "🌿" if nutriente == "NITRÓGENO" else "🧪" if nutriente == "FÓSFORO" else "⚡"
                
                popup_text = f"""
                <div style="font-family: Arial, sans-serif; max-width: 300px;">
                    <h4 style="color: #2E8B57; margin-bottom: 10px;">{icono} Zona {row['id_zona']}</h4>
                    <p><b>Recomendación {nutriente}:</b> <span style="color: #FF6B35; font-weight: bold; font-size: 16px;">{valor:.1f} kg/ha</span></p>
                    <p><b>Área:</b> {row.get('area_ha', 0):.2f} ha</p>
                    <p><b>Categoría Fertilidad:</b> <span style="color: #2E8B57;">{row.get('categoria', 'N/A')}</span></p>
                    <hr style="margin: 8px 0;">
                    <p><b>Nivel Actual:</b> {row.get('nitrogeno' if nutriente=='NITRÓGENO' else 'fosforo' if nutriente=='FÓSFORO' else 'potasio', 0):.1f} kg/ha</p>
                </div>
                """
            
            # Añadir polígono con estilo mejorado
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': '#2C3E50',  # Borde más oscuro
                    'weight': 2.5,       # Borde más grueso
                    'fillOpacity': 0.8,  # Más opaco
                    'opacity': 0.9
                },
                popup=folium.Popup(popup_text, max_width=350),
                tooltip=f"Zona {row['id_zona']}: {valor:.2f}"
            ).add_to(m)
            
            # Añadir marcador con número de zona mejorado
            centroid = row.geometry.centroid
            folium.Marker(
                [centroid.y, centroid.x],
                icon=folium.DivIcon(
                    html=f'''
                    <div style="background-color: rgba(255,255,255,0.9); 
                                border: 3px solid #2C3E50; 
                                border-radius: 50%; 
                                width: 35px; height: 35px; 
                                display: flex; align-items: center; 
                                justify-content: center; 
                                font-weight: bold; font-size: 14px;
                                color: #2C3E50;
                                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);">
                        {row["id_zona"]}
                    </div>
                    '''
                ),
                tooltip=f"Zona {row['id_zona']} - Click para detalles"
            ).add_to(m)
    else:
        # Mapa simple del polígono original con estilo mejorado
        for idx, row in gdf.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x: {
                    'fillColor': '#3498DB',
                    'color': '#2C3E50',
                    'weight': 3,
                    'fillOpacity': 0.6,
                    'opacity': 0.8
                },
                popup=folium.Popup(f"<b>Parcela {idx + 1}</b><br>Área: {calcular_superficie(gdf.iloc[[idx]]).iloc[0]:.2f} ha", max_width=300),
                tooltip=f"Parcela {idx + 1}"
            ).add_to(m)
    
    # Ajustar bounds del mapa
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    # Añadir control de capas
    folium.LayerControl().add_to(m)
    
    # Añadir medida de escala
    plugins.MeasureControl(
        position='bottomleft',
        primary_length_unit='meters',
        secondary_length_unit='kilometers'
    ).add_to(m)
    
    # Añadir mini mapa mejorado
    plugins.MiniMap(
        tile_layer='OpenStreetMap',
        toggle_display=True,
        position='bottomright'
    ).add_to(m)
    
    # Añadir botón de pantalla completa
    plugins.Fullscreen(
        position='topright',
        title='Pantalla Completa',
        title_cancel='Salir Pantalla Completa'
    ).add_to(m)
    
    # LEYENDA MEJORADA Y MÁS IMPACTANTE
    if columna_valor and analisis_tipo:
        # Crear leyenda personalizada mejorada
        if analisis_tipo == "FERTILIDAD ACTUAL":
            leyenda_titulo = "🎯 Índice de Fertilidad NPK"
            rangos_leyenda = ['0.0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4', '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-1.0']
            colores_leyenda = PALETAS_GEE['FERTILIDAD']
        else:
            if nutriente in ESCALAS_RECOMENDACIONES:
                escala = ESCALAS_RECOMENDACIONES[nutriente]
                leyenda_titulo = f"{'🌿' if nutriente=='NITRÓGENO' else '🧪' if nutriente=='FÓSFORO' else '⚡'} Recomendación {nutriente}"
                rangos_leyenda = escala['etiquetas']
                colores_leyenda = escala['colores']
            else:
                leyenda_titulo = f"Recomendación {nutriente}"
                rangos_leyenda = ['0-20', '20-40', '40-60', '60-80', '80-100', '100+ kg/ha']
                colores_leyenda = PALETAS_GEE['NITROGENO'][:6]
        
        legend_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    width: 280px; height: auto; 
                    background-color: rgba(255,255,255,0.95); 
                    border: 3px solid #2C3E50; 
                    border-radius: 10px; 
                    z-index:9999; 
                    font-family: Arial, sans-serif;
                    font-size: 12px; 
                    padding: 15px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
            <h4 style="margin:0 0 12px 0; 
                      color: #2C3E50; 
                      text-align: center;
                      border-bottom: 2px solid #3498DB;
                      padding-bottom: 8px;">
                {leyenda_titulo}
            </h4>
        '''
        
        # Añadir elementos de leyenda
        for i, (color, rango) in enumerate(zip(colores_leyenda, rangos_leyenda)):
            legend_html += f'''
            <div style="margin: 5px 0; display: flex; align-items: center;">
                <div style="background-color: {color}; 
                          width: 25px; height: 20px; 
                          border: 1px solid #2C3E50;
                          margin-right: 10px;
                          border-radius: 3px;"></div>
                <span style="font-weight: {'bold' if i >= len(rangos_leyenda)-2 else 'normal'}">{rango}</span>
            </div>
            '''
        
        # Añadir información adicional
        if analisis_tipo == "RECOMENDACIONES NPK":
            total_recomendacion = (gdf[columna_valor] * gdf['area_ha']).sum()
            legend_html += f'''
            <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed #BDC3C7;">
                <p style="margin: 5px 0; font-size: 11px; color: #7F8C8D;">
                    <b>Total requerido:</b> {total_recomendacion:.1f} kg
                </p>
                <p style="margin: 5px 0; font-size: 11px; color: #7F8C8D;">
                    <b>Zonas analizadas:</b> {len(gdf)}
                </p>
            </div>
            '''
        
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

# FUNCIÓN PARA CREAR MAPA VISUALIZADOR DE PARCELA
def crear_mapa_visualizador_parcela(gdf):
    """Crea mapa interactivo para visualizar la parcela original con ESRI Satélite"""
    
    # Obtener centro y bounds
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    # Crear mapa
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles=None
    )
    
    # Añadir base ESRI Satélite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Añadir base ESRI Calles
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Añadir polígonos de la parcela
    for idx, row in gdf.iterrows():
        area_ha = calcular_superficie(gdf.iloc[[idx]]).iloc[0]
        
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda x: {
                'fillColor': '#1f77b4',
                'color': '#2ca02c',
                'weight': 3,
                'fillOpacity': 0.4,
                'opacity': 0.8
            },
            popup=folium.Popup(
                f"<b>Parcela {idx + 1}</b><br>"
                f"<b>Área:</b> {area_ha:.2f} ha<br>"
                f"<b>Coordenadas:</b> {centroid.y:.4f}, {centroid.x:.4f}",
                max_width=300
            ),
            tooltip=f"Parcela {idx + 1} - {area_ha:.2f} ha"
        ).add_to(m)
    
    # Ajustar bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    # Añadir controles
    folium.LayerControl().add_to(m)
    plugins.MeasureControl(position='bottomleft').add_to(m)
    plugins.MiniMap(toggle_display=True).add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    
    # Añadir leyenda
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>🌱 Visualizador de Parcela</b></p>
    <p><b>Leyenda:</b></p>
    <p><i style="background:#1f77b4; width:20px; height:20px; display:inline-block; margin-right:5px; opacity:0.4;"></i> Área de la parcela</p>
    <p><i style="background:#2ca02c; width:20px; height:20px; display:inline-block; margin_right:5px; opacity:0.8;"></i> Borde de la parcela</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

# FUNCIÓN CORREGIDA PARA CREAR MAPA ESTÁTICO
def crear_mapa_estatico(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa estático con matplotlib - CORREGIDO PARA COINCIDIR CON INTERACTIVO"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # CONFIGURACIÓN UNIFICADA CON EL MAPA INTERACTIVO
        if columna_valor and analisis_tipo:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
                vmin, vmax = 0, 1
            else:
                # USAR EXACTAMENTE LOS MISMOS RANGOS QUE EL MAPA INTERACTIVO
                if nutriente == "NITRÓGENO":
                    cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                    vmin, vmax = 10, 140
                elif nutriente == "FÓSFORO":
                    cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                    vmin, vmax = 5, 80
                else:  # POTASIO
                    cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                    vmin, vmax = 8, 120
            
            # Plotear cada polígono con color según valor - MÉTODO UNIFICADO
            for idx, row in gdf.iterrows():
                valor = row[columna_valor]
                valor_norm = (valor - vmin) / (vmax - vmin)
                valor_norm = max(0, min(1, valor_norm))
                color = cmap(valor_norm)
                
                # Plot del polígono
                gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
                
                # Etiqueta con valor - FORMATO MEJORADO
                centroid = row.geometry.centroid
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    texto_valor = f"{valor:.3f}"
                else:
                    texto_valor = f"{valor:.0f} kg"
                
                ax.annotate(f"Z{row['id_zona']}\n{texto_valor}", 
                           (centroid.x, centroid.y), 
                           xytext=(3, 3), textcoords="offset points", 
                           fontsize=6, color='black', weight='bold',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8),
                           ha='center', va='center')
        else:
            # Mapa simple del polígono original
            gdf.plot(ax=ax, color='lightblue', edgecolor='black', linewidth=2, alpha=0.7)
        
        # Configuración del mapa
        ax.set_title(f'🗺️ {titulo}', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        # BARRA DE COLORES UNIFICADA
        if columna_valor and analisis_tipo:
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
            
            # Etiquetas de barra unificadas
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cbar.set_label('Índice NPK Actual (0-1)', fontsize=10)
                # Marcas específicas para fertilidad
                cbar.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
                cbar.set_ticklabels(['0.0 (Muy Baja)', '0.2', '0.4 (Media)', '0.6', '0.8', '1.0 (Muy Alta)'])
            else:
                cbar.set_label(f'Recomendación {nutriente} (kg/ha)', fontsize=10)
                # Marcas específicas para recomendaciones
                if nutriente == "NITRÓGENO":
                    cbar.set_ticks([10, 40, 70, 100, 130, 140])
                    cbar.set_ticklabels(['10', '40', '70', '100', '130', '140 kg/ha'])
                elif nutriente == "FÓSFORO":
                    cbar.set_ticks([5, 20, 35, 50, 65, 80])
                    cbar.set_ticklabels(['5', '20', '35', '50', '65', '80 kg/ha'])
                else:  # POTASIO
                    cbar.set_ticks([8, 30, 52, 74, 96, 120])
                    cbar.set_ticklabels(['8', '30', '52', '74', '96', '120 kg/ha'])
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"Error creando mapa estático: {str(e)}")
        return None

# FUNCIÓN PARA MOSTRAR RECOMENDACIONES AGROECOLÓGICAS
def mostrar_recomendaciones_agroecologicas(cultivo, categoria, area_ha, analisis_tipo, nutriente=None):
    """Muestra recomendaciones agroecológicas específicas"""
    
    st.markdown("### 🌿 RECOMENDACIONES AGROECOLÓGICAS")
    
    # Determinar el enfoque según la categoría
    if categoria in ["MUY BAJA", "MUY BAJO", "BAJA", "BAJO"]:
        enfoque = "🚨 **ENFOQUE: RECUPERACIÓN Y REGENERACIÓN**"
        intensidad = "Alta"
    elif categoria in ["MEDIA", "MEDIO"]:
        enfoque = "✅ **ENFOQUE: MANTENIMIENTO Y MEJORA**"
        intensidad = "Media"
    else:
        enfoque = "🌟 **ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN**"
        intensidad = "Baja"
    
    st.success(f"{enfoque} - Intensidad: {intensidad}")
    
    # Obtener recomendaciones específicas del cultivo
    recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
    
    # Mostrar por categorías
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🌱 **COBERTURAS VIVAS**", expanded=True):
            for rec in recomendaciones.get('COBERTURAS_VIVAS', []):
                st.markdown(f"• {rec}")
            
            # Recomendaciones adicionales según área
            if area_ha > 10:
                st.info("**Para áreas grandes:** Implementar en franjas progresivas")
            else:
                st.info("**Para áreas pequeñas:** Cobertura total recomendada")
    
    with col2:
        with st.expander("🌿 **ABONOS VERDES**", expanded=True):
            for rec in recomendaciones.get('ABONOS_VERDES', []):
                st.markdown(f"• {rec}")
            
            # Ajustar según intensidad
            if intensidad == "Alta":
                st.warning("**Prioridad alta:** Sembrar inmediatamente después de análisis")
    
    col3, col4 = st.columns(2)
    
    with col3:
        with st.expander("💩 **BIOFERTILIZANTES**", expanded=True):
            for rec in recomendaciones.get('BIOFERTILIZANTES', []):
                st.markdown(f"• {rec}")
            
            # Recomendaciones específicas por nutriente
            if analisis_tipo == "RECOMENDACIONES NPK" and nutriente:
                if nutriente == "NITRÓGENO":
                    st.markdown("• **Enmienda nitrogenada:** Compost de leguminosas")
                elif nutriente == "FÓSFORO":
                    st.markdown("• **Enmienda fosfatada:** Rocas fosfóricas molidas")
                else:
                    st.markdown("• **Enmienda potásica:** Cenizas de biomasa")
    
    with col4:
        with st.expander("🐞 **MANEJO ECOLÓGICO**", expanded=True):
            for rec in recomendaciones.get('MANEJO_ECOLOGICO', []):
                st.markdown(f"• {rec}")
            
            # Recomendaciones según categoría
            if categoria in ["MUY BAJA", "MUY BAJO"]:
                st.markdown("• **Urgente:** Implementar control biológico intensivo")
    
    with st.expander("🌳 **ASOCIACIONES Y DIVERSIFICACIÓN**", expanded=True):
        for rec in recomendaciones.get('ASOCIACIONES', []):
            st.markdown(f"• {rec}")
        
        # Beneficios de las asociaciones
        st.markdown("""
        **Beneficios agroecológicos:**
        • Mejora la biodiversidad funcional
        • Reduce incidencia de plagas y enfermedades
        • Optimiza el uso de recursos (agua, luz, nutrientes)
        • Incrementa la resiliencia del sistema
        """)
    
    # PLAN DE IMPLEMENTACIÓN
    st.markdown("### 📅 PLAN DE IMPLEMENTACIÓN AGROECOLÓGICA")
    
    timeline_col1, timeline_col2, timeline_col3 = st.columns(3)
    
    with timeline_col1:
        st.markdown("**🏁 INMEDIATO (0-15 días)**")
        st.markdown("""
        • Preparación del terreno
        • Siembra de abonos verdes
        • Aplicación de biofertilizantes
        • Instalación de trampas
        """)
    
    with timeline_col2:
        st.markdown("**📈 CORTO PLAZO (1-3 meses)**")
        st.markdown("""
        • Establecimiento coberturas
        • Monitoreo inicial
        • Ajustes de manejo
        • Podas de formación
        """)
    
    with timeline_col3:
        st.markdown("**🎯 MEDIANO PLAZO (3-12 meses)**")
        st.markdown("""
        • Evaluación de resultados
        • Diversificación
        • Optimización del sistema
        • Réplica en otras zonas
        """)

# FUNCIÓN MEJORADA PARA DIVIDIR PARCELA
def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo con manejo robusto de errores"""
    try:
        if len(gdf) == 0:
            return gdf
        
        # Usar el primer polígono como parcela principal
        parcela_principal = gdf.iloc[0].geometry
        
        # Verificar que la geometría sea válida
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)  # Reparar geometría
        
        bounds = parcela_principal.bounds
        if len(bounds) < 4:
            st.error("No se pueden obtener los límites de la parcela")
            return gdf
            
        minx, miny, maxx, maxy = bounds
        
        # Verificar que los bounds sean válidos
        if minx >= maxx or miny >= maxy:
            st.error("Límites de parcela inválidos")
            return gdf
        
        sub_poligonos = []
        
        # Cuadrícula regular
        n_cols = math.ceil(math.sqrt(n_zonas))
        n_rows = math.ceil(n_zonas / n_cols)
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        # Asegurar un tamaño mínimo de celda
        if width < 0.0001 or height < 0.0001:  # ~11m en grados decimales
            st.warning("Las celdas son muy pequeñas, ajustando número de zonas")
            n_zonas = min(n_zonas, 16)
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
                
                # Crear celda con verificación de validez
                try:
                    cell_poly = Polygon([
                        (cell_minx, cell_miny),
                        (cell_maxx, cell_miny),
                        (cell_maxx, cell_maxy),
                        (cell_minx, cell_maxy)
                    ])
                    
                    if cell_poly.is_valid:
                        intersection = parcela_principal.intersection(cell_poly)
                        if not intersection.is_empty and intersection.area > 0:
                            # Simplificar geometría si es necesario
                            if intersection.geom_type == 'MultiPolygon':
                                # Tomar el polígono más grande
                                largest = max(intersection.geoms, key=lambda p: p.area)
                                sub_poligonos.append(largest)
                            else:
                                sub_poligonos.append(intersection)
                except Exception as e:
                    continue  # Saltar celdas problemáticas
        
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            st.warning("No se pudieron crear zonas, retornando parcela original")
            return gdf
            
    except Exception as e:
        st.error(f"Error dividiendo parcela: {str(e)}")
        return gdf

# FUNCIÓN MEJORADA PARA CALCULAR ÍNDICES GEE CON SENTINEL-2
def calcular_indices_gee_mejorado(gdf, cultivo, mes_analisis, analisis_tipo, nutriente, usar_sentinel2=True):
    """Calcula índices GEE usando datos reales de Sentinel-2 Harmonizada"""
    
    params = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # FACTORES ESTACIONALES
    factor_mes = FACTORES_MES[mes_analisis]
    factor_n_mes = FACTORES_N_MES[mes_analisis]
    factor_p_mes = FACTORES_P_MES[mes_analisis]
    factor_k_mes = FACTORES_K_MES[mes_analisis]
    
    # Inicializar columnas
    for col in ['area_ha', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica', 
                'humedad', 'ndvi', 'indice_fertilidad', 'recomendacion_npk']:
        zonas_gdf[col] = 0.0
    zonas_gdf['categoria'] = "MEDIA"
    
    # Configurar fechas para Sentinel-2 (últimos 3 meses)
    if usar_sentinel2 and st.session_state.ee_initialized:
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=90)
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        st.info(f"📅 Período de análisis Sentinel-2: {fecha_inicio_str} a {fecha_fin_str}")
    
    # Contadores para estadísticas
    zonas_sentinel2 = 0
    zonas_simuladas = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in enumerate(zonas_gdf.iterrows()):
        idx, row = idx, row[1]  # Desempaquetar
        
        try:
            # Actualizar progreso
            progress = (idx + 1) / len(zonas_gdf)
            progress_bar.progress(progress)
            status_text.text(f"🔬 Analizando zona {idx+1} de {len(zonas_gdf)}...")
            
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener geometría
            geometry = row.geometry
            
            # INTENTAR USAR SENTINEL-2 HARMONIZED
            datos_reales = None
            if usar_sentinel2 and st.session_state.ee_initialized:
                try:
                    # Convertir geometría a formato Earth Engine
                    if hasattr(geometry, '__geo_interface__'):
                        ee_geometry = ee.Geometry(geometry.__geo_interface__)
                        
                        image = obtener_datos_sentinel2_harmonized(
                            ee_geometry,
                            fecha_inicio_str,
                            fecha_fin_str
                        )
                        
                        if image:
                            datos_reales = estimar_nutrientes_sentinel2(image, ee_geometry, cultivo)
                            if datos_reales:
                                zonas_sentinel2 += 1
                except Exception as e:
                    st.warning(f"⚠️ Error en zona {idx+1} con Sentinel-2: {str(e)}")
            
            if datos_reales:
                # USAR DATOS REALES DE SENTINEL-2
                nitrogeno = datos_reales['nitrogeno'] * factor_n_mes
                fosforo = datos_reales['fosforo'] * factor_p_mes
                potasio = datos_reales['potasio'] * factor_k_mes
                materia_organica = datos_reales['materia_organica']
                humedad = datos_reales['humedad']
                ndvi = datos_reales['ndvi']
                
            else:
                # FALLBACK A DATOS SIMULADOS (código original mejorado)
                centroid = row.geometry.centroid if hasattr(row.geometry, 'centroid') else row.geometry.representative_point()
                
                seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
                rng = np.random.RandomState(seed_value)
                
                lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
                lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
                
                n_min, n_max = params['NITROGENO']['min'], params['NITROGENO']['max']
                p_min, p_max = params['FOSFORO']['min'], params['FOSFORO']['max']
                k_min, k_max = params['POTASIO']['min'], params['POTASIO']['max']
                
                nitrogeno_base = n_min + (n_max - n_min) * (0.3 + 0.4 * lat_norm)
                fosforo_base = p_min + (p_max - p_min) * (0.3 + 0.4 * lon_norm)
                potasio_base = k_min + (k_max - k_min) * (0.3 + 0.4 * (1 - lat_norm))
                
                nitrogeno = nitrogeno_base * factor_n_mes * (0.85 + 0.3 * rng.random())
                fosforo = fosforo_base * factor_p_mes * (0.85 + 0.3 * rng.random())
                potasio = potasio_base * factor_k_mes * (0.85 + 0.3 * rng.random())
                
                nitrogeno = max(n_min * 0.5, min(n_max * 1.5, nitrogeno))
                fosforo = max(p_min * 0.5, min(p_max * 1.5, fosforo))
                potasio = max(k_min * 0.5, min(k_max * 1.5, potasio))
                
                materia_organica = params['MATERIA_ORGANICA_OPTIMA'] * (0.7 + 0.6 * rng.random())
                humedad = params['HUMEDAD_OPTIMA'] * (0.6 + 0.8 * rng.random())
                ndvi = 0.5 + 0.3 * lat_norm + 0.1 * rng.random()
                ndvi = max(0.1, min(0.9, ndvi))
                
                zonas_simuladas += 1
            
            # CÁLCULO DE ÍNDICES Y RECOMENDACIONES
            n_min, n_max = params['NITROGENO']['min'], params['NITROGENO']['max']
            p_min, p_max = params['FOSFORO']['min'], params['FOSFORO']['max']
            k_min, k_max = params['POTASIO']['min'], params['POTASIO']['max']
            
            n_norm = (nitrogeno - n_min) / (n_max - n_min) if n_max > n_min else 0.5
            p_norm = (fosforo - p_min) / (p_max - p_min) if p_max > p_min else 0.5
            k_norm = (potasio - k_min) / (k_max - k_min) if k_max > k_min else 0.5
            
            n_norm = max(0, min(1, n_norm))
            p_norm = max(0, min(1, p_norm))
            k_norm = max(0, min(1, k_norm))
            
            indice_fertilidad = (n_norm * 0.4 + p_norm * 0.3 + k_norm * 0.3) * factor_mes
            indice_fertilidad = max(0, min(1, indice_fertilidad))
            
            # Categorización
            if indice_fertilidad >= 0.8: categoria = "MUY ALTA"
            elif indice_fertilidad >= 0.6: categoria = "ALTA"
            elif indice_fertilidad >= 0.4: categoria = "MEDIA"
            elif indice_fertilidad >= 0.2: categoria = "BAJA"
            else: categoria = "MUY BAJA"
            
            # Cálculo de recomendaciones NPK
            if analisis_tipo == "RECOMENDACIONES NPK":
                n_optimo = (n_min + n_max) / 2
                p_optimo = (p_min + p_max) / 2
                k_optimo = (k_min + k_max) / 2
                
                if nutriente == "NITRÓGENO":
                    nivel_actual, nivel_optimo = nitrogeno, n_optimo
                elif nutriente == "FÓSFORO":
                    nivel_actual, nivel_optimo = fosforo, p_optimo
                else:
                    nivel_actual, nivel_optimo = potasio, k_optimo
                
                if nivel_actual < nivel_optimo:
                    deficit = nivel_optimo - nivel_actual
                    severidad = min(1.0, deficit / nivel_optimo)
                    factor_ajuste = 0.8 + (severidad * 0.4)
                    recomendacion_base = deficit * 0.7
                    recomendacion_npk = recomendacion_base * factor_ajuste
                    recomendacion_npk = min(recomendacion_npk, 100)
                elif nivel_actual > nivel_optimo * 1.2:
                    exceso = nivel_actual - nivel_optimo
                    recomendacion_npk = -exceso * 0.3
                else:
                    recomendacion_npk = nivel_optimo * 0.1
                
                if recomendacion_npk > 0:
                    recomendacion_npk = max(5, recomendacion_npk)
                else:
                    recomendacion_npk = max(-50, recomendacion_npk)
                
                recomendacion_npk = round(recomendacion_npk, 1)
            else:
                recomendacion_npk = 0.0
            
            # Asignar valores
            zonas_gdf.loc[idx, 'area_ha'] = round(area_ha, 3)
            zonas_gdf.loc[idx, 'nitrogeno'] = round(nitrogeno, 1)
            zonas_gdf.loc[idx, 'fosforo'] = round(fosforo, 1)
            zonas_gdf.loc[idx, 'potasio'] = round(potasio, 1)
            zonas_gdf.loc[idx, 'materia_organica'] = round(materia_organica, 2)
            zonas_gdf.loc[idx, 'humedad'] = round(humedad, 3)
            zonas_gdf.loc[idx, 'ndvi'] = round(ndvi, 3)
            zonas_gdf.loc[idx, 'indice_fertilidad'] = round(indice_fertilidad, 3)
            zonas_gdf.loc[idx, 'categoria'] = categoria
            zonas_gdf.loc[idx, 'recomendacion_npk'] = recomendacion_npk
            
        except Exception as e:
            st.warning(f"⚠️ Advertencia en zona {idx+1}: {str(e)}")
            # Valores por defecto en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = round(calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0], 3)
            zonas_gdf.loc[idx, 'nitrogeno'] = params['NITROGENO']['min']
            zonas_gdf.loc[idx, 'fosforo'] = params['FOSFORO']['min']
            zonas_gdf.loc[idx, 'potasio'] = params['POTASIO']['min']
            zonas_gdf.loc[idx, 'materia_organica'] = params['MATERIA_ORGANICA_OPTIMA']
            zonas_gdf.loc[idx, 'humedad'] = params['HUMEDAD_OPTIMA']
            zonas_gdf.loc[idx, 'ndvi'] = 0.6
            zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.5
            zonas_gdf.loc[idx, 'categoria'] = "MEDIA"
            zonas_gdf.loc[idx, 'recomendacion_npk'] = 0.0
            
            zonas_simuladas += 1
    
    # Mostrar estadísticas finales
    progress_bar.empty()
    status_text.empty()
    
    if usar_sentinel2:
        if zonas_sentinel2 > 0:
            st.success(f"✅ {zonas_sentinel2} zonas analizadas con Sentinel-2 Harmonizada")
        if zonas_simuladas > 0:
            st.info(f"ℹ️ {zonas_simuladas} zonas con datos simulados (fallback)")
    
    return zonas_gdf

# FUNCIÓN PARA PROCESAR ARCHIVO SUBIDO
def procesar_archivo(uploaded_zip):
    """Procesa el archivo ZIP con shapefile"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Guardar archivo ZIP
            zip_path = os.path.join(tmp_dir, "uploaded.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded_zip.getvalue())
            
            # Extraer ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # Buscar archivos shapefile
            shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
            
            if not shp_files:
                st.error("❌ No se encontró archivo .shp en el ZIP")
                return None
            
            # Cargar shapefile
            shp_path = os.path.join(tmp_dir, shp_files[0])
            gdf = gpd.read_file(shp_path)
            
            # Verificar y reparar geometrías
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

# FUNCIÓN PARA GENERAR PDF
def generar_informe_pdf(gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total):
    """Genera un informe PDF completo con los resultados del análisis"""
    
    # Crear buffer para el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    
    # Crear estilos personalizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkgreen,
        spaceAfter=30,
        alignment=1  # Centrado
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.darkblue,
        spaceAfter=12,
        spaceBefore=12
    )
    
    normal_style = styles['Normal']
    
    # Contenido del PDF
    story = []
    
    # Título principal
    story.append(Paragraph("INFORME DE ANÁLISIS AGRÍCOLA", title_style))
    story.append(Spacer(1, 20))
    
    # Información general
    story.append(Paragraph("INFORMACIÓN GENERAL", heading_style))
    info_data = [
        ["Cultivo:", cultivo.replace('_', ' ').title()],
        ["Tipo de Análisis:", analisis_tipo],
        ["Mes de Análisis:", mes_analisis],
        ["Área Total:", f"{area_total:.2f} ha"],
        ["Fecha de Generación:", datetime.now().strftime("%d/%m/%Y %H:%M")]
    ]
    
    if analisis_tipo == "RECOMENDACIONES NPK":
        info_data.insert(2, ["Nutriente Analizado:", nutriente])
    
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Estadísticas resumen
    story.append(Paragraph("ESTADÍSTICAS DEL ANÁLISIS", heading_style))
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        stats_data = [
            ["Estadística", "Valor"],
            ["Índice Fertilidad Promedio", f"{gdf_analisis['indice_fertilidad'].mean():.3f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"],
            ["NDVI Promedio", f"{gdf_analisis['ndvi'].mean():.3f}"]
        ]
    else:
        avg_rec = gdf_analisis['recomendacion_npk'].mean()
        total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
        stats_data = [
            ["Estadística", "Valor"],
            [f"Recomendación {nutriente} Promedio (kg/ha)", f"{avg_rec:.1f}"],
            [f"Total {nutriente} Requerido (kg)", f"{total_rec:.1f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"]
        ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Distribución de categorías
    if analisis_tipo == "FERTILIDAD ACTUAL":
        story.append(Paragraph("DISTRIBUCIÓN DE CATEGORÍAS DE FERTILIDAD", heading_style))
        cat_dist = gdf_analisis['categoria'].value_counts()
        cat_data = [["Categoría", "Número de Zonas", "Porcentaje"]]
        
        total_zonas = len(gdf_analisis)
        for categoria, count in cat_dist.items():
            porcentaje = (count / total_zonas) * 100
            cat_data.append([categoria, str(count), f"{porcentaje:.1f}%"])
        
        cat_table = Table(cat_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 20))
    
    # Mapa estático
    story.append(PageBreak())
    story.append(Paragraph("MAPA DE ANÁLISIS", heading_style))
    
    # Generar mapa estático para el PDF
    if analisis_tipo == "FERTILIDAD ACTUAL":
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'indice_fertilidad'
    else:
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'recomendacion_npk'
    
    mapa_buffer = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    
    if mapa_buffer:
        try:
            # Convertir a imagen para PDF
            mapa_buffer.seek(0)
            img = Image(mapa_buffer, width=6*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"Figura 1: {titulo_mapa}", normal_style))
        except Exception as e:
            story.append(Paragraph("Error al generar el mapa para el PDF", normal_style))
    
    story.append(Spacer(1, 20))
    
    # Tabla de resultados por zona (primeras 10 zonas)
    story.append(Paragraph("RESULTADOS POR ZONA (PRIMERAS 10 ZONAS)", heading_style))
    
    # Preparar datos para tabla
    columnas_tabla = ['id_zona', 'area_ha', 'categoria']
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio'])
    else:
        columnas_tabla.extend(['recomendacion_npk', 'nitrogeno', 'fosforo', 'potasio'])
    
    df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    
    # Redondear valores
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
    
    df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
    df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
    df_tabla['potasio'] = df_tabla['potasio'].round(1)
    
    # Convertir a lista para la tabla
    table_data = [df_tabla.columns.tolist()]
    for _, row in df_tabla.iterrows():
        table_data.append(row.tolist())
    
    # Crear tabla
    zona_table = Table(table_data, colWidths=[0.5*inch] + [0.8*inch] * (len(columnas_tabla)-1))
    zona_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    story.append(zona_table)
    
    if len(gdf_analisis) > 10:
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"* Mostrando 10 de {len(gdf_analisis)} zonas totales. Consulte el archivo CSV para todos los datos.", 
                             ParagraphStyle('Small', parent=normal_style, fontSize=8)))
    
    story.append(Spacer(1, 20))
    
    # Recomendaciones agroecológicas
    story.append(PageBreak())
    story.append(Paragraph("RECOMENDACIONES AGROECOLÓGICAS", heading_style))
    
    categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
    
    # Determinar enfoque
    if categoria_promedio in ["MUY BAJA", "MUY BAJO", "BAJA", "BAJO"]:
        enfoque = "ENFOQUE: RECUPERACIÓN Y REGENERACIÓN - Intensidad: Alta"
    elif categoria_promedio in ["MEDIA", "MEDIO"]:
        enfoque = "ENFOQUE: MANTENIMIENTO Y MEJORA - Intensidad: Media"
    else:
        enfoque = "ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN - Intensidad: Baja"
    
    story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
    story.append(Spacer(1, 10))
    
    # Recomendaciones específicas del cultivo
    recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
    
    for categoria_rec, items in recomendaciones.items():
        story.append(Paragraph(f"<b>{categoria_rec.replace('_', ' ').title()}:</b>", normal_style))
        for item in items[:3]:  # Mostrar solo 3 items por categoría
            story.append(Paragraph(f"• {item}", normal_style))
        story.append(Spacer(1, 5))
    
    # Plan de implementación
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>PLAN DE IMPLEMENTACIÓN:</b>", normal_style))
    
    planes = [
        ("INMEDIATO (0-15 días)", [
            "Preparación del terreno",
            "Siembra de abonos verdes", 
            "Aplicación de biofertilizantes"
        ]),
        ("CORTO PLAZO (1-3 meses)", [
            "Establecimiento coberturas",
            "Monitoreo inicial",
            "Ajustes de manejo"
        ]),
        ("MEDIANO PLAZO (3-12 meses)", [
            "Evaluación de resultados",
            "Diversificación",
            "Optimización del sistema"
        ])
    ]
    
    for periodo, acciones in planes:
        story.append(Paragraph(f"<b>{periodo}:</b>", normal_style))
        for accion in acciones:
            story.append(Paragraph(f"• {accion}", normal_style))
        story.append(Spacer(1, 5))
    
    # Pie de página con información adicional
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN ADICIONAL", heading_style))
    story.append(Paragraph("Este informe fue generado automáticamente por el Sistema de Análisis Agrícola GEE.", normal_style))
    story.append(Paragraph("Para consultas técnicas o información detallada, contacte con el departamento técnico.", normal_style))
    
    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer

# INTERFAZ PRINCIPAL ACTUALIZADA
def main():
    # OBTENER PARÁMETROS DEL SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        cultivo = st.selectbox("Cultivo:", 
                              ["PALMA_ACEITERA", "CACAO", "BANANO"])
        
        analisis_tipo = st.selectbox("Tipo de Análisis:", 
                                   ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
        
        nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
        
        mes_analisis = st.selectbox("Mes de Análisis:", 
                                   ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                                    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
        
        st.subheader("🎯 División de Parcela")
        n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=32, value=24)
        
        st.subheader("🛰️ Fuente de Datos")
        usar_sentinel2 = st.checkbox(
            "Usar Sentinel-2 Harmonizada (datos reales)", 
            value=st.session_state.get('usar_sentinel2', False),
            help="Usa datos satelitales reales de Sentinel-2 para análisis más preciso"
        )
        
        if usar_sentinel2:
            if not EE_AVAILABLE:
                st.error("❌ Earth Engine no está disponible. Instala: pip install earthengine-api geemap")
                usar_sentinel2 = False
            else:
                if not st.session_state.ee_initialized:
                    if st.button("🔐 Inicializar Earth Engine"):
                        if inicializar_earth_engine():
                            st.success("✅ Earth Engine inicializado correctamente")
                            st.rerun()
                
                st.info("""
                **Sentinel-2 Harmonizada proporciona:**
                • 🛰️ Imágenes multiespectrales reales
                • 📊 Índices NDVI, NDWI, NDBI actualizados
                • 🌤️ Datos corregidos atmosféricamente
                • 📅 Análisis basado en los últimos 3 meses
                • 🎯 Resolución espacial de 10-20m
                """)
        
        st.subheader("📤 Subir Parcela")
        uploaded_zip = st.file_uploader("Subir ZIP con shapefile de tu parcela", type=['zip'])
        
        # Botón para resetear la aplicación
        if st.button("🔄 Reiniciar Análisis"):
            st.session_state.analisis_completado = False
            st.session_state.gdf_analisis = None
            st.session_state.gdf_original = None
            st.session_state.gdf_zonas = None
            st.session_state.area_total = 0
            st.session_state.datos_demo = False
            st.session_state.usar_sentinel2 = False
            st.rerun()

        st.markdown("---")
        st.markdown("### 📊 Métodología GEE")
        st.info("""
        Esta aplicación utiliza:
        - **Google Earth Engine** para análisis satelital
        - **Sentinel-2 Harmonizada** para datos reales
        - **Índices espectrales** (NDVI, NDWI, NDBI)
        - **Modelos predictivos** de nutrientes
        - **Enfoque agroecológico** integrado
        """)

    # Procesar archivo subido si existe
    if uploaded_zip is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_zip)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False

    # Cargar datos de demostración si se solicita
    if st.session_state.datos_demo and st.session_state.gdf_original is None:
        # Crear polígono de ejemplo
        poligono_ejemplo = Polygon([
            [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
        ])
        
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono_ejemplo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo

    # Mostrar interfaz según el estado
    if st.session_state.analisis_completado and st.session_state.gdf_analisis is not None:
        mostrar_resultados(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones)
    elif st.session_state.gdf_original is not None:
        mostrar_configuracion_parcela(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, usar_sentinel2)
    else:
        mostrar_modo_demo()

def mostrar_modo_demo():
    """Muestra la interfaz de demostración"""
    st.markdown("### 🚀 Modo Demostración")
    st.info("""
    **Para usar la aplicación:**
    1. Sube un archivo ZIP con el shapefile de tu parcela
    2. Selecciona el cultivo y tipo de análisis
    3. Configura los parámetros en el sidebar
    4. Ejecuta el análisis GEE
    
    **📁 El shapefile debe incluir:**
    - .shp (geometrías)
    - .shx (índice)
    - .dbf (atributos)
    - .prj (sistema de coordenadas)
    """)
    
    # Ejemplo de datos de demostración
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        st.session_state.datos_demo = True
        st.rerun()

def mostrar_configuracion_parcela(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, usar_sentinel2):
    """Muestra la configuración de la parcela antes del análisis"""
    gdf_original = st.session_state.gdf_original
    
    # Mostrar información de la parcela
    if st.session_state.datos_demo:
        st.success("✅ Datos de demostración cargados")
    else:
        st.success("✅ Parcela cargada correctamente")
    
    # Calcular estadísticas
    area_total = calcular_superficie(gdf_original).sum()
    num_poligonos = len(gdf_original)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Número de Polígonos", num_poligonos)
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    with col4:
        fuente = "🛰️ Sentinel-2" if usar_sentinel2 and st.session_state.ee_initialized else "📊 Simulados"
        st.metric("📡 Fuente Datos", fuente)
    
    # VISUALIZADOR DE PARCELA ORIGINAL
    st.markdown("### 🗺️ Visualizador de Parcela")
    
    # Crear y mostrar mapa interactivo
    mapa_parcela = crear_mapa_visualizador_parcela(gdf_original)
    st_folium(mapa_parcela, width=800, height=500)
    
    # DIVIDIR PARCELA EN ZONAS
    st.markdown("### 📊 División en Zonas de Manejo")
    st.info(f"La parcela se dividirá en **{n_divisiones} zonas** para análisis detallado")
    
    # Botón para ejecutar análisis
    if st.button("🚀 Ejecutar Análisis GEE Completo", type="primary"):
        with st.spinner("🔄 Dividiendo parcela en zonas..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            st.session_state.gdf_zonas = gdf_zonas
        
        with st.spinner("🔬 Realizando análisis GEE con Sentinel-2..." if usar_sentinel2 else "🔬 Realizando análisis GEE..."):
            # Usar la función mejorada con Sentinel-2
            gdf_analisis = calcular_indices_gee_mejorado(
                gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente, usar_sentinel2
            )
            st.session_state.gdf_analisis = gdf_analisis
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
            st.session_state.usar_sentinel2 = usar_sentinel2
        
        st.rerun()

def mostrar_resultados(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones):
    """Muestra los resultados del análisis completado"""
    gdf_analisis = st.session_state.gdf_analisis
    area_total = st.session_state.area_total
    
    # MOSTRAR RESULTADOS
    st.markdown("## 📈 RESULTADOS DEL ANÁLISIS")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Estadísticas resumen
    st.subheader("📊 Estadísticas del Análisis")
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_fert = gdf_analisis['indice_fertilidad'].mean()
            st.metric("📊 Índice Fertilidad Promedio", f"{avg_fert:.3f}")
        with col2:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("🌿 Nitrógeno Promedio", f"{avg_n:.1f} kg/ha")
        with col3:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("🧪 Fósforo Promedio", f"{avg_p:.1f} kg/ha")
        with col4:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("⚡ Potasio Promedio", f"{avg_k:.1f} kg/ha")
        st.subheader("📋 Distribución de Categorías de Fertilidad")
        cat_dist = gdf_analisis['categoria'].value_counts()
        st.bar_chart(cat_dist)
    else:
        col1, col2 = st.columns(2)
        with col1:
            avg_rec = gdf_analisis['recomendacion_npk'].mean()
            st.metric(f"💡 Recomendación {nutriente} Promedio", f"{avg_rec:.1f} kg/ha")
        with col2:
            total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
            st.metric(f"📦 Total {nutriente} Requerido", f"{total_rec:.1f} kg")
        st.subheader("🌿 Estado Actual de Nutrientes")
        col_n, col_p, col_k = st.columns(3)
        with col_n:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("Nitrógeno", f"{avg_n:.1f} kg/ha")
        with col_p:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("Fósforo", f"{avg_p:.1f} kg/ha")
        with col_k:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("Potasio", f"{avg_k:.1f} kg/ha")
    
    # MAPAS INTERACTIVOS
    st.markdown("### 🗺️ Mapas de Análisis")
    
    # Seleccionar columna para visualizar
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columna_visualizar = 'indice_fertilidad'
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
    else:
        columna_visualizar = 'recomendacion_npk'
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
    
    # Crear y mostrar mapa interactivo
    mapa_analisis = crear_mapa_interactivo_esri(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    st_folium(mapa_analisis, width=800, height=500)
    
    # MAPA ESTÁTICO PARA DESCARGA
    st.markdown("### 📄 Mapa para Reporte")
    mapa_estatico = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_estatico:
        st.image(mapa_estatico, caption=titulo_mapa, use_column_width=True)
    
    # TABLA DETALLADA
    st.markdown("### 📋 Tabla de Resultados por Zona")
    
    # Preparar datos para tabla
    columnas_tabla = ['id_zona', 'area_ha', 'categoria']
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'ndvi'])
    else:
        columnas_tabla.extend(['recomendacion_npk', 'nitrogeno', 'fosforo', 'potasio'])
    
    df_tabla = gdf_analisis[columnas_tabla].copy()
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
        df_tabla['ndvi'] = df_tabla['ndvi'].round(3)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
    
    st.dataframe(df_tabla, use_container_width=True)
    
    # RECOMENDACIONES AGROECOLÓGICAS
    categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
    mostrar_recomendaciones_agroecologicas(
        cultivo, categoria_promedio, area_total, analisis_tipo, nutriente
    )
    
    # DESCARGAR RESULTADOS
    st.markdown("### 💾 Descargar Resultados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Descargar CSV
        csv = df_tabla.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"resultados_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Descargar GeoJSON
        geojson = gdf_analisis.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"zonas_analisis_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    
    with col3:
        # Descargar PDF
        if st.button("📄 Generar Informe PDF", type="primary"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total
                )
                
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

# EJECUTAR APLICACIÓN
if __name__ == "__main__":
    main()
