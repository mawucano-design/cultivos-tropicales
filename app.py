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
from shapely.geometry import Polygon, LineString, Point, MultiLineString
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
from scipy.interpolate import griddata
import warnings
import sys
import shutil
from scipy.ndimage import gaussian_filter
warnings.filterwarnings('ignore')

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA GEE COMPLETA CON AGROECOLOGÍA")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# ========== PARÁMETROS MEJORADOS ==========
PARAMETROS_CULTIVOS = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 120, 'max': 200, 'optimo': 160},
        'FOSFORO': {'min': 40, 'max': 80, 'optimo': 60},
        'POTASIO': {'min': 160, 'max': 240, 'optimo': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.35,
        'pH_OPTIMO': 5.5,
        'CONDUCTIVIDAD_OPTIMA': 1.2
    },
    'CACAO': {
        'NITROGENO': {'min': 100, 'max': 180, 'optimo': 140},
        'FOSFORO': {'min': 30, 'max': 60, 'optimo': 45},
        'POTASIO': {'min': 120, 'max': 200, 'optimo': 160},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.4,
        'pH_OPTIMO': 6.0,
        'CONDUCTIVIDAD_OPTIMA': 1.0
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 280, 'optimo': 230},
        'FOSFORO': {'min': 50, 'max': 90, 'optimo': 70},
        'POTASIO': {'min': 250, 'max': 350, 'optimo': 300},
        'MATERIA_ORGANICA_OPTIMA': 4.5,
        'HUMEDAD_OPTIMA': 0.45,
        'pH_OPTIMO': 6.2,
        'CONDUCTIVIDAD_OPTIMA': 1.5
    }
}

# PARÁMETROS DE TEXTURA DEL SUELO POR CULTIVO
TEXTURA_SUELO_OPTIMA = {
    'PALMA_ACEITERA': {
        'textura_optima': 'Franco Arcilloso',
        'arena_optima': 40,
        'limo_optima': 30,
        'arcilla_optima': 30,
        'densidad_aparente_optima': 1.3,
        'porosidad_optima': 0.5
    },
    'CACAO': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.2,
        'porosidad_optima': 0.55
    },
    'BANANO': {
        'textura_optima': 'Franco Arcilloso-Arenoso',
        'arena_optima': 50,
        'limo_optima': 30,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52
    }
}

# PARÁMETROS PARA CÁLCULO DE NDWI (SOBRE EL SUELO)
PARAMETROS_NDWI_SUELO = {
    'PALMA_ACEITERA': {
        'ndwi_optimo_suelo': 0.15,
        'ndwi_humedo_suelo': 0.25,
        'ndwi_seco_suelo': -0.15,
        'umbral_sequia': -0.1
    },
    'CACAO': {
        'ndwi_optimo_suelo': 0.18,
        'ndwi_humedo_suelo': 0.3,
        'ndwi_seco_suelo': -0.1,
        'umbral_sequia': -0.05
    },
    'BANANO': {
        'ndwi_optimo_suelo': 0.2,
        'ndwi_humedo_suelo': 0.35,
        'ndwi_seco_suelo': -0.05,
        'umbral_sequia': 0.0
    }
}

# PARÁMETROS PARA ANÁLISIS DE CURVAS DE NIVEL
PARAMETROS_CURVAS_NIVEL = {
    'intervalo_curvas': 5.0,
    'resolucion_dem': 10.0,
    'min_elevacion': 100,
    'max_elevacion': 500,
    'factor_relieve': 0.5
}

# CLASIFICACIÓN DE PENDIENTES
CLASIFICACION_PENDIENTES = {
    'PLANA (0-2%)': {'min': 0, 'max': 2, 'color': '#4daf4a', 'factor_erosivo': 0.1},
    'SUAVE (2-5%)': {'min': 2, 'max': 5, 'color': '#a6d96a', 'factor_erosivo': 0.3},
    'MODERADA (5-10%)': {'min': 5, 'max': 10, 'color': '#ffffbf', 'factor_erosivo': 0.6},
    'FUERTE (10-15%)': {'min': 10, 'max': 15, 'color': '#fdae61', 'factor_erosivo': 0.8},
    'MUY FUERTE (15-25%)': {'min': 15, 'max': 25, 'color': '#f46d43', 'factor_erosivo': 0.9},
    'EXTREMA (>25%)': {'min': 25, 'max': 100, 'color': '#d73027', 'factor_erosivo': 1.0}
}

# CLASIFICACIÓN DE TEXTURAS DEL SUELO
CLASIFICACION_TEXTURAS = {
    'Franco': {'arena_min': 43, 'arena_max': 52, 'limo_min': 28, 'limo_max': 50, 'arcilla_min': 7, 'arcilla_max': 27},
    'Franco Arcilloso': {'arena_min': 20, 'arena_max': 45, 'limo_min': 15, 'limo_max': 53, 'arcilla_min': 25, 'arcilla_max': 35},
    'Franco Arcilloso-Arenoso': {'arena_min': 40, 'arena_max': 50, 'limo_min': 20, 'limo_max': 40, 'arcilla_min': 20, 'arcilla_max': 30},
    'Arenoso': {'arena_min': 85, 'arena_max': 100, 'limo_max': 15, 'arcilla_max': 15},
    'Arcilloso': {'arena_max': 45, 'limo_max': 40, 'arcilla_min': 35}
}

# FACTORES EDÁFICOS MÁS REALISTAS
FACTORES_SUELO = {
    'Arcilloso': {'retention': 1.3, 'drainage': 0.7, 'aeration': 0.6, 'workability': 0.5},
    'Franco Arcilloso': {'retention': 1.2, 'drainage': 0.8, 'aeration': 0.7, 'workability': 0.7},
    'Franco': {'retention': 1.0, 'drainage': 1.0, 'aeration': 1.0, 'workability': 1.0},
    'Franco Arcilloso-Arenoso': {'retention': 0.8, 'drainage': 1.2, 'aeration': 1.3, 'workability': 1.2},
    'Arenoso': {'retention': 0.6, 'drainage': 1.4, 'aeration': 1.5, 'workability': 1.4}
}

# RECOMENDACIONES POR TIPO DE TEXTURA
RECOMENDACIONES_TEXTURA = {
    'Franco': {
        'propiedades': [
            "Equilibrio arena-limo-arcilla",
            "Buena aireación y drenaje",
            "CIC Intermedia-alta",
            "Retención de agua adecuada"
        ],
        'limitantes': [
            "Puede compactarse con maquinaria pesada",
            "Erosión en pendientes si no hay cobertura"
        ],
        'manejo': [
            "Mantener coberturas vivas o muertas",
            "Evitar tránsito excesivo de maquinaria",
            "Fertilización eficiente, sin muchas pérdidas",
            "Ideal para densidad estándar 9 × 9 m"
        ]
    },
    'Franco Arcilloso': {
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
            "Implementar drenajes (canales y subdrenes)",
            "Subsolado previo a siembra",
            "Incorporar materia orgánica (raquis, compost)",
            "Fertilización fraccionada en lluvias intensas"
        ]
    },
    'Franco Arcilloso-Arenoso': {
        'propiedades': [
            "Arena 40–50%, arcilla 20–30%",
            "Buen desarrollo radicular",
            "Mayor drenaje que franco arcilloso",
            "Retención de agua moderada-baja"
        ],
        'limitantes': [
            "Riesgo de lixiviación de nutrientes",
            "Estrés hídrico en veranos",
            "Fertilidad moderada"
        ],
        'manejo': [
            "Uso de coberturas leguminosas",
            "Aplicar mulching (raquis, hojas)",
            "Riego suplementario en sequía",
            "Fertilización fraccionada con énfasis en K y Mg"
        ]
    },
    'Arenoso': {
        'propiedades': [
            "Alto contenido de arena (>85%)",
            "Excelente drenaje",
            "Baja retención de agua",
            "Fácil laboreo"
        ],
        'limitantes': [
            "Baja retención de nutrientes",
            "Riesgo alto de erosión",
            "Requiere riego frecuente"
        ],
        'manejo': [
            "Aplicaciones frecuentes de materia orgánica",
            "Riego por goteo para eficiencia hídrica",
            "Fertilización fraccionada en pequeñas dosis",
            "Barreras vivas contra erosión"
        ]
    },
    'Arcilloso': {
        'propiedades': [
            "Alto contenido de arcilla (>35%)",
            "Alta retención de agua y nutrientes",
            "Estructura densa",
            "Alta fertilidad potencial"
        ],
        'limitantes': [
            "Drenaje muy lento",
            "Alta compactación",
            "Difícil laboreo cuando está húmedo"
        ],
        'manejo': [
            "Añadir materia orgánica para mejorar estructura",
            "Evitar laboreo en condiciones húmedas",
            "Implementar sistemas de drenaje profundo",
            "Cultivos de cobertura para romper compactación"
        ]
    }
}

# PRINCIPIOS AGROECOLÓGICOS
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

# RECOMENDACIONES PARA MANEJO DE PENDIENTES
RECOMENDACIONES_PENDIENTES = {
    'PLANA (0-2%)': [
        "Diseño rectangular de plantación",
        "Sistemas de riego por gravedad eficientes",
        "Labranza convencional posible",
        "Maquinaria pesada sin restricciones"
    ],
    'SUAVE (2-5%)': [
        "Diseño en contorno ligero",
        "Surcos siguiendo curvas de nivel",
        "Labranza reducida recomendada",
        "Barreras vivas cada 50 metros"
    ],
    'MODERADA (5-10%)': [
        "Diseño en contorno estricto",
        "Terrazas de base ancha",
        "Cultivos en franjas",
        "Barreras vivas cada 30 metros"
    ],
    'FUERTE (10-15%)': [
        "Terrazas individuales por planta",
        "Sistemas agroforestales",
        "Cultivo en callejones (alley cropping)",
        "Barreras vivas cada 20 metros"
    ],
    'MUY FUERTE (15-25%)': [
        "Terrazas con muros de piedra",
        "Sistemas silvopastoriles",
        "Cultivos permanentes de cobertura",
        "Evitar labranza, usar siembra directa"
    ],
    'EXTREMA (>25%)': [
        "Forestación o agroforestería densa",
        "Terrazas estrechas con vegetación permanente",
        "Sistemas de captación de agua",
        "No usar maquinaria, solo manual"
    ]
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

# FACTORES ESTACIONALES PARA NDWI DEL SUELO
FACTORES_NDWI_MES = {
    "ENERO": 0.8, "FEBRERO": 0.85, "MARZO": 0.9, "ABRIL": 0.95,
    "MAYO": 1.0, "JUNIO": 0.95, "JULIO": 0.85, "AGOSTO": 0.8,
    "SEPTIEMBRE": 0.85, "OCTUBRE": 0.9, "NOVIEMBRE": 0.95, "DICIEMBRE": 0.9
}

# PALETAS GEE MEJORADAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'NDWI_SUELO': ['#8b0000', '#ff4500', '#ffa500', '#ffff00', '#adff2f', '#32cd32', '#006400'],
    'ELEVACION': ['#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf', '#fee08b', '#fdae61', '#f46d43', '#d73027'],
    'PENDIENTE': ['#4daf4a', '#a6d96a', '#ffffbf', '#fdae61', '#f46d43', '#d73027']
}

# ========== FUNCIONES AUXILIARES ==========

def clasificar_pendiente(pendiente_porcentaje):
    """Clasifica la pendiente según categorías establecidas"""
    for categoria, params in CLASIFICACION_PENDIENTES.items():
        if params['min'] <= pendiente_porcentaje < params['max']:
            return categoria, params['color']
    return "EXTREMA (>25%)", CLASIFICACION_PENDIENTES['EXTREMA (>25%)']['color']

def calcular_estadisticas_pendiente(pendiente_grid):
    """Calcula estadísticas de pendiente del terreno"""
    pendiente_flat = pendiente_grid.flatten()
    pendiente_flat = pendiente_flat[~np.isnan(pendiente_flat)]
    
    if len(pendiente_flat) == 0:
        return {
            'promedio': 0,
            'min': 0,
            'max': 0,
            'std': 0,
            'distribucion': {}
        }
    
    stats = {
        'promedio': float(np.mean(pendiente_flat)),
        'min': float(np.min(pendiente_flat)),
        'max': float(np.max(pendiente_flat)),
        'std': float(np.std(pendiente_flat)),
        'distribucion': {}
    }
    
    # Calcular distribución por categoría
    for categoria, params in CLASIFICACION_PENDIENTES.items():
        mask = (pendiente_flat >= params['min']) & (pendiente_flat < params['max'])
        stats['distribucion'][categoria] = {
            'porcentaje': float(np.sum(mask) / len(pendiente_flat) * 100),
            'area_ha': float(np.sum(mask) * (PARAMETROS_CURVAS_NIVEL['resolucion_dem']**2) / 10000),
            'color': params['color']
        }
    
    return stats

def clasificar_textura_suelo(arena, limo, arcilla):
    """Clasifica la textura del suelo según los rangos de la imagen"""
    try:
        # Normalizar porcentajes a 100%
        total = arena + limo + arcilla
        if total == 0:
            return "NO_DETERMINADA"
        
        arena_norm = (arena / total) * 100
        limo_norm = (limo / total) * 100
        arcilla_norm = (arcilla / total) * 100
        
        # Clasificación según los rangos de la imagen
        if arcilla_norm >= 35:
            return "Arcilloso"
        elif arcilla_norm >= 25 and arcilla_norm <= 35 and arena_norm >= 20 and arena_norm <= 45:
            return "Franco Arcilloso"
        elif arcilla_norm >= 20 and arcilla_norm <= 30 and arena_norm >= 40 and arena_norm <= 50:
            return "Franco Arcilloso-Arenoso"
        elif arcilla_norm >= 7 and arcilla_norm <= 27 and arena_norm >= 43 and arena_norm <= 52:
            return "Franco"
        elif arena_norm >= 85:
            return "Arenoso"
        else:
            return "Franco"
        
    except Exception as e:
        return "NO_DETERMINADA"

def calcular_propiedades_fisicas_suelo(textura, materia_organica):
    """Calcula propiedades físicas del suelo basadas en textura y MO"""
    propiedades = {
        'capacidad_campo': 0.0,
        'punto_marchitez': 0.0,
        'agua_disponible': 0.0,
        'densidad_aparente': 0.0,
        'porosidad': 0.0,
        'conductividad_hidraulica': 0.0,
        'aireacion': 0.0,
        'drenaje': 0.0
    }
    
    # Valores base según textura (mm/m)
    base_propiedades = {
        'Arcilloso': {'cc': 380, 'pm': 220, 'da': 1.35, 'porosidad': 0.45, 'kh': 0.1, 'aireacion': 0.6, 'drenaje': 0.3},
        'Franco Arcilloso': {'cc': 320, 'pm': 160, 'da': 1.25, 'porosidad': 0.53, 'kh': 0.5, 'aireacion': 0.7, 'drenaje': 0.6},
        'Franco': {'cc': 280, 'pm': 120, 'da': 1.2, 'porosidad': 0.55, 'kh': 1.5, 'aireacion': 1.0, 'drenaje': 1.0},
        'Franco Arcilloso-Arenoso': {'cc': 220, 'pm': 100, 'da': 1.35, 'porosidad': 0.49, 'kh': 3.0, 'aireacion': 1.3, 'drenaje': 1.2},
        'Arenoso': {'cc': 150, 'pm': 60, 'da': 1.5, 'porosidad': 0.43, 'kh': 10.0, 'aireacion': 1.5, 'drenaje': 1.5}
    }
    
    if textura in base_propiedades:
        base = base_propiedades[textura]
        
        # Ajustar por materia orgánica
        factor_mo = 1.0 + (materia_organica * 0.05)
        
        propiedades['capacidad_campo'] = base['cc'] * factor_mo
        propiedades['punto_marchitez'] = base['pm'] * factor_mo
        propiedades['agua_disponible'] = (base['cc'] - base['pm']) * factor_mo
        propiedades['densidad_aparente'] = base['da'] / factor_mo
        propiedades['porosidad'] = min(0.65, base['porosidad'] * factor_mo)
        propiedades['conductividad_hidraulica'] = base['kh'] * factor_mo
        propiedades['aireacion'] = min(1.0, base['aireacion'] * factor_mo)
        propiedades['drenaje'] = min(2.0, base['drenaje'] * factor_mo)
    
    return propiedades

def evaluar_adecuacion_textura(textura_actual, cultivo):
    """Evalúa qué tan adecuada es la textura para el cultivo específico"""
    textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
    
    if textura_actual == textura_optima:
        return "ÓPTIMA", 1.0
    elif textura_actual == "NO_DETERMINADA":
        return "NO_DETERMINADA", 0
    
    # Matriz de compatibilidad
    compatibilidad = {
        'Franco': {'Franco Arcilloso': 0.8, 'Franco Arcilloso-Arenoso': 0.7, 'Arcilloso': 0.4, 'Arenoso': 0.6},
        'Franco Arcilloso': {'Franco': 0.8, 'Franco Arcilloso-Arenoso': 0.6, 'Arcilloso': 0.9, 'Arenoso': 0.4},
        'Franco Arcilloso-Arenoso': {'Franco': 0.7, 'Franco Arcilloso': 0.6, 'Arcilloso': 0.5, 'Arenoso': 0.8},
        'Arcilloso': {'Franco': 0.4, 'Franco Arcilloso': 0.9, 'Franco Arcilloso-Arenoso': 0.5, 'Arenoso': 0.2},
        'Arenoso': {'Franco': 0.6, 'Franco Arcilloso': 0.4, 'Franco Arcilloso-Arenoso': 0.8, 'Arcilloso': 0.2}
    }
    
    if textura_actual in compatibilidad and textura_optima in compatibilidad[textura_actual]:
        puntaje = compatibilidad[textura_actual][textura_optima]
        if puntaje >= 0.8:
            return "MUY ADECUADA", puntaje
        elif puntaje >= 0.6:
            return "ADECUADA", puntaje
        elif puntaje >= 0.4:
            return "MODERADA", puntaje
        else:
            return "LIMITANTE", puntaje
    
    return "LIMITANTE", 0.3

def calcular_superficie(gdf):
    """Calcula superficie en hectáreas con manejo robusto de CRS"""
    try:
        if gdf is None or gdf.empty or gdf.geometry.isnull().all():
            return 0.0
            
        # Verificar si el CRS es geográfico (grados)
        if gdf.crs and gdf.crs.is_geographic:
            try:
                gdf_proj = gdf.to_crs('EPSG:3116')
                area_m2 = gdf_proj.geometry.area.sum()
            except:
                area_m2 = gdf.geometry.area.sum() * 111000 * 111000
        else:
            area_m2 = gdf.geometry.area.sum()
            
        return area_m2 / 10000
        
    except Exception as e:
        try:
            return gdf.geometry.area.sum() / 10000
        except:
            return 0.0

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
    
    # Añadir capa de relieve
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Relieve',
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
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Franco Arcilloso-Arenoso': '#f6e8c3',
                'Arenoso': '#d8b365',
                'Arcilloso': '#01665e',
                'NO_DETERMINADA': '#999999'
            }
            unidad = "Textura"
        elif analisis_tipo == "ANÁLISIS NDWI SUELO":
            vmin, vmax = -1, 1
            colores = PALETAS_GEE['NDWI_SUELO']
            unidad = "Índice"
        elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
            vmin, vmax = gdf[columna_valor].min(), gdf[columna_valor].max()
            colores = PALETAS_GEE['ELEVACION']
            unidad = "m"
        else:
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
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                # Manejo especial para textura (valores categóricos)
                textura = row[columna_valor]
                color = colores_textura.get(textura, '#999999')
                valor_display = textura
            else:
                # Manejo para valores numéricos
                valor = row[columna_valor]
                color = obtener_color(valor, vmin, vmax, colores)
                if analisis_tipo in ["FERTILIDAD ACTUAL", "ANÁLISIS NDWI SUELO"]:
                    valor_display = f"{valor:.3f}"
                elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                    valor_display = f"{valor:.1f}"
                else:
                    valor_display = f"{valor:.1f}"
            
            # Popup más informativo
            if analisis_tipo == "FERTILIDAD ACTUAL":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Índice Fertilidad:</b> {valor_display}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>MO:</b> {row.get('materia_organica', 0):.1f}%<br>
                    <b>NDVI:</b> {row.get('ndvi', 0):.3f}
                </div>
                """
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Textura:</b> {valor_display}<br>
                    <b>Adecuación:</b> {row.get('adecuacion_textura', 0):.1%}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <hr>
                    <b>Arena:</b> {row.get('arena', 0):.1f}%<br>
                    <b>Limo:</b> {row.get('limo', 0):.1f}%<br>
                    <b>Arcilla:</b> {row.get('arcilla', 0):.1f}%<br>
                    <b>Capacidad Campo:</b> {row.get('capacidad_campo', 0):.1f} mm/m<br>
                    <b>Agua Disponible:</b> {row.get('agua_disponible', 0):.1f} mm/m
                </div>
                """
            elif analisis_tipo == "ANÁLISIS NDWI SUELO":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>NDWI Suelo:</b> {valor_display}<br>
                    <b>Estado Humedad:</b> {row.get('estado_humedad_suelo', 'N/A')}<br>
                    <b>Riesgo Sequía:</b> {row.get('riesgo_sequia', 'N/A')}<br>
                    <b>Recomendación Riego:</b> {row.get('recomendacion_riego', 'N/A')}<br>
                    <hr>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Déficit Humedad:</b> {row.get('deficit_humedad', 0):.3f}<br>
                    <b>Humedad:</b> {row.get('humedad', 0):.1%}<br>
                    <b>NDVI:</b> {row.get('ndvi', 0):.3f}
                </div>
                """
            elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Curva {row['id_curva']}</h4>
                    <b>Elevación:</b> {valor_display} m<br>
                    <b>Longitud:</b> {row.get('longitud_m', 0):.1f} m<br>
                    <hr>
                    <b>Tipo:</b> Curva de nivel<br>
                    <b>Intervalo:</b> {PARAMETROS_CURVAS_NIVEL['intervalo_curvas']} m
                </div>
                """
            else:
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Recomendación {nutriente}:</b> {valor_display} {unidad}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría Fertilidad:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N Actual:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P Actual:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K Actual:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>Déficit:</b> {row.get('deficit_npk', 0):.1f} kg/ha
                </div>
                """
            
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
            
            # Marcador con número de zona mejorado
            if analisis_tipo != "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
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
                    f"<b>Polígono {idx + 1}</b><br>Área: {calcular_superficie(gdf.iloc[[idx]]):.2f} ha", 
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
        
        if analisis_tipo == "FERTILIDAD ACTUAL":
            steps = 8
            for i in range(steps):
                value = i / (steps - 1)
                color_idx = int((i / (steps - 1)) * (len(PALETAS_GEE['FERTILIDAD']) - 1))
                color = PALETAS_GEE['FERTILIDAD'][color_idx]
                categoria = ["Muy Baja", "Baja", "Media-Baja", "Media", "Media-Alta", "Alta", "Muy Alta"][min(i, 6)] if i < 7 else "Óptima"
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.1f} ({categoria})</div>'
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            # Leyenda categórica para texturas
            colores_textura = {
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Franco Arcilloso-Arenoso': '#f6e8c3',
                'Arenoso': '#d8b365',
                'Arcilloso': '#01665e'
            }
            for textura, color in colores_textura.items():
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {textura}</div>'
        elif analisis_tipo == "ANÁLISIS NDWI SUELO":
            steps = 7
            values = [-1.0, -0.5, -0.1, 0.0, 0.1, 0.2, 1.0]
            labels = ["Muy Seco", "Seco", "Moderado", "Óptimo", "Húmedo", "Muy Húmedo", "Saturado"]
            for i in range(steps):
                value = values[i]
                color_idx = int((i / (steps - 1)) * (len(PALETAS_GEE['NDWI_SUELO']) - 1))
                color = PALETAS_GEE['NDWI_SUELO'][color_idx]
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.1f} ({labels[i]})</div>'
        elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
            steps = 6
            for i in range(steps):
                value = vmin + (i / (steps - 1)) * (vmax - vmin)
                color_idx = int((i / (steps - 1)) * (len(colores) - 1))
                color = colores[color_idx]
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.0f} m</div>'
        else:
            steps = 6
            for i in range(steps):
                value = vmin + (i / (steps - 1)) * (vmax - vmin)
                color_idx = int((i / (steps - 1)) * (len(colores) - 1))
                color = colores[color_idx]
                intensidad = ["Muy Baja", "Baja", "Media", "Alta", "Muy Alta", "Máxima"][i]
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.0f} ({intensidad})</div>'
        
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
        area_ha = calcular_superficie(gdf.iloc[[idx]])
        
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

def crear_mapa_estatico(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa estático con matplotlib"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # CONFIGURACIÓN UNIFICADA CON EL MAPA INTERACTIVO
        if columna_valor and analisis_tipo:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
                vmin, vmax = 0, 1
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                # Mapa categórico para texturas
                colores_textura = {
                    'Franco': '#c7eae5',
                    'Franco Arcilloso': '#5ab4ac',
                    'Franco Arcilloso-Arenoso': '#f6e8c3',
                    'Arenoso': '#d8b365',
                    'Arcilloso': '#01665e',
                    'NO_DETERMINADA': '#999999'
                }
            elif analisis_tipo == "ANÁLISIS NDWI SUELO":
                cmap = LinearSegmentedColormap.from_list('ndwi_suelo_gee', PALETAS_GEE['NDWI_SUELO'])
                vmin, vmax = -1, 1
            elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                cmap = LinearSegmentedColormap.from_list('elevacion_gee', PALETAS_GEE['ELEVACION'])
                vmin, vmax = gdf[columna_valor].min(), gdf[columna_valor].max()
            else:
                # USAR EXACTAMENTE LOS MISMOS RANGOS QUE EL MAPA INTERACTIVO
                if nutriente == "NITRÓGENO":
                    cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                    vmin, vmax = 0, 250
                elif nutriente == "FÓSFORO":
                    cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                    vmin, vmax = 0, 120
                else:  # POTASIO
                    cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                    vmin, vmax = 0, 200
            
            # Plotear cada polígono con color según valor
            for idx, row in gdf.iterrows():
                if analisis_tipo == "ANÁLISIS DE TEXTURA":
                    # Manejo especial para textura
                    textura = row[columna_valor]
                    color = colores_textura.get(textura, '#999999')
                else:
                    valor = row[columna_valor]
                    valor_norm = (valor - vmin) / (vmax - vmin)
                    valor_norm = max(0, min(1, valor_norm))
                    color = cmap(valor_norm)
                
                # Plot del polígono
                gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
                
                # Etiqueta con valor
                centroid = row.geometry.centroid
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    texto_valor = f"{row[columna_valor]:.3f}"
                elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                    texto_valor = row[columna_valor]
                elif analisis_tipo == "ANÁLISIS NDWI SUELO":
                    texto_valor = f"{row[columna_valor]:.3f}"
                elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                    texto_valor = f"{row[columna_valor]:.0f}"
                else:
                    texto_valor = f"{row[columna_valor]:.0f} kg"
                
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
        if columna_valor and analisis_tipo and analisis_tipo != "ANÁLISIS DE TEXTURA":
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
            
            # Etiquetas de barra unificadas
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cbar.set_label('Índice NPK Actual (0-1)', fontsize=10)
                cbar.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
                cbar.set_ticklabels(['0.0 (Muy Baja)', '0.2', '0.4 (Media)', '0.6', '0.8', '1.0 (Muy Alta)'])
            elif analisis_tipo == "ANÁLISIS NDWI SUELO":
                cbar.set_label('NDWI Suelo (-1 a 1)', fontsize=10)
                cbar.set_ticks([-1, -0.5, -0.1, 0, 0.1, 0.2, 1])
                cbar.set_ticklabels(['-1 (Muy Seco)', '-0.5', '-0.1', '0', '0.1', '0.2', '1 (Saturado)'])
            elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                cbar.set_label('Elevación (metros)', fontsize=10)
                cbar.set_ticks([vmin, (vmin+vmax)/2, vmax])
                cbar.set_ticklabels([f'{vmin:.0f} m', f'{(vmin+vmax)/2:.0f} m', f'{vmax:.0f} m'])
            else:
                cbar.set_label(f'Recomendación {nutriente} (kg/ha)', fontsize=10)
                if nutriente == "NITRÓGENO":
                    cbar.set_ticks([0, 50, 100, 150, 200, 250])
                    cbar.set_ticklabels(['0', '50', '100', '150', '200', '250 kg/ha'])
                elif nutriente == "FÓSFORO":
                    cbar.set_ticks([0, 24, 48, 72, 96, 120])
                    cbar.set_ticklabels(['0', '24', '48', '72', '96', '120 kg/ha'])
                else:  # POTASIO
                    cbar.set_ticks([0, 40, 80, 120, 160, 200])
                    cbar.set_ticklabels(['0', '40', '80', '120', '160', '200 kg/ha'])
        
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

def mostrar_recomendaciones_agroecologicas(cultivo, categoria, area_ha, analisis_tipo, nutriente=None, textura_data=None):
    """Muestra recomendaciones agroecológicas específicas"""
    
    st.markdown("### 🌿 RECOMENDACIONES ESPECÍFICAS")
    
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and textura_data:
        textura_predominante = textura_data.get('textura_predominante', 'Franco')
        adecuacion_promedio = textura_data.get('adecuacion_promedio', 0.5)
        
        # Mostrar información detallada de la textura según imagen
        st.markdown(f"#### 🏗️ **{textura_predominante.upper()}**")
        
        if textura_predominante in RECOMENDACIONES_TEXTURA:
            info_textura = RECOMENDACIONES_TEXTURA[textura_predominante]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**✅ PROPIEDADES FÍSICAS**")
                for prop in info_textura['propiedades']:
                    st.markdown(f"• {prop}")
            
            with col2:
                st.markdown("**⚠️ LIMITANTES**")
                for lim in info_textura['limitantes']:
                    st.markdown(f"• {lim}")
            
            with col3:
                st.markdown("**🛠️ MANEJO RECOMENDADO**")
                for man in info_textura['manejo']:
                    st.markdown(f"• {man}")
            
            # Evaluación de adecuación
            st.markdown("#### 📊 EVALUACIÓN DE ADECUACIÓN")
            if adecuacion_promedio >= 0.8:
                st.success(f"**ADECUACIÓN: ÓPTIMA** ({adecuacion_promedio:.1%}) - Textura ideal para {cultivo.replace('_', ' ').title()}")
            elif adecuacion_promedio >= 0.6:
                st.warning(f"**ADECUACIÓN: MODERADA** ({adecuacion_promedio:.1%}) - Requiere ajustes en manejo")
            else:
                st.error(f"**ADECUACIÓN: LIMITANTE** ({adecuacion_promedio:.1%}) - Necesita mejoras significativas")
    else:
        # Enfoque tradicional basado en fertilidad
        if categoria in ["MUY BAJA", "BAJA"]:
            enfoque = "🚨 **ENFOQUE: RECUPERACIÓN Y REGENERACIÓN**"
            intensidad = "Alta"
        elif categoria in ["MEDIA"]:
            enfoque = "✅ **ENFOQUE: MANTENIMIENTO Y MEJORA**"
            intensidad = "Media"
        else:
            enfoque = "🌟 **ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN**"
            intensidad = "Baja"
        
        st.success(f"{enfoque} - Intensidad: {intensidad}")
    
    # Obtener recomendaciones específicas del cultivo
    recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
    
    # Mostrar por categorías
    st.markdown("#### 🌱 PRÁCTICAS AGROECOLÓGICAS")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("**COBERTURAS VIVAS**", expanded=True):
            for rec in recomendaciones.get('COBERTURAS_VIVAS', []):
                st.markdown(f"• {rec}")
    
    with col2:
        with st.expander("**ABONOS VERDES**", expanded=True):
            for rec in recomendaciones.get('ABONOS_VERDES', []):
                st.markdown(f"• {rec}")
    
    col3, col4 = st.columns(2)
    
    with col3:
        with st.expander("**BIOFERTILIZANTES**", expanded=True):
            for rec in recomendaciones.get('BIOFERTILIZANTES', []):
                st.markdown(f"• {rec}")
    
    with col4:
        with st.expander("**MANEJO ECOLÓGICO**", expanded=True):
            for rec in recomendaciones.get('MANEJO_ECOLOGICO', []):
                st.markdown(f"• {rec}")
    
    with st.expander("**ASOCIACIONES Y DIVERSIFICACIÓN**", expanded=True):
        for rec in recomendaciones.get('ASOCIACIONES', []):
            st.markdown(f"• {rec}")
    
    # PLAN DE IMPLEMENTACIÓN
    st.markdown("### 📅 PLAN DE IMPLEMENTACIÓN")
    
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

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo con manejo robusto de errores"""
    try:
        if len(gdf) == 0:
            return gdf
        
        # Usar el primer polígono como parcela principal
        parcela_principal = gdf.iloc[0].geometry
        
        # Verificar que la geometría sea válida
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        
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
        if width < 0.0001 or height < 0.0001:
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
                                largest = max(intersection.geoms, key=lambda p: p.area)
                                sub_poligonos.append(largest)
                            else:
                                sub_poligonos.append(intersection)
                except Exception as e:
                    continue
        
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

def analizar_textura_suelo(gdf, cultivo, mes_analisis):
    """Realiza análisis completo de textura del suelo"""
    
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para textura
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['arena'] = 0.0
    zonas_gdf['limo'] = 0.0
    zonas_gdf['arcilla'] = 0.0
    zonas_gdf['textura_suelo'] = "NO_DETERMINADA"
    zonas_gdf['adecuacion_textura'] = 0.0
    zonas_gdf['categoria_adecuacion'] = "NO_DETERMINADA"
    zonas_gdf['capacidad_campo'] = 0.0
    zonas_gdf['punto_marchitez'] = 0.0
    zonas_gdf['agua_disponible'] = 0.0
    zonas_gdf['densidad_aparente'] = 0.0
    zonas_gdf['porosidad'] = 0.0
    zonas_gdf['conductividad_hidraulica'] = 0.0
    zonas_gdf['aireacion'] = 0.0
    zonas_gdf['drenaje'] = 0.0
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Normalizar coordenadas para variabilidad espacial
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # SIMULAR COMPOSICIÓN GRANULOMÉTRICA
            variabilidad_local = 0.15 + 0.7 * (lat_norm * lon_norm)
            
            # Valores óptimos para el cultivo
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            
            # Simular composición basada en textura óptima del cultivo
            base_arena = arena_optima
            base_limo = limo_optima
            base_arcilla = arcilla_optima
            
            # Ajustar según variabilidad local
            arena = max(5, min(95, rng.normal(
                base_arena * (0.8 + 0.4 * variabilidad_local),
                base_arena * 0.15
            )))
            
            limo = max(5, min(95, rng.normal(
                base_limo * (0.7 + 0.6 * variabilidad_local),
                base_limo * 0.2
            )))
            
            arcilla = max(5, min(95, rng.normal(
                base_arcilla * (0.75 + 0.5 * variabilidad_local),
                base_arcilla * 0.15
            )))
            
            # Normalizar a 100%
            total = arena + limo + arcilla
            arena = (arena / total) * 100
            limo = (limo / total) * 100
            arcilla = (arcilla / total) * 100
            
            # Clasificar textura según imagen
            textura = clasificar_textura_suelo(arena, limo, arcilla)
            
            # Evaluar adecuación para el cultivo
            categoria_adecuacion, puntaje_adecuacion = evaluar_adecuacion_textura(textura, cultivo)
            
            # Simular materia orgánica para propiedades físicas
            materia_organica = max(1.0, min(8.0, rng.normal(3.0, 1.0)))
            
            # Calcular propiedades físicas
            propiedades_fisicas = calcular_propiedades_fisicas_suelo(textura, materia_organica)
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = arena
            zonas_gdf.loc[idx, 'limo'] = limo
            zonas_gdf.loc[idx, 'arcilla'] = arcilla
            zonas_gdf.loc[idx, 'textura_suelo'] = textura
            zonas_gdf.loc[idx, 'adecuacion_textura'] = puntaje_adecuacion
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = categoria_adecuacion
            zonas_gdf.loc[idx, 'capacidad_campo'] = propiedades_fisicas['capacidad_campo']
            zonas_gdf.loc[idx, 'punto_marchitez'] = propiedades_fisicas['punto_marchitez']
            zonas_gdf.loc[idx, 'agua_disponible'] = propiedades_fisicas['agua_disponible']
            zonas_gdf.loc[idx, 'densidad_aparente'] = propiedades_fisicas['densidad_aparente']
            zonas_gdf.loc[idx, 'porosidad'] = propiedades_fisicas['porosidad']
            zonas_gdf.loc[idx, 'conductividad_hidraulica'] = propiedades_fisicas['conductividad_hidraulica']
            zonas_gdf.loc[idx, 'aireacion'] = propiedades_fisicas['aireacion']
            zonas_gdf.loc[idx, 'drenaje'] = propiedades_fisicas['drenaje']
            
        except Exception as e:
            # Valores por defecto en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            
            # Propiedades físicas por defecto
            propiedades_default = calcular_propiedades_fisicas_suelo(params_textura['textura_optima'], 3.0)
            for prop, valor in propiedades_default.items():
                zonas_gdf.loc[idx, prop] = valor
    
    return zonas_gdf

def analizar_ndwi_suelo(gdf, cultivo, mes_analisis):
    """Realiza análisis específico del NDWI del suelo (contenido de agua en el suelo)"""
    
    params_ndwi = PARAMETROS_NDWI_SUELO[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas específicas para NDWI del suelo
    zonas_gdf['ndwi_suelo'] = 0.0
    zonas_gdf['estado_humedad_suelo'] = "MEDIO"
    zonas_gdf['deficit_humedad'] = 0.0
    zonas_gdf['recomendacion_riego'] = "NINGUNA"
    zonas_gdf['riesgo_sequia'] = "BAJO"
    
    factor_ndwi_mes = FACTORES_NDWI_MES[mes_analisis]
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_ndwi")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Normalizar coordenadas
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # Variabilidad espacial
            variabilidad_local = 0.3 + 0.5 * (lat_norm * lon_norm)
            
            # CÁLCULO DETALLADO DE NDWI DEL SUELO
            base_ndwi = params_ndwi['ndwi_optimo_suelo']
            
            # Simular variaciones basadas en factores:
            variacion_topografia = rng.normal(0, 0.1) * (1 - variabilidad_local)
            variacion_textura = variabilidad_local * 0.15
            variacion_profundidad = rng.random() * 0.1
            
            # Calcular NDWI del suelo
            ndwi_suelo = (
                base_ndwi + 
                variacion_topografia + 
                variacion_textura + 
                variacion_profundidad
            )
            
            # Aplicar factor estacional
            ndwi_suelo *= factor_ndwi_mes
            
            # Agregar variabilidad aleatoria
            ndwi_suelo += rng.normal(0, 0.03)
            
            # Limitar valores
            ndwi_suelo = max(-1.0, min(1.0, ndwi_suelo))
            
            # Calcular déficit de humedad
            deficit_humedad = max(0, params_ndwi['ndwi_optimo_suelo'] - ndwi_suelo)
            
            # Clasificar estado de humedad
            if ndwi_suelo >= params_ndwi['ndwi_humedo_suelo']:
                estado_humedad = "MUY HÚMEDO"
                recomendacion_riego = "REDUCIR RIEGO"
                riesgo_sequia = "NULO"
            elif ndwi_suelo >= params_ndwi['ndwi_optimo_suelo']:
                estado_humedad = "ÓPTIMO"
                recomendacion_riego = "MANTENER"
                riesgo_sequia = "BAJO"
            elif ndwi_suelo >= params_ndwi['umbral_sequia']:
                estado_humedad = "MODERADO"
                recomendacion_riego = "RIEGO MODERADO"
                riesgo_sequia = "MODERADO"
            elif ndwi_suelo >= params_ndwi['ndwi_seco_suelo']:
                estado_humedad = "SECO"
                recomendacion_riego = "RIEGO URGENTE"
                riesgo_sequia = "ALTO"
            else:
                estado_humedad = "MUY SECO"
                recomendacion_riego = "RIEGO INTENSIVO"
                riesgo_sequia = "CRÍTICO"
            
            # Asignar valores
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'ndwi_suelo'] = ndwi_suelo
            zonas_gdf.loc[idx, 'estado_humedad_suelo'] = estado_humedad
            zonas_gdf.loc[idx, 'deficit_humedad'] = deficit_humedad
            zonas_gdf.loc[idx, 'recomendacion_riego'] = recomendacion_riego
            zonas_gdf.loc[idx, 'riesgo_sequia'] = riesgo_sequia
            
        except Exception as e:
            # Valores por defecto
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'ndwi_suelo'] = params_ndwi['ndwi_optimo_suelo']
            zonas_gdf.loc[idx, 'estado_humedad_suelo'] = "ÓPTIMO"
            zonas_gdf.loc[idx, 'deficit_humedad'] = 0.0
            zonas_gdf.loc[idx, 'recomendacion_riego'] = "MANTENER"
            zonas_gdf.loc[idx, 'riesgo_sequia'] = "BAJO"
    
    return zonas_gdf

def calcular_indices_gee(gdf, cultivo, mes_analisis, analisis_tipo, nutriente):
    """Calcula índices GEE mejorados con cálculos NPK más precisos y NDWI del suelo"""
    
    params = PARAMETROS_CULTIVOS[cultivo]
    params_ndwi = PARAMETROS_NDWI_SUELO[cultivo]
    zonas_gdf = gdf.copy()
    
    # FACTORES ESTACIONALES MEJORADOS
    factor_mes = FACTORES_MES[mes_analisis]
    factor_n_mes = FACTORES_N_MES[mes_analisis]
    factor_p_mes = FACTORES_P_MES[mes_analisis]
    factor_k_mes = FACTORES_K_MES[mes_analisis]
    factor_ndwi_mes = FACTORES_NDWI_MES[mes_analisis]
    
    # Inicializar columnas adicionales
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['nitrogeno'] = 0.0
    zonas_gdf['fosforo'] = 0.0
    zonas_gdf['potasio'] = 0.0
    zonas_gdf['materia_organica'] = 0.0
    zonas_gdf['humedad'] = 0.0
    zonas_gdf['ph'] = 0.0
    zonas_gdf['conductividad'] = 0.0
    zonas_gdf['ndvi'] = 0.0
    zonas_gdf['ndwi_suelo'] = 0.0
    zonas_gdf['estado_humedad_suelo'] = "MEDIO"
    zonas_gdf['indice_fertilidad'] = 0.0
    zonas_gdf['categoria'] = "MEDIA"
    zonas_gdf['recomendacion_npk'] = 0.0
    zonas_gdf['deficit_npk'] = 0.0
    zonas_gdf['prioridad'] = "MEDIA"
    
    for idx, row in zonas_gdf.iterrows():
        try:
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            
            # Semilla más estable para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # Normalizar coordenadas para variabilidad espacial más realista
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # SIMULACIÓN MÁS REALISTA DE PARÁMETROS DEL SUELO
            n_optimo = params['NITROGENO']['optimo']
            p_optimo = params['FOSFORO']['optimo']
            k_optimo = params['POTASIO']['optimo']
            
            # Variabilidad espacial más pronunciada
            variabilidad_local = 0.2 + 0.6 * (lat_norm * lon_norm)
            
            # Simular valores con distribución normal más realista
            nitrogeno = max(0, rng.normal(
                n_optimo * (0.6 + 0.3 * variabilidad_local),
                n_optimo * 0.2
            ))
            
            fosforo = max(0, rng.normal(
                p_optimo * (0.5 + 0.4 * variabilidad_local),
                p_optimo * 0.25
            ))
            
            potasio = max(0, rng.normal(
                k_optimo * (0.55 + 0.35 * variabilidad_local),
                k_optimo * 0.22
            ))
            
            # Aplicar factores estacionales mejorados
            nitrogeno *= factor_n_mes * (0.8 + 0.3 * rng.random())
            fosforo *= factor_p_mes * (0.8 + 0.3 * rng.random())
            potasio *= factor_k_mes * (0.8 + 0.3 * rng.random())
            
            # Parámetros adicionales del suelo simulados
            materia_organica = max(1.0, min(8.0, rng.normal(
                params['MATERIA_ORGANICA_OPTIMA'] * 0.7,
                1.0
            )))
            
            humedad = max(0.1, min(0.8, rng.normal(
                params['HUMEDAD_OPTIMA'],
                0.1
            )))
            
            ph = max(4.0, min(8.0, rng.normal(
                params['pH_OPTIMO'],
                0.5
            )))
            
            conductividad = max(0.1, min(3.0, rng.normal(
                params['CONDUCTIVIDAD_OPTIMA'],
                0.3
            )))
            
            # NDVI con correlación con fertilidad
            base_ndvi = 0.3 + 0.5 * variabilidad_local
            ndvi = max(0.1, min(0.95, rng.normal(base_ndvi, 0.1)))
            
            # CÁLCULO DE NDWI DEL SUELO
            base_ndwi_suelo = params_ndwi['ndwi_optimo_suelo']
            
            # Ajustar por humedad del suelo
            ajuste_humedad = (humedad - 0.3) * 0.5
            
            # Ajustar por materia orgánica
            ajuste_mo = materia_organica * 0.02
            
            # Ajustar por textura
            ajuste_textura = variabilidad_local * 0.1
            
            # Cálculo del NDWI del suelo
            ndwi_suelo = base_ndwi_suelo + ajuste_humedad + ajuste_mo + ajuste_textura
            
            # Aplicar factor estacional
            ndwi_suelo *= factor_ndwi_mes
            
            # Agregar variabilidad aleatoria
            ndwi_suelo += rng.normal(0, 0.05)
            
            # Limitar valores entre -1 y 1
            ndwi_suelo = max(-1.0, min(1.0, ndwi_suelo))
            
            # Clasificar estado de humedad del suelo basado en NDWI
            if ndwi_suelo >= params_ndwi['ndwi_humedo_suelo']:
                estado_humedad = "MUY HÚMEDO"
            elif ndwi_suelo >= params_ndwi['ndwi_optimo_suelo']:
                estado_humedad = "ÓPTIMO"
            elif ndwi_suelo >= params_ndwi['umbral_sequia']:
                estado_humedad = "MODERADO"
            elif ndwi_suelo >= params_ndwi['ndwi_seco_suelo']:
                estado_humedad = "SECO"
            else:
                estado_humedad = "MUY SECO"
            
            # CÁLCULO MEJORADO DE ÍNDICE DE FERTILIDAD
            n_norm = max(0, min(1, nitrogeno / (n_optimo * 1.5)))
            p_norm = max(0, min(1, fosforo / (p_optimo * 1.5)))
            k_norm = max(0, min(1, potasio / (k_optimo * 1.5)))
            mo_norm = max(0, min(1, materia_organica / 8.0))
            ph_norm = max(0, min(1, 1 - abs(ph - params['pH_OPTIMO']) / 2.0))
            
            # Normalizar NDWI del suelo para índice de fertilidad
            ndwi_suelo_norm = (ndwi_suelo + 1) / 2
            
            # Índice compuesto mejorado
            indice_fertilidad = (
                n_norm * 0.22 +
                p_norm * 0.18 +
                k_norm * 0.18 +
                mo_norm * 0.15 +
                ph_norm * 0.10 +
                ndvi * 0.08 +
                ndwi_suelo_norm * 0.09
            ) * factor_mes
            
            indice_fertilidad = max(0, min(1, indice_fertilidad))
            
            # CATEGORIZACIÓN MEJORADA
            if indice_fertilidad >= 0.85:
                categoria = "EXCELENTE"
                prioridad = "BAJA"
            elif indice_fertilidad >= 0.70:
                categoria = "MUY ALTA"
                prioridad = "MEDIA-BAJA"
            elif indice_fertilidad >= 0.55:
                categoria = "ALTA"
                prioridad = "MEDIA"
            elif indice_fertilidad >= 0.40:
                categoria = "MEDIA"
                prioridad = "MEDIA-ALTA"
            elif indice_fertilidad >= 0.25:
                categoria = "BAJA"
                prioridad = "ALTA"
            else:
                categoria = "MUY BAJA"
                prioridad = "URGENTE"
            
            # CÁLCULO CORREGIDO DE RECOMENDACIONES NPK
            if nutriente == "NITRÓGENO":
                deficit_nitrogeno = max(0, n_optimo - nitrogeno)
                
                if deficit_nitrogeno <= 0:
                    deficit_nitrogeno = n_optimo * 0.3
                
                factor_eficiencia = 1.4
                factor_crecimiento = 1.2
                factor_materia_organica = max(0.7, 1.0 - (materia_organica / 15.0))
                factor_ndvi = 1.0 + (0.5 - ndvi) * 0.4
                
                recomendacion = (deficit_nitrogeno * factor_eficiencia * factor_crecimiento * 
                               factor_materia_organica * factor_ndvi)
                
                recomendacion = min(recomendacion, 250)
                recomendacion = max(20, recomendacion)
                
                deficit = max(0, n_optimo - nitrogeno)
                
            elif nutriente == "FÓSFORO":
                deficit_fosforo = max(0, p_optimo - fosforo)
                
                if deficit_fosforo <= 0:
                    deficit_fosforo = p_optimo * 0.2
                
                factor_eficiencia = 1.6
                factor_ph = 1.0
                if ph < 5.5 or ph > 7.5:
                    factor_ph = 1.3
                factor_materia_organica = 1.1
                
                recomendacion = (deficit_fosforo * factor_eficiencia * 
                               factor_ph * factor_materia_organica)
                
                recomendacion = min(recomendacion, 120)
                recomendacion = max(10, recomendacion)
                
                deficit = max(0, p_optimo - fosforo)
                
            else:  # POTASIO
                deficit_potasio = max(0, k_optimo - potasio)
                
                if deficit_potasio <= 0:
                    deficit_potasio = k_optimo * 0.15
                
                factor_eficiencia = 1.3
                factor_textura = 1.0
                if materia_organica < 2.0:
                    factor_textura = 1.2
                factor_rendimiento = 1.0 + (0.5 - ndvi) * 0.3
                
                recomendacion = (deficit_potasio * factor_eficiencia * 
                               factor_textura * factor_rendimiento)
                
                recomendacion = min(recomendacion, 200)
                recomendacion = max(15, recomendacion)
                
                deficit = max(0, k_optimo - potasio)
            
            # Ajuste final basado en la categoría de fertilidad
            if categoria in ["MUY BAJA", "BAJA"]:
                recomendacion *= 1.3
            elif categoria in ["ALTA", "MUY ALTA", "EXCELENTE"]:
                recomendacion *= 0.8
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'nitrogeno'] = nitrogeno
            zonas_gdf.loc[idx, 'fosforo'] = fosforo
            zonas_gdf.loc[idx, 'potasio'] = potasio
            zonas_gdf.loc[idx, 'materia_organica'] = materia_organica
            zonas_gdf.loc[idx, 'humedad'] = humedad
            zonas_gdf.loc[idx, 'ph'] = ph
            zonas_gdf.loc[idx, 'conductividad'] = conductividad
            zonas_gdf.loc[idx, 'ndvi'] = ndvi
            zonas_gdf.loc[idx, 'ndwi_suelo'] = ndwi_suelo
            zonas_gdf.loc[idx, 'estado_humedad_suelo'] = estado_humedad
            zonas_gdf.loc[idx, 'indice_fertilidad'] = indice_fertilidad
            zonas_gdf.loc[idx, 'categoria'] = categoria
            zonas_gdf.loc[idx, 'recomendacion_npk'] = recomendacion
            zonas_gdf.loc[idx, 'deficit_npk'] = deficit
            zonas_gdf.loc[idx, 'prioridad'] = prioridad
            
        except Exception as e:
            # Valores por defecto mejorados en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'nitrogeno'] = params['NITROGENO']['optimo'] * 0.7
            zonas_gdf.loc[idx, 'fosforo'] = params['FOSFORO']['optimo'] * 0.6
            zonas_gdf.loc[idx, 'potasio'] = params['POTASIO']['optimo'] * 0.65
            zonas_gdf.loc[idx, 'materia_organica'] = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
            zonas_gdf.loc[idx, 'humedad'] = params['HUMEDAD_OPTIMA']
            zonas_gdf.loc[idx, 'ph'] = params['pH_OPTIMO']
            zonas_gdf.loc[idx, 'conductividad'] = params['CONDUCTIVIDAD_OPTIMA']
            zonas_gdf.loc[idx, 'ndvi'] = 0.5
            zonas_gdf.loc[idx, 'ndwi_suelo'] = params_ndwi['ndwi_optimo_suelo']
            zonas_gdf.loc[idx, 'estado_humedad_suelo'] = "ÓPTIMO"
            zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.4
            zonas_gdf.loc[idx, 'categoria'] = "MEDIA"
            zonas_gdf.loc[idx, 'recomendacion_npk'] = 50
            zonas_gdf.loc[idx, 'deficit_npk'] = 20
            zonas_gdf.loc[idx, 'prioridad'] = "MEDIA"
    
    return zonas_gdf

def generar_dem_sintetico(gdf, resolucion=10.0):
    """Genera un DEM sintético basado en datos LiDAR simulados"""
    
    # Obtener bounds del polígono
    bounds = gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    
    # Convertir resolución de metros a grados (aproximadamente)
    resolucion_grados = resolucion / 111111
    
    # Crear malla de puntos
    x = np.arange(minx, maxx, resolucion_grados)
    y = np.arange(miny, maxy, resolucion_grados)
    
    if len(x) < 2 or len(y) < 2:
        resolucion_grados = (maxx - minx) / 10
        x = np.linspace(minx, maxx, 10)
        y = np.linspace(miny, maxy, 10)
    
    X, Y = np.meshgrid(x, y)
    
    # Generar elevaciones sintéticas con patrones realistas
    elevacion_base = np.random.uniform(100, 300)
    
    slope_x = np.random.uniform(-0.001, 0.001)
    slope_y = np.random.uniform(-0.001, 0.001)
    
    relief = np.zeros_like(X)
    
    n_hills = np.random.randint(2, 5)
    for _ in range(n_hills):
        hill_center_x = np.random.uniform(minx, maxx)
        hill_center_y = np.random.uniform(miny, maxy)
        hill_radius = np.random.uniform(0.001, 0.005)
        hill_height = np.random.uniform(10, 50)
        
        dist = np.sqrt((X - hill_center_x)**2 + (Y - hill_center_y)**2)
        relief += hill_height * np.exp(-(dist**2) / (2 * hill_radius**2))
    
    noise = np.random.randn(*X.shape) * 2
    
    Z = elevacion_base + slope_x * (X - minx) + slope_y * (Y - miny) + relief + noise
    
    Z = np.maximum(Z, 50)
    
    return X, Y, Z, bounds

def calcular_curvas_nivel(gdf, intervalo=5.0, resolucion=10.0):
    """Calcula curvas de nivel a partir de DEM sintético"""
    
    try:
        X, Y, Z, bounds = generar_dem_sintetico(gdf, resolucion)
        
        points = np.column_stack([X.flatten(), Y.flatten()])
        values = Z.flatten()
        
        grid_x, grid_y = np.mgrid[bounds[0]:bounds[2]:resolucion/111111, bounds[1]:bounds[3]:resolucion/111111]
        
        grid_z = griddata(points, values, (grid_x, grid_y), method='cubic')
        
        z_min, z_max = np.nanmin(grid_z), np.nanmax(grid_z)
        niveles = np.arange(np.floor(z_min/intervalo)*intervalo, np.ceil(z_max/intervalo)*intervalo, intervalo)
        
        dy, dx = np.gradient(grid_z, resolucion, resolucion)
        pendiente = np.sqrt(dx**2 + dy**2) * 100
        
        aspecto = np.arctan2(dy, dx) * 180 / np.pi
        aspecto = np.mod(aspecto + 360, 360)
        
        poligono_principal = gdf.iloc[0].geometry
        
        curvas_lineas = []
        
        Z_suavizado = gaussian_filter(grid_z, sigma=1)
        
        curvas_lineas = generar_curvas_directas_simplificado(grid_x, grid_y, Z_suavizado, niveles, poligono_principal)
        
        if curvas_lineas:
            gdf_curvas = gpd.GeoDataFrame({
                'id_curva': range(1, len(curvas_lineas) + 1),
                'geometry': curvas_lineas
            }, crs=gdf.crs)
            
            for idx in range(len(curvas_lineas)):
                if idx < len(niveles):
                    gdf_curvas.loc[idx, 'elevacion'] = round(niveles[idx], 1)
                else:
                    nivel_idx = int((idx / len(curvas_lineas)) * len(niveles))
                    if nivel_idx < len(niveles):
                        gdf_curvas.loc[idx, 'elevacion'] = round(niveles[nivel_idx], 1)
                    else:
                        gdf_curvas.loc[idx, 'elevacion'] = round(z_min + (idx * intervalo), 1)
        else:
            gdf_curvas = gpd.GeoDataFrame(columns=['id_curva', 'elevacion', 'geometry'], crs=gdf.crs)
        
        return gdf_curvas, grid_x, grid_y, grid_z, pendiente, aspecto, bounds
        
    except Exception as e:
        st.warning(f"⚠️ Error al calcular curvas de nivel: {str(e)}")
        
        X, Y, Z, bounds = generar_dem_sintetico(gdf, resolucion)
        
        gdf_curvas = gpd.GeoDataFrame(columns=['id_curva', 'elevacion', 'geometry'], crs=gdf.crs)
        
        pendiente = np.zeros_like(Z)
        aspecto = np.zeros_like(Z)
        
        return gdf_curvas, X, Y, Z, pendiente, aspecto, bounds

def generar_curvas_directas_simplificado(grid_x, grid_y, grid_z, niveles, poligono_principal):
    """Genera curvas de nivel simplificadas directamente desde el grid"""
    curvas = []
    
    try:
        centro = poligono_principal.centroid
        bounds = poligono_principal.bounds
        
        ancho = bounds[2] - bounds[0]
        alto = bounds[3] - bounds[1]
        radio_max = min(ancho, alto) / 2
        
        n_curvas = min(10, len(niveles))
        for i in range(1, n_curvas + 1):
            radio = radio_max * (i / n_curvas)
            
            circle = centro.buffer(radio)
            interseccion = poligono_principal.intersection(circle)
            
            if interseccion.geom_type == 'LineString':
                curvas.append(interseccion)
            elif interseccion.geom_type == 'MultiLineString':
                for parte in interseccion.geoms:
                    curvas.append(parte)
        
        if not curvas:
            for i in range(3):
                y = bounds[1] + (i + 1) * (alto / 4)
                linea = LineString([(bounds[0], y), (bounds[2], y)])
                if poligono_principal.intersects(linea):
                    interseccion = poligono_principal.intersection(linea)
                    if interseccion.geom_type == 'LineString':
                        curvas.append(interseccion)
            
            for i in range(3):
                x = bounds[0] + (i + 1) * (ancho / 4)
                linea = LineString([(x, bounds[1]), (x, bounds[3])])
                if poligono_principal.intersects(linea):
                    interseccion = poligono_principal.intersection(linea)
                    if interseccion.geom_type == 'LineString':
                        curvas.append(interseccion)
    
    except Exception as e:
        if hasattr(poligono_principal, 'exterior'):
            curvas.append(poligono_principal.exterior)
    
    return curvas

def crear_mapa_curvas_nivel(gdf_original, gdf_curvas, dem_data=None):
    """Crea mapa interactivo con curvas de nivel"""
    
    if gdf_original.empty:
        m = folium.Map(location=[0, 0], zoom_start=2)
        return m
    
    centroid = gdf_original.geometry.centroid.iloc[0]
    bounds = gdf_original.total_bounds
    
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
    )
    
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
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Relieve',
        overlay=False
    ).add_to(m)
    
    try:
        area_parcela = calcular_superficie(gdf_original)
    except Exception as e:
        area_parcela = 0.0
    
    folium.GeoJson(
        gdf_original.geometry.__geo_interface__,
        style_function=lambda x: {
            'fillColor': '#1f77b4',
            'color': '#2ca02c',
            'weight': 3,
            'fillOpacity': 0.3,
            'opacity': 0.8
        },
        popup=folium.Popup(f"Parcela - Área: {area_parcela:.2f} ha", max_width=300),
        tooltip="Parcela principal"
    ).add_to(m)
    
    if not gdf_curvas.empty and 'elevacion' in gdf_curvas.columns:
        for idx, row in gdf_curvas.iterrows():
            if dem_data is not None:
                grid_z = dem_data['grid_z']
                z_min, z_max = np.nanmin(grid_z), np.nanmax(grid_z)
                
                if z_max > z_min:
                    norm_elev = (row['elevacion'] - z_min) / (z_max - z_min)
                else:
                    norm_elev = 0.5
                
                colores = PALETAS_GEE['ELEVACION']
                color_idx = int(norm_elev * (len(colores) - 1))
                color = colores[color_idx]
                
                if row['elevacion'] % 25 == 0:
                    weight = 3
                elif row['elevacion'] % 5 == 0:
                    weight = 2
                else:
                    weight = 1
            else:
                color = '#00441b'
                weight = 1
            
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color, weight=weight: {
                    'color': color,
                    'weight': weight,
                    'fillOpacity': 0,
                    'opacity': 0.8
                },
                popup=folium.Popup(f"Curva de nivel {row['id_curva']}<br>Elevación: {row['elevacion']} m", max_width=200),
                tooltip=f"Elevación: {row['elevacion']} m"
            ).add_to(m)
    
    if dem_data is not None:
        grid_z = dem_data['grid_z']
        grid_x = dem_data['grid_x']
        grid_y = dem_data['grid_y']
        
        if not np.all(np.isnan(grid_z)):
            idx_max = np.unravel_index(np.nanargmax(grid_z), grid_z.shape)
            punto_alto = [grid_y[idx_max], grid_x[idx_max]]
            
            folium.Marker(
                punto_alto,
                icon=folium.DivIcon(
                    html='<div style="background-color: red; color: white; padding: 5px; border-radius: 50%;">▲</div>'
                ),
                popup=f"Punto más alto: {grid_z[idx_max]:.1f} m",
                tooltip="Punto más alto"
            ).add_to(m)
            
            idx_min = np.unravel_index(np.nanargmin(grid_z), grid_z.shape)
            punto_bajo = [grid_y[idx_min], grid_x[idx_min]]
            
            folium.Marker(
                punto_bajo,
                icon=folium.DivIcon(
                    html='<div style="background-color: blue; color: white; padding: 5px; border-radius: 50%;">▼</div>'
                ),
                popup=f"Punto más bajo: {grid_z[idx_min]:.1f} m",
                tooltip="Punto más bajo"
            ).add_to(m)
    
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    folium.LayerControl().add_to(m)
    plugins.MeasureControl(position='bottomleft', primary_length_unit='meters').add_to(m)
    plugins.MiniMap(toggle_display=True).add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 250px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius:5px;
                font-family: Arial;">
        <h4 style="margin:0 0 10px 0; text-align:center;">🏔️ Curvas de Nivel</h4>
        <p><b>Leyenda:</b></p>
        <p><i style="background:#1f77b4; width:20px; height:20px; display:inline-block; margin-right:5px; opacity:0.3;"></i> Área de parcela</p>
        <p><i style="background:#00441b; width:20px; height:2px; display:inline-block; margin-right:5px; opacity:0.8; vertical-align:middle;"></i> Curvas de nivel</p>
        <p><span style="background:red; color:white; width:20px; height:20px; display:inline-block; margin-right:5px; border-radius:50%; text-align:center; line-height:20px;">▲</span> Punto más alto</p>
        <p><span style="background:blue; color:white; width:20px; height:20px; display:inline-block; margin-right:5px; border-radius:50%; text-align:center; line-height:20px;">▼</span> Punto más bajo</p>
        <p style="margin-top:10px; font-size:10px; color:#666;">
            💡 Curvas más gruesas indican intervalos mayores (cada 25m)
        </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def crear_mapa_pendientes(grid_x, grid_y, pendiente_grid, gdf_original):
    """Crea mapa de calor de pendientes"""
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    X = grid_x.flatten()
    Y = grid_y.flatten()
    Z = pendiente_grid.flatten()
    
    from matplotlib.tri import Triangulation, LinearTriInterpolator
    
    valid_mask = ~np.isnan(Z)
    if np.sum(valid_mask) > 0:
        tri = Triangulation(X[valid_mask], Y[valid_mask])
        interpolator = LinearTriInterpolator(tri, Z[valid_mask])
        
        xi = np.linspace(X[valid_mask].min(), X[valid_mask].max(), 100)
        yi = np.linspace(Y[valid_mask].min(), Y[valid_mask].max(), 100)
        Xi, Yi = np.meshgrid(xi, yi)
        
        Zi = interpolator(Xi, Yi)
        
        cmap = LinearSegmentedColormap.from_list('pendiente_cmap', 
                                                [CLASIFICACION_PENDIENTES[c]['color'] for c in CLASIFICACION_PENDIENTES])
        
        heatmap = ax.contourf(Xi, Yi, Zi, levels=20, cmap=cmap, alpha=0.7)
        
        contours = ax.contour(Xi, Yi, Zi, levels=[2, 5, 10, 15, 25], colors='black', linewidths=0.5, alpha=0.5)
        ax.clabel(contours, inline=True, fontsize=8, fmt='%1.0f%%')
    
    gdf_original.plot(ax=ax, color='none', edgecolor='black', linewidth=2)
    
    ax.set_title('Mapa de Pendientes (%)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Longitud')
    ax.set_ylabel('Latitud')
    ax.grid(True, alpha=0.3)
    
    if 'heatmap' in locals():
        cbar = plt.colorbar(heatmap, ax=ax, shrink=0.8)
        cbar.set_label('Pendiente (%)', fontsize=10)
    
    patches = []
    for categoria, params in CLASIFICACION_PENDIENTES.items():
        patches.append(mpatches.Patch(color=params['color'], label=categoria))
    
    ax.legend(handles=patches, loc='upper left', fontsize=8, title='Categorías de Pendiente')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf

def procesar_archivo(uploaded_file):
    """Procesa el archivo ZIP con shapefile o archivo KML"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            if uploaded_file.name.lower().endswith('.kml'):
                gdf = gpd.read_file(file_path, driver='KML')
            else:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.endswith('.kml')]
                
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                elif kml_files:
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    gdf = gpd.read_file(kml_path, driver='KML')
                else:
                    st.error("❌ No se encontró archivo .shp o .kml en el ZIP")
                    return None
            
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def generar_informe_pdf(gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, gdf_textura=None):
    """Genera un informe PDF completo con los resultados del análisis"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkgreen,
        spaceAfter=30,
        alignment=1
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
    
    story = []
    
    story.append(Paragraph("INFORME DE ANÁLISIS AGRÍCOLA", title_style))
    story.append(Spacer(1, 20))
    
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
    
    story.append(Paragraph("ESTADÍSTICAS DEL ANÁLISIS", heading_style))
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        stats_data = [
            ["Estadística", "Valor"],
            ["Índice Fertilidad Promedio", f"{gdf_analisis['indice_fertilidad'].mean():.3f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"],
            ["Materia Orgánica Promedio (%)", f"{gdf_analisis['materia_organica'].mean():.1f}"],
            ["NDVI Promedio", f"{gdf_analisis['ndvi'].mean():.3f}"],
            ["NDWI Suelo Promedio", f"{gdf_analisis['ndwi_suelo'].mean():.3f}" if 'ndwi_suelo' in gdf_analisis.columns else "N/A"]
        ]
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        stats_data = [
            ["Estadística", "Valor"],
            ["Textura Predominante", gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "N/A"],
            ["Adecuación Promedio", f"{gdf_textura['adecuacion_textura'].mean():.1%}"],
            ["Arena Promedio (%)", f"{gdf_textura['arena'].mean():.1f}"],
            ["Limo Promedio (%)", f"{gdf_textura['limo'].mean():.1f}"],
            ["Arcilla Promedio (%)", f"{gdf_textura['arcilla'].mean():.1f}"],
            ["Agua Disponible Promedio (mm/m)", f"{gdf_textura['agua_disponible'].mean():.0f}"]
        ]
    elif analisis_tipo == "ANÁLISIS NDWI SUELO":
        stats_data = [
            ["Estadística", "Valor"],
            ["NDWI Suelo Promedio", f"{gdf_analisis['ndwi_suelo'].mean():.3f}"],
            ["Estado Humedad Predominante", gdf_analisis['estado_humedad_suelo'].mode()[0] if len(gdf_analisis) > 0 else "N/A"],
            ["Déficit Humedad Promedio", f"{gdf_analisis['deficit_humedad'].mean():.3f}"],
            ["Zonas con Riesgo Sequía", f"{len(gdf_analisis[gdf_analisis['riesgo_sequia'].isin(['ALTO', 'CRÍTICO'])])}/{len(gdf_analisis)}"]
        ]
    elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
        stats_data = [
            ["Estadística", "Valor"],
            ["Número de Curvas", f"{len(gdf_analisis)}"],
            ["Elevación Promedio (m)", f"{gdf_analisis['elevacion'].mean():.1f}"],
            ["Elevación Mínima (m)", f"{gdf_analisis['elevacion'].min():.1f}"],
            ["Elevación Máxima (m)", f"{gdf_analisis['elevacion'].max():.1f}"],
            ["Rango de Elevación (m)", f"{gdf_analisis['elevacion'].max() - gdf_analisis['elevacion'].min():.1f}"]
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
    
    story.append(PageBreak())
    story.append(Paragraph("MAPA DE ANÁLISIS", heading_style))
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'indice_fertilidad'
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        titulo_mapa = f"Textura del Suelo - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'textura_suelo'
        gdf_analisis = gdf_textura
    elif analisis_tipo == "ANÁLISIS NDWI SUELO":
        titulo_mapa = f"NDWI del Suelo - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'ndwi_suelo'
    elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
        titulo_mapa = f"Curvas de Nivel - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'elevacion'
    else:
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'recomendacion_npk'
    
    mapa_buffer = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    
    if mapa_buffer:
        try:
            mapa_buffer.seek(0)
            img = Image(mapa_buffer, width=6*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"Figura 1: {titulo_mapa}", normal_style))
        except Exception as e:
            story.append(Paragraph("Error al generar el mapa para el PDF", normal_style))
    
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("RESULTADOS POR ZONA (PRIMERAS 10 ZONAS)", heading_style))
    
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        columnas_tabla = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
        df_tabla = gdf_textura[columnas_tabla].head(10).copy()
    elif analisis_tipo == "ANÁLISIS NDWI SUELO":
        columnas_tabla = ['id_zona', 'area_ha', 'ndwi_suelo', 'estado_humedad_suelo', 'deficit_humedad', 'recomendacion_riego', 'riesgo_sequia']
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
        columnas_tabla = ['id_curva', 'elevacion']
        if 'longitud_m' in gdf_analisis.columns:
            columnas_tabla.append('longitud_m')
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    else:
        columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
        if analisis_tipo == "FERTILIDAD ACTUAL":
            columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica'])
        else:
            columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
        
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    
    if 'area_ha' in df_tabla.columns:
        df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
    elif analisis_tipo == "ANÁLISIS DE TEXTURA":
        df_tabla['adecuacion_textura'] = df_tabla['adecuacion_textura'].round(3)
        df_tabla['arena'] = df_tabla['arena'].round(1)
        df_tabla['limo'] = df_tabla['limo'].round(1)
        df_tabla['arcilla'] = df_tabla['arcilla'].round(1)
    elif analisis_tipo == "ANÁLISIS NDWI SUELO":
        df_tabla['ndwi_suelo'] = df_tabla['ndwi_suelo'].round(3)
        df_tabla['deficit_humedad'] = df_tabla['deficit_humedad'].round(3)
    elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
        df_tabla['elevacion'] = df_tabla['elevacion'].round(1)
        if 'longitud_m' in df_tabla.columns:
            df_tabla['longitud_m'] = df_tabla['longitud_m'].round(1)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    
    if 'nitrogeno' in df_tabla.columns:
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
    if 'fosforo' in df_tabla.columns:
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
    if 'potasio' in df_tabla.columns:
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
    if 'materia_organica' in df_tabla.columns:
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
    
    table_data = [df_tabla.columns.tolist()]
    for _, row in df_tabla.iterrows():
        table_data.append(row.tolist())
    
    zona_table = Table(table_data, colWidths=[0.5*inch] + [0.7*inch] * (len(columnas_tabla)-1))
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
    
    story.append(PageBreak())
    story.append(Paragraph("RECOMENDACIONES", heading_style))
    
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
        adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
        
        if adecuacion_promedio >= 0.8:
            enfoque = "ENFOQUE: MANTENIMIENTO - Textura adecuada"
        elif adecuacion_promedio >= 0.6:
            enfoque = "ENFOQUE: MEJORA MODERADA - Ajustes menores necesarios"
        else:
            enfoque = "ENFOQUE: MEJORA INTEGRAL - Enmiendas requeridas"
        
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        
        if textura_predominante in RECOMENDACIONES_TEXTURA:
            info_textura = RECOMENDACIONES_TEXTURA[textura_predominante]
            story.append(Paragraph(f"<b>Propiedades de {textura_predominante}:</b>", normal_style))
            for prop in info_textura['propiedades'][:3]:
                story.append(Paragraph(f"• {prop}", normal_style))
            
            story.append(Spacer(1, 5))
            story.append(Paragraph(f"<b>Manejo Recomendado:</b>", normal_style))
            for man in info_textura['manejo'][:3]:
                story.append(Paragraph(f"• {man}", normal_style))
    elif analisis_tipo == "ANÁLISIS NDWI SUELO":
        avg_ndwi = gdf_analisis['ndwi_suelo'].mean() if not gdf_analisis.empty else 0
        
        if avg_ndwi >= 0.15:
            enfoque = "ENFOQUE: CONSERVACIÓN - Humedad óptima detectada"
            recomendaciones = [
                "Mantener frecuencia actual de riego",
                "Implementar coberturas vivas para conservar humedad",
                "Monitorear semanalmente con sensores de humedad"
            ]
        elif avg_ndwi >= 0.0:
            enfoque = "ENFOQUE: AJUSTE MODERADO - Humedad moderada"
            recomendaciones = [
                "Incrementar riego en 15-20%",
                "Aplicar mulching (cobertura seca) entre plantas",
                "Programar riegos en horas de menor evaporación"
            ]
        else:
            enfoque = "ENFOQUE: INTERVENCIÓN URGENTE - Déficit de humedad"
            recomendaciones = [
                "Riego intensivo inmediato (30-40% más)",
                "Implementar riego por goteo o aspersión",
                "Aplicar polímeros retenedores de agua en raíces"
            ]
        
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        
        for rec in recomendaciones:
            story.append(Paragraph(f"• {rec}", normal_style))
    elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
        elevacion_promedio = gdf_analisis['elevacion'].mean() if not gdf_analisis.empty else 0
        rango_elevacion = gdf_analisis['elevacion'].max() - gdf_analisis['elevacion'].min() if not gdf_analisis.empty else 0
        
        if rango_elevacion < 20:
            enfoque = "ENFOQUE: TERRENO PLANO - Manejo convencional"
            recomendaciones = [
                "Diseño rectangular de plantación",
                "Sistemas de riego por gravedad",
                "Labranza convencional posible",
                "Maquinaria pesada sin restricciones"
            ]
        elif rango_elevacion < 50:
            enfoque = "ENFOQUE: LADERA SUAVE - Diseño en contorno"
            recomendaciones = [
                "Diseño en contorno ligero",
                "Surcos siguiendo curvas de nivel",
                "Labranza reducida recomendada",
                "Barreras vivas cada 50 metros"
            ]
        else:
            enfoque = "ENFOQUE: LADERA PRONUNCIADA - Terrazas y bancales"
            recomendaciones = [
                "Terrazas de base ancha",
                "Cultivos en franjas",
                "Barreras vivas cada 30 metros",
                "Sistemas de drenaje en contorno"
            ]
        
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        
        for rec in recomendaciones:
            story.append(Paragraph(f"• {rec}", normal_style))
    else:
        categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
        
        if categoria_promedio in ["MUY BAJA", "BAJA"]:
            enfoque = "ENFOQUE: RECUPERACIÓN Y REGENERACIÓN - Intensidad: Alta"
        elif categoria_promedio in ["MEDIA"]:
            enfoque = "ENFOQUE: MANTENIMIENTO Y MEJORA - Intensidad: Media"
        else:
            enfoque = "ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN - Intensidad: Baja"
        
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        
        recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
        
        for categoria_rec, items in recomendaciones.items():
            story.append(Paragraph(f"<b>{categoria_rec.replace('_', ' ').title()}:</b>", normal_style))
            for item in items[:2]:
                story.append(Paragraph(f"• {item}", normal_style))
            story.append(Spacer(1, 5))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN ADICIONAL", heading_style))
    story.append(Paragraph("Este informe fue generado automáticamente por el Sistema de Análisis Agrícola GEE.", normal_style))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer

def generar_informe_ndwi_pdf(gdf_ndwi, cultivo, mes_analisis, area_total):
    """Genera un informe PDF específico para análisis de NDWI del suelo"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=30,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0066cc'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    normal_style = styles['Normal']
    
    story = []
    
    story.append(Paragraph("INFORME DE ANÁLISIS NDWI DEL SUELO", title_style))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("INFORMACIÓN GENERAL", heading_style))
    info_data = [
        ["Cultivo:", cultivo.replace('_', ' ').title()],
        ["Análisis:", "NDWI del Suelo (Contenido de Agua)"],
        ["Mes de Análisis:", mes_analisis],
        ["Área Total:", f"{area_total:.2f} ha"],
        ["Fecha de Generación:", datetime.now().strftime("%d/%m/%Y %H:%M")]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f2ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.darkblue),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("ESTADÍSTICAS DEL NDWI DEL SUELO", heading_style))
    
    if not gdf_ndwi.empty:
        stats_data = [
            ["Estadística", "Valor"],
            ["NDWI Suelo Promedio", f"{gdf_ndwi['ndwi_suelo'].mean():.3f}"],
            ["Estado Humedad Predominante", gdf_ndwi['estado_humedad_suelo'].mode()[0] if len(gdf_ndwi) > 0 else "N/A"],
            ["Déficit Humedad Promedio", f"{gdf_ndwi['deficit_humedad'].mean():.3f}"],
            ["Zonas con Riesgo Sequía", f"{len(gdf_ndwi[gdf_ndwi['riesgo_sequia'].isin(['ALTO', 'CRÍTICO'])])}/{len(gdf_ndwi)}"],
            ["Recomendación Riego Predominante", gdf_ndwi['recomendacion_riego'].mode()[0] if len(gdf_ndwi) > 0 else "N/A"]
        ]
    else:
        stats_data = [["Estadística", "Valor"], ["Sin datos disponibles", "N/A"]]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
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
    
    story.append(Paragraph("INTERPRETACIÓN DE VALORES NDWI", heading_style))
    
    interpretacion_data = [
        ["Rango NDWI", "Estado del Suelo", "Interpretación", "Acción Recomendada"],
        ["0.2 a 1.0", "Muy Húmedo", "Contenido de agua excesivo", "Reducir riego, mejorar drenaje"],
        ["0.1 a 0.2", "Óptimo", "Humedad ideal para cultivo", "Mantener prácticas actuales"],
        ["0.0 a 0.1", "Moderado", "Humedad aceptable", "Monitorear, riego ligero si es necesario"],
        ["-0.1 a 0.0", "Seco", "Déficit de humedad", "Incrementar riego en 20-30%"],
        ["-1.0 a -0.1", "Muy Seco", "Riesgo de sequía", "Riego urgente, medidas de conservación"]
    ]
    
    interpretacion_table = Table(interpretacion_data, colWidths=[1*inch, 1.2*inch, 2*inch, 2*inch])
    interpretacion_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3399ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f8ff')])
    ]))
    story.append(interpretacion_table)
    story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    story.append(Paragraph("RECOMENDACIONES DE MANEJO DE AGUA", heading_style))
    
    avg_ndwi = gdf_ndwi['ndwi_suelo'].mean() if not gdf_ndwi.empty else 0
    
    if avg_ndwi >= 0.15:
        enfoque = "ENFOQUE: CONSERVACIÓN - Humedad óptima detectada"
        recomendaciones = [
            "Mantener frecuencia actual de riego",
            "Implementar coberturas vivas para conservar humedad",
            "Monitorear semanalmente con sensores de humedad",
            "Considerar riego deficitario controlado en épocas lluviosas"
        ]
    elif avg_ndwi >= 0.0:
        enfoque = "ENFOQUE: AJUSTE MODERADO - Humedad moderada"
        recomendaciones = [
            "Incrementar riego en 15-20%",
            "Aplicar mulching (cobertura seca) entre plantas",
            "Programar riegos en horas de menor evaporación",
            "Considerar riego por goteo para mayor eficiencia"
        ]
    else:
        enfoque = "ENFOQUE: INTERVENCIÓN URGENTE - Déficit de humedad"
        recomendaciones = [
            "Riego intensivo inmediato (30-40% más)",
            "Implementar riego por goteo o aspersión",
            "Aplicar polímeros retenedores de agua en raíces",
            "Reducir labranza para conservar humedad residual",
            "Considerar cultivos de cobertura para sombrear suelo"
        ]
    
    story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
    story.append(Spacer(1, 10))
    
    for rec in recomendaciones:
        story.append(Paragraph(f"• {rec}", normal_style))
    
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("RESULTADOS POR ZONA (PRIMERAS 10 ZONAS)", heading_style))
    
    if not gdf_ndwi.empty:
        columnas_tabla = ['id_zona', 'ndwi_suelo', 'estado_humedad_suelo', 'deficit_humedad', 'recomendacion_riego', 'riesgo_sequia']
        
        columnas_existentes = [col for col in columnas_tabla if col in gdf_ndwi.columns]
        df_tabla = gdf_ndwi[columnas_existentes].head(10).copy()
        
        if 'ndwi_suelo' in df_tabla.columns:
            df_tabla['ndwi_suelo'] = df_tabla['ndwi_suelo'].round(3)
        if 'deficit_humedad' in df_tabla.columns:
            df_tabla['deficit_humedad'] = df_tabla['deficit_humedad'].round(3)
        
        table_data = [df_tabla.columns.tolist()]
        for _, row in df_tabla.iterrows():
            table_data.append(row.tolist())
        
        zona_table = Table(table_data, colWidths=[0.6*inch] * len(columnas_existentes))
        zona_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3399ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f8ff')])
        ]))
        story.append(zona_table)
        
        if len(gdf_ndwi) > 10:
            story.append(Spacer(1, 5))
            story.append(Paragraph(f"* Mostrando 10 de {len(gdf_ndwi)} zonas totales", 
                                 ParagraphStyle('Small', parent=normal_style, fontSize=8)))
    else:
        story.append(Paragraph("No hay datos disponibles para mostrar", normal_style))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN TÉCNICA", heading_style))
    
    info_tecnica = [
        "Método: NDWI (Normalized Difference Water Index) del Suelo",
        "Fórmula: (SWIR1 - SWIR2) / (SWIR1 + SWIR2)",
        "Bandas Sentinel-2: B8A (NIR) y B11 (SWIR)",
        "Rango válido: -1.0 a 1.0",
        "Interpretación: Valores positivos indican mayor contenido de agua",
        "Resolución espacial: 20m (Sentinel-2)",
        "Actualización: Datos actualizados cada 5 días"
    ]
    
    for info in info_tecnica:
        story.append(Paragraph(f"• {info}", normal_style))
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("INFORME GENERADO AUTOMÁTICAMENTE - SISTEMA DE ANÁLISIS GEE", 
                         ParagraphStyle('Footer', parent=normal_style, fontSize=8, alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer

def mostrar_resultados_textura(cultivo, mes_analisis):
    """Muestra los resultados del análisis de textura"""
    if st.session_state.analisis_textura is None:
        st.warning("No hay datos de análisis de textura disponibles")
        return
    
    gdf_textura = st.session_state.analisis_textura
    area_total = st.session_state.area_total
    
    st.markdown("## 🏗️ ANÁLISIS DE TEXTURA DEL SUELO")
    
    if st.button("⬅️ Volver a Configuración", key="volver_textura"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    st.subheader("📊 Estadísticas del Análisis de Textura")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if 'textura_suelo' in gdf_textura.columns:
            textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "NO_DETERMINADA"
        else:
            textura_predominante = "NO_DETERMINADA"
        st.metric("🏗️ Textura Predominante", textura_predominante)
    with col2:
        if 'adecuacion_textura' in gdf_textura.columns:
            avg_adecuacion = gdf_textura['adecuacion_textura'].mean()
        else:
            avg_adecuacion = 0
        st.metric("📊 Adecuación Promedio", f"{avg_adecuacion:.1%}")
    with col3:
        if 'arena' in gdf_textura.columns:
            avg_arena = gdf_textura['arena'].mean()
        else:
            avg_arena = 0
        st.metric("🏖️ Arena Promedio", f"{avg_arena:.1f}%")
    with col4:
        if 'arcilla' in gdf_textura.columns:
            avg_arcilla = gdf_textura['arcilla'].mean()
        else:
            avg_arcilla = 0
        st.metric("🧱 Arcilla Promedio", f"{avg_arcilla:.1f}%")
    
    st.subheader("🔺 Composición Granulométrica Promedio")
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    
    if all(col in gdf_textura.columns for col in ['arena', 'limo', 'arcilla']):
        composicion = [
            gdf_textura['arena'].mean(),
            gdf_textura['limo'].mean(), 
            gdf_textura['arcilla'].mean()
        ]
        labels = ['Arena', 'Limo', 'Arcilla']
        colors_pie = ['#d8b365', '#f6e8c3', '#01665e']
        
        ax.pie(composicion, labels=labels, colors=colors_pie, autopct='%1.1f%%', startangle=90)
        ax.set_title('Composición Promedio del Suelo')
        
        st.pyplot(fig)
    
    st.subheader("📋 Distribución de Texturas del Suelo")
    if 'textura_suelo' in gdf_textura.columns:
        textura_dist = gdf_textura['textura_suelo'].value_counts()
        st.bar_chart(textura_dist)
    
    st.subheader("🗺️ Mapa de Texturas del Suelo")
    if 'textura_suelo' in gdf_textura.columns:
        mapa_textura = crear_mapa_interactivo_esri(
            gdf_textura, 
            f"Textura del Suelo - {cultivo.replace('_', ' ').title()}", 
            'textura_suelo', 
            "ANÁLISIS DE TEXTURA"
        )
        st_folium(mapa_textura, width=800, height=500)
    
    st.subheader("📋 Tabla de Resultados por Zona")
    if all(col in gdf_textura.columns for col in ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']):
        columnas_textura = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla', 'capacidad_campo', 'agua_disponible']
        
        columnas_existentes = [col for col in columnas_textura if col in gdf_textura.columns]
        df_textura = gdf_textura[columnas_existentes].copy()
        
        if 'area_ha' in df_textura.columns:
            df_textura['area_ha'] = df_textura['area_ha'].round(3)
        if 'arena' in df_textura.columns:
            df_textura['arena'] = df_textura['arena'].round(1)
        if 'limo' in df_textura.columns:
            df_textura['limo'] = df_textura['limo'].round(1)
        if 'arcilla' in df_textura.columns:
            df_textura['arcilla'] = df_textura['arcilla'].round(1)
        if 'capacidad_campo' in df_textura.columns:
            df_textura['capacidad_campo'] = df_textura['capacidad_campo'].round(1)
        if 'agua_disponible' in df_textura.columns:
            df_textura['agua_disponible'] = df_textura['agua_disponible'].round(1)
        
        st.dataframe(df_textura, use_container_width=True)
    
    if 'textura_suelo' in gdf_textura.columns:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
        if 'adecuacion_textura' in gdf_textura.columns:
            adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
        else:
            adecuacion_promedio = 0.5
        
        textura_data = {
            'textura_predominante': textura_predominante,
            'adecuacion_promedio': adecuacion_promedio
        }
        mostrar_recomendaciones_agroecologicas(
            cultivo, "", area_total, "ANÁLISIS DE TEXTURA", None, textura_data
        )
    
    st.markdown("### 💾 Descargar Resultados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if all(col in gdf_textura.columns for col in ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']):
            columnas_descarga = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
            df_descarga = gdf_textura[columnas_descarga].copy()
            df_descarga['area_ha'] = df_descarga['area_ha'].round(3)
            df_descarga['adecuacion_textura'] = df_descarga['adecuacion_textura'].round(3)
            df_descarga['arena'] = df_descarga['arena'].round(1)
            df_descarga['limo'] = df_descarga['limo'].round(1)
            df_descarga['arcilla'] = df_descarga['arcilla'].round(1)
            
            csv = df_descarga.to_csv(index=False)
            st.download_button(
                label="📥 Descargar Tabla CSV",
                data=csv,
                file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    with col2:
        geojson = gdf_textura.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_textura"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_textura, cultivo, "ANÁLISIS DE TEXTURA", "", mes_analisis, area_total, gdf_textura
                )
                
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def mostrar_resultados_ndwi_suelo(cultivo, mes_analisis):
    """Muestra los resultados del análisis de NDWI del suelo"""
    
    if st.session_state.gdf_analisis is None or 'ndwi_suelo' not in st.session_state.gdf_analisis.columns:
        with st.spinner("💧 Analizando NDWI del suelo..."):
            if st.session_state.gdf_zonas is not None:
                gdf_ndwi = analizar_ndwi_suelo(st.session_state.gdf_zonas, cultivo, mes_analisis)
                st.session_state.gdf_analisis = gdf_ndwi
            else:
                st.error("No hay datos de zonas disponibles")
                return
    else:
        gdf_ndwi = st.session_state.gdf_analisis
    
    area_total = st.session_state.area_total
    
    st.markdown("## 💧 ANÁLISIS DE NDWI DEL SUELO (CONTENIDO DE AGUA)")
    
    if st.button("⬅️ Volver a Configuración", key="volver_ndwi"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    with st.expander("📚 ¿Qué es el NDWI del suelo?", expanded=False):
        st.markdown("""
        **NDWI (Normalized Difference Water Index) del Suelo**:
        
        - **Propósito**: Detectar contenido de agua en el suelo, no en la vegetación
        - **Fórmula**: (SWIR1 - SWIR2) / (SWIR1 + SWIR2) o (NIR - SWIR) / (NIR + SWIR)
        - **Bandas utilizadas**: 
          - SWIR1 (1.57-1.65µm): Sensible al contenido de agua
          - SWIR2 (2.11-2.29µm): Sensible a la humedad del suelo
        - **Interpretación**:
          - Valores altos (> 0.2): Suelo húmedo/óptimo
          - Valores medios (0.0 - 0.2): Humedad moderada
          - Valores bajos (< 0.0): Suelo seco
          - Valores muy bajos (< -0.1): Riesgo de sequía
        
        **Diferencia con NDVI**:
        - NDVI: Mide salud de vegetación (usa rojo e infrarrojo cercano)
        - NDWI suelo: Mide humedad del suelo (usa infrarrojo de onda corta)
        """)
    
    st.subheader("📊 Estadísticas del NDWI del Suelo")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if 'ndwi_suelo' in gdf_ndwi.columns:
            avg_ndwi = gdf_ndwi['ndwi_suelo'].mean()
        else:
            avg_ndwi = 0
        st.metric("💧 NDWI Suelo Promedio", f"{avg_ndwi:.3f}")
    with col2:
        if 'estado_humedad_suelo' in gdf_ndwi.columns:
            estado_predominante = gdf_ndwi['estado_humedad_suelo'].mode()[0] if len(gdf_ndwi) > 0 else "N/A"
        else:
            estado_predominante = "N/A"
        st.metric("🌡️ Estado Predominante", estado_predominante)
    with col3:
        if 'riesgo_sequia' in gdf_ndwi.columns:
            zonas_sequia = len(gdf_ndwi[gdf_ndwi['riesgo_sequia'].isin(['ALTO', 'CRÍTICO'])])
            total_zonas = len(gdf_ndwi)
        else:
            zonas_sequia = 0
            total_zonas = 0
        st.metric("⚠️ Zonas con Riesgo Sequía", f"{zonas_sequia}/{total_zonas}")
    with col4:
        if 'deficit_humedad' in gdf_ndwi.columns:
            deficit_promedio = gdf_ndwi['deficit_humedad'].mean()
        else:
            deficit_promedio = 0
        st.metric("📉 Déficit Humedad Promedio", f"{deficit_promedio:.3f}")
    
    st.subheader("📋 Distribución de Estados de Humedad")
    if 'estado_humedad_suelo' in gdf_ndwi.columns:
        estado_dist = gdf_ndwi['estado_humedad_suelo'].value_counts()
        st.bar_chart(estado_dist)
    
    st.subheader("🗺️ Mapa de NDWI del Suelo")
    
    if 'area_ha' not in gdf_ndwi.columns:
        gdf_ndwi['area_ha'] = [calcular_superficie(gdf_ndwi.iloc[[idx]]) for idx in range(len(gdf_ndwi))]
    
    if 'ndwi_suelo' in gdf_ndwi.columns:
        mapa_ndwi = crear_mapa_interactivo_esri(
            gdf_ndwi, 
            f"NDWI del Suelo - {cultivo.replace('_', ' ').title()}", 
            'ndwi_suelo', 
            "ANÁLISIS NDWI SUELO"
        )
        st_folium(mapa_ndwi, width=800, height=500)
    
    st.subheader("📋 Tabla de Resultados por Zona")
    
    columnas_ndwi = ['id_zona', 'area_ha', 'ndwi_suelo', 'estado_humedad_suelo', 
                    'deficit_humedad', 'recomendacion_riego', 'riesgo_sequia']
    
    columnas_existentes = [col for col in columnas_ndwi if col in gdf_ndwi.columns]
    df_ndwi = gdf_ndwi[columnas_existentes].copy()
    
    if 'area_ha' in df_ndwi.columns:
        df_ndwi['area_ha'] = df_ndwi['area_ha'].round(3)
    if 'ndwi_suelo' in df_ndwi.columns:
        df_ndwi['ndwi_suelo'] = df_ndwi['ndwi_suelo'].round(3)
    if 'deficit_humedad' in df_ndwi.columns:
        df_ndwi['deficit_humedad'] = df_ndwi['deficit_humedad'].round(3)
    
    st.dataframe(df_ndwi, use_container_width=True)
    
    st.markdown("### 💡 RECOMENDACIONES DE MANEJO DE AGUA")
    
    if 'ndwi_suelo' in gdf_ndwi.columns:
        avg_ndwi = gdf_ndwi['ndwi_suelo'].mean()
        params_ndwi = PARAMETROS_NDWI_SUELO[cultivo]
        
        if avg_ndwi >= params_ndwi['ndwi_optimo_suelo']:
            st.success("✅ **ESTADO GENERAL: ÓPTIMO** - El contenido de agua en el suelo es adecuado")
            st.markdown("""
            **Acciones recomendadas:**
            - Mantener prácticas actuales de riego
            - Monitorear semanalmente el NDWI
            - Implementar coberturas para conservar humedad
            """)
        elif avg_ndwi >= params_ndwi['umbral_sequia']:
            st.warning("⚠️ **ESTADO GENERAL: ATENCIÓN** - Humedad del suelo moderada")
            st.markdown("""
            **Acciones recomendadas:**
            - Incrementar frecuencia de riego en 20%
            - Aplicar mulching (cobertura seca)
            - Considerar riego por goteo para eficiencia
            - Monitorear cada 3-4 días
            """)
        else:
            st.error("🚨 **ESTADO GENERAL: CRÍTICO** - Déficit de humedad en el suelo")
            st.markdown("""
            **Acciones urgentes:**
            - Riego intensivo inmediato
            - Implementar riego por goteo o aspersión
            - Aplicar polímeros retenedores de agua
            - Reducir labranza para conservar humedad
            - Monitorear diariamente
            """)
    
    if st.session_state.analisis_textura is not None:
        st.markdown("### 🏗️ RECOMENDACIONES POR TIPO DE TEXTURA")
        
        gdf_textura = st.session_state.analisis_textura
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
        
        recomendaciones_riego_por_textura = {
            'Arcilloso': [
                "Riegos menos frecuentes pero más profundos",
                "Evitar riegos superficiales que causen encharcamiento",
                "Intervalo entre riegos: 7-10 días en época seca",
                "Monitorear drenaje para evitar saturación"
            ],
            'Franco Arcilloso': [
                "Riegos cada 5-7 días en época seca",
                "Aplicar 25-30 mm por riego",
                "Implementar riego por surcos o goteo",
                "Usar tensiómetros para programación"
            ],
            'Franco': [
                "Riegos cada 4-6 días en época seca",
                "Aplicar 20-25 mm por riego",
                "Ideal para riego por aspersión",
                "Buena respuesta a riego deficitario controlado"
            ],
            'Franco Arcilloso-Arenoso': [
                "Riegos frecuentes (cada 2-4 días)",
                "Aplicar 15-20 mm por riego",
                "Riego por goteo recomendado",
                "Considerar polímeros retenedores de agua"
            ],
            'Arenoso': [
                "Riegos diarios o cada 2 días",
                "Aplicar 10-15 mm por riego",
                "Riego por goteo obligatorio",
                "Aplicar materia orgánica para retención",
                "Considerar cultivos tolerantes a sequía"
            ]
        }
        
        if textura_predominante in recomendaciones_riego_por_textura:
            st.info(f"**Textura Predominante: {textura_predominante}**")
            for rec in recomendaciones_riego_por_textura[textura_predominante]:
                st.markdown(f"• {rec}")
    
    st.markdown("### 💾 Descargar Resultados NDWI")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if len(df_ndwi.columns) > 0:
            csv = df_ndwi.to_csv(index=False)
            st.download_button(
                label="📥 Descargar Tabla CSV",
                data=csv,
                file_name=f"ndwi_suelo_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    with col2:
        geojson = gdf_ndwi.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"ndwi_suelo_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    
    with col3:
        if st.button("📄 Generar Informe NDWI PDF", type="primary", key="pdf_ndwi"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_ndwi_pdf(gdf_ndwi, cultivo, mes_analisis, area_total)
                
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_ndwi_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def mostrar_resultados_curvas_nivel(cultivo, mes_analisis, intervalo_curvas=5.0, resolucion_dem=10.0):
    """Muestra resultados del análisis de curvas de nivel"""
    
    if st.session_state.curvas_nivel is None or st.session_state.dem_data is None:
        st.warning("No hay datos de curvas de nivel disponibles")
        return
    
    gdf_curvas = st.session_state.curvas_nivel
    dem_data = st.session_state.dem_data
    area_total = st.session_state.area_total
    
    st.markdown("## 🏔️ ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)")
    
    if st.button("⬅️ Volver a Configuración", key="volver_curvas"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    with st.expander("📚 ¿Qué son las curvas de nivel?", expanded=False):
        st.markdown("""
        **Curvas de nivel (Líneas de contorno)**:
        
        - **Definición**: Líneas que conectan puntos de igual elevación sobre el nivel del mar
        - **Fuente de datos**: LiDAR (Light Detection and Ranging) o Modelos Digitales de Elevación (DEM)
        - **Resolución típica LiDAR**: 1-5 puntos/m²
        - **Precisión vertical**: 10-20 cm
        - **Aplicaciones en agricultura**:
          - Diseño de sistemas de riego y drenaje
          - Prevención de erosión
          - Planificación de terrazas y bancales
          - Diseño de caminos y accesos
          - Identificación de zonas de acumulación de agua
        
        **Interpretación**:
        - Curvas muy juntas = Pendientes pronunciadas
        - Curvas separadas = Terreno plano
        - Curvas en forma de V = Valles (apuntan hacia arriba)
        - Curvas en forma de U = Crestas (apuntan hacia abajo)
        """)
    
    st.subheader("📊 Estadísticas Topográficas")
    
    grid_z = dem_data['grid_z']
    pendiente_grid = dem_data['pendiente_grid']
    
    elevaciones = grid_z.flatten()
    elevaciones = elevaciones[~np.isnan(elevaciones)]
    
    if len(elevaciones) > 0:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            elevacion_promedio = np.mean(elevaciones)
            st.metric("🏔️ Elevación Promedio", f"{elevacion_promedio:.1f} m")
        with col2:
            rango_elevacion = np.max(elevaciones) - np.min(elevaciones)
            st.metric("📏 Rango de Elevación", f"{rango_elevacion:.1f} m")
        with col3:
            stats_pendiente = calcular_estadisticas_pendiente(pendiente_grid)
            st.metric("📐 Pendiente Promedio", f"{stats_pendiente['promedio']:.1f}%")
        with col4:
            num_curvas = len(gdf_curvas) if not gdf_curvas.empty else 0
            st.metric("🔄 Número de Curvas", f"{num_curvas}")
    
    st.subheader("🗺️ Mapa de Curvas de Nivel")
    
    if not gdf_curvas.empty:
        mapa_curvas = crear_mapa_curvas_nivel(st.session_state.gdf_original, gdf_curvas, dem_data)
        st_folium(mapa_curvas, width=800, height=500)
    else:
        st.warning("No se pudieron generar curvas de nivel para esta parcela")
    
    st.subheader("📈 Distribución de Pendientes")
    
    if 'pendiente_grid' in dem_data:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        pendiente_flat = pendiente_grid.flatten()
        pendiente_flat = pendiente_flat[~np.isnan(pendiente_flat)]
        
        if len(pendiente_flat) > 0:
            ax1.hist(pendiente_flat, bins=30, edgecolor='black', color='#74c476', alpha=0.7)
            ax1.axvline(x=stats_pendiente['promedio'], color='red', linestyle='--', label=f'Promedio: {stats_pendiente["promedio"]:.1f}%')
            ax1.set_xlabel('Pendiente (%)')
            ax1.set_ylabel('Frecuencia')
            ax1.set_title('Distribución de Pendientes')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            if stats_pendiente['distribucion']:
                categorias = []
                porcentajes = []
                colores = []
                
                for cat, data in stats_pendiente['distribucion'].items():
                    if data['porcentaje'] > 0:
                        categorias.append(cat.split(' ')[0])
                        porcentajes.append(data['porcentaje'])
                        colores.append(data['color'])
                
                if porcentajes:
                    ax2.pie(porcentajes, labels=categorias, colors=colores, autopct='%1.1f%%', startangle=90)
                    ax2.set_title('Distribución por Categoría de Pendiente')
        
        plt.tight_layout()
        st.pyplot(fig)
    
    st.subheader("🗺️ Mapa de Pendientes (Heatmap)")
    
    if all(key in dem_data for key in ['grid_x', 'grid_y', 'pendiente_grid']):
        mapa_pendientes = crear_mapa_pendientes(
            dem_data['grid_x'], 
            dem_data['grid_y'], 
            dem_data['pendiente_grid'], 
            st.session_state.gdf_original
        )
        if mapa_pendientes:
            st.image(mapa_pendientes, caption='Mapa de Pendientes', use_column_width=True)
    
    st.subheader("⚠️ Análisis de Riesgo de Erosión")
    
    if 'pendiente_grid' in dem_data and stats_pendiente['distribucion']:
        riesgo_total = 0
        for categoria, data in stats_pendiente['distribucion'].items():
            if categoria in CLASIFICACION_PENDIENTES:
                riesgo_total += data['porcentaje'] * CLASIFICACION_PENDIENTES[categoria]['factor_erosivo']
        
        riesgo_promedio = riesgo_total / 100
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if riesgo_promedio < 0.3:
                st.success("✅ **RIESGO BAJO**")
                st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
            elif riesgo_promedio < 0.6:
                st.warning("⚠️ **RIESGO MODERADO**")
                st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
            else:
                st.error("🚨 **RIESGO ALTO**")
                st.metric("Factor Riesgo", f"{riesgo_promedio:.2f}")
        
        with col2:
            area_critica = sum(data['area_ha'] for cat, data in stats_pendiente['distribucion'].items() 
                             if cat in ['FUERTE (10-15%)', 'MUY FUERTE (15-25%)', 'EXTREMA (>25%)'])
            st.metric("Área Crítica (>10%)", f"{area_critica:.2f} ha")
        
        with col3:
            area_manejable = sum(data['area_ha'] for cat, data in stats_pendiente['distribucion'].items() 
                               if cat in ['PLANA (0-2%)', 'SUAVE (2-5%)', 'MODERADA (5-10%)'])
            st.metric("Área Manejable (<10%)", f"{area_manejable:.2f} ha")
    
    st.markdown("### 💡 RECOMENDACIONES DE MANEJO POR PENDIENTE")
    
    if 'distribucion' in stats_pendiente:
        cat_predominante = max(stats_pendiente['distribucion'].items(), key=lambda x: x[1]['porcentaje'])[0]
        
        if cat_predominante in RECOMENDACIONES_PENDIENTES:
            st.info(f"**Categoría Predominante: {cat_predominante}**")
            for rec in RECOMENDACIONES_PENDIENTES[cat_predominante]:
                st.markdown(f"• {rec}")
        
        st.markdown(f"#### 🌱 Recomendaciones Específicas para {cultivo.replace('_', ' ').title()}")
        
        recomendaciones_especificas = {
            'PALMA_ACEITERA': [
                "En pendientes < 10%: diseño triangular 9×9×9 m",
                "En pendientes 10-15%: terrazas individuales por palma",
                "En pendientes > 15%: considerar otras áreas o sistemas agroforestales",
                "Drenajes en contorno cada 50-100 m según pendiente",
                "Barreras vivas con leguminosas entre hileras"
            ],
            'CACAO': [
                "Pendientes < 15%: ideal para sistemas agroforestales",
                "Pendientes 15-25%: terrazas con barreras vivas",
                "Pendientes > 25%: cacao bajo sombra de bosque secundario",
                "Árboles de sombra (Erythrina, Inga) en curvas de nivel",
                "Sistemas de drenaje en V invertida"
            ],
            'BANANO': [
                "Pendientes < 10%: diseño rectangular 3×3 m",
                "Pendientes 10-15%: hileras en contorno con drenaje en zig-zag",
                "Pendientes > 15%: no recomendado por riesgo de vuelco",
                "Sistemas de riego por goteo siguiendo curvas de nivel",
                "Barreras con vetiver o caña everygreen"
            ]
        }
        
        if cultivo in recomendaciones_especificas:
            for rec in recomendaciones_especificas[cultivo]:
                st.markdown(f"• {rec}")
    
    st.subheader("📋 Tabla de Curvas de Nivel")
    
    if not gdf_curvas.empty and 'elevacion' in gdf_curvas.columns:
        gdf_curvas_proj = gdf_curvas.to_crs('EPSG:3116')
        gdf_curvas['longitud_m'] = gdf_curvas_proj.geometry.length
        
        df_curvas = gdf_curvas[['id_curva', 'elevacion', 'longitud_m']].copy()
        df_curvas['longitud_m'] = df_curvas['longitud_m'].round(1)
        
        df_curvas = df_curvas.sort_values('elevacion')
        
        intervalos = [0, 100, 200, 300, 400, 500]
        df_intervalos = pd.DataFrame()
        
        for i in range(len(intervalos)-1):
            mask = (df_curvas['elevacion'] >= intervalos[i]) & (df_curvas['elevacion'] < intervalos[i+1])
            if mask.any():
                df_intervalos = pd.concat([df_intervalos, pd.DataFrame({
                    'Intervalo (m)': f"{intervalos[i]}-{intervalos[i+1]}",
                    'N° Curvas': df_curvas[mask].shape[0],
                    'Longitud Total (m)': df_curvas[mask]['longitud_m'].sum().round(1),
                    'Elevación Promedio (m)': df_curvas[mask]['elevacion'].mean().round(1)
                }, index=[0])])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Curvas de Nivel**")
            st.dataframe(df_curvas.head(10), use_container_width=True)
            if len(df_curvas) > 10:
                st.caption(f"Mostrando 10 de {len(df_curvas)} curvas")
        
        with col2:
            st.markdown("**Estadísticas por Intervalo**")
            st.dataframe(df_intervalos, use_container_width=True)
    
    st.markdown("### 💾 Descargar Resultados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not gdf_curvas.empty:
            geojson = gdf_curvas.to_json()
            st.download_button(
                label="🗺️ Descargar Curvas (GeoJSON)",
                data=geojson,
                file_name=f"curvas_nivel_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
                mime="application/json"
            )
    
    with col2:
        if dem_data and 'grid_z' in dem_data:
            sample_points = []
            grid_x = dem_data['grid_x']
            grid_y = dem_data['grid_y']
            grid_z = dem_data['grid_z']
            
            for i in range(0, grid_x.shape[0], 5):
                for j in range(0, grid_x.shape[1], 5):
                    if not np.isnan(grid_z[i, j]):
                        sample_points.append({
                            'lat': grid_y[i, j],
                            'lon': grid_x[i, j],
                            'elevacion_m': grid_z[i, j],
                            'pendiente_%': dem_data['pendiente_grid'][i, j] if 'pendiente_grid' in dem_data else None
                        })
            
            if sample_points:
                df_dem = pd.DataFrame(sample_points)
                csv = df_dem.to_csv(index=False)
                st.download_button(
                    label="📊 Descargar Muestras DEM (CSV)",
                    data=csv,
                    file_name=f"dem_muestras_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
    
    with col3:
        if st.button("📄 Generar Informe Curvas PDF", type="primary", key="pdf_curvas"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_curvas, cultivo, "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)", None, mes_analisis, area_total, None
                )
                
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_curvas_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def ejecutar_analisis_curvas_nivel(gdf_original, intervalo=5.0, resolucion=10.0):
    """Ejecuta el análisis completo de curvas de nivel"""
    
    with st.spinner("🔄 Generando modelo digital de elevación (DEM)..."):
        gdf_curvas, grid_x, grid_y, grid_z, pendiente_grid, aspecto_grid, bounds = calcular_curvas_nivel(
            gdf_original, intervalo, resolucion
        )
    
    st.session_state.curvas_nivel = gdf_curvas
    st.session_state.dem_data = {
        'grid_x': grid_x,
        'grid_y': grid_y,
        'grid_z': grid_z,
        'pendiente_grid': pendiente_grid,
        'aspecto_grid': aspecto_grid,
        'bounds': bounds
    }
    
    return gdf_curvas

def mostrar_resultados_principales(cultivo, analisis_tipo, nutriente, mes_analisis):
    """Muestra los resultados del análisis principal"""
    gdf_analisis = st.session_state.gdf_analisis
    area_total = st.session_state.area_total

    if analisis_tipo not in ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"]:
        st.warning("⚠️ El análisis principal no está disponible para este tipo de análisis.")
        st.write("Use las pestañas específicas: **Análisis de Textura**, **NDWI del Suelo** o **Curvas de Nivel**.")
        return

    st.markdown("## 📈 RESULTADOS DEL ANÁLISIS PRINCIPAL")
    if st.button("⬅️ Volver a Configuración", key="volver_principal"):
        st.session_state.analisis_completado = False
        st.rerun()
    
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
        
        col5, col6, col7 = st.columns(3)
        with col5:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("🌱 Materia Orgánica Promedio", f"{avg_mo:.1f}%")
        with col6:
            avg_ndvi = gdf_analisis['ndvi'].mean()
            st.metric("📡 NDVI Promedio", f"{avg_ndvi:.3f}")
        with col7:
            if 'ndwi_suelo' in gdf_analisis.columns:
                avg_ndwi = gdf_analisis['ndwi_suelo'].mean()
                st.metric("💧 NDWI Suelo Promedio", f"{avg_ndwi:.3f}")
            else:
                zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
                st.metric("🎯 Prioridad Predominante", zona_prioridad)
        
        st.subheader("📋 Distribución de Categorías de Fertilidad")
        cat_dist = gdf_analisis['categoria'].value_counts()
        st.bar_chart(cat_dist)
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_rec = gdf_analisis['recomendacion_npk'].mean()
            st.metric(f"💡 Recomendación {nutriente} Promedio", f"{avg_rec:.1f} kg/ha")
        with col2:
            total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
            st.metric(f"📦 Total {nutriente} Requerido", f"{total_rec:.1f} kg")
        with col3:
            zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
            st.metric("🎯 Prioridad Aplicación", zona_prioridad)
        
        st.subheader("🌿 Estado Actual de Nutrientes")
        col_n, col_p, col_k, col_mo = st.columns(4)
        with col_n:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("Nitrógeno", f"{avg_n:.1f} kg/ha")
        with col_p:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("Fósforo", f"{avg_p:.1f} kg/ha")
        with col_k:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("Potasio", f"{avg_k:.1f} kg/ha")
        with col_mo:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("Materia Orgánica", f"{avg_mo:.1f}%")
    
    st.markdown("### 🗺️ Mapas de Análisis")
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columna_visualizar = 'indice_fertilidad'
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
    else:
        columna_visualizar = 'recomendacion_npk'
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
    
    mapa_analisis = crear_mapa_interactivo_esri(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    st_folium(mapa_analisis, width=800, height=500)
    
    st.markdown("### 📄 Mapa para Reporte")
    mapa_estatico = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_estatico:
        st.image(mapa_estatico, caption=titulo_mapa, use_column_width=True)
    
    st.markdown("### 📋 Tabla de Resultados por Zona")
    
    columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica', 'ndvi'])
        if 'ndwi_suelo' in gdf_analisis.columns:
            columnas_tabla.extend(['ndwi_suelo', 'estado_humedad_suelo'])
    else:
        columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
    
    df_tabla = gdf_analisis[columnas_tabla].copy()
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
        df_tabla['ndvi'] = df_tabla['ndvi'].round(3)
        if 'ndwi_suelo' in df_tabla.columns:
            df_tabla['ndwi_suelo'] = df_tabla['ndwi_suelo'].round(3)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    
    st.dataframe(df_tabla, use_container_width=True)
    
    categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
    mostrar_recomendaciones_agroecologicas(
        cultivo, categoria_promedio, area_total, analisis_tipo, nutriente
    )
    
    st.markdown("### 💾 Descargar Resultados")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = df_tabla.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"resultados_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col2:
        geojson = gdf_analisis.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"zonas_analisis_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_principal"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, st.session_state.analisis_textura
                )
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def mostrar_configuracion_parcela(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, intervalo_curvas=5.0, resolucion_dem=10.0):
    """Muestra la configuración de la parcela antes del análisis"""
    gdf_original = st.session_state.gdf_original
    
    if st.session_state.datos_demo:
        st.success("✅ Datos de demostración cargados")
    else:
        st.success("✅ Parcela cargada correctamente")
    
    area_total = calcular_superficie(gdf_original)
    num_poligonos = len(gdf_original)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Número de Polígonos", num_poligonos)
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    
    st.markdown("### 🗺️ Visualizador de Parcela")
    
    mapa_parcela = crear_mapa_visualizador_parcela(gdf_original)
    st_folium(mapa_parcela, width=800, height=500)
    
    st.markdown("### 📊 División en Zonas de Manejo")
    st.info(f"La parcela se dividirá en **{n_divisiones} zonas** para análisis detallado")
    
    if st.button("🚀 Ejecutar Análisis GEE Completo", type="primary"):
        with st.spinner("🔄 Dividiendo parcela en zonas..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            st.session_state.gdf_zonas = gdf_zonas
        
        with st.spinner("🔬 Realizando análisis GEE..."):
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                gdf_analisis = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_analisis
                st.session_state.gdf_analisis = gdf_analisis
            elif analisis_tipo == "ANÁLISIS NDWI SUELO":
                gdf_analisis = analizar_ndwi_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.gdf_analisis = gdf_analisis
            elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
                gdf_analisis = ejecutar_analisis_curvas_nivel(gdf_original, intervalo_curvas, resolucion_dem)
                st.session_state.gdf_analisis = gdf_analisis
            else:
                gdf_analisis = calcular_indices_gee(
                    gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente
                )
                st.session_state.gdf_analisis = gdf_analisis
            
            if analisis_tipo not in ["ANÁLISIS DE TEXTURA", "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)"]:
                with st.spinner("🏗️ Realizando análisis de textura..."):
                    gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                    st.session_state.analisis_textura = gdf_textura
            
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
        
        st.rerun()

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
    
    **NUEVO: Análisis de Curvas de Nivel (LiDAR/DEM)**
    - Generación de modelo digital de elevación
    - Cálculo automático de curvas de nivel
    - Análisis de pendientes y riesgo de erosión
    - Recomendaciones específicas por topografía
    """)
    
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        st.session_state.datos_demo = True
        st.rerun()

# ========== FUNCIÓN PRINCIPAL ==========
def main():
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        cultivo = st.selectbox("Cultivo:", 
                              ["PALMA_ACEITERA", "CACAO", "BANANO"])
        
        analisis_tipo = st.selectbox("Tipo de Análisis:", 
                                   ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA", 
                                    "ANÁLISIS NDWI SUELO", "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)"])
        
        if analisis_tipo not in ["ANÁLISIS DE TEXTURA", "ANÁLISIS NDWI SUELO", "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)"]:
            nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
        else:
            nutriente = None
        
        mes_analisis = st.selectbox("Mes de Análisis:", 
                                   ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                                    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
        
        st.subheader("🎯 División de Parcela")
        n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=32, value=24)
        
        intervalo_curvas = 5.0
        resolucion_dem = 10.0
        if analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
            st.subheader("🏔️ Configuración Curvas de Nivel")
            intervalo_curvas = st.slider("Intervalo entre curvas (metros):", 1.0, 20.0, 5.0, 1.0)
            resolucion_dem = st.slider("Resolución DEM (metros):", 5.0, 50.0, 10.0, 5.0)
        
        st.subheader("📤 Subir Parcela")
        uploaded_file = st.file_uploader("Subir ZIP con shapefile o archivo KML de tu parcela", type=['zip', 'kml'])
        
        if st.button("🔄 Reiniciar Análisis"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Métodología GEE")
    st.sidebar.info("""
    Esta aplicación utiliza:
    - **Google Earth Engine** para análisis satelital
    - **Índices espectrales** (NDVI, NDBI, etc.)
    - **Modelos predictivos** de nutrientes
    - **Análisis de textura** del suelo actualizado
    - **NDWI del suelo** para contenido de agua
    - **LiDAR/DEM** para curvas de nivel
    - **Enfoque agroecológico** integrado
    """)
    
    # Inicializar session_state si no existe
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
    if 'curvas_nivel' not in st.session_state:
        st.session_state.curvas_nivel = None
    if 'dem_data' not in st.session_state:
        st.session_state.dem_data = None
    
    # Procesar archivo subido si existe
    if uploaded_file is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
    
    # Cargar datos de demostración si se solicita
    if st.session_state.datos_demo and st.session_state.gdf_original is None:
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
    if st.session_state.analisis_completado:
        if analisis_tipo == "ANÁLISIS DE TEXTURA":
            mostrar_resultados_textura(cultivo, mes_analisis)
        elif analisis_tipo == "ANÁLISIS NDWI SUELO":
            mostrar_resultados_ndwi_suelo(cultivo, mes_analisis)
        elif analisis_tipo == "ANÁLISIS DE CURVAS DE NIVEL (LIDAR/DEM)":
            mostrar_resultados_curvas_nivel(cultivo, mes_analisis, intervalo_curvas, resolucion_dem)
        else:
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Análisis Principal", "🏗️ Análisis de Textura", 
                                             "💧 NDWI del Suelo", "🏔️ Curvas de Nivel"])
            
            with tab1:
                mostrar_resultados_principales(cultivo, analisis_tipo, nutriente, mes_analisis)
            
            with tab2:
                if st.session_state.analisis_textura is not None:
                    mostrar_resultados_textura(cultivo, mes_analisis)
                else:
                    st.info("Ejecuta el análisis principal para obtener datos de textura")
            
            with tab3:
                if st.session_state.gdf_analisis is not None and 'ndwi_suelo' in st.session_state.gdf_analisis.columns:
                    mostrar_resultados_ndwi_suelo(cultivo, mes_analisis)
                elif st.session_state.gdf_zonas is not None:
                    with st.spinner("💧 Analizando NDWI del suelo..."):
                        gdf_ndwi = analizar_ndwi_suelo(st.session_state.gdf_zonas, cultivo, mes_analisis)
                        st.session_state.gdf_analisis = gdf_ndwi
                        mostrar_resultados_ndwi_suelo(cultivo, mes_analisis)
                else:
                    st.info("Ejecuta el análisis principal para obtener datos de NDWI del suelo")
            
            with tab4:
                if st.session_state.curvas_nivel is not None:
                    mostrar_resultados_curvas_nivel(cultivo, mes_analisis, intervalo_curvas, resolucion_dem)
                elif st.session_state.gdf_original is not None:
                    with st.spinner("🏔️ Generando curvas de nivel desde LiDAR/DEM..."):
                        gdf_curvas = ejecutar_analisis_curvas_nivel(
                            st.session_state.gdf_original, intervalo_curvas, resolucion_dem
                        )
                        mostrar_resultados_curvas_nivel(cultivo, mes_analisis, intervalo_curvas, resolucion_dem)
                else:
                    st.info("Carga una parcela para generar curvas de nivel")
                    
    elif st.session_state.gdf_original is not None:
        mostrar_configuracion_parcela(cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, 
                                     intervalo_curvas, resolucion_dem)
    else:
        mostrar_modo_demo()

# ========== EJECUCIÓN PRINCIPAL ==========
if __name__ == "__main__":
    main()
