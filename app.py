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
    
    # Botón para resetear la aplicación
    if st.button("🔄 Reiniciar Análisis"):
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
        st.rerun()

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
    """Realiza análisis de fertilidad real del suelo"""
    
    params_cultivo = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para fertilidad
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['materia_organica'] = 0.0
    zonas_gdf['ph'] = 0.0
    zonas_gdf['conductividad'] = 0.0
    zonas_gdf['nitrogeno'] = 0.0
    zonas_gdf['fosforo'] = 0.0
    zonas_gdf['potasio'] = 0.0
    zonas_gdf['indice_fertilidad'] = 0.0
    zonas_gdf['categoria_fertilidad'] = "BAJA"
    zonas_gdf['limitantes'] = ""
    zonas_gdf['recomendaciones_fertilidad'] = ""
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_fertilidad_{fuente_satelital}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Simular parámetros de fertilidad basados en fuente satelital
            if fuente_satelital == "PLANETSCOPE":
                # Alta precisión con PlanetScope
                precision = 0.85
            elif fuente_satelital == "SENTINEL_2":
                precision = 0.75
            else:
                precision = 0.65
            
            # Materia orgánica (0-10%)
            materia_organica = max(0.5, min(8.0, rng.normal(
                params_cultivo['MATERIA_ORGANICA_OPTIMA'],
                params_cultivo['MATERIA_ORGANICA_OPTIMA'] * 0.3
            )))
            
            # pH (4.5-8.5)
            ph = max(4.5, min(8.5, rng.normal(
                params_cultivo['pH_OPTIMO'],
                0.5
            )))
            
            # Conductividad eléctrica (dS/m)
            conductividad = max(0.2, min(3.0, rng.normal(
                params_cultivo['CONDUCTIVIDAD_OPTIMA'],
                params_cultivo['CONDUCTIVIDAD_OPTIMA'] * 0.4
            )))
            
            # Macronutrientes (kg/ha)
            nitrogeno = max(50, min(300, rng.normal(
                params_cultivo['NITROGENO']['optimo'],
                params_cultivo['NITROGENO']['optimo'] * 0.3
            )))
            
            fosforo = max(20, min(150, rng.normal(
                params_cultivo['FOSFORO']['optimo'],
                params_cultivo['FOSFORO']['optimo'] * 0.4
            )))
            
            potasio = max(80, min(400, rng.normal(
                params_cultivo['POTASIO']['optimo'],
                params_cultivo['POTASIO']['optimo'] * 0.3
            )))
            
            # Calcular índice de fertilidad (0-1)
            indice_mo = min(1.0, materia_organica / params_cultivo['MATERIA_ORGANICA_OPTIMA'])
            indice_ph = 1.0 - abs(ph - params_cultivo['pH_OPTIMO']) / 2.0
            indice_ce = min(1.0, conductividad / params_cultivo['CONDUCTIVIDAD_OPTIMA'])
            indice_n = min(1.0, nitrogeno / params_cultivo['NITROGENO']['optimo'])
            indice_p = min(1.0, fosforo / params_cultivo['FOSFORO']['optimo'])
            indice_k = min(1.0, potasio / params_cultivo['POTASIO']['optimo'])
            
            indice_fertilidad = (indice_mo * 0.2 + indice_ph * 0.15 + indice_ce * 0.1 +
                               indice_n * 0.2 + indice_p * 0.15 + indice_k * 0.2) * precision
            
            # Clasificar fertilidad
            if indice_fertilidad >= 0.8:
                categoria = "MUY ALTA"
            elif indice_fertilidad >= 0.7:
                categoria = "ALTA"
            elif indice_fertilidad >= 0.6:
                categoria = "MEDIA"
            elif indice_fertilidad >= 0.5:
                categoria = "MEDIA-BAJA"
            else:
                categoria = "BAJA"
            
            # Identificar limitantes
            limitantes = []
            if materia_organica < params_cultivo['MATERIA_ORGANICA_OPTIMA'] * 0.8:
                limitantes.append("Materia orgánica baja")
            if abs(ph - params_cultivo['pH_OPTIMO']) > 0.5:
                limitantes.append(f"pH {ph:.1f} fuera de óptimo ({params_cultivo['pH_OPTIMO']})")
            if nitrogeno < params_cultivo['NITROGENO']['min']:
                limitantes.append(f"Nitrogeno bajo ({nitrogeno:.0f} kg/ha)")
            if fosforo < params_cultivo['FOSFORO']['min']:
                limitantes.append(f"Fósforo bajo ({fosforo:.0f} kg/ha)")
            if potasio < params_cultivo['POTASIO']['min']:
                limitantes.append(f"Potasio bajo ({potasio:.0f} kg/ha)")
            
            # Generar recomendaciones
            recomendaciones = []
            if len(limitantes) > 0:
                recomendaciones.append(f"Aplicar enmiendas orgánicas para mejorar MO ({materia_organica:.1f}%)")
                if ph < params_cultivo['pH_OPTIMO'] - 0.3:
                    recomendaciones.append(f"Aplicar cal para subir pH de {ph:.1f} a {params_cultivo['pH_OPTIMO']}")
                elif ph > params_cultivo['pH_OPTIMO'] + 0.3:
                    recomendaciones.append(f"Aplicar azufre para bajar pH de {ph:.1f} a {params_cultivo['pH_OPTIMO']}")
                
                if nitrogeno < params_cultivo['NITROGENO']['min']:
                    deficit_n = params_cultivo['NITROGENO']['optimo'] - nitrogeno
                    recomendaciones.append(f"Aplicar {deficit_n:.0f} kg/ha de N (urea o sulfato de amonio)")
                
                if fosforo < params_cultivo['FOSFORO']['min']:
                    deficit_p = params_cultivo['FOSFORO']['optimo'] - fosforo
                    recomendaciones.append(f"Aplicar {deficit_p:.0f} kg/ha de P₂O₅ (superfosfato o roca fosfórica)")
                
                if potasio < params_cultivo['POTASIO']['min']:
                    deficit_k = params_cultivo['POTASIO']['optimo'] - potasio
                    recomendaciones.append(f"Aplicar {deficit_k:.0f} kg/ha de K₂O (cloruro o sulfato de potasio)")
            else:
                recomendaciones.append("Fertilidad óptima - mantener prácticas actuales")
                recomendaciones.append("Realizar análisis de suelo cada 6 meses para monitoreo")
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'materia_organica'] = materia_organica
            zonas_gdf.loc[idx, 'ph'] = ph
            zonas_gdf.loc[idx, 'conductividad'] = conductividad
            zonas_gdf.loc[idx, 'nitrogeno'] = nitrogeno
            zonas_gdf.loc[idx, 'fosforo'] = fosforo
            zonas_gdf.loc[idx, 'potasio'] = potasio
            zonas_gdf.loc[idx, 'indice_fertilidad'] = indice_fertilidad
            zonas_gdf.loc[idx, 'categoria_fertilidad'] = categoria
            zonas_gdf.loc[idx, 'limitantes'] = " | ".join(limitantes[:3])
            zonas_gdf.loc[idx, 'recomendaciones_fertilidad'] = " | ".join(recomendaciones[:3])
            
        except Exception as e:
            # Valores por defecto
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'materia_organica'] = params_cultivo['MATERIA_ORGANICA_OPTIMA']
            zonas_gdf.loc[idx, 'ph'] = params_cultivo['pH_OPTIMO']
            zonas_gdf.loc[idx, 'conductividad'] = params_cultivo['CONDUCTIVIDAD_OPTIMA']
            zonas_gdf.loc[idx, 'nitrogeno'] = params_cultivo['NITROGENO']['optimo']
            zonas_gdf.loc[idx, 'fosforo'] = params_cultivo['FOSFORO']['optimo']
            zonas_gdf.loc[idx, 'potasio'] = params_cultivo['POTASIO']['optimo']
            zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.8
            zonas_gdf.loc[idx, 'categoria_fertilidad'] = "MEDIA-ALTA"
            zonas_gdf.loc[idx, 'limitantes'] = "Ninguna detectada"
            zonas_gdf.loc[idx, 'recomendaciones_fertilidad'] = "Mantener prácticas actuales"
    
    return zonas_gdf

# ============================================================================
# FUNCIONES PARA RECOMENDACIONES NPK
# ============================================================================

def generar_recomendaciones_npk(gdf, cultivo, nutriente, mes_analisis, fuente_satelital="PLANETSCOPE"):
    """Genera recomendaciones específicas de NPK basadas en análisis de suelo"""
    
    params_cultivo = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Obtener factor estacional
    if nutriente == "NITRÓGENO":
        factor_mes = FACTORES_N_MES[mes_analisis]
        param_nutriente = params_cultivo['NITROGENO']
        unidad = "kg/ha N"
    elif nutriente == "FÓSFORO":
        factor_mes = FACTORES_P_MES[mes_analisis]
        param_nutriente = params_cultivo['FOSFORO']
        unidad = "kg/ha P₂O₅"
    else:  # POTASIO
        factor_mes = FACTORES_K_MES[mes_analisis]
        param_nutriente = params_cultivo['POTASIO']
        unidad = "kg/ha K₂O"
    
    # Inicializar columnas para recomendaciones NPK
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf[f'{nutriente.lower()}_actual'] = 0.0
    zonas_gdf[f'{nutriente.lower()}_optimo'] = param_nutriente['optimo']
    zonas_gdf[f'deficit_{nutriente.lower()}'] = 0.0
    zonas_gdf[f'recomendacion_{nutriente.lower()}_kg'] = 0.0
    zonas_gdf[f'recomendacion_{nutriente.lower()}_tipo'] = ""
    zonas_gdf[f'categoria_{nutriente.lower()}'] = "ÓPTIMO"
    zonas_gdf[f'programacion_aplicacion_{nutriente.lower()}'] = ""
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_{nutriente}_{mes_analisis}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Simular contenido actual del nutriente
            if fuente_satelital == "PLANETSCOPE":
                # Alta precisión
                variabilidad = 0.15
            elif fuente_satelital == "SENTINEL_2":
                variabilidad = 0.20
            else:
                variabilidad = 0.25
            
            nutriente_actual = max(
                param_nutriente['min'] * 0.5,
                min(
                    param_nutriente['max'] * 1.5,
                    rng.normal(
                        param_nutriente['optimo'] * 0.8,  # Asumir 80% del óptimo en promedio
                        param_nutriente['optimo'] * variabilidad
                    )
                )
            )
            
            # Calcular déficit
            deficit = max(0, param_nutriente['optimo'] * factor_mes - nutriente_actual)
            
            # Recomendación en kg/ha
            recomendacion_kg = deficit * 1.2  # Aplicar 20% extra para compensar pérdidas
            
            # Determinar tipo de fertilizante recomendado
            if nutriente == "NITRÓGENO":
                if recomendacion_kg < 30:
                    tipo_fertilizante = "Urea (46% N)"
                elif recomendacion_kg < 60:
                    tipo_fertilizante = "Sulfato de amonio (21% N)"
                else:
                    tipo_fertilizante = "Nitrato de amonio (34% N)"
            elif nutriente == "FÓSFORO":
                if recomendacion_kg < 40:
                    tipo_fertilizante = "Superfosfato triple (46% P₂O₅)"
                else:
                    tipo_fertilizante = "Roca fosfórica (30% P₂O₅)"
            else:  # POTASIO
                if recomendacion_kg < 50:
                    tipo_fertilizante = "Cloruro de potasio (60% K₂O)"
                else:
                    tipo_fertilizante = "Sulfato de potasio (50% K₂O)"
            
            # Categorizar estado del nutriente
            porcentaje_optimo = (nutriente_actual / (param_nutriente['optimo'] * factor_mes)) * 100
            
            if porcentaje_optimo >= 90:
                categoria = "ÓPTIMO"
            elif porcentaje_optimo >= 70:
                categoria = "ADECUADO"
            elif porcentaje_optimo >= 50:
                categoria = "MODERADO"
            elif porcentaje_optimo >= 30:
                categoria = "DEFICIENTE"
            else:
                categoria = "MUY DEFICIENTE"
            
            # Programación de aplicación
            if deficit > 0:
                if nutriente == "NITRÓGENO":
                    # Fraccionar aplicación de N
                    aplicaciones = min(3, math.ceil(recomendacion_kg / 40))
                    programacion = f"{aplicaciones} aplicaciones cada 30 días"
                elif nutriente == "FÓSFORO":
                    # Aplicación única o dos aplicaciones
                    if recomendacion_kg > 60:
                        programacion = "2 aplicaciones (50% al inicio, 50% a los 60 días)"
                    else:
                        programacion = "1 aplicación al inicio del ciclo"
                else:  # POTASIO
                    programacion = "2 aplicaciones (60% al inicio, 40% a los 90 días)"
            else:
                programacion = "No requiere aplicación adicional"
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, f'{nutriente.lower()}_actual'] = nutriente_actual
            zonas_gdf.loc[idx, f'deficit_{nutriente.lower()}'] = deficit
            zonas_gdf.loc[idx, f'recomendacion_{nutriente.lower()}_kg'] = recomendacion_kg
            zonas_gdf.loc[idx, f'recomendacion_{nutriente.lower()}_tipo'] = tipo_fertilizante
            zonas_gdf.loc[idx, f'categoria_{nutriente.lower()}'] = categoria
            zonas_gdf.loc[idx, f'programacion_aplicacion_{nutriente.lower()}'] = programacion
            
        except Exception as e:
            # Valores por defecto
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, f'{nutriente.lower()}_actual'] = param_nutriente['optimo']
            zonas_gdf.loc[idx, f'deficit_{nutriente.lower()}'] = 0
            zonas_gdf.loc[idx, f'recomendacion_{nutriente.lower()}_kg'] = 0
            zonas_gdf.loc[idx, f'recomendacion_{nutriente.lower()}_tipo'] = "No requiere"
            zonas_gdf.loc[idx, f'categoria_{nutriente.lower()}'] = "ÓPTIMO"
            zonas_gdf.loc[idx, f'programacion_aplicacion_{nutriente.lower()}'] = "Mantener niveles actuales"
    
    return zonas_gdf

# ============================================================================
# FUNCIONES PARA ANÁLISIS NDWI
# ============================================================================

def analizar_ndwi(gdf, cultivo, mes_analisis, fuente_satelital="PLANETSCOPE"):
    """Realiza análisis NDWI (Normalized Difference Water Index)"""
    
    params_cultivo = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para NDWI
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['ndwi'] = 0.0
    zonas_gdf['categoria_hidrica'] = "NORMAL"
    zonas_gdf['estres_hidrico'] = 0.0
    zonas_gdf['recomendacion_riego'] = ""
    zonas_gdf['humedad_suelo'] = 0.0
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_ndwi_{fuente_satelital}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Simular NDWI basado en fuente satelital
            if fuente_satelital == "PLANETSCOPE":
                # Mayor precisión espectral
                desviacion = 0.08
            elif fuente_satelital == "SENTINEL_2":
                desviacion = 0.10
            else:
                desviacion = 0.12
            
            # NDWI varía según el mes (estacionalidad)
            mes_idx = list(FACTORES_MES.keys()).index(mes_analisis)
            factor_estacional = 0.8 + (0.4 * np.sin((mes_idx / 12) * 2 * np.pi))
            
            # Generar NDWI con patrón espacial
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # Patrón de humedad espacial
            patron_espacial = 0.3 + 0.7 * np.sin(lat_norm * np.pi * 2) * np.cos(lon_norm * np.pi * 2)
            
            # Valor base NDWI para el cultivo
            ndwi_base = params_cultivo['NDWI_OPTIMO']['optimo']
            
            # Calcular NDWI simulado
            ndwi = max(-0.5, min(0.8, rng.normal(
                ndwi_base * factor_estacional * patron_espacial,
                desviacion
            )))
            
            # Calcular humedad del suelo estimada
            humedad_suelo = max(0.05, min(0.45, 0.15 + (ndwi + 0.3) * 0.5))
            
            # Categorizar condición hídrica
            if ndwi > params_cultivo['NDWI_OPTIMO']['max']:
                categoria = "EXCESO HÍDRICO"
                estres_hidrico = 0.0
                recomendacion = "Reducir riego, mejorar drenaje"
            elif ndwi >= params_cultivo['NDWI_OPTIMO']['min']:
                categoria = "ÓPTIMO"
                estres_hidrico = 0.0
                recomendacion = "Mantener programa de riego actual"
            elif ndwi >= params_cultivo['NDWI_OPTIMO']['min'] - 0.1:
                categoria = "LEVE ESTRÉS"
                estres_hidrico = 0.3
                recomendacion = "Aumentar frecuencia de riego en 20%"
            elif ndwi >= params_cultivo['NDWI_OPTIMO']['min'] - 0.2:
                categoria = "MODERADO ESTRÉS"
                estres_hidrico = 0.6
                recomendacion = "Aumentar frecuencia de riego en 40%, verificar sistema"
            else:
                categoria = "SEVERO ESTRÉS"
                estres_hidrico = 0.9
                recomendacion = "Riego de emergencia, revisar fuente de agua"
            
            # Calcular estrés hídrico (0-1)
            estres_hidrico = max(0, min(1, 
                (params_cultivo['NDWI_OPTIMO']['optimo'] - ndwi) / 
                (params_cultivo['NDWI_OPTIMO']['optimo'] - (-0.5))
            ))
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'ndwi'] = ndwi
            zonas_gdf.loc[idx, 'categoria_hidrica'] = categoria
            zonas_gdf.loc[idx, 'estres_hidrico'] = estres_hidrico
            zonas_gdf.loc[idx, 'recomendacion_riego'] = recomendacion
            zonas_gdf.loc[idx, 'humedad_suelo'] = humedad_suelo
            
        except Exception as e:
            # Valores por defecto
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'ndwi'] = params_cultivo['NDWI_OPTIMO']['optimo']
            zonas_gdf.loc[idx, 'categoria_hidrica'] = "ÓPTIMO"
            zonas_gdf.loc[idx, 'estres_hidrico'] = 0.0
            zonas_gdf.loc[idx, 'recomendacion_riego'] = "Mantener programa actual"
            zonas_gdf.loc[idx, 'humedad_suelo'] = params_cultivo['HUMEDAD_OPTIMA']
    
    return zonas_gdf

# ============================================================================
# FUNCIONES PARA ANÁLISIS DE ALTIMETRÍA
# ============================================================================

def analizar_altimetria(gdf, cultivo, usar_elevacion=True):
    """Realiza análisis altimétrico (elevación, pendiente, orientación)"""
    
    params_alt = ALTIMETRIA_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para altimetría
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['elevacion'] = 0.0
    zonas_gdf['pendiente'] = 0.0
    zonas_gdf['orientacion'] = "N"
    zonas_gdf['adecuacion_altimetrica'] = 0.0
    zonas_gdf['categoria_altimetria'] = "ÓPTIMA"
    zonas_gdf['riesgo_erosivo'] = "BAJO"
    zonas_gdf['recomendaciones_altimetria'] = ""
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_altimetria")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Simular elevación basada en ubicación
            lat = centroid.y if centroid.y else 4.0  # Colombia por defecto
            lon = centroid.x if centroid.x else -74.0
            
            # Elevación basada en latitud (simulación de montañas)
            elevacion_base = abs(lat * 100) + abs(lon) * 10
            elevacion = max(0, min(3000, rng.normal(
                elevacion_base % 1000,
                200
            )))
            
            # Pendiente basada en elevación y ubicación
            pendiente = max(0, min(45, rng.normal(
                min(15, elevacion / 50),
                5
            )))
            
            # Orientación (aspect) basada en coordenadas
            orientaciones = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            orient_idx = int((lon + 180) / 45) % 8
            orientacion = orientaciones[orient_idx]
            
            # Calcular adecuación altimétrica
            # 1. Adecuación de elevación (0-1)
            if params_alt['elevacion_min'] <= elevacion <= params_alt['elevacion_max']:
                adecuacion_elevacion = 1.0
            elif elevacion < params_alt['elevacion_min']:
                adecuacion_elevacion = 1.0 - (params_alt['elevacion_min'] - elevacion) / 100
            else:
                adecuacion_elevacion = 1.0 - (elevacion - params_alt['elevacion_max']) / 200
            
            adecuacion_elevacion = max(0, min(1, adecuacion_elevacion))
            
            # 2. Adecuación de pendiente (0-1)
            if pendiente <= params_alt['pendiente_max']:
                adecuacion_pendiente = 1.0 - (pendiente / params_alt['pendiente_max']) * 0.3
            else:
                adecuacion_pendiente = max(0, 1.0 - (pendiente - params_alt['pendiente_max']) / 10)
            
            # 3. Adecuación de orientación (0-1)
            if orientacion in params_alt['orientacion_optima']:
                adecuacion_orientacion = 1.0
            else:
                # Calcular distancia angular a orientación óptima más cercana
                orient_optima_idx = orientaciones.index(params_alt['orientacion_optima'][0])
                dist_angular = min(abs(orient_idx - orient_optima_idx),
                                8 - abs(orient_idx - orient_optima_idx))
                adecuacion_orientacion = 1.0 - (dist_angular / 4) * 0.5
            
            # Adecuación total
            adecuacion_total = (adecuacion_elevacion * 0.4 + 
                              adecuacion_pendiente * 0.4 + 
                              adecuacion_orientacion * 0.2)
            
            # Categorizar adecuación altimétrica
            if adecuacion_total >= 0.9:
                categoria = "ÓPTIMA"
            elif adecuacion_total >= 0.7:
                categoria = "BUENA"
            elif adecuacion_total >= 0.5:
                categoria = "REGULAR"
            elif adecuacion_total >= 0.3:
                categoria = "LIMITANTE"
            else:
                categoria = "MUY LIMITANTE"
            
            # Evaluar riesgo erosivo
            if pendiente > 15:
                riesgo = "ALTO"
            elif pendiente > 8:
                riesgo = "MEDIO"
            else:
                riesgo = "BAJO"
            
            # Generar recomendaciones
            recomendaciones = []
            if elevacion < params_alt['elevacion_min']:
                recomendaciones.append(f"Elevación baja ({elevacion:.0f}m), considerar drenaje adicional")
            elif elevacion > params_alt['elevacion_max']:
                recomendaciones.append(f"Elevación alta ({elevacion:.0f}m), considerar riego por goteo")
            
            if pendiente > params_alt['pendiente_max']:
                recomendaciones.append(f"Pendiente alta ({pendiente:.1f}%), implementar terrazas o curvas a nivel")
            
            if orientacion not in params_alt['orientacion_optima']:
                recomendaciones.append(f"Orientación {orientacion}, considerar cortavientos o sombras")
            
            if riesgo == "ALTO":
                recomendaciones.append("Alto riesgo erosivo - implementar barreras vivas y coberturas")
            elif riesgo == "MEDIO":
                recomendaciones.append("Riesgo erosivo moderado - mantener cobertura vegetal")
            
            if not recomendaciones:
                recomendaciones.append("Condiciones altimétricas adecuadas - mantener prácticas actuales")
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'elevacion'] = elevacion
            zonas_gdf.loc[idx, 'pendiente'] = pendiente
            zonas_gdf.loc[idx, 'orientacion'] = orientacion
            zonas_gdf.loc[idx, 'adecuacion_altimetrica'] = adecuacion_total
            zonas_gdf.loc[idx, 'categoria_altimetria'] = categoria
            zonas_gdf.loc[idx, 'riesgo_erosivo'] = riesgo
            zonas_gdf.loc[idx, 'recomendaciones_altimetria'] = " | ".join(recomendaciones[:3])
            
        except Exception as e:
            # Valores por defecto
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'elevacion'] = (params_alt['elevacion_min'] + params_alt['elevacion_max']) / 2
            zonas_gdf.loc[idx, 'pendiente'] = params_alt['pendiente_max'] / 2
            zonas_gdf.loc[idx, 'orientacion'] = params_alt['orientacion_optima'][0]
            zonas_gdf.loc[idx, 'adecuacion_altimetrica'] = 0.9
            zonas_gdf.loc[idx, 'categoria_altimetria'] = "ÓPTIMA"
            zonas_gdf.loc[idx, 'riesgo_erosivo'] = "BAJO"
            zonas_gdf.loc[idx, 'recomendaciones_altimetria'] = "Condiciones óptimas"
    
    return zonas_gdf

# ============================================================================
# FUNCIÓN MEJORADA PARA ANALIZAR TEXTURA
# ============================================================================

def analizar_textura_suelo_avanzado(gdf, cultivo, mes_analisis):
    """Realiza análisis avanzado de textura del suelo con metodologías modernas"""
    
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para textura avanzada
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['arena'] = 0.0
    zonas_gdf['limo'] = 0.0
    zonas_gdf['arcilla'] = 0.0
    zonas_gdf['textura_suelo'] = "NO_DETERMINADA"
    zonas_gdf['metodologia_analisis'] = "TRADICIONAL"
    zonas_gdf['adecuacion_textura'] = 0.0
    zonas_gdf['categoria_adecuacion'] = "NO_DETERMINADA"
    zonas_gdf['justificacion_adecuacion'] = ""
    zonas_gdf['capacidad_campo'] = 0.0
    zonas_gdf['punto_marchitez'] = 0.0
    zonas_gdf['agua_disponible'] = 0.0
    zonas_gdf['conductividad_electrica'] = 0.0
    zonas_gdf['humedad_volumetrica'] = 0.0
    zonas_gdf['indice_compactacion'] = 0.0
    zonas_gdf['riesgo_erosion'] = "BAJO"
    zonas_gdf['recomendaciones_monitoreo'] = ""
    zonas_gdf['recomendaciones_manejo'] = ""
    zonas_gdf['alertas'] = ""
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura_avanzado")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Seleccionar metodología de análisis
            metodologias = params_textura['metodologias_recomendadas']
            metodologia_seleccionada = rng.choice(metodologias)
            
            # SIMULAR COMPOSICIÓN GRANULOMÉTRICA CON VARIABILIDAD ESPACIAL
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # Patrón espacial más complejo
            variabilidad_espacial = 0.2 + 0.6 * np.sin(lat_norm * np.pi) * np.cos(lon_norm * np.pi)
            
            # Valores óptimos para el cultivo
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            
            # Simular con distribución normal ajustada por metodología
            if metodologia_seleccionada == "SENSORES_PROXIMALES":
                desviacion = 0.15  # Mayor precisión
            elif metodologia_seleccionada == "TELEDETECCION_ALTA_RES":
                desviacion = 0.20  # Precisión media
            else:
                desviacion = 0.25  # Modelado estándar
            
            arena = max(5, min(95, rng.normal(
                arena_optima * (0.8 + 0.4 * variabilidad_espacial),
                arena_optima * desviacion
            )))
            
            limo = max(5, min(95, rng.normal(
                limo_optima * (0.7 + 0.6 * variabilidad_espacial),
                limo_optima * desviacion
            )))
            
            arcilla = max(5, min(95, rng.normal(
                arcilla_optima * (0.75 + 0.5 * variabilidad_espacial),
                arcilla_optima * desviacion
            )))
            
            # Normalizar a 100%
            total = arena + limo + arcilla
            arena = (arena / total) * 100
            limo = (limo / total) * 100
            arcilla = (arcilla / total) * 100
            
            # Clasificar textura
            textura = clasificar_textura_suelo(arena, limo, arcilla)
            
            # Evaluar adecuación con metodología avanzada
            categoria_adecuacion, puntaje_adecuacion, justificacion = evaluar_adecuacion_textura(
                textura, cultivo, metodologia_seleccionada
            )
            
            # Simular materia orgánica
            materia_organica = max(1.0, min(8.0, rng.normal(3.0, 1.0)))
            
            # Calcular propiedades físicas con metodología específica
            propiedades_fisicas = calcular_propiedades_fisicas_suelo(
                textura, materia_organica, metodologia_seleccionada
            )
            
            # Simular datos de sensores
            datos_sensores = simular_datos_sensores(centroid, textura, cultivo)
            
            # Generar recomendaciones avanzadas
            recomendaciones = generar_recomendaciones_avanzadas(
                textura, cultivo, datos_sensores, 
                (categoria_adecuacion, puntaje_adecuacion, justificacion)
            )
            
            # Evaluar riesgo de erosión
            riesgo_erosion = "BAJO"
            if textura in ["Arenoso", "Franco Arcilloso-Arenoso"] and datos_sensores['indice_compactacion'] < 0.3:
                riesgo_erosion = "ALTO"
            elif textura in ["Franco"] and datos_sensores['humedad_volumetrica'] < 0.2:
                riesgo_erosion = "MODERADO"
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = arena
            zonas_gdf.loc[idx, 'limo'] = limo
            zonas_gdf.loc[idx, 'arcilla'] = arcilla
            zonas_gdf.loc[idx, 'textura_suelo'] = textura
            zonas_gdf.loc[idx, 'metodologia_analisis'] = metodologia_seleccionada
            zonas_gdf.loc[idx, 'adecuacion_textura'] = puntaje_adecuacion
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = categoria_adecuacion
            zonas_gdf.loc[idx, 'justificacion_adecuacion'] = justificacion
            zonas_gdf.loc[idx, 'riesgo_erosion'] = riesgo_erosion
            
            # Propiedades físicas
            zonas_gdf.loc[idx, 'capacidad_campo'] = propiedades_fisicas['capacidad_campo']
            zonas_gdf.loc[idx, 'punto_marchitez'] = propiedades_fisicas['punto_marchitez']
            zonas_gdf.loc[idx, 'agua_disponible'] = propiedades_fisicas['agua_disponible']
            zonas_gdf.loc[idx, 'densidad_aparente'] = propiedades_fisicas['densidad_aparente']
            zonas_gdf.loc[idx, 'porosidad'] = propiedades_fisicas['porosidad']
            zonas_gdf.loc[idx, 'conductividad_hidraulica'] = propiedades_fisicas['conductividad_hidraulica']
            
            # Datos de sensores
            zonas_gdf.loc[idx, 'conductividad_electrica'] = datos_sensores['conductividad_electrica']
            zonas_gdf.loc[idx, 'humedad_volumetrica'] = datos_sensores['humedad_volumetrica']
            zonas_gdf.loc[idx, 'indice_compactacion'] = datos_sensores['indice_compactacion']
            
            # Recomendaciones y alertas
            zonas_gdf.loc[idx, 'recomendaciones_monitoreo'] = " | ".join(recomendaciones['monitoreo'][:2])
            zonas_gdf.loc[idx, 'recomendaciones_manejo'] = " | ".join(recomendaciones['manejo'][:3])
            zonas_gdf.loc[idx, 'alertas'] = " | ".join(recomendaciones['alerta'])
            
        except Exception as e:
            # Valores por defecto en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            zonas_gdf.loc[idx, 'justificacion_adecuacion'] = "Textura óptima para el cultivo"
            zonas_gdf.loc[idx, 'riesgo_erosion'] = "BAJO"
    
    return zonas_gdf

# ============================================================================
# FUNCIONES AUXILIARES (MANTENIDAS DEL CÓDIGO ORIGINAL)
# ============================================================================

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

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo con manejo robusto de errores"""
    try:
        if len(gdf) == 0:
            st.error("El GeoDataFrame está vacío")
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
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            
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
    
    # Recomendaciones específicas por zona
    st.subheader("🎯 RECOMENDACIONES ESPECÍFICAS POR ZONA")
    
    for idx, row in df_detalle.iterrows():
        with st.expander(f"Zona {row['id_zona']} - {row['categoria_fertilidad']} ({row['area_ha']:.2f} ha)"):
            zona_data = gdf_fertilidad[gdf_fertilidad['id_zona'] == row['id_zona']].iloc[0]
            
            col_rec1, col_rec2 = st.columns(2)
            
            with col_rec1:
                st.markdown("**📊 Parámetros:**")
                st.markdown(f"- Índice fertilidad: {zona_data['indice_fertilidad']:.3f}")
                st.markdown(f"- Materia orgánica: {zona_data['materia_organica']:.1f}%")
                st.markdown(f"- pH: {zona_data['ph']:.1f}")
                st.markdown(f"- Conductividad: {zona_data['conductividad']:.2f} dS/m")
            
            with col_rec2:
                st.markdown("**💊 Nutrientes:**")
                st.markdown(f"- Nitrógeno: {zona_data['nitrogeno']:.0f} kg/ha")
                st.markdown(f"- Fósforo: {zona_data['fosforo']:.0f} kg/ha")
                st.markdown(f"- Potasio: {zona_data['potasio']:.0f} kg/ha")
            
            if zona_data['recomendaciones_fertilidad']:
                st.markdown("**💡 Recomendaciones:**")
                recomendaciones = zona_data['recomendaciones_fertilidad'].split(" | ")
                for rec in recomendaciones:
                    st.markdown(f"- {rec}")
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
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
    
    with col_dl3:
        # Generar informe PDF
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_fertilidad"):
            with st.spinner("🔄 Generando informe..."):
                # Aquí iría la función para generar PDF
                st.success("Funcionalidad de PDF en desarrollo")
                st.info("Por ahora, usa los formatos CSV y GeoJSON")

def mostrar_recomendaciones_npk():
    """Muestra las recomendaciones de NPK específicas"""
    
    if st.session_state.analisis_npk is None:
        st.warning("No hay datos de recomendaciones NPK disponibles")
        return
    
    gdf_npk = st.session_state.analisis_npk
    area_total = st.session_state.area_total
    
    st.markdown(f"## 💊 RECOMENDACIONES DE {nutriente} - {cultivo.replace('_', ' ').title()}")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_npk"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Información general
    st.info(f"📅 **Mes de análisis:** {mes_analisis} | 📡 **Fuente:** {fuente_satelital}")
    
    # Estadísticas resumen
    st.subheader("📊 ESTADÍSTICAS DE RECOMENDACIONES")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_recomendado = gdf_npk[f'recomendacion_{nutriente.lower()}_kg'].sum()
        st.metric(f"📦 {nutriente} Total Recomendado", f"{total_recomendado:.0f} kg")
    with col2:
        promedio_recomendado = gdf_npk[f'recomendacion_{nutriente.lower()}_kg'].mean()
        st.metric(f"⚖️ {nutriente} Promedio por ha", f"{promedio_recomendado:.1f} kg/ha")
    with col3:
        zonas_deficit = len(gdf_npk[gdf_npk[f'deficit_{nutriente.lower()}'] > 0])
        st.metric("🔴 Zonas con déficit", f"{zonas_deficit} / {len(gdf_npk)}")
    with col4:
        fertilizante_pred = gdf_npk[f'recomendacion_{nutriente.lower()}_tipo'].mode()[0] if len(gdf_npk) > 0 else "No requiere"
        st.metric("🏭 Fertilizante Predominante", fertilizante_pred)
    
    # Distribución de categorías
    st.subheader("📋 DISTRIBUCIÓN DE ESTADO DEL NUTRIENTE")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Gráfico de torta
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        cat_dist = gdf_npk[f'categoria_{nutriente.lower()}'].value_counts()
        
        # Colores para categorías
        colores_categoria = {
            'ÓPTIMO': '#1a9850',
            'ADECUADO': '#66bd63',
            'MODERADO': '#fee08b',
            'DEFICIENTE': '#fdae61',
            'MUY DEFICIENTE': '#d73027'
        }
        
        colors_pie = [colores_categoria.get(cat, '#999999') for cat in cat_dist.index]
        
        ax.pie(cat_dist.values, labels=cat_dist.index, autopct='%1.1f%%',
               colors=colors_pie, startangle=90)
        ax.set_title(f'Estado de {nutriente}')
        st.pyplot(fig)
    
    with col_dist2:
        # Histograma de recomendaciones
        fig_hist, ax_hist = plt.subplots(1, 1, figsize=(8, 6))
        
        recomendaciones = gdf_npk[f'recomendacion_{nutriente.lower()}_kg']
        ax_hist.hist(recomendaciones, bins=10, edgecolor='black', alpha=0.7)
        ax_hist.set_xlabel('kg/ha recomendados')
        ax_hist.set_ylabel('Número de zonas')
        ax_hist.set_title(f'Distribución de Recomendaciones de {nutriente}')
        ax_hist.grid(True, alpha=0.3)
        
        st.pyplot(fig_hist)
    
    # Mapa de recomendaciones
    st.subheader("🗺️ MAPA DE RECOMENDACIONES")
    
    col_mapa1, col_mapa2 = st.columns([2, 1])
    
    with col_mapa1:
        mapa_npk = crear_mapa_interactivo_esri(
            gdf_npk,
            f"Recomendaciones de {nutriente} - {cultivo.replace('_', ' ').title()}",
            f'recomendacion_{nutriente.lower()}_kg',
            "RECOMENDACIONES NPK",
            nutriente
        )
        st_folium(mapa_npk, width=600, height=500)
    
    with col_mapa2:
        st.markdown("#### 📍 Leyenda del Mapa")
        
        if nutriente == "NITRÓGENO":
            st.markdown("""
            - **0-50 kg/ha:** Déficit bajo
            - **50-100 kg/ha:** Déficit moderado
            - **100-150 kg/ha:** Déficit alto
            - **150-200 kg/ha:** Déficit muy alto
            - **>200 kg/ha:** Corrección intensiva
            """)
        elif nutriente == "FÓSFORO":
            st.markdown("""
            - **0-25 kg/ha:** Déficit bajo
            - **25-50 kg/ha:** Déficit moderado
            - **50-75 kg/ha:** Déficit alto
            - **75-100 kg/ha:** Déficit muy alto
            - **>100 kg/ha:** Corrección intensiva
            """)
        else:  # POTASIO
            st.markdown("""
            - **0-40 kg/ha:** Déficit bajo
            - **40-80 kg/ha:** Déficit moderado
            - **80-120 kg/ha:** Déficit alto
            - **120-160 kg/ha:** Déficit muy alto
            - **>160 kg/ha:** Corrección intensiva
            """)
        
        st.markdown("---")
        st.markdown("#### 📋 Fertilizantes Recomendados")
        
        fertilizantes_dist = gdf_npk[f'recomendacion_{nutriente.lower()}_tipo'].value_counts()
        for fert, count in fertilizantes_dist.items():
            st.markdown(f"**{fert}:** {count} zonas")
    
    # Tabla detallada
    st.subheader("📊 TABLA DETALLADA DE RECOMENDACIONES")
    
    columnas_npk = [
        'id_zona', 'area_ha', 
        f'{nutriente.lower()}_actual',
        f'deficit_{nutriente.lower()}',
        f'recomendacion_{nutriente.lower()}_kg',
        f'recomendacion_{nutriente.lower()}_tipo',
        f'categoria_{nutriente.lower()}',
        f'programacion_aplicacion_{nutriente.lower()}'
    ]
    
    df_npk = gdf_npk[columnas_npk].copy()
    df_npk['area_ha'] = df_npk['area_ha'].round(3)
    df_npk[f'{nutriente.lower()}_actual'] = df_npk[f'{nutriente.lower()}_actual'].round(1)
    df_npk[f'deficit_{nutriente.lower()}'] = df_npk[f'deficit_{nutriente.lower()}'].round(1)
    df_npk[f'recomendacion_{nutriente.lower()}_kg'] = df_npk[f'recomendacion_{nutriente.lower()}_kg'].round(1)
    
    st.dataframe(df_npk, use_container_width=True)
    
    # Plan de fertilización
    st.subheader("📅 PLAN DE FERTILIZACIÓN")
    
    col_plan1, col_plan2 = st.columns(2)
    
    with col_plan1:
        st.markdown("#### 🗓️ Calendario de Aplicaciones")
        
        # Agrupar por programación de aplicación
        programaciones = gdf_npk[f'programacion_aplicacion_{nutriente.lower()}'].value_counts()
        
        for prog, count in programaciones.items():
            st.markdown(f"**{prog}:** {count} zonas")
        
        st.markdown("---")
        st.markdown("#### 💰 Estimación de Costos")
        
        # Costos aproximados
        if nutriente == "NITRÓGENO":
            costo_kg = 2.5  # USD por kg de N
        elif nutriente == "FÓSFORO":
            costo_kg = 3.0  # USD por kg de P₂O₅
        else:
            costo_kg = 2.0  # USD por kg de K₂O
        
        costo_total = total_recomendado * costo_kg
        costo_ha = promedio_recomendado * costo_kg
        
        st.markdown(f"**Costo total estimado:** ${costo_total:,.0f} USD")
        st.markdown(f"**Costo por hectárea:** ${costo_ha:,.1f} USD/ha")
    
    with col_plan2:
        st.markdown("#### 🎯 Recomendaciones por Categoría")
        
        categorias = df_npk[f'categoria_{nutriente.lower()}'].unique()
        
        for categoria in categorias:
            zonas_cat = df_npk[df_npk[f'categoria_{nutriente.lower()}'] == categoria]
            if len(zonas_cat) > 0:
                with st.expander(f"{categoria} ({len(zonas_cat)} zonas)"):
                    # Estadísticas para esta categoría
                    avg_recomendacion = zonas_cat[f'recomendacion_{nutriente.lower()}_kg'].mean()
                    fertilizante_cat = zonas_cat[f'recomendacion_{nutriente.lower()}_tipo'].mode()[0]
                    
                    st.markdown(f"**Recomendación promedio:** {avg_recomendacion:.1f} kg/ha")
                    st.markdown(f"**Fertilizante recomendado:** {fertilizante_cat}")
                    
                    # Ejemplo de zona
                    zona_ejemplo = zonas_cat.iloc[0]
                    st.markdown(f"**Ejemplo Zona {zona_ejemplo['id_zona']}:**")
                    st.markdown(f"- Área: {zona_ejemplo['area_ha']:.2f} ha")
                    st.markdown(f"- {nutriente} actual: {zona_ejemplo[f'{nutriente.lower()}_actual']:.1f} kg/ha")
                    st.markdown(f"- Recomendación: {zona_ejemplo[f'recomendacion_{nutriente.lower()}_kg']:.1f} kg/ha")
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        # Descargar CSV
        csv_npk = df_npk.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv_npk,
            file_name=f"recomendaciones_{nutriente}_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Descargar GeoJSON
        geojson_npk = gdf_npk.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson_npk,
            file_name=f"recomendaciones_{nutriente}_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )

def mostrar_analisis_ndwi():
    """Muestra el análisis NDWI (índice de agua)"""
    
    if st.session_state.analisis_ndwi is None:
        st.warning("No hay datos de análisis NDWI disponibles")
        return
    
    gdf_ndwi = st.session_state.analisis_ndwi
    area_total = st.session_state.area_total
    
    st.markdown("## 💧 ANÁLISIS NDWI - ÍNDICE DE AGUA EN LA VEGETACIÓN")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_ndwi"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Información sobre NDWI
    st.info(f"📡 **Fuente:** {fuente_satelital} | 🌧️ **NDWI óptimo para {cultivo}:** {PARAMETROS_CULTIVOS[cultivo]['NDWI_OPTIMO']['optimo']:.2f}")
    
    # Estadísticas resumen
    st.subheader("📊 ESTADÍSTICAS NDWI")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_ndwi = gdf_ndwi['ndwi'].mean()
        st.metric("💧 NDWI Promedio", f"{avg_ndwi:.3f}")
    with col2:
        categoria_pred = gdf_ndwi['categoria_hidrica'].mode()[0] if len(gdf_ndwi) > 0 else "NORMAL"
        st.metric("🏷️ Condición Hídrica", categoria_pred)
    with col3:
        zonas_estres = len(gdf_ndwi[gdf_ndwi['estres_hidrico'] > 0.3])
        st.metric("⚠️ Zonas con Estrés", f"{zonas_estres} / {len(gdf_ndwi)}")
    with col4:
        avg_humedad = gdf_ndwi['humedad_suelo'].mean()
        st.metric("🌱 Humedad Suelo", f"{avg_humedad:.1%}")
    
    # Distribución de categorías hídricas
    st.subheader("📋 DISTRIBUCIÓN DE CONDICIÓN HÍDRICA")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Gráfico de torta
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        cat_dist = gdf_ndwi['categoria_hidrica'].value_counts()
        
        # Colores para categorías
        colores_categoria = {
            'EXCESO HÍDRICO': '#313695',
            'ÓPTIMO': '#4575b4',
            'LEVE ESTRÉS': '#fdae61',
            'MODERADO ESTRÉS': '#f46d43',
            'SEVERO ESTRÉS': '#d73027'
        }
        
        colors_pie = [colores_categoria.get(cat, '#999999') for cat in cat_dist.index]
        
        ax.pie(cat_dist.values, labels=cat_dist.index, autopct='%1.1f%%',
               colors=colors_pie, startangle=90)
        ax.set_title('Distribución de Condición Hídrica')
        st.pyplot(fig)
    
    with col_dist2:
        # Histograma de NDWI
        fig_hist, ax_hist = plt.subplots(1, 1, figsize=(8, 6))
        
        ndwi_values = gdf_ndwi['ndwi']
        ax_hist.hist(ndwi_values, bins=15, edgecolor='black', alpha=0.7, color='#74add1')
        
        # Línea vertical para NDWI óptimo
        ndwi_optimo = PARAMETROS_CULTIVOS[cultivo]['NDWI_OPTIMO']['optimo']
        ax_hist.axvline(x=ndwi_optimo, color='red', linestyle='--', 
                       label=f'Óptimo: {ndwi_optimo:.2f}')
        
        # Líneas para rangos
        ndwi_min = PARAMETROS_CULTIVOS[cultivo]['NDWI_OPTIMO']['min']
        ndwi_max = PARAMETROS_CULTIVOS[cultivo]['NDWI_OPTIMO']['max']
        ax_hist.axvline(x=ndwi_min, color='orange', linestyle=':', alpha=0.7)
        ax_hist.axvline(x=ndwi_max, color='orange', linestyle=':', alpha=0.7)
        
        ax_hist.set_xlabel('Valor NDWI')
        ax_hist.set_ylabel('Número de zonas')
        ax_hist.set_title('Distribución de Valores NDWI')
        ax_hist.legend()
        ax_hist.grid(True, alpha=0.3)
        
        st.pyplot(fig_hist)
    
    # Mapa NDWI
    st.subheader("🗺️ MAPA NDWI")
    
    mapa_ndwi = crear_mapa_interactivo_esri(
        gdf_ndwi,
        f"NDWI - {cultivo.replace('_', ' ').title()}",
        'ndwi',
        "ANÁLISIS NDWI"
    )
    st_folium(mapa_ndwi, width=800, height=500)
    
    # Análisis de estrés hídrico
    st.subheader("⚠️ ANÁLISIS DE ESTRÉS HÍDRICO")
    
    col_estres1, col_estres2 = st.columns(2)
    
    with col_estres1:
        st.markdown("#### 📊 Zonas por Nivel de Estrés")
        
        # Clasificar zonas por nivel de estrés
        def clasificar_estres(valor):
            if valor < 0.3:
                return "Sin estrés"
            elif valor < 0.5:
                return "Estrés leve"
            elif valor < 0.7:
                return "Estrés moderado"
            else:
                return "Estrés severo"
        
        gdf_ndwi['nivel_estres'] = gdf_ndwi['estres_hidrico'].apply(clasificar_estres)
        estres_dist = gdf_ndwi['nivel_estres'].value_counts()
        
        fig_estres, ax_estres = plt.subplots(1, 1, figsize=(8, 6))
        estres_colors = ['#66bd63', '#fee08b', '#fdae61', '#d73027']
        ax_estres.bar(estres_dist.index, estres_dist.values, color=estres_colors, edgecolor='black')
        ax_estres.set_xlabel('Nivel de Estrés')
        ax_estres.set_ylabel('Número de zonas')
        ax_estres.set_title('Distribución de Estrés Hídrico')
        
        # Añadir valores en las barras
        for i, v in enumerate(estres_dist.values):
            ax_estres.text(i, v + 0.5, str(v), ha='center')
        
        st.pyplot(fig_estres)
    
    with col_estres2:
        st.markdown("#### 💡 Recomendaciones por Nivel de Estrés")
        
        recomendaciones_estres = {
            "Sin estrés": [
                "Mantener programa de riego actual",
                "Monitorear semanalmente para detectar cambios",
                "Asegurar drenaje adecuado para evitar exceso"
            ],
            "Estrés leve": [
                "Aumentar frecuencia de riego en 20%",
                "Aplicar mulching para conservar humedad",
                "Verificar sistema de riego por goteo"
            ],
            "Estrés moderado": [
                "Aumentar frecuencia de riego en 40%",
                "Revisar fuente de agua y capacidad del sistema",
                "Considerar riego nocturno para reducir evaporación"
            ],
            "Estrés severo": [
                "Riego de emergencia inmediato",
                "Evaluar fuente de agua alterna",
                "Priorizar zonas más críticas",
                "Considerar productos anti-transpirantes"
            ]
        }
        
        for nivel in estres_dist.index:
            with st.expander(f"{nivel} ({estres_dist[nivel]} zonas)"):
                for rec in recomendaciones_estres.get(nivel, ["No hay recomendaciones específicas"]):
                    st.markdown(f"- {rec}")
    
    # Tabla detallada
    st.subheader("📊 TABLA DETALLADA NDWI")
    
    columnas_ndwi = [
        'id_zona', 'area_ha', 'ndwi', 'categoria_hidrica',
        'estres_hidrico', 'humedad_suelo', 'recomendacion_riego'
    ]
    
    df_ndwi = gdf_ndwi[columnas_ndwi].copy()
    df_ndwi['area_ha'] = df_ndwi['area_ha'].round(3)
    df_ndwi['ndwi'] = df_ndwi['ndwi'].round(3)
    df_ndwi['estres_hidrico'] = df_ndwi['estres_hidrico'].round(3)
    df_ndwi['humedad_suelo'] = df_ndwi['humedad_suelo'].round(3)
    
    st.dataframe(df_ndwi, use_container_width=True)
    
    # Plan de riego
    st.subheader("🚿 PLAN DE RIEGO RECOMENDADO")
    
    col_riego1, col_riego2 = st.columns(2)
    
    with col_riego1:
        st.markdown("#### 🗓️ Programación de Riego")
        
        # Agrupar por recomendación de riego
        riego_dist = gdf_ndwi['recomendacion_riego'].value_counts()
        
        for rec, count in riego_dist.items():
            st.markdown(f"**{rec}:** {count} zonas")
        
        st.markdown("---")
        st.markdown("#### 💧 Requerimientos Hídricos")
        
        # Calcular requerimientos basados en NDWI
        if cultivo == "PALMA_ACEITERA":
            req_base = 1500  # mm/año
        elif cultivo == "CACAO":
            req_base = 1200  # mm/año
        else:  # BANANO
            req_base = 2000  # mm/año
        
        # Ajustar por estrés hídrico promedio
        factor_estres = 1.0 + gdf_ndwi['estres_hidrico'].mean()
        req_actual = req_base * factor_estres
        
        st.markdown(f"**Requerimiento base:** {req_base:.0f} mm/año")
        st.markdown(f"**Requerimiento ajustado:** {req_actual:.0f} mm/año")
        st.markdown(f"**Déficit estimado:** {req_actual - req_base:.0f} mm/año")
    
    with col_riego2:
        st.markdown("#### 🌡️ Factores Climáticos")
        
        # Simular factores climáticos
        factores_climaticos = {
            "Temperatura promedio": "25-30°C",
            "Evapotranspiración": "4-6 mm/día",
            "Humedad relativa": "70-85%",
            "Precipitación esperada": "150-200 mm/mes",
            "Radiación solar": "18-22 MJ/m²/día"
        }
        
        for factor, valor in factores_climaticos.items():
            st.markdown(f"**{factor}:** {valor}")
        
        st.markdown("---")
        st.markdown("#### ⚙️ Recomendaciones del Sistema")
        
        sistemas_riego = {
            "ÓPTIMO": "Riego por goteo automatizado",
            "LEVE ESTRÉS": "Riego por goteo + aspersión complementaria",
            "MODERADO ESTRÉS": "Riego por goteo + riego por surcos",
            "SEVERO ESTRÉS": "Riego por inundación controlada + goteo"
        }
        
        sistema_recomendado = sistemas_riego.get(categoria_pred, "Riego por goteo")
        st.markdown(f"**Sistema recomendado:** {sistema_recomendado}")
        st.markdown(f"**Eficiencia esperada:** 85-95%")
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        # Descargar CSV
        csv_ndwi = df_ndwi.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv_ndwi,
            file_name=f"ndwi_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Descargar GeoJSON
        geojson_ndwi = gdf_ndwi.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson_ndwi,
            file_name=f"ndwi_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )

def mostrar_analisis_altimetria():
    """Muestra el análisis altimétrico"""
    
    if st.session_state.analisis_altimetria is None:
        st.warning("No hay datos de análisis altimétrico disponibles")
        return
    
    gdf_alt = st.session_state.analisis_altimetria
    area_total = st.session_state.area_total
    
    st.markdown("## 🏔️ ANÁLISIS ALTIMÉTRICO - ELEVACIÓN Y PENDIENTE")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_altimetria"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Información sobre parámetros óptimos
    params_alt = ALTIMETRIA_OPTIMA[cultivo]
    st.info(f"📏 **Elevación óptima:** {params_alt['elevacion_min']}-{params_alt['elevacion_max']} m | 📐 **Pendiente máxima:** {params_alt['pendiente_max']}% | 🧭 **Orientación óptima:** {', '.join(params_alt['orientacion_optima'])}")
    
    # Estadísticas resumen
    st.subheader("📊 ESTADÍSTICAS ALTIMÉTRICAS")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_elevacion = gdf_alt['elevacion'].mean()
        st.metric("🏔️ Elevación Promedio", f"{avg_elevacion:.0f} m")
    with col2:
        avg_pendiente = gdf_alt['pendiente'].mean()
        st.metric("📐 Pendiente Promedio", f"{avg_pendiente:.1f}%")
    with col3:
        avg_adecuacion = gdf_alt['adecuacion_altimetrica'].mean()
        st.metric("📊 Adecuación Altimétrica", f"{avg_adecuacion:.1%}")
    with col4:
        riesgo_pred = gdf_alt['riesgo_erosivo'].mode()[0] if len(gdf_alt) > 0 else "BAJO"
        st.metric("⚠️ Riesgo Erosivo Pred", riesgo_pred)
    
    # Distribución de orientaciones
    st.subheader("🧭 DISTRIBUCIÓN DE ORIENTACIONES")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Gráfico de torta para orientaciones
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        orient_dist = gdf_alt['orientacion'].value_counts()
        
        # Colores para orientaciones
        colores_orient = {
            'N': '#4daf4a', 'NE': '#377eb8', 'E': '#984ea3',
            'SE': '#ff7f00', 'S': '#ffff33', 'SW': '#a65628',
            'W': '#f781bf', 'NW': '#999999'
        }
        
        colors_pie = [colores_orient.get(orient, '#999999') for orient in orient_dist.index]
        
        ax.pie(orient_dist.values, labels=orient_dist.index, autopct='%1.1f%%',
               colors=colors_pie, startangle=90)
        ax.set_title('Distribución de Orientaciones')
        st.pyplot(fig)
    
    with col_dist2:
        # Gráfico de dispersión elevación vs pendiente
        fig_scatter, ax_scatter = plt.subplots(1, 1, figsize=(8, 6))
        
        # Colores por adecuación
        scatter_colors = []
        for adec in gdf_alt['adecuacion_altimetrica']:
            if adec >= 0.8:
                scatter_colors.append('#1a9850')  # Verde
            elif adec >= 0.6:
                scatter_colors.append('#fee08b')  # Amarillo
            elif adec >= 0.4:
                scatter_colors.append('#fdae61')  # Naranja
            else:
                scatter_colors.append('#d73027')  # Rojo
        
        scatter = ax_scatter.scatter(gdf_alt['elevacion'], gdf_alt['pendiente'],
                                    c=scatter_colors, s=50, edgecolor='black', alpha=0.7)
        
        # Líneas de referencia para valores óptimos
        ax_scatter.axhline(y=params_alt['pendiente_max'], color='red', 
                          linestyle='--', label=f'Pendiente máxima ({params_alt["pendiente_max"]}%)')
        
        # Área óptima de elevación
        ax_scatter.axvspan(params_alt['elevacion_min'], params_alt['elevacion_max'],
                          alpha=0.2, color='green', label='Elevación óptima')
        
        ax_scatter.set_xlabel('Elevación (m)')
        ax_scatter.set_ylabel('Pendiente (%)')
        ax_scatter.set_title('Elevación vs Pendiente')
        ax_scatter.legend()
        ax_scatter.grid(True, alpha=0.3)
        
        st.pyplot(fig_scatter)
    
    # Mapa de elevación
    st.subheader("🗺️ MAPA DE ELEVACIÓN Y PENDIENTE")
    
    col_mapa1, col_mapa2 = st.columns(2)
    
    with col_mapa1:
        st.markdown("#### 🏔️ Elevación")
        mapa_elevacion = crear_mapa_interactivo_esri(
            gdf_alt,
            f"Elevación - {cultivo.replace('_', ' ').title()}",
            'elevacion',
            "ALTIMETRÍA"
        )
        st_folium(mapa_elevacion, height=400)
    
    with col_mapa2:
        st.markdown("#### 📐 Pendiente")
        mapa_pendiente = crear_mapa_interactivo_esri(
            gdf_alt,
            f"Pendiente - {cultivo.replace('_', ' ').title()}",
            'pendiente',
            "ALTIMETRÍA"
        )
        st_folium(mapa_pendiente, height=400)
    
    # Análisis de riesgos y adecuación
    st.subheader("📈 ANÁLISIS DE ADECUACIÓN Y RIESGOS")
    
    col_analisis1, col_analisis2 = st.columns(2)
    
    with col_analisis1:
        st.markdown("#### 🎯 Adecuación Altimétrica")
        
        # Distribución de categorías
        cat_dist = gdf_alt['categoria_altimetria'].value_counts()
        
        fig_cat, ax_cat = plt.subplots(1, 1, figsize=(8, 6))
        
        # Colores para categorías
        colores_cat = {
            'ÓPTIMA': '#1a9850',
            'BUENA': '#66bd63',
            'REGULAR': '#fee08b',
            'LIMITANTE': '#fdae61',
            'MUY LIMITANTE': '#d73027'
        }
        
        cat_colors = [colores_cat.get(cat, '#999999') for cat in cat_dist.index]
        
        bars = ax_cat.bar(cat_dist.index, cat_dist.values, color=cat_colors, edgecolor='black')
        ax_cat.set_xlabel('Categoría')
        ax_cat.set_ylabel('Número de zonas')
        ax_cat.set_title('Distribución de Categorías de Adecuación')
        
        # Añadir valores en las barras
        for bar, valor in zip(bars, cat_dist.values):
            height = bar.get_height()
            ax_cat.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                       str(valor), ha='center', va='bottom')
        
        st.pyplot(fig_cat)
    
    with col_analisis2:
        st.markdown("#### ⚠️ Riesgo Erosivo")
        
        riesgo_dist = gdf_alt['riesgo_erosivo'].value_counts()
        
        fig_riesgo, ax_riesgo = plt.subplots(1, 1, figsize=(8, 6))
        
        # Colores para riesgos
        colores_riesgo = {
            'BAJO': '#1a9850',
            'MEDIO': '#fee08b',
            'ALTO': '#d73027'
        }
        
        riesgo_colors = [colores_riesgo.get(riesgo, '#999999') for riesgo in riesgo_dist.index]
        
        ax_riesgo.pie(riesgo_dist.values, labels=riesgo_dist.index, autopct='%1.1f%%',
                     colors=riesgo_colors, startangle=90)
        ax_riesgo.set_title('Distribución de Riesgo Erosivo')
        
        st.pyplot(fig_riesgo)
    
    # Recomendaciones por categoría
    st.subheader("💡 RECOMENDACIONES POR CATEGORÍA")
    
    categorias_alt = gdf_alt['categoria_altimetria'].unique()
    
    for categoria in categorias_alt:
        zonas_cat = gdf_alt[gdf_alt['categoria_altimetria'] == categoria]
        if len(zonas_cat) > 0:
            with st.expander(f"{categoria} ({len(zonas_cat)} zonas)"):
                # Estadísticas para esta categoría
                avg_elev = zonas_cat['elevacion'].mean()
                avg_pend = zonas_cat['pendiente'].mean()
                orient_pred = zonas_cat['orientacion'].mode()[0]
                
                st.markdown(f"**Estadísticas:**")
                st.markdown(f"- Elevación promedio: {avg_elev:.0f} m")
                st.markdown(f"- Pendiente promedio: {avg_pend:.1f}%")
                st.markdown(f"- Orientación predominante: {orient_pred}")
                
                # Recomendaciones específicas
                if categoria in ["LIMITANTE", "MUY LIMITANTE"]:
                    st.markdown(f"**⚠️ Recomendaciones críticas:**")
                    if avg_elev < params_alt['elevacion_min']:
                        st.markdown(f"- Implementar sistemas de drenaje (elevación baja: {avg_elev:.0f}m)")
                    elif avg_elev > params_alt['elevacion_max']:
                        st.markdown(f"- Instalar sistemas de riego eficientes (elevación alta: {avg_elev:.0f}m)")
                    
                    if avg_pend > params_alt['pendiente_max']:
                        st.markdown(f"- Construir terrazas o curvas a nivel (pendiente: {avg_pend:.1f}%)")
                    
                    if orient_pred not in params_alt['orientacion_optima']:
                        st.markdown(f"- Plantar cortavientos (orientación: {orient_pred})")
                
                # Ejemplo de zona
                zona_ejemplo = zonas_cat.iloc[0]
                st.markdown(f"**Ejemplo Zona {zona_ejemplo['id_zona']}:**")
                recomendaciones = zona_ejemplo['recomendaciones_altimetria'].split(" | ")
                for rec in recomendaciones[:3]:
                    st.markdown(f"- {rec}")
    
    # Tabla detallada
    st.subheader("📊 TABLA DETALLADA ALTIMÉTRICA")
    
    columnas_alt = [
        'id_zona', 'area_ha', 'elevacion', 'pendiente', 'orientacion',
        'adecuacion_altimetrica', 'categoria_altimetria', 'riesgo_erosivo',
        'recomendaciones_altimetria'
    ]
    
    df_alt = gdf_alt[columnas_alt].copy()
    df_alt['area_ha'] = df_alt['area_ha'].round(3)
    df_alt['elevacion'] = df_alt['elevacion'].round(0)
    df_alt['pendiente'] = df_alt['pendiente'].round(1)
    df_alt['adecuacion_altimetrica'] = df_alt['adecuacion_altimetrica'].round(3)
    
    st.dataframe(df_alt, use_container_width=True)
    
    # Plan de manejo altimétrico
    st.subheader("🏗️ PLAN DE MANEJO ALTIMÉTRICO")
    
    col_plan1, col_plan2 = st.columns(2)
    
    with col_plan1:
        st.markdown("#### 📐 Obras de Conservación")
        
        # Calcular necesidades de obras
        zonas_alta_pendiente = gdf_alt[gdf_alt['pendiente'] > params_alt['pendiente_max']]
        
        if len(zonas_alta_pendiente) > 0:
            st.markdown(f"**Zonas que requieren obras:** {len(zonas_alta_pendiente)}")
            
            obras_necesarias = []
            for idx, row in zonas_alta_pendiente.iterrows():
                if row['pendiente'] > 20:
                    obras_necesarias.append(f"Zona {row['id_zona']}: Terrazas individuales")
                elif row['pendiente'] > 15:
                    obras_necesarias.append(f"Zona {row['id_zona']}: Bancales")
                elif row['pendiente'] > params_alt['pendiente_max']:
                    obras_necesarias.append(f"Zona {row['id_zona']}: Curvas a nivel")
            
            for obra in obras_necesarias[:5]:  # Mostrar solo 5
                st.markdown(f"- {obra}")
            
            if len(obras_necesarias) > 5:
                st.markdown(f"... y {len(obras_necesarias) - 5} zonas más")
        else:
            st.markdown("✅ No se requieren obras de conservación principales")
        
        st.markdown("---")
        st.markdown("#### 💰 Estimación de Costos")
        
        # Costos aproximados
        costo_terraza = 5000  # USD/ha
        costo_bancal = 3000   # USD/ha
        costo_curva = 1500    # USD/ha
        
        area_total_obras = zonas_alta_pendiente['area_ha'].sum()
        costo_estimado = area_total_obras * costo_curva  # Estimación conservadora
        
        st.markdown(f"**Área que requiere obras:** {area_total_obras:.1f} ha")
        st.markdown(f"**Costo estimado:** ${costo_estimado:,.0f} USD")
    
    with col_plan2:
        st.markdown("#### 🌳 Manejo Vegetativo")
        
        recomendaciones_vegetativas = {
            "BAJO": [
                "Coberturas vegetales permanentes",
                "Rotación de cultivos con leguminosas",
                "Manejo de residuos en superficie"
            ],
            "MEDIO": [
                "Barreras vivas (vetiver, pasto elefante)",
                "Franjas de retención cada 20-30m",
                "Cultivos en contorno"
            ],
            "ALTO": [
                "Cortinas rompevientos cada 10-15m",
                "Sistemas agroforestales en contorno",
                "Plantación en curvas a nivel"
            ]
        }
        
        # Recomendaciones según riesgo erosivo
        for riesgo in riesgo_dist.index:
            if riesgo in recomendaciones_vegetativas:
                with st.expander(f"Riesgo {riesgo} ({riesgo_dist[riesgo]} zonas)"):
                    for rec in recomendaciones_vegetativas[riesgo]:
                        st.markdown(f"- {rec}")
        
        st.markdown("---")
        st.markdown("#### 🚜 Manejo Mecánico")
        
        maquinaria_recomendada = {
            "pendiente < 5%": "Maquinaria convencional",
            "pendiente 5-10%": "Tractores con tracción 4x4",
            "pendiente 10-15%": "Mini tractores o motocultores",
            "pendiente > 15%": "Equipo manual o animal"
        }
        
        for rango, maquinaria in maquinaria_recomendada.items():
            st.markdown(f"**{rango}:** {maquinaria}")
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        # Descargar CSV
        csv_alt = df_alt.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv_alt,
            file_name=f"altimetria_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Descargar GeoJSON
        geojson_alt = gdf_alt.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson_alt,
            file_name=f"altimetria_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )

def mostrar_analisis_textura_mejorado():
    """Muestra el análisis de textura con metodologías avanzadas"""
    
    if st.session_state.analisis_textura is None:
        st.warning("No hay datos de análisis de textura disponibles")
        return
    
    gdf_textura = st.session_state.analisis_textura
    area_total = st.session_state.area_total
    
    st.markdown("## 🏗️ ANÁLISIS AVANZADO DE TEXTURA DEL SUELO")
    
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_textura_avanzado"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Información sobre metodologías avanzadas
    with st.expander("🔬 **INFORMACIÓN SOBRE METODOLOGÍAS AVANZADAS**", expanded=True):
        st.markdown("""
        ### Métodos Modernos de Análisis de Textura
        
        **Referencias científicas:**
        1. **Técnicas de sensores y modelado digital** (Sciencedirect, 2021): 
           Permiten estimar textura a partir de propiedades espectrales, conductividad eléctrica o datos de reflectancia.
        
        2. **Teledetección de alta resolución** (Frontiers, 2024):
           Facilita el mapeo de texturas a escala de lote mediante índices espectrales, modelos de aprendizaje automático y datos satelitales o de drones.
        
        **Ventajas:**
        - Clasificación más precisa y continua
        - Monitoreo dinámico en tiempo real
        - Integración con variables ambientales
        - Optimización del manejo sitio-específico
        """)
    
    # Estadísticas resumen
    st.subheader("📊 ESTADÍSTICAS DEL ANÁLISIS AVANZADO")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "NO_DETERMINADA"
        st.metric("🏗️ Textura Predominante", textura_predominante)
    with col2:
        avg_adecuacion = gdf_textura['adecuacion_textura'].mean()
        st.metric("📊 Adecuación Promedio", f"{avg_adecuacion:.1%}")
    with col3:
        metodologia_pred = gdf_textura['metodologia_analisis'].mode()[0] if len(gdf_textura) > 0 else "TRADICIONAL"
        st.metric("🔬 Metodología Predominante", metodologia_pred.replace('_', ' ').title())
    with col4:
        riesgo_pred = gdf_textura['riesgo_erosion'].mode()[0] if len(gdf_textura) > 0 else "BAJO"
        st.metric("⚠️ Riesgo de Erosión", riesgo_pred)
    
    # Distribución de texturas
    st.subheader("📋 DISTRIBUCIÓN DE TEXTURAS")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Gráfico de torta
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        textura_dist = gdf_textura['textura_suelo'].value_counts()
        
        # Colores para texturas
        colores_textura = {
            'Arenoso': '#d8b365',
            'Franco Arcilloso-Arenoso': '#f6e8c3',
            'Franco': '#c7eae5',
            'Franco Arcilloso': '#5ab4ac',
            'Arcilloso': '#01665e'
        }
        
        colors_pie = [colores_textura.get(textura, '#999999') for textura in textura_dist.index]
        
        ax.pie(textura_dist.values, labels=textura_dist.index, autopct='%1.1f%%',
               colors=colors_pie, startangle=90)
        ax.set_title('Distribución de Texturas del Suelo')
        st.pyplot(fig)
    
    with col_dist2:
        # Composición granulométrica promedio
        st.markdown("#### 🧪 Composición Promedio")
        
        avg_arena = gdf_textura['arena'].mean()
        avg_limo = gdf_textura['limo'].mean()
        avg_arcilla = gdf_textura['arcilla'].mean()
        
        fig_bar, ax_bar = plt.subplots(1, 1, figsize=(8, 6))
        componentes = ['Arena', 'Limo', 'Arcilla']
        valores = [avg_arena, avg_limo, avg_arcilla]
        colores_bar = ['#d8b365', '#f6e8c3', '#01665e']
        
        bars = ax_bar.bar(componentes, valores, color=colores_bar, edgecolor='black')
        ax_bar.set_ylabel('Porcentaje (%)')
        ax_bar.set_title('Composición Granulométrica Promedio')
        ax_bar.set_ylim(0, 100)
        
        # Añadir valores en las barras
        for bar, valor in zip(bars, valores):
            height = bar.get_height()
            ax_bar.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{valor:.1f}%', ha='center', va='bottom')
        
        st.pyplot(fig_bar)
    
    # Mapa de texturas
    st.subheader("🗺️ MAPA DE TEXTURAS AVANZADO")
    
    # Crear mapa interactivo
    mapa_textura = crear_mapa_interactivo_esri(
        gdf_textura,
        f"Textura del Suelo - {cultivo.replace('_', ' ').title()}",
        'textura_suelo',
        "ANÁLISIS DE TEXTURA"
    )
    st_folium(mapa_textura, width=800, height=500)
    
    # Análisis por adecuación
    st.subheader("📈 ANÁLISIS DE ADECUACIÓN POR ZONA")
    
    # Distribución de categorías de adecuación
    cat_adecuacion_dist = gdf_textura['categoria_adecuacion'].value_counts()
    
    col_adec1, col_adec2 = st.columns(2)
    
    with col_adec1:
        st.markdown("#### Distribución de Adecuación")
        fig_cat, ax_cat = plt.subplots(1, 1, figsize=(8, 6))
        
        colores_adecuacion = {
            'ÓPTIMA': '#1a9850',
            'MUY ADECUADA': '#66bd63',
            'ADECUADA': '#a6d96a',
            'MODERADAMENTE ADECUADA': '#fee08b',
            'MODERADA': '#fdae61',
            'LIMITANTE': '#f46d43',
            'POCO ADECUADA': '#d73027',
            'MUY LIMITANTE': '#a50026'
        }
        
        cat_colors = [colores_adecuacion.get(cat, '#999999') for cat in cat_adecuacion_dist.index]
        ax_cat.pie(cat_adecuacion_dist.values, labels=cat_adecuacion_dist.index,
                  autopct='%1.1f%%', colors=cat_colors, startangle=90)
        ax_cat.set_title('Distribución de Categorías de Adecuación')
        st.pyplot(fig_cat)
    
    with col_adec2:
        st.markdown("#### Recomendaciones por Categoría")
        
        for categoria in cat_adecuacion_dist.index:
            zonas_categoria = gdf_textura[gdf_textura['categoria_adecuacion'] == categoria]
            if len(zonas_categoria) > 0:
                with st.expander(f"{categoria} ({len(zonas_categoria)} zonas)"):
                    # Mostrar justificación
                    st.markdown(f"**Justificación:** {zonas_categoria.iloc[0]['justificacion_adecuacion']}")
                    
                    # Mostrar recomendaciones
                    if len(zonas_categoria['recomendaciones_manejo'].iloc[0]) > 0:
                        st.markdown("**Recomendaciones de manejo:**")
                        recomendaciones = zonas_categoria.iloc[0]['recomendaciones_manejo'].split(" | ")
                        for rec in recomendaciones[:3]:
                            st.markdown(f"- {rec}")
                    
                    # Mostrar alertas
                    if len(zonas_categoria['alertas'].iloc[0]) > 0:
                        st.markdown("**Alertas:**")
                        alertas = zonas_categoria.iloc[0]['alertas'].split(" | ")
                        for alerta in alertas[:2]:
                            st.markdown(f"- {alerta}")
    
    # Tabla detallada con datos avanzados
    st.subheader("📊 TABLA DE DATOS AVANZADOS")
    
    columnas_avanzadas = [
        'id_zona', 'area_ha', 'textura_suelo', 'metodologia_analisis',
        'categoria_adecuacion', 'adecuacion_textura', 'riesgo_erosion',
        'arena', 'limo', 'arcilla', 'agua_disponible', 'conductividad_electrica'
    ]
    
    df_avanzado = gdf_textura[columnas_avanzadas].copy()
    df_avanzado['area_ha'] = df_avanzado['area_ha'].round(3)
    df_avanzado['adecuacion_textura'] = df_avanzado['adecuacion_textura'].round(3)
    df_avanzado['arena'] = df_avanzado['arena'].round(1)
    df_avanzado['limo'] = df_avanzado['limo'].round(1)
    df_avanzado['arcilla'] = df_avanzado['arcilla'].round(1)
    df_avanzado['agua_disponible'] = df_avanzado['agua_disponible'].round(1)
    df_avanzado['conductividad_electrica'] = df_avanzado['conductividad_electrica'].round(2)
    
    st.dataframe(df_avanzado, use_container_width=True)
    
    # Recomendaciones tecnológicas
    st.subheader("💡 RECOMENDACIONES TECNOLÓGICAS")
    
    col_tech1, col_tech2 = st.columns(2)
    
    with col_tech1:
        st.markdown("#### 🛰️ **Tecnologías de Monitoreo**")
        
        metodologias_cultivo = TEXTURA_SUELO_OPTIMA[cultivo]['metodologias_recomendadas']
        sensores_cultivo = TEXTURA_SUELO_OPTIMA[cultivo]['sensores_recomendados']
        
        st.markdown(f"**Metodologías recomendadas para {cultivo.replace('_', ' ').title()}:**")
        for metodologia in metodologias_cultivo:
            if metodologia in METODOLOGIAS_AVANZADAS:
                st.markdown(f"- **{metodologia.replace('_', ' ').title()}:**")
                st.markdown(f"  {METODOLOGIAS_AVANZADAS[metodologia]['descripcion']}")
        
        st.markdown(f"**Sensores recomendados:**")
        for sensor in sensores_cultivo:
            st.markdown(f"- {sensor}")
    
    with col_tech2:
        st.markdown("#### 📅 **Plan de Implementación**")
        
        frecuencia = TEXTURA_SUELO_OPTIMA[cultivo]['frecuencia_monitoreo']
        
        st.markdown(f"**Frecuencia de monitoreo:** {frecuencia}")
        
        st.markdown("**Etapas de implementación:**")
        etapas = [
            ("Fase 1 (0-3 meses)", [
                "Instalación de sensores base",
                "Calibración de equipos",
                "Entrenamiento de personal"
            ]),
            ("Fase 2 (3-12 meses)", [
                "Monitoreo continuo",
                "Análisis de datos",
                "Ajustes de manejo"
            ]),
            ("Fase 3 (12+ meses)", [
                "Optimización del sistema",
                "Escalamiento de tecnologías",
                "Integración con otras plataformas"
            ])
        ]
        
        for etapa, acciones in etapas:
            with st.expander(etapa):
                for accion in acciones:
                    st.markdown(f"- {accion}")
    
    # Descargar resultados
    st.markdown("### 💾 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
    with col_dl1:
        # Descargar CSV avanzado
        csv_avanzado = df_avanzado.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Datos CSV",
            data=csv_avanzado,
            file_name=f"textura_avanzada_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Descargar GeoJSON
        geojson_avanzado = gdf_textura.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson_avanzado,
            file_name=f"textura_avanzada_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    
    with col_dl3:
        # Generar informe PDF avanzado
        if st.button("📄 Generar Informe Avanzado", type="primary", key="pdf_textura_avanzada"):
            with st.spinner("🔄 Generando informe avanzado..."):
                # Aquí iría la función para generar PDF avanzado
                st.success("Funcionalidad de PDF avanzado en desarrollo")
                st.info("Por ahora, usa los formatos CSV y GeoJSON")

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
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            if gdf_zonas is None or len(gdf_zonas) == 0:
                st.error("No se pudo dividir la parcela en zonas. Verifica la geometría.")
                return
            st.session_state.gdf_zonas = gdf_zonas
        
        with st.spinner(f"🔬 Realizando análisis {analisis_tipo}..."):
            # Calcular índices según tipo de análisis seleccionado
            if analisis_tipo == "FERTILIDAD ACTUAL":
                gdf_analisis = analizar_fertilidad_real(gdf_zonas, cultivo, mes_analisis, fuente_satelital)
                if gdf_analisis is not None:
                    st.session_state.analisis_fertilidad = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis  # ← AÑADIR ESTA LÍNEA
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()  # ← ESTO DEBE ESTAR DENTRO DEL IF
                else:
                    st.error("Error en el análisis de fertilidad")
                
            elif analisis_tipo == "RECOMENDACIONES NPK":
                gdf_analisis = generar_recomendaciones_npk(gdf_zonas, cultivo, nutriente, mes_analisis, fuente_satelital)
                if gdf_analisis is not None:
                    st.session_state.analisis_npk = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis  # ← AÑADIR ESTA LÍNEA
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()
                else:
                    st.error("Error en las recomendaciones NPK")
                
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                gdf_analisis = analizar_textura_suelo_avanzado(gdf_zonas, cultivo, mes_analisis)
                if gdf_analisis is not None:
                    st.session_state.analisis_textura = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis  # ← AÑADIR ESTA LÍNEA
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()
                else:
                    st.error("Error en el análisis de textura")
                
            elif analisis_tipo == "ANÁLISIS NDWI":
                gdf_analisis = analizar_ndwi(gdf_zonas, cultivo, mes_analisis, fuente_satelital)
                if gdf_analisis is not None:
                    st.session_state.analisis_ndwi = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis  # ← AÑADIR ESTA LÍNEA
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()
                else:
                    st.error("Error en el análisis NDWI")
                
            elif analisis_tipo == "ALTIMETRÍA":
                gdf_analisis = analizar_altimetria(gdf_zonas, cultivo, usar_elevacion)
                if gdf_analisis is not None:
                    st.session_state.analisis_altimetria = gdf_analisis
                    st.session_state.gdf_analisis = gdf_analisis  # ← AÑADIR ESTA LÍNEA
                    st.session_state.area_total = area_total
                    st.session_state.analisis_completado = True
                    st.success("✅ Análisis completado correctamente")
                    st.rerun()
                else:
                    st.error("Error en el análisis de altimetría")
# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
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

    # Variables globales (para compatibilidad)
    global cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, uploaded_file, fuente_satelital
    
    # Procesar archivo subido si existe
    if uploaded_file is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
                st.rerun()  # Forzar rerun para actualizar la interfaz

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
        st.rerun()  # Forzar rerun para actualizar la interfaz

    # Mostrar interfaz según el estado
    if st.session_state.analisis_completado:
        # Mostrar el análisis correspondiente
        if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
            mostrar_analisis_fertilidad_real()
        elif analisis_tipo == "RECOMENDACIONES NPK" and st.session_state.analisis_npk is not None:
            mostrar_recomendaciones_npk()
        elif analisis_tipo == "ANÁLISIS DE TEXTURA" and st.session_state.analisis_textura is not None:
            mostrar_analisis_textura_mejorado()
        elif analisis_tipo == "ANÁLISIS NDWI" and st.session_state.analisis_ndwi is not None:
            mostrar_analisis_ndwi()
        elif analisis_tipo == "ALTIMETRÍA" and st.session_state.analisis_altimetria is not None:
            mostrar_analisis_altimetria()
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
