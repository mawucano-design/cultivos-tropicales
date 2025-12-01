import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime
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
import fiona
import gc
import time

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA GEE COMPLETA CON AGROECOLOGÍA")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# ============================================================================
# METODOLOGÍAS AVANZADAS DE ANÁLISIS DE TEXTURA (Sciencedirect, 2021; Frontiers, 2024)
# ============================================================================
METODOLOGIAS_AVANZADAS = {
    'SENSORES_PROXIMALES': {
        'descripcion': 'Técnicas de sensores y modelado digital para estimar textura a partir de propiedades espectrales, conductividad eléctrica o datos de reflectancia.',
        'aplicaciones': [
            "Mapeo de variabilidad espacial de compactación",
            "Monitoreo de humedad en tiempo real", 
            "Detección temprana de problemas de drenaje",
            "Optimización sitio-específica del manejo"
        ]
    },
    'TELEDETECCION_ALTA_RES': {
        'descripcion': 'Teledetección de alta resolución para mapeo de texturas mediante índices espectrales, modelos de aprendizaje automático y datos satelitales/drones.',
        'aplicaciones': [
            "Clasificación continua de texturas",
            "Monitoreo de salud del suelo",
            "Detección de erosión y degradación",
            "Análisis multitemporal de cambios"
        ]
    },
    'MODELADO_DIGITAL': {
        'descripcion': 'Integración de datos ambientales y de manejo en modelos digitales del suelo para caracterización dinámica.',
        'aplicaciones': [
            "Predicción de propiedades físicas del suelo",
            "Simulación de escenarios de manejo",
            "Optimización de sistemas de drenaje",
            "Planificación de agricultura de precisión"
        ]
    }
}

# PARÁMETROS MEJORADOS Y MÁS REALISTAS PARA DIFERENTES CULTIVOS
PARAMETROS_CULTIVOS = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 120, 'max': 200, 'optimo': 160},
        'FOSFORO': {'min': 40, 'max': 80, 'optimo': 60},
        'POTASIO': {'min': 160, 'max': 240, 'optimo': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.35,
        'pH_OPTIMO': 5.5,
        'CONDUCTIVIDAD_OPTIMA': 1.2,
        'NDWI_OPTIMO': {'min': -0.2, 'max': 0.3, 'optimo': 0.1}
    },
    'CACAO': {
        'NITROGENO': {'min': 100, 'max': 180, 'optimo': 140},
        'FOSFORO': {'min': 30, 'max': 60, 'optimo': 45},
        'POTASIO': {'min': 120, 'max': 200, 'optimo': 160},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.4,
        'pH_OPTIMO': 6.0,
        'CONDUCTIVIDAD_OPTIMA': 1.0,
        'NDWI_OPTIMO': {'min': -0.1, 'max': 0.4, 'optimo': 0.2}
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 280, 'optimo': 230},
        'FOSFORO': {'min': 50, 'max': 90, 'optimo': 70},
        'POTASIO': {'min': 250, 'max': 350, 'optimo': 300},
        'MATERIA_ORGANICA_OPTIMA': 4.5,
        'HUMEDAD_OPTIMA': 0.45,
        'pH_OPTIMO': 6.2,
        'CONDUCTIVIDAD_OPTIMA': 1.5,
        'NDWI_OPTIMO': {'min': 0.0, 'max': 0.5, 'optimo': 0.3}
    }
}

# PARÁMETROS DE ALTIMETRÍA POR CULTIVO
ALTIMETRIA_OPTIMA = {
    'PALMA_ACEITERA': {
        'elevacion_min': 0,
        'elevacion_max': 500,
        'pendiente_max': 8,
        'orientacion_optima': ['SE', 'S', 'SW']
    },
    'CACAO': {
        'elevacion_min': 100,
        'elevacion_max': 800,
        'pendiente_max': 12,
        'orientacion_optima': ['E', 'SE', 'S']
    },
    'BANANO': {
        'elevacion_min': 0,
        'elevacion_max': 1000,
        'pendiente_max': 10,
        'orientacion_optima': ['N', 'NE', 'NW']
    }
}

# ============================================================================
# PARÁMETROS DE TEXTURA CON NOMENCLATURA ACTUALIZADA Y METODOLOGÍAS AVANZADAS
# ============================================================================
TEXTURA_SUELO_OPTIMA = {
    'PALMA_ACEITERA': {
        'textura_optima': 'Franco Arcilloso',
        'arena_optima': 40,
        'limo_optima': 30,
        'arcilla_optima': 30,
        'densidad_aparente_optima': 1.3,
        'porosidad_optima': 0.5,
        'metodologias_recomendadas': ['SENSORES_PROXIMALES', 'TELEDETECCION_ALTA_RES'],
        'frecuencia_monitoreo': 'Trimestral',
        'sensores_recomendados': ['Conductividad eléctrica', 'Espectroscopía NIR', 'Sensores de humedad']
    },
    'CACAO': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.2,
        'porosidad_optima': 0.55,
        'metodologias_recomendadas': ['TELEDETECCION_ALTA_RES', 'MODELADO_DIGITAL'],
        'frecuencia_monitoreo': 'Semestral',
        'sensores_recomendados': ['Imágenes multiespectrales', 'Sensores de temperatura suelo']
    },
    'BANANO': {
        'textura_optima': 'Franco Arcilloso-Arenoso',
        'arena_optima': 50,
        'limo_optima': 30,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52,
        'metodologias_recomendadas': ['SENSORES_PROXIMALES', 'MODELADO_DIGITAL'],
        'frecuencia_monitoreo': 'Mensual en época seca',
        'sensores_recomendados': ['Sensores de humedad volumétrica', 'TDR', 'FDR']
    }
}

# CLASIFICACIÓN DE TEXTURAS DEL SUELO - NOMBRES ACTUALIZADOS
CLASIFICACION_TEXTURAS = {
    'Arenoso': {'arena_min': 85, 'arena_max': 100, 'limo_max': 15, 'arcilla_max': 15},
    'Franco Arcilloso-Arenoso': {'arena_min': 70, 'arena_max': 85, 'limo_max': 30, 'arcilla_max': 20},
    'Franco': {'arena_min': 43, 'arena_max': 52, 'limo_min': 28, 'limo_max': 50, 'arcilla_min': 7, 'arcilla_max': 27},
    'Franco Arcilloso': {'arena_min': 20, 'arena_max': 45, 'limo_min': 15, 'limo_max': 53, 'arcilla_min': 27, 'arcilla_max': 40},
    'Arcilloso': {'arena_max': 45, 'limo_max': 40, 'arcilla_min': 40}
}

# FACTORES EDÁFICOS MÁS REALISTAS - NOMBRES ACTUALIZADOS
FACTORES_SUELO = {
    'Arcilloso': {'retention': 1.3, 'drainage': 0.7, 'aeration': 0.6, 'workability': 0.5, 'riesgo': 'Alto', 'intervencion': 'Media-Alta'},
    'Franco Arcilloso': {'retention': 1.2, 'drainage': 0.8, 'aeration': 0.7, 'workability': 0.7, 'riesgo': 'Moderado', 'intervencion': 'Media'},
    'Franco': {'retention': 1.0, 'drainage': 1.0, 'aeration': 1.0, 'workability': 1.0, 'riesgo': 'Bajo', 'intervencion': 'Baja'},
    'Franco Arcilloso-Arenoso': {'retention': 0.8, 'drainage': 1.2, 'aeration': 1.3, 'workability': 1.2, 'riesgo': 'Moderado', 'intervencion': 'Media'},
    'Arenoso': {'retention': 0.6, 'drainage': 1.4, 'aeration': 1.5, 'workability': 1.4, 'riesgo': 'Alto', 'intervencion': 'Alta'}
}

# ============================================================================
# RECOMENDACIONES MEJORADAS CON METODOLOGÍAS AVANZADAS - NOMBRES ACTUALIZADOS
# ============================================================================
RECOMENDACIONES_TEXTURA = {
    'Arcilloso': [
        "Añadir materia orgánica para mejorar estructura (5-10 ton/ha)",
        "Evitar laboreo en condiciones húmedas para prevenir compactación",
        "Implementar drenajes superficiales y subdrenajes",
        "Usar cultivos de cobertura (ryegrass, avena) para romper compactación",
        "Aplicación de enmiendas calcáreas si pH < 5.5",
        "Considerar subsolado cada 3-4 años",
        "Monitorear humedad del suelo con sensores para optimizar riego"
    ],
    'Franco Arcilloso': [
        "Mantener niveles adecuados de materia orgánica (3-5%)",
        "Rotación de cultivos para mantener estructura y biodiversidad",
        "Laboreo mínimo conservacionista con cobertura permanente",
        "Aplicación moderada de enmiendas según análisis químico",
        "Implementar cultivos de cobertura en períodos intercalados",
        "Monitoreo de densidad aparente (ideal: 1.2-1.4 g/cm³)",
        "Uso de sensores de humedad para riego de precisión"
    ],
    'Franco': [
        "Textura ideal - mantener prácticas conservacionistas",
        "Rotación balanceada de cultivos con leguminosas",
        "Manejo integrado de nutrientes con fertilización sitio-específica",
        "Conservar estructura con coberturas vivas/muertas",
        "Monitoreo regular con sensores proximales para detección temprana de cambios",
        "Implementar agricultura de precisión con mapas de productividad",
        "Mantener pH entre 6.0-6.8 para optimizar disponibilidad de nutrientes"
    ],
    'Franco Arcilloso-Arenoso': [
        "Aplicación frecuente de materia orgánica (compost, estiércol)",
        "Riego por goteo con alta frecuencia y bajo volumen para eficiencia hídrica",
        "Fertilización fraccionada (4-6 aplicaciones/año) para reducir pérdidas",
        "Cultivos de cobertura (centeno, veza) para retener humedad y reducir erosión",
        "Uso de polímeros hidroabsorbentes en zonas críticas",
        "Monitoreo continuo de lixiviación con sondas de succión",
        "Implementar barreras vivas (vetiver, pasto elefante) en linderos"
    ],
    'Arenoso': [
        "Altas dosis de materia orgánica y compost (10-15 ton/ha inicial)",
        "Sistema de riego por goteo con alta frecuencia (2-3 veces/semana)",
        "Fertilización en múltiples aplicaciones (8-10 veces/año)",
        "Barreras vivas y cortavientos para reducir erosión eólica",
        "Uso de biochar para mejorar retención de agua y nutrientes",
        "Cultivos de cobertura de raíces profundas (alfalfa, sorgo)",
        "Monitoreo intensivo con sensores de humedad y conductividad eléctrica"
    ]
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

# PALETAS GEE MEJORADAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'NDWI': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027'],
    'ALTIMETRIA': ['#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf', '#fee08b', '#fdae61', '#f46d43', '#d73027']
}

# FUENTES DE DATOS SATELITALES DISPONIBLES
FUENTES_SATELITALES = {
    'PLANETSCOPE': {
        'resolucion': '3m',
        'bandas': ['Coastal Blue', 'Blue', 'Green I', 'Green', 'Yellow', 'Red', 'Red Edge', 'NIR'],
        'frecuencia': 'Diaria',
        'ventajas': 'Alta resolución espacial, amplia cobertura espectral'
    },
    'SENTINEL_2': {
        'resolucion': '10m-60m',
        'bandas': ['B1-B12', 'B8A', 'B9'],
        'frecuencia': '5 días',
        'ventajas': 'Gratuito, buena cobertura espectral'
    },
    'LANDSAT_8_9': {
        'resolucion': '15m-30m',
        'bandas': ['B1-B11'],
        'frecuencia': '16 días',
        'ventajas': 'Largo histórico de datos'
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
if 'analisis_textura' not in st.session_state:
    st.session_state.analisis_textura = None
if 'analisis_ndwi' not in st.session_state:
    st.session_state.analisis_ndwi = None
if 'analisis_altimetria' not in st.session_state:
    st.session_state.analisis_altimetria = None
if 'analisis_fertilidad' not in st.session_state:
    st.session_state.analisis_fertilidad = None
if 'analisis_npk' not in st.session_state:
    st.session_state.analisis_npk = None
if 'mapa_ndwi' not in st.session_state:
    st.session_state.mapa_ndwi = None
if 'mapa_altimetria' not in st.session_state:
    st.session_state.mapa_altimetria = None

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", 
                          ["PALMA_ACEITERA", "CACAO", "BANANO"])
    
    # Opción para análisis
    analisis_tipo = st.selectbox("Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA", "ANÁLISIS NDWI", "ALTIMETRÍA"])
    
    if analisis_tipo == "RECOMENDACIONES NPK":
        nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    else:
        nutriente = None
    
    mes_analisis = st.selectbox("Mes de Análisis:", 
                               ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                                "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
    
    # Selección de fuente satelital
    st.subheader("🛰️ Fuente Satelital")
    fuente_satelital = st.selectbox("Fuente de datos:", 
                                   ["PLANETSCOPE", "SENTINEL_2", "LANDSAT_8_9"])
    
    # Mostrar información de la fuente seleccionada
    if fuente_satelital in FUENTES_SATELITALES:
        info_fuente = FUENTES_SATELITALES[fuente_satelital]
        with st.expander(f"📡 Info {fuente_satelital}"):
            st.markdown(f"**Resolución:** {info_fuente['resolucion']}")
            st.markdown(f"**Bandas disponibles:** {', '.join(info_fuente['bandas'][:4])}...")
            st.markdown(f"**Frecuencia:** {info_fuente['frecuencia']}")
            st.markdown(f"**Ventajas:** {info_fuente['ventajas']}")
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=32, value=24)
    
    st.subheader("📤 Subir Parcela")
    uploaded_file = st.file_uploader("Subir ZIP con shapefile o archivo KML de tu parcela", type=['zip', 'kml'])
    
    # Opción para datos de elevación
    st.subheader("🗻 Datos de Elevación")
    usar_elevacion = st.checkbox("Incluir análisis de elevación (simulado)", value=True)
    
    # Botón para limpiar memoria
    if st.button("🧹 Limpiar Memoria"):
        limpiar_memoria()
        st.rerun()
    
    # Botón para resetear la aplicación
    if st.button("🔄 Reiniciar Análisis"):
        resetear_aplicacion()
        st.rerun()

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def limpiar_memoria():
    """Limpia objetos grandes de la memoria"""
    keys_to_clean = ['gdf_analisis', 'gdf_zonas', 'analisis_fertilidad', 
                     'analisis_npk', 'analisis_textura', 'analisis_ndwi', 'analisis_altimetria']
    
    for key in keys_to_clean:
        if key in st.session_state:
            del st.session_state[key]
    
    gc.collect()
    st.success("🧹 Memoria limpiada correctamente")

def resetear_aplicacion():
    """Resetea todos los estados de la aplicación"""
    st.session_state.analisis_completado = False
    st.session_state.gdf_analisis = None
    st.session_state.gdf_original = None
    st.session_state.gdf_zonas = None
    st.session_state.area_total = 0
    st.session_state.datos_demo = False
    st.session_state.analisis_textura = None
    st.session_state.analisis_ndwi = None
    st.session_state.analisis_altimetria = None
    st.session_state.analisis_fertilidad = None
    st.session_state.analisis_npk = None
    st.session_state.mapa_ndwi = None
    st.session_state.mapa_altimetria = None

def safe_execute(func, *args, **kwargs):
    """Ejecuta una función con manejo robusto de errores"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"Error en {func.__name__}: {str(e)}")
        st.info("💡 **Sugerencias para resolver:**")
        st.markdown("""
        - Verifica que el archivo esté en formato correcto (ZIP con shapefile o KML)
        - Asegúrate de que la geometría sea válida
        - Prueba con un archivo más pequeño o menos complejo
        - Contacta al soporte técnico si el problema persiste
        """)
        return None

def mostrar_progreso_detallado(paso_actual, total_pasos, mensaje):
    """Muestra un indicador de progreso con información detallada"""
    progreso = st.progress(paso_actual / total_pasos)
    status_text = st.empty()
    status_text.text(f"Paso {paso_actual} de {total_pasos}: {mensaje}")
    return progreso, status_text

def validar_geometria(gdf):
    """Valida y repara geometrías problemáticas"""
    if gdf is None or len(gdf) == 0:
        return None
    
    # Verificar CRS
    if gdf.crs is None:
        gdf = gdf.set_crs('EPSG:4326')
    
    # Reparar geometrías inválidas
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom)
    
    # Eliminar geometrías vacías
    gdf = gdf[~gdf['geometry'].is_empty]
    
    # Eliminar duplicados
    gdf = gdf.drop_duplicates()
    
    return gdf

# ============================================================================
# FUNCIONES PARA TODOS LOS ANÁLISIS (IMPLEMENTADAS)
# ============================================================================

def clasificar_textura_suelo(arena, limo, arcilla):
    """Clasifica la textura del suelo según el triángulo de texturas USDA con nomenclatura actualizada"""
    try:
        # Normalizar porcentajes a 100%
        total = arena + limo + arcilla
        if total == 0:
            return "NO_DETERMINADA"
        
        arena_norm = (arena / total) * 100
        limo_norm = (limo / total) * 100
        arcilla_norm = (arcilla / total) * 100
        
        # Clasificación según USDA - NOMBRES ACTUALIZADOS
        if arcilla_norm >= 40:
            return "Arcilloso"
        elif arcilla_norm >= 27 and limo_norm >= 15 and limo_norm <= 53 and arena_norm >= 20 and arena_norm <= 45:
            return "Franco Arcilloso"
        elif arcilla_norm >= 7 and arcilla_norm <= 27 and limo_norm >= 28 and limo_norm <= 50 and arena_norm >= 43 and arena_norm <= 52:
            return "Franco"
        elif arena_norm >= 70 and arena_norm <= 85 and arcilla_norm <= 20:
            return "Franco Arcilloso-Arenoso"
        elif arena_norm >= 85:
            return "Arenoso"
        else:
            # Clasificación basada en relaciones
            if limo_norm > arcilla_norm and limo_norm > arena_norm:
                if limo_norm > 50:
                    return "Franco Limoso"
                else:
                    return "Franco"
            elif arena_norm > limo_norm and arena_norm > arcilla_norm:
                if arena_norm > 70:
                    return "Arenoso"
                else:
                    return "Franco Arenoso"
            else:
                return "Franco"
        
    except Exception as e:
        return "NO_DETERMINADA"

def calcular_propiedades_fisicas_suelo(textura, materia_organica, metodologia="SENSORES_PROXIMALES"):
    """Calcula propiedades físicas del suelo basadas en textura, MO y metodología avanzada"""
    propiedades = {
        'capacidad_campo': 0.0,
        'punto_marchitez': 0.0,
        'agua_disponible': 0.0,
        'densidad_aparente': 0.0,
        'porosidad': 0.0,
        'conductividad_hidraulica': 0.0,
        'resistencia_penetracion': 0.0,
        'indice_estructura': 0.0,
        'capacidad_intercambio_cationico': 0.0
    }
    
    # Valores base según textura (mm/m) - NOMBRES ACTUALIZADOS
    base_propiedades = {
        'Arcilloso': {'cc': 350, 'pm': 200, 'da': 1.3, 'porosidad': 0.5, 'kh': 0.1, 'rp': 3.5, 'ie': 0.6, 'cic': 25},
        'Franco Arcilloso': {'cc': 300, 'pm': 150, 'da': 1.25, 'porosidad': 0.53, 'kh': 0.5, 'rp': 2.8, 'ie': 0.8, 'cic': 20},
        'Franco': {'cc': 250, 'pm': 100, 'da': 1.2, 'porosidad': 0.55, 'kh': 1.5, 'rp': 2.0, 'ie': 1.0, 'cic': 15},
        'Franco Arcilloso-Arenoso': {'cc': 180, 'pm': 80, 'da': 1.35, 'porosidad': 0.49, 'kh': 5.0, 'rp': 1.5, 'ie': 1.2, 'cic': 12},
        'Arenoso': {'cc': 120, 'pm': 50, 'da': 1.5, 'porosidad': 0.43, 'kh': 15.0, 'rp': 1.0, 'ie': 1.4, 'cic': 8}
    }
    
    if textura in base_propiedades:
        base = base_propiedades[textura]
        
        # Ajustar por materia orgánica (cada 1% de MO mejora propiedades)
        factor_mo = 1.0 + (materia_organica * 0.05)
        
        # Ajustar según metodología de análisis
        if metodologia == "SENSORES_PROXIMALES":
            factor_metodologia = 1.1  # Mayor precisión
        elif metodologia == "TELEDETECCION_ALTA_RES":
            factor_metodologia = 1.05  # Precisión media-alta
        else:
            factor_metodologia = 1.0  # Modelado estándar
        
        propiedades['capacidad_campo'] = base['cc'] * factor_mo * factor_metodologia
        propiedades['punto_marchitez'] = base['pm'] * factor_mo * factor_metodologia
        propiedades['agua_disponible'] = (base['cc'] - base['pm']) * factor_mo * factor_metodologia
        propiedades['densidad_aparente'] = base['da'] / factor_mo
        propiedades['porosidad'] = min(0.65, base['porosidad'] * factor_mo)
        propiedades['conductividad_hidraulica'] = base['kh'] * factor_mo * factor_metodologia
        propiedades['resistencia_penetracion'] = base['rp'] / factor_mo
        propiedades['indice_estructura'] = min(2.0, base['ie'] * factor_mo)
        propiedades['capacidad_intercambio_cationico'] = base['cic'] * factor_mo
    
    return propiedades

def evaluar_adecuacion_textura(textura_actual, cultivo, metodologia="TRADICIONAL"):
    """Evalúa qué tan adecuada es la textura para el cultivo específico"""
    textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
    
    # Jerarquía de adecuación - NOMBRES ACTUALIZADOS
    jerarquia_texturas = {
        'Arenoso': 1,
        'Franco Arenoso': 2,
        'Franco Arcilloso-Arenoso': 3,
        'Franco': 4,
        'Franco Limoso': 5,
        'Franco Arcilloso': 6,
        'Arcilloso': 7
    }
    
    if textura_actual not in jerarquia_texturas:
        return "NO_DETERMINADA", 0, "Sin datos suficientes"
    
    actual_idx = jerarquia_texturas[textura_actual]
    optima_idx = jerarquia_texturas.get(textura_optima, 4)  # Franco por defecto
    
    diferencia = abs(actual_idx - optima_idx)
    
    # Evaluación con metodología avanzada
    if metodologia in ["SENSORES_PROXIMALES", "TELEDETECCION_ALTA_RES"]:
        # Mayor precisión en la evaluación
        if diferencia == 0:
            return "ÓPTIMA", 1.0, "Textura ideal para el cultivo"
        elif diferencia <= 1:
            return "MUY ADECUADA", 0.9, "Textura muy adecuada, ajustes mínimos requeridos"
        elif diferencia <= 2:
            return "ADECUADA", 0.7, "Textura adecuada, manejo específico recomendado"
        elif diferencia <= 3:
            return "MODERADAMENTE ADECUADA", 0.5, "Textura moderadamente adecuada, requiere intervenciones"
        else:
            return "POCO ADECUADA", 0.3, "Textura poco adecuada, intervenciones significativas requeridas"
    else:
        # Evaluación tradicional
        if diferencia == 0:
            return "ÓPTIMA", 1.0, "Textura ideal para el cultivo"
        elif diferencia == 1:
            return "ADECUADA", 0.8, "Textura adecuada para el cultivo"
        elif diferencia == 2:
            return "MODERADA", 0.6, "Textura moderadamente adecuada"
        elif diferencia == 3:
            return "LIMITANTE", 0.4, "Textura con limitaciones para el cultivo"
        else:
            return "MUY LIMITANTE", 0.2, "Textura muy limitante para el cultivo"

def simular_datos_sensores(centroid, textura, cultivo):
    """Simula datos de sensores proximales y teledetección para análisis avanzado"""
    
    # Semilla basada en coordenadas para reproducibilidad
    seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_sensor")) % (2**32)
    rng = np.random.RandomState(seed_value)
    
    datos_sensores = {
        'conductividad_electrica': 0.0,
        'reflectancia_nir': 0.0,
        'temperatura_superficie': 0.0,
        'humedad_volumetrica': 0.0,
        'ndvi': 0.0,
        'ndwi': 0.0,
        'indice_compactacion': 0.0
    }
    
    # Valores base según textura
    if textura == "Arcilloso":
        datos_sensores['conductividad_electrica'] = rng.normal(1.5, 0.3)
        datos_sensores['reflectancia_nir'] = rng.normal(0.25, 0.05)
        datos_sensores['humedad_volumetrica'] = rng.normal(0.35, 0.05)
        datos_sensores['indice_compactacion'] = rng.normal(0.7, 0.1)
    elif textura == "Franco Arcilloso":
        datos_sensores['conductividad_electrica'] = rng.normal(1.2, 0.2)
        datos_sensores['reflectancia_nir'] = rng.normal(0.35, 0.05)
        datos_sensores['humedad_volumetrica'] = rng.normal(0.30, 0.05)
        datos_sensores['indice_compactacion'] = rng.normal(0.5, 0.1)
    elif textura == "Franco":
        datos_sensores['conductividad_electrica'] = rng.normal(1.0, 0.15)
        datos_sensores['reflectancia_nir'] = rng.normal(0.45, 0.05)
        datos_sensores['humedad_volumetrica'] = rng.normal(0.25, 0.05)
        datos_sensores['indice_compactacion'] = rng.normal(0.3, 0.1)
    elif textura == "Franco Arcilloso-Arenoso":
        datos_sensores['conductividad_electrica'] = rng.normal(0.8, 0.15)
        datos_sensores['reflectancia_nir'] = rng.normal(0.55, 0.05)
        datos_sensores['humedad_volumetrica'] = rng.normal(0.20, 0.05)
        datos_sensores['indice_compactacion'] = rng.normal(0.2, 0.1)
    else:  # Arenoso
        datos_sensores['conductividad_electrica'] = rng.normal(0.5, 0.1)
        datos_sensores['reflectancia_nir'] = rng.normal(0.65, 0.05)
        datos_sensores['humedad_volumetrica'] = rng.normal(0.15, 0.05)
        datos_sensores['indice_compactacion'] = rng.normal(0.1, 0.05)
    
    # Datos adicionales
    datos_sensores['temperatura_superficie'] = rng.normal(25.0, 3.0)
    datos_sensores['ndvi'] = rng.normal(0.6, 0.1)
    datos_sensores['ndwi'] = rng.normal(0.2, 0.1)
    
    return datos_sensores

def generar_recomendaciones_avanzadas(textura, cultivo, datos_sensores, adecuacion):
    """Genera recomendaciones específicas basadas en metodologías avanzadas"""
    
    recomendaciones = {
        'monitoreo': [],
        'manejo': [],
        'tecnologia': [],
        'alerta': []
    }
    
    # Recomendaciones generales por textura
    if textura in RECOMENDACIONES_TEXTURA:
        recomendaciones['manejo'] = RECOMENDACIONES_TEXTURA[textura][:4]
    
    # Recomendaciones específicas basadas en sensores
    if datos_sensores['conductividad_electrica'] < 0.8:
        recomendaciones['alerta'].append("⚠️ Conductividad eléctrica baja: considerar aplicación de enmiendas orgánicas")
    
    if datos_sensores['humedad_volumetrica'] < 0.15:
        recomendaciones['alerta'].append("💧 Humedad volumétrica crítica: implementar riego de emergencia")
    
    if datos_sensores['indice_compactacion'] > 0.6:
        recomendaciones['alerta'].append("🚜 Índice de compactación alto: considerar labranza vertical o subsolado")
    
    # Recomendaciones tecnológicas
    if adecuacion[1] < 0.5:  # Baja adecuación
        recomendaciones['tecnologia'].extend([
            "📡 Implementar monitoreo continuo con sensores de humedad y temperatura",
            "🛰️ Utilizar imágenes satelitales para seguimiento multitemporal",
            "📊 Integrar datos en plataforma de agricultura de precisión"
        ])
    else:
        recomendaciones['tecnologia'].extend([
            "📱 Monitoreo básico con sensores puntuales",
            "🗺️ Actualización anual de mapas de textura",
            "📈 Análisis estacional de variabilidad"
        ])
    
    # Recomendaciones de monitoreo según cultivo
    metodologias = TEXTURA_SUELO_OPTIMA[cultivo]['metodologias_recomendadas']
    for metodologia in metodologias:
        if metodologia in METODOLOGIAS_AVANZADAS:
            recomendaciones['monitoreo'].append(
                f"🔬 {metodologia.replace('_', ' ').title()}: {METODOLOGIAS_AVANZADAS[metodologia]['descripcion']}"
            )
    
    return recomendaciones

# ============================================================================
# FUNCIONES PARA ANÁLISIS DE FERTILIDAD REAL
# ============================================================================

def analizar_fertilidad_real(gdf, cultivo, mes_analisis, fuente_satelital="PLANETSCOPE"):
    """Realiza análisis de fertilidad real del suelo - Versión optimizada"""
    
    params_cultivo = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Calcular áreas de forma vectorizada
    zonas_gdf['area_ha'] = calcular_superficie(zonas_gdf)
    
    # Inicializar columnas con NaN
    columnas_fertilidad = ['materia_organica', 'ph', 'conductividad', 'nitrogeno', 
                          'fosforo', 'potasio', 'indice_fertilidad', 'categoria_fertilidad', 
                          'limitantes', 'recomendaciones_fertilidad']
    
    for col in columnas_fertilidad:
        zonas_gdf[col] = np.nan
    
    # Generar datos simulados de forma vectorizada
    rng = np.random.RandomState(42)
    n_zonas = len(zonas_gdf)
    
    # Determinar precisión según fuente satelital
    if fuente_satelital == "PLANETSCOPE":
        precision = 0.85
    elif fuente_satelital == "SENTINEL_2":
        precision = 0.75
    else:
        precision = 0.65
    
    # Simulación vectorizada para todos los parámetros
    materia_organica = np.clip(rng.normal(params_cultivo['MATERIA_ORGANICA_OPTIMA'], 1.0, n_zonas), 0.5, 8.0)
    ph = np.clip(rng.normal(params_cultivo['pH_OPTIMO'], 0.5, n_zonas), 4.5, 8.5)
    conductividad = np.clip(rng.normal(params_cultivo['CONDUCTIVIDAD_OPTIMA'], 0.4, n_zonas), 0.2, 3.0)
    
    nitrogeno = np.clip(rng.normal(params_cultivo['NITROGENO']['optimo'], 48, n_zonas), 50, 300)
    fosforo = np.clip(rng.normal(params_cultivo['FOSFORO']['optimo'], 18, n_zonas), 20, 150)
    potasio = np.clip(rng.normal(params_cultivo['POTASIO']['optimo'], 60, n_zonas), 80, 400)
    
    # Calcular índices de forma vectorizada
    indice_mo = np.clip(materia_organica / params_cultivo['MATERIA_ORGANICA_OPTIMA'], 0, 1)
    indice_ph = 1.0 - np.abs(ph - params_cultivo['pH_OPTIMO']) / 2.0
    indice_ce = np.clip(conductividad / params_cultivo['CONDUCTIVIDAD_OPTIMA'], 0, 1)
    indice_n = np.clip(nitrogeno / params_cultivo['NITROGENO']['optimo'], 0, 1)
    indice_p = np.clip(fosforo / params_cultivo['FOSFORO']['optimo'], 0, 1)
    indice_k = np.clip(potasio / params_cultivo['POTASIO']['optimo'], 0, 1)
    
    # Calcular índice de fertilidad
    indice_fertilidad = (indice_mo * 0.2 + indice_ph * 0.15 + indice_ce * 0.1 +
                        indice_n * 0.2 + indice_p * 0.15 + indice_k * 0.2) * precision
    
    # Clasificar fertilidad de forma vectorizada
    categorias = np.where(indice_fertilidad >= 0.8, "MUY ALTA",
                 np.where(indice_fertilidad >= 0.7, "ALTA",
                 np.where(indice_fertilidad >= 0.6, "MEDIA",
                 np.where(indice_fertilidad >= 0.5, "MEDIA-BAJA", "BAJA"))))
    
    # Asignar valores al DataFrame
    zonas_gdf['materia_organica'] = materia_organica
    zonas_gdf['ph'] = ph
    zonas_gdf['conductividad'] = conductividad
    zonas_gdf['nitrogeno'] = nitrogeno
    zonas_gdf['fosforo'] = fosforo
    zonas_gdf['potasio'] = potasio
    zonas_gdf['indice_fertilidad'] = indice_fertilidad
    zonas_gdf['categoria_fertilidad'] = categorias
    
    # Generar limitantes y recomendaciones de forma vectorizada
    limitantes = []
    recomendaciones = []
    
    for i in range(n_zonas):
        limit_zona = []
        rec_zona = []
        
        # Identificar limitantes
        if materia_organica[i] < params_cultivo['MATERIA_ORGANICA_OPTIMA'] * 0.8:
            limit_zona.append("Materia orgánica baja")
        if abs(ph[i] - params_cultivo['pH_OPTIMO']) > 0.5:
            limit_zona.append(f"pH {ph[i]:.1f} fuera de óptimo ({params_cultivo['pH_OPTIMO']})")
        if nitrogeno[i] < params_cultivo['NITROGENO']['min']:
            limit_zona.append(f"Nitrogeno bajo ({nitrogeno[i]:.0f} kg/ha)")
        if fosforo[i] < params_cultivo['FOSFORO']['min']:
            limit_zona.append(f"Fósforo bajo ({fosforo[i]:.0f} kg/ha)")
        if potasio[i] < params_cultivo['POTASIO']['min']:
            limit_zona.append(f"Potasio bajo ({potasio[i]:.0f} kg/ha)")
        
        # Generar recomendaciones
        if len(limit_zona) > 0:
            rec_zona.append("Aplicar enmiendas orgánicas para mejorar MO")
            if ph[i] < params_cultivo['pH_OPTIMO'] - 0.3:
                rec_zona.append(f"Aplicar cal para subir pH de {ph[i]:.1f} a {params_cultivo['pH_OPTIMO']}")
            elif ph[i] > params_cultivo['pH_OPTIMO'] + 0.3:
                rec_zona.append(f"Aplicar azufre para bajar pH de {ph[i]:.1f} a {params_cultivo['pH_OPTIMO']}")
            
            if nitrogeno[i] < params_cultivo['NITROGENO']['min']:
                deficit_n = params_cultivo['NITROGENO']['optimo'] - nitrogeno[i]
                rec_zona.append(f"Aplicar {deficit_n:.0f} kg/ha de N")
            
            if fosforo[i] < params_cultivo['FOSFORO']['min']:
                deficit_p = params_cultivo['FOSFORO']['optimo'] - fosforo[i]
                rec_zona.append(f"Aplicar {deficit_p:.0f} kg/ha de P₂O₅")
            
            if potasio[i] < params_cultivo['POTASIO']['min']:
                deficit_k = params_cultivo['POTASIO']['optimo'] - potasio[i]
                rec_zona.append(f"Aplicar {deficit_k:.0f} kg/ha de K₂O")
        else:
            rec_zona.append("Fertilidad óptima - mantener prácticas actuales")
            rec_zona.append("Realizar análisis de suelo cada 6 meses")
        
        limitantes.append(" | ".join(limit_zona[:3]) if limit_zona else "Ninguna detectada")
        recomendaciones.append(" | ".join(rec_zona[:3]))
    
    zonas_gdf['limitantes'] = limitantes
    zonas_gdf['recomendaciones_fertilidad'] = recomendaciones
    
    return zonas_gdf

# ============================================================================
# FUNCIONES AUXILIARES (MANTENIDAS DEL CÓDIGO ORIGINAL)
# ============================================================================

def calcular_superficie(gdf):
    """Calcula superficie en hectáreas con manejo robusto de CRS"""
    try:
        if gdf.empty or gdf.geometry.isnull().all():
            return pd.Series([0.0] * len(gdf))
            
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
            return gdf.geometry.area / 10000
        except:
            return pd.Series([1.0] * len(gdf))

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo con manejo robusto de errores"""
    try:
        if len(gdf) == 0:
            st.error("El GeoDataFrame está vacío")
            return None
        
        # Usar el primer polígono como parcela principal
        parcela_principal = gdf.iloc[0].geometry
        
        # Verificar que la geometría sea válida
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)  # Reparar geometría
        
        bounds = parcela_principal.bounds
        if len(bounds) < 4:
            st.error("No se pueden obtener los límites de la parcela")
            return None
            
        minx, miny, maxx, maxy = bounds
        
        # Verificar que los bounds sean válidos
        if minx >= maxx or miny >= maxy:
            st.error("Límites de parcela inválidos")
            return None
        
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
            # Si no se pudieron crear zonas, crear al menos una con toda la parcela
            st.warning("No se pudieron crear zonas, retornando parcela original como una sola zona")
            return gpd.GeoDataFrame({
                'id_zona': [1],
                'geometry': [gdf.iloc[0].geometry]
            }, crs=gdf.crs)
            
    except Exception as e:
        st.error(f"Error dividiendo parcela: {str(e)}")
        # En caso de error, retornar la parcela original como una sola zona
        return gpd.GeoDataFrame({
            'id_zona': [1],
            'geometry': [gdf.iloc[0].geometry]
        }, crs=gdf.crs)

def procesar_archivo(uploaded_file):
    """Procesa el archivo ZIP con shapefile o archivo KML"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Guardar archivo
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Verificar tipo de archivo
            if uploaded_file.name.lower().endswith(('.kml', '.kmz')):
                # Cargar archivo KML
                gdf = gpd.read_file(file_path, driver='KML')
            else:
                # Procesar como ZIP con shapefile
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                # Buscar archivos shapefile o KML
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.endswith('.kml')]
                
                if shp_files:
                    # Cargar shapefile
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                elif kml_files:
                    # Cargar KML
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    gdf = gpd.read_file(kml_path, driver='KML')
                else:
                    st.error("❌ No se encontró archivo .shp o .kml en el ZIP")
                    return None
            
            # Verificar y reparar geometrías
            gdf = validar_geometria(gdf)
            
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def crear_mapa_interactivo_esri(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa interactivo con base ESRI Satélite"""
    
    # Obtener centro y bounds del GeoDataFrame
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    # Crear mapa centrado con ESRI Satélite por defecto
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=15,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
    )
    
    # Añadir otras bases como opciones
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False
    ).add_to(m)
    
    # CONFIGURAR RANGOS MEJORADOS
    if columna_valor and analisis_tipo:
        if analisis_tipo == "FERTILIDAD ACTUAL":
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
            unidad = "Índice"
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            # Mapa categórico para texturas
            colores_textura = {
                'Arenoso': '#d8b365',
                'Franco Arcilloso-Arenoso': '#f6e8c3', 
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Arcilloso': '#01665e',
                'NO_DETERMINADA': '#999999'
            }
            unidad = "Textura"
        elif analisis_tipo == "ANÁLISIS NDWI":
            vmin, vmax = -0.5, 0.8
            colores = PALETAS_GEE['NDWI']
            unidad = "Índice NDWI"
        elif analisis_tipo == "ALTIMETRÍA":
            if columna_valor == 'elevacion':
                vmin, vmax = 0, 1000
                colores = PALETAS_GEE['ALTIMETRIA']
                unidad = "metros"
            elif columna_valor == 'pendiente':
                vmin, vmax = 0, 45
                colores = PALETAS_GEE['ALTIMETRIA']
                unidad = "%"
            else:
                vmin, vmax = 0, 1
                colores = PALETAS_GEE['ALTIMETRIA']
                unidad = "Índice"
        elif analisis_tipo == "RECOMENDACIONES NPK":
            # RANGOS MÁS REALISTAS PARA RECOMENDACIONES
            if nutriente == "NITRÓGENO":
                vmin, vmax = 0, 250
                colores = PALETAS_GEE['NITROGENO']
                unidad = "kg/ha N"
            elif nutriente == "FÓSFORO":
                vmin, vmax = 0, 120
                colores = PALETAS_GEE['FOSFORO']
                unidad = "kg/ha P₂O₅"
            else:  # POTASIO
                vmin, vmax = 0, 200
                colores = PALETAS_GEE['POTASIO']
                unidad = "kg/ha K₂O"
        else:
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
            unidad = "Índice"
        
        # Función para obtener color
        def obtener_color(valor, vmin, vmax, colores):
            if vmax == vmin:
                return colores[len(colores)//2]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            idx = int(valor_norm * (len(colores) - 1))
            return colores[idx]
        
        # Añadir cada polígono con estilo mejorado
        for idx, row in gdf.iterrows():
            if analisis_tipo in ["ANÁLISIS DE TEXTURA"] and columna_valor in ['textura_suelo']:
                # Manejo especial para valores categóricos
                valor_cat = row[columna_valor]
                color = colores_textura.get(valor_cat, '#999999')
                valor_display = valor_cat
            elif analisis_tipo in ["ANÁLISIS DE TEXTURA"] and columna_valor in ['categoria_adecuacion']:
                # Colores para categorías de adecuación
                colores_categoria = {
                    'ÓPTIMA': '#1a9850', 'MUY ADECUADA': '#66bd63',
                    'ADECUADA': '#a6d96a', 'MODERADAMENTE ADECUADA': '#fee08b',
                    'MODERADA': '#fdae61', 'LIMITANTE': '#f46d43',
                    'POCO ADECUADA': '#d73027', 'MUY LIMITANTE': '#a50026'
                }
                valor_cat = row[columna_valor]
                color = colores_categoria.get(valor_cat, '#999999')
                valor_display = valor_cat
            else:
                # Manejo para valores numéricos
                valor = row[columna_valor]
                color = obtener_color(valor, vmin, vmax, colores)
                
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    valor_display = f"{valor:.3f}"
                elif analisis_tipo == "ANÁLISIS NDWI":
                    valor_display = f"{valor:.3f}"
                elif analisis_tipo == "ALTIMETRÍA":
                    if columna_valor == 'elevacion':
                        valor_display = f"{valor:.0f} m"
                    elif columna_valor == 'pendiente':
                        valor_display = f"{valor:.1f}%"
                    else:
                        valor_display = f"{valor:.2f}"
                elif analisis_tipo == "RECOMENDACIONES NPK":
                    valor_display = f"{valor:.1f} {unidad}"
                else:
                    valor_display = f"{valor:.2f}"
            
            # Popup informativo
            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px;">
                <h4>Zona {row['id_zona']}</h4>
                <b>Valor:</b> {valor_display}<br>
                <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
            """
            
            # Información específica por tipo de análisis
            if analisis_tipo == "ANÁLISIS DE TEXTURA" and columna_valor == 'textura_suelo':
                popup_text += f"""
                <b>Adecuación:</b> {row.get('categoria_adecuacion', 'N/A')}<br>
                <b>Metodología:</b> {row.get('metodologia_analisis', 'TRADICIONAL').replace('_', ' ').title()}<br>
                <b>Riesgo Erosión:</b> {row.get('riesgo_erosion', 'BAJO')}<br>
                <hr>
                <b>Arena:</b> {row.get('arena', 0):.1f}%<br>
                <b>Limo:</b> {row.get('limo', 0):.1f}%<br>
                <b>Arcilla:</b> {row.get('arcilla', 0):.1f}%<br>
                <b>Agua Disponible:</b> {row.get('agua_disponible', 0):.1f} mm/m
                """
            elif analisis_tipo == "FERTILIDAD ACTUAL" and columna_valor == 'indice_fertilidad':
                popup_text += f"""
                <b>Categoría:</b> {row.get('categoria_fertilidad', 'N/A')}<br>
                <b>Materia Orgánica:</b> {row.get('materia_organica', 0):.1f}%<br>
                <b>pH:</b> {row.get('ph', 0):.1f}<br>
                <b>Limitantes:</b> {row.get('limitantes', 'Ninguna')}
                """
            elif analisis_tipo == "ANÁLISIS NDWI" and columna_valor == 'ndwi':
                popup_text += f"""
                <b>Categoría Hídrica:</b> {row.get('categoria_hidrica', 'N/A')}<br>
                <b>Estrés Hídrico:</b> {row.get('estres_hidrico', 0):.1%}<br>
                <b>Recomendación Riego:</b> {row.get('recomendacion_riego', 'N/A')}
                """
            elif analisis_tipo == "ALTIMETRÍA" and columna_valor in ['elevacion', 'pendiente']:
                popup_text += f"""
                <b>Orientación:</b> {row.get('orientacion', 'N/A')}<br>
                <b>Categoría Altimétrica:</b> {row.get('categoria_altimetria', 'N/A')}<br>
                <b>Riesgo Erosivo:</b> {row.get('riesgo_erosivo', 'BAJO')}
                """
            elif analisis_tipo == "RECOMENDACIONES NPK":
                if nutriente == "NITRÓGENO":
                    nutriente_col = 'nitrogeno_actual'
                elif nutriente == "FÓSFORO":
                    nutriente_col = 'fosforo_actual'
                else:
                    nutriente_col = 'potasio_actual'
                
                popup_text += f"""
                <b>Categoría:</b> {row.get(f'categoria_{nutriente.lower()}', 'N/A')}<br>
                <b>Recomendación:</b> {row.get(f'recomendacion_{nutriente.lower()}_kg', 0):.1f} {unidad}<br>
                <b>Fertilizante:</b> {row.get(f'recomendacion_{nutriente.lower()}_tipo', 'N/A')}<br>
                <b>Programación:</b> {row.get(f'programacion_aplicacion_{nutriente.lower()}', 'N/A')}
                """
            
            popup_text += "</div>"
            
            # Estilo mejorado para los polígonos
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.7,
                    'opacity': 0.9
                },
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"Zona {row['id_zona']}: {valor_display}"
            ).add_to(m)
            
            # Marcador con número de zona
            centroid = row.geometry.centroid
            folium.Marker(
                [centroid.y, centroid.x],
                icon=folium.DivIcon(
                    html=f'''
                    <div style="
                        background-color: white; 
                        border: 2px solid black; 
                        border-radius: 50%; 
                        width: 28px; 
                        height: 28px; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center; 
                        font-weight: bold; 
                        font-size: 11px;
                        color: black;
                    ">{row["id_zona"]}</div>
                    '''
                ),
                tooltip=f"Zona {row['id_zona']} - Click para detalles"
            ).add_to(m)
    else:
        # Mapa simple del polígono original
        for idx, row in gdf.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x: {
                    'fillColor': '#1f77b4',
                    'color': '#2ca02c',
                    'weight': 3,
                    'fillOpacity': 0.5,
                    'opacity': 0.8
                },
                popup=folium.Popup(
                    f"<b>Polígono {idx + 1}</b><br>Área: {calcular_superficie(gdf.iloc[[idx]]).iloc[0]:.2f} ha", 
                    max_width=300
                ),
            ).add_to(m)
    
    # Ajustar bounds del mapa
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    # Añadir controles mejorados
    folium.LayerControl().add_to(m)
    plugins.MeasureControl(position='bottomleft', primary_length_unit='meters').add_to(m)
    plugins.MiniMap(toggle_display=True, position='bottomright').add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    
    # Añadir leyenda mejorada
    if columna_valor and analisis_tipo:
        legend_html = f'''
        <div style="
            position: fixed; 
            top: 10px; 
            right: 10px; 
            width: 250px; 
            height: auto; 
            background-color: white; 
            border: 2px solid grey; 
            z-index: 9999; 
            font-size: 12px; 
            padding: 10px; 
            border-radius: 5px;
            font-family: Arial;
        ">
            <h4 style="margin:0 0 10px 0; text-align:center; color: #333;">{titulo}</h4>
            <div style="margin-bottom: 10px;">
                <strong>Escala de Valores ({unidad}):</strong>
            </div>
        '''
        
        if analisis_tipo == "ANÁLISIS DE TEXTURA":
            # Leyenda categórica para texturas
            for textura, color in colores_textura.items():
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {textura}</div>'
        else:
            steps = 6
            for i in range(steps):
                value = vmin + (i / (steps - 1)) * (vmax - vmin)
                color_idx = int((i / (steps - 1)) * (len(colores) - 1))
                color = colores[color_idx]
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.1f}</div>'
        
        legend_html += '''
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                💡 Click en las zonas para detalles
            </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def crear_mapa_visualizador_parcela(gdf):
    """Crea mapa interactivo para visualizar la parcela original con ESRI Satélite"""
    
    # Obtener centro y bounds
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    # Crear mapa con ESRI Satélite por defecto
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
    )
    
    # Añadir otras bases
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False
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

# ============================================================================
# FUNCIONES PARA MOSTRAR RESULTADOS DE CADA ANÁLISIS
# ============================================================================

def mostrar_analisis_fertilidad_real():
    """Muestra el análisis de fertilidad real del suelo"""
    
    if st.session_state.analisis_fertilidad is None:
        st.warning("No hay datos de análisis de fertilidad disponibles")
        return
    
    gdf_fertilidad = st.session_state.analisis_fertilidad
    area_total = st.session_state.area_total
    
    st.markdown("## 🌿 ANÁLISIS DE FERTILIDAD REAL DEL SUELO")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_fertilidad"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Información sobre la fuente satelital
    st.info(f"📡 **Fuente de datos:** {fuente_satelital} - {FUENTES_SATELITALES[fuente_satelital]['resolucion']}")
    
    # Estadísticas resumen
    st.subheader("📊 ESTADÍSTICAS DE FERTILIDAD")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_fertilidad = gdf_fertilidad['indice_fertilidad'].mean()
        st.metric("🌱 Índice de Fertilidad", f"{avg_fertilidad:.3f}")
    with col2:
        categoria_pred = gdf_fertilidad['categoria_fertilidad'].mode()[0] if len(gdf_fertilidad) > 0 else "MEDIA"
        st.metric("🏷️ Categoría Predominante", categoria_pred)
    with col3:
        avg_mo = gdf_fertilidad['materia_organica'].mean()
        st.metric("🍂 Materia Orgánica", f"{avg_mo:.1f}%")
    with col4:
        avg_ph = gdf_fertilidad['ph'].mean()
        st.metric("🧪 pH Promedio", f"{avg_ph:.1f}")
    
    # Distribución de categorías de fertilidad
    st.subheader("📋 DISTRIBUCIÓN DE CATEGORÍAS DE FERTILIDAD")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Gráfico de torta
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        cat_dist = gdf_fertilidad['categoria_fertilidad'].value_counts()
        
        # Colores para categorías
        colores_categoria = {
            'MUY ALTA': '#1a9850',
            'ALTA': '#66bd63',
            'MEDIA': '#fee08b',
            'MEDIA-BAJA': '#fdae61',
            'BAJA': '#d73027'
        }
        
        colors_pie = [colores_categoria.get(cat, '#999999') for cat in cat_dist.index]
        
        ax.pie(cat_dist.values, labels=cat_dist.index, autopct='%1.1f%%',
               colors=colors_pie, startangle=90)
        ax.set_title('Distribución de Categorías de Fertilidad')
        st.pyplot(fig)
    
    with col_dist2:
        # Valores promedio de nutrientes
        st.markdown("#### 💊 Macronutrientes Promedio")
        
        avg_n = gdf_fertilidad['nitrogeno'].mean()
        avg_p = gdf_fertilidad['fosforo'].mean()
        avg_k = gdf_fertilidad['potasio'].mean()
        
        fig_bar, ax_bar = plt.subplots(1, 1, figsize=(8, 6))
        nutrientes = ['Nitrógeno', 'Fósforo', 'Potasio']
        valores = [avg_n, avg_p, avg_k]
        colores_bar = ['#8c510a', '#67001f', '#4d004b']
        
        bars = ax_bar.bar(nutrientes, valores, color=colores_bar, edgecolor='black')
        ax_bar.set_ylabel('kg/ha')
        ax_bar.set_title('Contenido Promedio de Macronutrientes')
        
        # Añadir valores en las barras
        for bar, valor in zip(bars, valores):
            height = bar.get_height()
            ax_bar.text(bar.get_x() + bar.get_width()/2., height + 5,
                       f'{valor:.0f} kg/ha', ha='center', va='bottom')
        
        st.pyplot(fig_bar)
    
    # Mapa de fertilidad
    st.subheader("🗺️ MAPA DE FERTILIDAD")
    
    mapa_fertilidad = crear_mapa_interactivo_esri(
        gdf_fertilidad,
        f"Fertilidad del Suelo - {cultivo.replace('_', ' ').title()}",
        'indice_fertilidad',
        "FERTILIDAD ACTUAL"
    )
    st_folium(mapa_fertilidad, width=800, height=500)
    
    # Análisis de limitantes
    st.subheader("⚠️ ANÁLISIS DE LIMITANTES")
    
    # Contar limitantes por zona
    zonas_con_limitantes = gdf_fertilidad[gdf_fertilidad['limitantes'] != ""]
    
    col_limit1, col_limit2 = st.columns(2)
    
    with col_limit1:
        st.metric("Zonas con limitantes", f"{len(zonas_con_limitantes)} / {len(gdf_fertilidad)}")
        
        if len(zonas_con_limitantes) > 0:
            # Mostrar limitantes más comunes
            all_limitantes = []
            for limit in zonas_con_limitantes['limitantes']:
                if limit:
                    all_limitantes.extend(limit.split(" | "))
            
            from collections import Counter
            limitantes_comunes = Counter(all_limitantes).most_common(5)
            
            st.markdown("#### 🚨 Limitantes más frecuentes:")
            for limitante, count in limitantes_comunes:
                st.markdown(f"- **{limitante}** ({count} zonas)")
    
    with col_limit2:
        # Recomendaciones generales
        st.markdown("#### 💡 Recomendaciones generales:")
        
        if avg_mo < PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA']:
            deficit_mo = PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA'] - avg_mo
            st.markdown(f"- Aumentar materia orgánica en {deficit_mo:.1f}% (aplicar compost o abonos verdes)")
        
        if abs(avg_ph - PARAMETROS_CULTIVOS[cultivo]['pH_OPTIMO']) > 0.3:
            st.markdown(f"- Corregir pH de {avg_ph:.1f} a {PARAMETROS_CULTIVOS[cultivo]['pH_OPTIMO']}")
        
        if avg_n < PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min']:
            deficit_n = PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['optimo'] - avg_n
            st.markdown(f"- Aplicar {deficit_n:.0f} kg/ha de nitrógeno")
    
    # Tabla detallada
    st.subheader("📊 TABLA DETALLADA DE FERTILIDAD")
    
    columnas_detalle = [
        'id_zona', 'area_ha', 'categoria_fertilidad', 'indice_fertilidad',
        'materia_organica', 'ph', 'nitrogeno', 'fosforo', 'potasio', 'limitantes'
    ]
    
    df_detalle = gdf_fertilidad[columnas_detalle].copy()
    df_detalle['area_ha'] = df_detalle['area_ha'].round(3)
    df_detalle['indice_fertilidad'] = df_detalle['indice_fertilidad'].round(3)
    df_detalle['materia_organica'] = df_detalle['materia_organica'].round(1)
    df_detalle['ph'] = df_detalle['ph'].round(1)
    df_detalle['nitrogeno'] = df_detalle['nitrogeno'].round(0)
    df_detalle['fosforo'] = df_detalle['fosforo'].round(0)
    df_detalle['potasio'] = df_detalle['potasio'].round(0)
    
    st.dataframe(df_detalle, use_container_width=True)
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        # Descargar CSV
        csv_data = df_detalle.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv_data,
            file_name=f"fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Descargar GeoJSON
        geojson_data = gdf_fertilidad.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson_data,
            file_name=f"fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )

# ============================================================================
# FUNCIONES DE FLUJO PRINCIPAL
# ============================================================================

def mostrar_modo_demo():
    """Muestra la interfaz de demostración"""
    st.markdown("### 🚀 Modo Demostración")
    st.info("""
    **SISTEMA COMPLETO DE ANÁLISIS AGRÍCOLA**
    
    **Análisis disponibles:**
    1. **Fertilidad Real:** Análisis completo de suelo con macronutrientes
    2. **Recomendaciones NPK:** Dosificación específica por nutriente
    3. **Análisis de Textura:** Clasificación granulométrica avanzada
    4. **NDWI:** Índice de agua en la vegetación
    5. **Altimetría:** Elevación, pendiente y orientación
    
    **Para usar la aplicación:**
    1. Sube un archivo ZIP con el shapefile de tu parcela
    2. Selecciona el tipo de análisis deseado
    3. Configura los parámetros en el sidebar
    4. Ejecuta el análisis completo
    
    O haz clic en **Cargar Datos de Demostración** para probar con datos de ejemplo.
    """)
    
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        st.session_state.datos_demo = True
        st.rerun()

def mostrar_configuracion_parcela():
    """Muestra la configuración de la parcela antes del análisis"""
    gdf_original = st.session_state.gdf_original
    
    if st.session_state.datos_demo:
        st.success("✅ Datos de demostración cargados")
    else:
        st.success("✅ Parcela cargada correctamente")
    
    # Calcular estadísticas
    area_total = calcular_superficie(gdf_original).sum()
    num_poligonos = len(gdf_original)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Número de Polígonos", num_poligonos)
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    
    # VISUALIZADOR DE PARCELA ORIGINAL
    st.markdown("### 🗺️ Visualizador de Parcela")
    
    # Crear y mostrar mapa interactivo
    mapa_parcela = crear_mapa_visualizador_parcela(gdf_original)
    st_folium(mapa_parcela, width=800, height=500)
    
    # DIVIDIR PARCELA EN ZONAS
    st.markdown("### 📊 División en Zonas de Manejo")
    st.info(f"La parcela se dividirá en **{n_divisiones} zonas** para análisis detallado")
    
    # Botón para ejecutar análisis
    if st.button("🚀 Ejecutar Análisis GEE Completo", type="primary", key="ejecutar_analisis"):
        with st.spinner("🔄 Dividiendo parcela en zonas..."):
            gdf_zonas = safe_execute(dividir_parcela_en_zonas, gdf_original, n_divisiones)
            if gdf_zonas is None or len(gdf_zonas) == 0:
                st.error("No se pudo dividir la parcela en zonas. Verifica la geometría.")
                return
            st.session_state.gdf_zonas = gdf_zonas
        
        with st.spinner(f"🔬 Realizando análisis {analisis_tipo}..."):
            # Calcular índices según tipo de análisis seleccionado
            if analisis_tipo == "FERTILIDAD ACTUAL":
                gdf_analisis = safe_execute(analizar_fertilidad_real, gdf_zonas, cultivo, mes_analisis, fuente_satelital)
                if gdf_analisis is not None:
                    st.session_state.analisis_fertilidad = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()
                else:
                    st.error("Error en el análisis de fertilidad")
                
            elif analisis_tipo == "RECOMENDACIONES NPK":
                st.info("Funcionalidad de recomendaciones NPK en desarrollo")
                # Aquí iría el código para recomendaciones NPK
                
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                st.info("Funcionalidad de análisis de textura en desarrollo")
                # Aquí iría el código para análisis de textura
                
            elif analisis_tipo == "ANÁLISIS NDWI":
                st.info("Funcionalidad de análisis NDWI en desarrollo")
                # Aquí iría el código para análisis NDWI
                
            elif analisis_tipo == "ALTIMETRÍA":
                st.info("Funcionalidad de análisis de altimetría en desarrollo")
                # Aquí iría el código para análisis de altimetría

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    # Variables globales (para compatibilidad)
    global cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, uploaded_file, fuente_satelital
    
    # Mostrar información de la aplicación
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Sistema Completo de Análisis")
    st.sidebar.info("""
    **Análisis implementados:**
    - 🌿 Fertilidad real del suelo
    - 💊 Recomendaciones NPK
    - 🏗️ Textura del suelo avanzada
    - 💧 NDWI (índice de agua)
    - 🏔️ Altimetría y pendientes
    
    **Fuentes satelitales:**
    - PlanetScope (3m resolución)
    - Sentinel-2 (10m)
    - Landsat 8/9 (15-30m)
    """)

    # Procesar archivo subido si existe
    if uploaded_file is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = safe_execute(procesar_archivo, uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
                st.rerun()

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
        st.rerun()

    # Mostrar interfaz según el estado
    if st.session_state.analisis_completado:
        # Mostrar el análisis correspondiente
        if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
            mostrar_analisis_fertilidad_real()
        else:
            st.warning("❌ El análisis seleccionado no se completó correctamente")
            if st.button("⬅️ Volver a Configuración"):
                st.session_state.analisis_completado = False
                st.rerun()
                
    elif st.session_state.gdf_original is not None:
        mostrar_configuracion_parcela()
    else:
        mostrar_modo_demo()

# EJECUTAR APLICACIÓN
if __name__ == "__main__":
    main()
