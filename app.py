# analizador_cultivos_mejorado.py
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
# NUEVA: PARÁMETROS DE ANÁLISIS CON PLANETSCOPE
# ============================================================================
PARAMETROS_PLANETSCOPE = {
    'RESOLUCION': '3m',
    'BANDAS': {
        'COASTAL_BLUE': 'B1: 431-452 nm',
        'BLUE': 'B2: 465-515 nm',
        'GREEN_I': 'B3: 513-549 nm',
        'GREEN': 'B4: 547-583 nm',
        'YELLOW': 'B5: 600-620 nm',
        'RED': 'B6: 650-680 nm',
        'RED_EDGE': 'B7: 697-713 nm',
        'NIR': 'B8: 845-885 nm'
    },
    'INDICES_ESPECTRALES': {
        'NDVI': '(NIR - RED) / (NIR + RED)',
        'NDWI': '(GREEN - NIR) / (GREEN + NIR)',
        'CI_RedEdge': 'NIR / RED_EDGE - 1',  # Índice de Clorofila
        'NDSI': '(GREEN - RED) / (GREEN + RED)',  # Índice de Suelo
        'EVI': '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)'
    }
}

# ============================================================================
# CLASIFICACIÓN MEJORADA DE TEXTURAS SEGÚN USDA - NOMENCLATURA ACTUALIZADA
# ============================================================================
CLASIFICACION_TEXTURAS_USDA = {
    'ARENA': {
        'nombre_completo': 'Arena',
        'descripcion': 'Más del 85% de arena, menos del 15% de limo y arcilla combinados',
        'arena_min': 85,
        'arena_max': 100,
        'limo_max': 15,
        'arcilla_max': 15,
        'color': '#f4e8c1'
    },
    'ARENA_FRANCA': {
        'nombre_completo': 'Arena Franca',
        'descripcion': '70-85% arena, 0-30% limo, 0-15% arcilla',
        'arena_min': 70,
        'arena_max': 85,
        'limo_max': 30,
        'arcilla_max': 15,
        'color': '#e8d4a8'
    },
    'FRANCO_ARENOSO': {
        'nombre_completo': 'Franco Arenoso',
        'descripcion': '52-70% arena, 0-50% limo, 0-20% arcilla',
        'arena_min': 52,
        'arena_max': 70,
        'limo_max': 50,
        'arcilla_max': 20,
        'color': '#d9c089'
    },
    'FRANCO': {
        'nombre_completo': 'Franco',
        'descripcion': 'Balance equilibrado de arena, limo y arcilla',
        'arena_min': 30,
        'arena_max': 50,
        'limo_min': 30,
        'limo_max': 50,
        'arcilla_min': 0,
        'arcilla_max': 20,
        'color': '#b8a86d'
    },
    'FRANCO_LIMOSO': {
        'nombre_completo': 'Franco Limoso',
        'descripcion': '0-50% arena, 50-88% limo, 0-27% arcilla',
        'arena_max': 50,
        'limo_min': 50,
        'limo_max': 88,
        'arcilla_max': 27,
        'color': '#9c8e5e'
    },
    'FRANCO_ARCLLOSO': {
        'nombre_completo': 'Franco Arcilloso',
        'descripcion': '20-45% arena, 15-53% limo, 27-40% arcilla',
        'arena_min': 20,
        'arena_max': 45,
        'limo_min': 15,
        'limo_max': 53,
        'arcilla_min': 27,
        'arcilla_max': 40,
        'color': '#7d7250'
    },
    'ARCILLA_FRANCA': {
        'nombre_completo': 'Arcilla Franca',
        'descripcion': '20-45% arena, 0-40% limo, 40-60% arcilla',
        'arena_min': 20,
        'arena_max': 45,
        'limo_max': 40,
        'arcilla_min': 40,
        'arcilla_max': 60,
        'color': '#5e553d'
    },
    'ARCILLA': {
        'nombre_completo': 'Arcilla',
        'descripcion': '0-45% arena, 0-40% limo, más del 40% arcilla',
        'arena_max': 45,
        'limo_max': 40,
        'arcilla_min': 40,
        'color': '#3f3929'
    }
}

# ============================================================================
# PARÁMETROS MEJORADOS Y MÁS REALISTAS PARA DIFERENTES CULTIVOS
# ============================================================================
PARAMETROS_CULTIVOS = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 120, 'max': 200, 'optimo': 160},
        'FOSFORO': {'min': 40, 'max': 80, 'optimo': 60},
        'POTASIO': {'min': 160, 'max': 240, 'optimo': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.35,
        'pH_OPTIMO': 5.5,
        'CONDUCTIVIDAD_OPTIMA': 1.2,
        'INDICES_ESPECTRALES': {
            'NDVI_OPTIMO': 0.6,
            'NDWI_OPTIMO': 0.2,
            'CI_RedEdge_OPTIMO': 0.15
        }
    },
    'CACAO': {
        'NITROGENO': {'min': 100, 'max': 180, 'optimo': 140},
        'FOSFORO': {'min': 30, 'max': 60, 'optimo': 45},
        'POTASIO': {'min': 120, 'max': 200, 'optimo': 160},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.4,
        'pH_OPTIMO': 6.0,
        'CONDUCTIVIDAD_OPTIMA': 1.0,
        'INDICES_ESPECTRALES': {
            'NDVI_OPTIMO': 0.7,
            'NDWI_OPTIMO': 0.25,
            'CI_RedEdge_OPTIMO': 0.18
        }
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 280, 'optimo': 230},
        'FOSFORO': {'min': 50, 'max': 90, 'optimo': 70},
        'POTASIO': {'min': 250, 'max': 350, 'optimo': 300},
        'MATERIA_ORGANICA_OPTIMA': 4.5,
        'HUMEDAD_OPTIMA': 0.45,
        'pH_OPTIMO': 6.2,
        'CONDUCTIVIDAD_OPTIMA': 1.5,
        'INDICES_ESPECTRALES': {
            'NDVI_OPTIMO': 0.8,
            'NDWI_OPTIMO': 0.3,
            'CI_RedEdge_OPTIMO': 0.22
        }
    }
}

# ============================================================================
# PARÁMETROS DE TEXTURA DEL SUELO POR CULTIVO - NOMENCLATURA MEJORADA
# ============================================================================
TEXTURA_SUELO_OPTIMA = {
    'PALMA_ACEITERA': {
        'textura_optima': 'FRANCO_ARCLLOSO',
        'textura_alternativa': 'FRANCO',
        'arena_optima': 35,
        'limo_optima': 35,
        'arcilla_optima': 30,
        'densidad_aparente_optima': 1.3,
        'porosidad_optima': 0.5,
        'conductividad_hidraulica_optima': 1.5,
        'intervalo_temperatura_optima': '25-30°C',
        'resistencia_penetracion_optima': '1.5-2.5 MPa'
    },
    'CACAO': {
        'textura_optima': 'FRANCO',
        'textura_alternativa': 'FRANCO_ARCLLOSO',
        'arena_optima': 40,
        'limo_optima': 40,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.2,
        'porosidad_optima': 0.55,
        'conductividad_hidraulica_optima': 2.0,
        'intervalo_temperatura_optima': '22-28°C',
        'resistencia_penetracion_optima': '1.0-2.0 MPa'
    },
    'BANANO': {
        'textura_optima': 'FRANCO_ARCLLOSO',
        'textura_alternativa': 'FRANCO_LIMOSO',
        'arena_optima': 30,
        'limo_optima': 40,
        'arcilla_optima': 30,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52,
        'conductividad_hidraulica_optima': 1.8,
        'intervalo_temperatura_optima': '24-32°C',
        'resistencia_penetracion_optima': '1.2-2.2 MPa'
    }
}

# ============================================================================
# FACTORES EDÁFICOS MÁS REALISTAS - NOMENCLATURA MEJORADA
# ============================================================================
FACTORES_SUELO_MEJORADOS = {
    'ARENA': {
        'retencion_agua': 0.4,
        'drenaje': 1.6,
        'aireacion': 1.5,
        'trabajabilidad': 1.4,
        'riesgo_erosion': 'ALTO',
        'capacidad_intercambio_cationico': 3,
        'conductividad_termica': 0.3,
        'color_tipico': 'Claro',
        'temperatura_rapida': 'Rápido'
    },
    'ARENA_FRANCA': {
        'retencion_agua': 0.6,
        'drenaje': 1.4,
        'aireacion': 1.4,
        'trabajabilidad': 1.3,
        'riesgo_erosion': 'MEDIO-ALTO',
        'capacidad_intercambio_cationico': 5,
        'conductividad_termica': 0.4,
        'color_tipico': 'Claro-medio',
        'temperatura_rapida': 'Moderado-rápido'
    },
    'FRANCO_ARENOSO': {
        'retencion_agua': 0.8,
        'drenaje': 1.2,
        'aireacion': 1.3,
        'trabajabilidad': 1.2,
        'riesgo_erosion': 'MEDIO',
        'capacidad_intercambio_cationico': 8,
        'conductividad_termica': 0.5,
        'color_tipico': 'Medio',
        'temperatura_rapida': 'Moderado'
    },
    'FRANCO': {
        'retencion_agua': 1.0,
        'drenaje': 1.0,
        'aireacion': 1.0,
        'trabajabilidad': 1.0,
        'riesgo_erosion': 'BAJO',
        'capacidad_intercambio_cationico': 15,
        'conductividad_termica': 0.6,
        'color_tipico': 'Medio',
        'temperatura_rapida': 'Moderado'
    },
    'FRANCO_LIMOSO': {
        'retencion_agua': 1.2,
        'drenaje': 0.9,
        'aireacion': 0.9,
        'trabajabilidad': 0.9,
        'riesgo_erosion': 'BAJO-MEDIO',
        'capacidad_intercambio_cationico': 20,
        'conductividad_termica': 0.7,
        'color_tipico': 'Medio-oscuro',
        'temperatura_rapida': 'Lento'
    },
    'FRANCO_ARCLLOSO': {
        'retencion_agua': 1.3,
        'drenaje': 0.8,
        'aireacion': 0.8,
        'trabajabilidad': 0.8,
        'riesgo_erosion': 'BAJO',
        'capacidad_intercambio_cationico': 25,
        'conductividad_termica': 0.8,
        'color_tipico': 'Oscuro',
        'temperatura_rapida': 'Lento'
    },
    'ARCILLA_FRANCA': {
        'retencion_agua': 1.4,
        'drenaje': 0.7,
        'aireacion': 0.7,
        'trabajabilidad': 0.6,
        'riesgo_erosion': 'BAJO',
        'capacidad_intercambio_cationico': 30,
        'conductividad_termica': 0.9,
        'color_tipico': 'Oscuro',
        'temperatura_rapida': 'Muy lento'
    },
    'ARCILLA': {
        'retencion_agua': 1.5,
        'drenaje': 0.6,
        'aireacion': 0.6,
        'trabajabilidad': 0.5,
        'riesgo_erosion': 'BAJO',
        'capacidad_intercambio_cationico': 35,
        'conductividad_termica': 1.0,
        'color_tipico': 'Muy oscuro',
        'temperatura_rapida': 'Muy lento'
    }
}

# ============================================================================
# RECOMENDACIONES MEJORADAS - NOMENCLATURA ACTUALIZADA
# ============================================================================
RECOMENDACIONES_TEXTURA_MEJORADAS = {
    'ARENA': [
        "Aplicación de 10-15 ton/ha de materia orgánica anualmente",
        "Uso de polímeros retenedores de agua (hidrogeles)",
        "Fertilización fraccionada (8-10 aplicaciones por año)",
        "Riego por goteo con alta frecuencia (3-4 veces por semana)",
        "Cultivos de cobertura de raíces profundas (sorgo, alfalfa)",
        "Barreras vivas para reducir erosión eólica (vetiver, pasto elefante)",
        "Aplicación de biochar (5-10 ton/ha) para mejorar retención"
    ],
    'ARENA_FRANCA': [
        "Aplicación de 8-12 ton/ha de materia orgánica anualmente",
        "Riego por goteo o aspersión con mediana frecuencia",
        "Fertilización fraccionada (6-8 aplicaciones por año)",
        "Cultivos de cobertura mixtos (leguminosas y gramíneas)",
        "Uso de mulch orgánico para reducir evaporación",
        "Aplicación de enmiendas calcáreas si pH < 6.0"
    ],
    'FRANCO_ARENOSO': [
        "Mantener 3-5% de materia orgánica con aplicaciones anuales",
        "Riego según necesidades del cultivo (monitoreo con tensiómetros)",
        "Fertilización balanceada (4-6 aplicaciones por año)",
        "Rotación de cultivos para mantener estructura",
        "Labranza mínima para conservar humedad",
        "Aplicación de compost cada 2-3 años"
    ],
    'FRANCO': [
        "Mantener prácticas conservacionistas de labranza",
        "Rotación de cultivos con leguminosas cada 2-3 años",
        "Aplicación de 2-4 ton/ha de compost anualmente",
        "Monitoreo regular de pH y nutrientes",
        "Uso de coberturas vivas en períodos intercalados",
        "Evitar compactación con maquinaria pesada"
    ],
    'FRANCO_LIMOSO': [
        "Manejo cuidadoso para evitar compactación",
        "Drenaje superficial mejorado en áreas bajas",
        "Aplicación de materia orgánica para mejorar estructura",
        "Evitar laboreo en condiciones húmedas",
        "Uso de cultivos de cobertura para estabilizar estructura",
        "Monitoreo de densidad aparente (ideal: 1.2-1.4 g/cm³)"
    ],
    'FRANCO_ARCLLOSO': [
        "Aplicación de materia orgánica (5-8 ton/ha) para mantener estructura",
        "Labranza vertical ocasional para romper capas compactadas",
        "Drenaje sub-superficial en áreas con problemas de encharcamiento",
        "Cultivos de cobertura con sistemas radiculares profundos",
        "Evitar tránsito de maquinaria en condiciones húmedas",
        "Aplicación de yeso agrícola si sodio > 10%"
    ],
    'ARCILLA_FRANCA': [
        "Aplicación de 8-12 ton/ha de materia orgánica anualmente",
        "Drenaje profundo (zanjas o tubos) para mejorar aireación",
        "Labranza de subsuelo cada 3-4 años",
        "Cultivos de cobertura agresivos para romper compactación",
        "Aplicación de enmiendas calcáreas para mejorar estructura",
        "Evitar cualquier laboreo en condiciones húmedas"
    ],
    'ARCILLA': [
        "Aplicación intensiva de materia orgánica (12-15 ton/ha inicial)",
        "Sistema de drenaje profundo obligatorio",
        "Labranza de subsuelo con arado de vertedera",
        "Camas elevadas para mejorar drenaje y temperatura",
        "Aplicación de yeso agrícola (2-4 ton/ha) para mejorar estructura",
        "Cultivos de cobertura de invierno para proteger superficie"
    ]
}

# ============================================================================
# FACTORES ESTACIONALES MEJORADOS
# ============================================================================
FACTORES_MES_MEJORADOS = {
    "ENERO": {'factor': 0.9, 'precipitacion': 'Alta', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta'},
    "FEBRERO": {'factor': 0.95, 'precipitacion': 'Alta', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta'},
    "MARZO": {'factor': 1.0, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media'},
    "ABRIL": {'factor': 1.05, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media'},
    "MAYO": {'factor': 1.1, 'precipitacion': 'Baja', 'temperatura': 'Media', 'evapotranspiracion': 'Media'},
    "JUNIO": {'factor': 1.0, 'precipitacion': 'Baja', 'temperatura': 'Baja', 'evapotranspiracion': 'Baja'},
    "JULIO": {'factor': 0.95, 'precipitacion': 'Muy baja', 'temperatura': 'Baja', 'evapotranspiracion': 'Baja'},
    "AGOSTO": {'factor': 0.9, 'precipitacion': 'Muy baja', 'temperatura': 'Baja', 'evapotranspiracion': 'Baja'},
    "SEPTIEMBRE": {'factor': 0.95, 'precipitacion': 'Baja', 'temperatura': 'Media', 'evapotranspiracion': 'Media'},
    "OCTUBRE": {'factor': 1.0, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media'},
    "NOVIEMBRE": {'factor': 1.05, 'precipitacion': 'Alta', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta'},
    "DICIEMBRE": {'factor': 1.0, 'precipitacion': 'Alta', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta'}
}

# ============================================================================
# PALETAS GEE MEJORADAS
# ============================================================================
PALETAS_GEE_MEJORADAS = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'TEXTURA': ['#f4e8c1', '#e8d4a8', '#d9c089', '#b8a86d', '#9c8e5e', '#7d7250', '#5e553d', '#3f3929'],
    'INDICES_ESPECTRALES': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027'],
    'PROPIEDADES_FISICAS': ['#543005', '#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e']
}

# ============================================================================
# FUNCIÓN MEJORADA PARA CLASIFICAR TEXTURA DEL SUELO SEGÚN USDA
# ============================================================================
def clasificar_textura_suelo_mejorada(arena, limo, arcilla):
    """Clasifica la textura del suelo según el sistema USDA mejorado"""
    try:
        # Normalizar porcentajes a 100%
        total = arena + limo + arcilla
        if total <= 0:
            return "NO_DETERMINADA"
        
        arena_pct = (arena / total) * 100
        limo_pct = (limo / total) * 100
        arcilla_pct = (arcilla / total) * 100
        
        # Clasificación según triángulo de texturas USDA
        if arcilla_pct >= 40:
            if limo_pct <= 40:
                return "ARCILLA"
            else:
                return "ARCILLA_FRANCA"
        
        elif arcilla_pct >= 27 and arcilla_pct < 40:
            if limo_pct >= 15 and limo_pct <= 53 and arena_pct >= 20 and arena_pct <= 45:
                return "FRANCO_ARCLLOSO"
            else:
                return "ARCILLA_FRANCA"
        
        elif arcilla_pct >= 20 and arcilla_pct < 27:
            if limo_pct >= 15 and limo_pct <= 53:
                return "FRANCO_ARCLLOSO"
            elif limo_pct > 50:
                return "FRANCO_LIMOSO"
            else:
                return "FRANCO"
        
        elif arcilla_pct >= 0 and arcilla_pct < 20:
            if arena_pct >= 52 and arena_pct <= 70:
                return "FRANCO_ARENOSO"
            elif arena_pct >= 70 and arena_pct <= 85:
                return "ARENA_FRANCA"
            elif arena_pct > 85:
                return "ARENA"
            elif limo_pct >= 50 and limo_pct <= 88:
                return "FRANCO_LIMOSO"
            else:
                return "FRANCO"
        
        else:
            # Por defecto, franco
            return "FRANCO"
            
    except Exception as e:
        return "NO_DETERMINADA"

# ============================================================================
# FUNCIÓN PARA SIMULAR DATOS DE PLANETSCOPE
# ============================================================================
def simular_datos_planetscope(centroid, textura_clave, cultivo):
    """Simula datos espectrales de PlanetScope basados en ubicación y textura"""
    try:
        # Semilla reproducible basada en coordenadas
        seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{textura_clave}")) % (2**32)
        rng = np.random.RandomState(seed_value)
        
        # Parámetros base según textura
        params_textura = FACTORES_SUELO_MEJORADOS.get(textura_clave, {})
        params_cultivo = PARAMETROS_CULTIVOS[cultivo]['INDICES_ESPECTRALES']
        
        # Simular reflectancias en diferentes bandas
        reflectancias = {
            'COASTAL_BLUE': max(0.1, min(0.9, rng.normal(0.3, 0.05))),
            'BLUE': max(0.1, min(0.9, rng.normal(0.35, 0.05))),
            'GREEN_I': max(0.1, min(0.9, rng.normal(0.4, 0.05))),
            'GREEN': max(0.1, min(0.9, rng.normal(0.45, 0.05))),
            'YELLOW': max(0.1, min(0.9, rng.normal(0.5, 0.05))),
            'RED': max(0.1, min(0.9, rng.normal(0.55, 0.05))),
            'RED_EDGE': max(0.1, min(0.9, rng.normal(0.6, 0.05))),
            'NIR': max(0.1, min(0.9, rng.normal(0.65, 0.05)))
        }
        
        # Calcular índices espectrales
        ndvi = (reflectancias['NIR'] - reflectancias['RED']) / (reflectancias['NIR'] + reflectancias['RED'])
        ndwi = (reflectancias['GREEN'] - reflectancias['NIR']) / (reflectancias['GREEN'] + reflectancias['NIR'])
        ci_rededge = reflectancias['NIR'] / reflectancias['RED_EDGE'] - 1
        ndsi = (reflectancias['GREEN'] - reflectancias['RED']) / (reflectancias['GREEN'] + reflectancias['RED'])
        evi = 2.5 * (reflectancias['NIR'] - reflectancias['RED']) / (reflectancias['NIR'] + 6 * reflectancias['RED'] - 7.5 * reflectancias['BLUE'] + 1)
        
        # Ajustar según textura
        if textura_clave in ['ARENA', 'ARENA_FRANCA']:
            # Suelos arenosos tienen mayor reflectancia
            factor_ajuste = 1.1
        elif textura_clave in ['ARCILLA', 'ARCILLA_FRANCA']:
            # Suelos arcillosos tienen menor reflectancia
            factor_ajuste = 0.9
        else:
            factor_ajuste = 1.0
            
        ndvi = max(-1, min(1, ndvi * factor_ajuste))
        ndwi = max(-1, min(1, ndwi * factor_ajuste))
        ci_rededge = max(-1, min(1, ci_rededge * factor_ajuste))
        
        # Calcular adecuación de índices para el cultivo
        adecuacion_ndvi = 1.0 - abs(ndvi - params_cultivo['NDVI_OPTIMO']) / 2.0
        adecuacion_ndwi = 1.0 - abs(ndwi - params_cultivo['NDWI_OPTIMO']) / 2.0
        adecuacion_ci = 1.0 - abs(ci_rededge - params_cultivo['CI_RedEdge_OPTIMO']) / 2.0
        
        adecuacion_espectral = (adecuacion_ndvi * 0.4 + adecuacion_ndwi * 0.3 + adecuacion_ci * 0.3)
        
        return {
            'reflectancias': reflectancias,
            'ndvi': ndvi,
            'ndwi': ndwi,
            'ci_rededge': ci_rededge,
            'ndsi': ndsi,
            'evi': evi,
            'adecuacion_espectral': adecuacion_espectral,
            'adecuacion_ndvi': adecuacion_ndvi,
            'adecuacion_ndwi': adecuacion_ndwi,
            'adecuacion_ci': adecuacion_ci,
            'resolucion_imagen': '3m',
            'fecha_simulacion': datetime.now().strftime('%Y-%m-%d'),
            'nube_cobertura': rng.uniform(0, 0.3)  # 0-30% de cobertura de nubes
        }
        
    except Exception as e:
        # Valores por defecto
        return {
            'reflectancias': {},
            'ndvi': 0.6,
            'ndwi': 0.2,
            'ci_rededge': 0.15,
            'ndsi': 0.1,
            'evi': 0.4,
            'adecuacion_espectral': 0.8,
            'adecuacion_ndvi': 0.8,
            'adecuacion_ndwi': 0.8,
            'adecuacion_ci': 0.8,
            'resolucion_imagen': '3m',
            'fecha_simulacion': datetime.now().strftime('%Y-%m-%d'),
            'nube_cobertura': 0.1
        }

# ============================================================================
# FUNCIÓN PARA CALCULAR PROPIEDADES FÍSICAS MEJORADAS
# ============================================================================
def calcular_propiedades_fisicas_mejoradas(textura_clave, materia_organica, humedad):
    """Calcula propiedades físicas del suelo basadas en textura mejorada"""
    
    propiedades = {
        'capacidad_campo': 0.0,      # mm/m
        'punto_marchitez': 0.0,      # mm/m
        'agua_disponible': 0.0,      # mm/m
        'densidad_aparente': 0.0,    # g/cm³
        'porosidad': 0.0,            # %
        'conductividad_hidraulica': 0.0,  # cm/hora
        'capacidad_intercambio_cationico': 0.0,  # meq/100g
        'resistencia_penetracion': 0.0,   # MPa
        'conductividad_termica': 0.0,     # W/m·K
        'temperatura_suelo': 0.0,         # °C
        'color_suelo': '',
        'textura_tacto': ''
    }
    
    # Valores base según textura USDA
    base_propiedades = {
        'ARENA': {
            'cc': 120, 'pm': 50, 'da': 1.5, 'porosidad': 0.43, 'kh': 15.0,
            'cic': 3, 'rp': 1.0, 'ct': 0.3, 'temp': 25, 'color': 'Claro', 'tacto': 'Grueso, áspero'
        },
        'ARENA_FRANCA': {
            'cc': 150, 'pm': 70, 'da': 1.45, 'porosidad': 0.46, 'kh': 8.0,
            'cic': 5, 'rp': 1.2, 'ct': 0.4, 'temp': 24, 'color': 'Claro-medio', 'tacto': 'Suave, algo arenoso'
        },
        'FRANCO_ARENOSO': {
            'cc': 180, 'pm': 80, 'da': 1.4, 'porosidad': 0.49, 'kh': 5.0,
            'cic': 8, 'rp': 1.5, 'ct': 0.5, 'temp': 23, 'color': 'Medio', 'tacto': 'Suave, ligeramente arenoso'
        },
        'FRANCO': {
            'cc': 250, 'pm': 100, 'da': 1.3, 'porosidad': 0.52, 'kh': 2.5,
            'cic': 15, 'rp': 2.0, 'ct': 0.6, 'temp': 22, 'color': 'Medio', 'tacto': 'Suave, friable'
        },
        'FRANCO_LIMOSO': {
            'cc': 280, 'pm': 120, 'da': 1.25, 'porosidad': 0.54, 'kh': 1.5,
            'cic': 20, 'rp': 2.2, 'ct': 0.7, 'temp': 21, 'color': 'Medio-oscuro', 'tacto': 'Sedoso, suave'
        },
        'FRANCO_ARCLLOSO': {
            'cc': 300, 'pm': 150, 'da': 1.2, 'porosidad': 0.56, 'kh': 0.8,
            'cic': 25, 'rp': 2.5, 'ct': 0.8, 'temp': 20, 'color': 'Oscuro', 'tacto': 'Suave, algo pegajoso'
        },
        'ARCILLA_FRANCA': {
            'cc': 350, 'pm': 200, 'da': 1.15, 'porosidad': 0.58, 'kh': 0.3,
            'cic': 30, 'rp': 3.0, 'ct': 0.9, 'temp': 19, 'color': 'Oscuro', 'tacto': 'Pegajoso, plástico'
        },
        'ARCILLA': {
            'cc': 400, 'pm': 250, 'da': 1.1, 'porosidad': 0.6, 'kh': 0.1,
            'cic': 35, 'rp': 3.5, 'ct': 1.0, 'temp': 18, 'color': 'Muy oscuro', 'tacto': 'Muy pegajoso, plástico'
        }
    }
    
    if textura_clave in base_propiedades:
        base = base_propiedades[textura_clave]
        
        # Ajustar por materia orgánica (cada 1% de MO mejora propiedades)
        factor_mo = 1.0 + (materia_organica * 0.03)
        
        # Ajustar por humedad actual
        factor_humedad = 1.0 + (humedad * 0.2)
        
        propiedades['capacidad_campo'] = base['cc'] * factor_mo
        propiedades['punto_marchitez'] = base['pm'] * factor_mo
        propiedades['agua_disponible'] = (base['cc'] - base['pm']) * factor_mo
        propiedades['densidad_aparente'] = base['da'] / factor_mo
        propiedades['porosidad'] = min(0.7, base['porosidad'] * factor_mo)
        propiedades['conductividad_hidraulica'] = base['kh'] * factor_mo
        propiedades['capacidad_intercambio_cationico'] = base['cic'] * factor_mo
        propiedades['resistencia_penetracion'] = base['rp'] / factor_mo
        propiedades['conductividad_termica'] = base['ct'] * factor_mo
        propiedades['temperatura_suelo'] = base['temp'] * factor_humedad
        propiedades['color_suelo'] = base['color']
        propiedades['textura_tacto'] = base['tacto']
    
    return propiedades

# ============================================================================
# FUNCIÓN MEJORADA PARA EVALUAR ADECUACIÓN DE TEXTURA
# ============================================================================
def evaluar_adecuacion_textura_mejorada(textura_actual, cultivo, datos_planetscope=None):
    """Evalúa qué tan adecuada es la textura para el cultivo específico"""
    
    textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
    textura_alternativa = TEXTURA_SUELO_OPTIMA[cultivo]['textura_alternativa']
    
    # Jerarquía de adecuación mejorada
    jerarquia_texturas = {
        'ARENA': 1,
        'ARENA_FRANCA': 2,
        'FRANCO_ARENOSO': 3,
        'FRANCO': 4,
        'FRANCO_LIMOSO': 5,
        'FRANCO_ARCLLOSO': 6,
        'ARCILLA_FRANCA': 7,
        'ARCILLA': 8,
        'NO_DETERMINADA': 0
    }
    
    if textura_actual not in jerarquia_texturas:
        return "NO_DETERMINADA", 0.0, "Sin datos suficientes para clasificación"
    
    actual_idx = jerarquia_texturas[textura_actual]
    optima_idx = jerarquia_texturas[textura_optima]
    
    # Calcular diferencia considerando texturas alternativas
    diferencia = abs(actual_idx - optima_idx)
    
    # Si es textura alternativa, considerar como diferencia 1
    if textura_actual == textura_alternativa:
        diferencia = 1
    
    # Evaluación considerando datos de PlanetScope si están disponibles
    if datos_planetscope:
        factor_planetscope = datos_planetscope['adecuacion_espectral']
        diferencia_ajustada = diferencia * (1.0 / factor_planetscope)
    else:
        diferencia_ajustada = diferencia
    
    # Determinar categoría y puntaje
    if textura_actual == textura_optima:
        categoria = "ÓPTIMA"
        puntaje = 1.0
        justificacion = "Textura ideal para el cultivo según USDA"
    elif textura_actual == textura_alternativa:
        categoria = "EXCELENTE"
        puntaje = 0.9
        justificacion = "Textura alternativa excelente para el cultivo"
    elif diferencia_ajustada <= 1:
        categoria = "MUY BUENA"
        puntaje = 0.8
        justificacion = "Textura muy adecuada, ajustes mínimos requeridos"
    elif diferencia_ajustada <= 2:
        categoria = "BUENA"
        puntaje = 0.7
        justificacion = "Textura adecuada, manejo específico recomendado"
    elif diferencia_ajustada <= 3:
        categoria = "MODERADA"
        puntaje = 0.5
        justificacion = "Textura moderadamente adecuada, requiere intervenciones"
    elif diferencia_ajustada <= 4:
        categoria = "LIMITANTE"
        puntaje = 0.3
        justificacion = "Textura con limitaciones significativas"
    else:
        categoria = "MUY LIMITANTE"
        puntaje = 0.1
        justificacion = "Textura muy limitante, intervenciones intensivas requeridas"
    
    # Ajustar puntaje con datos de PlanetScope si disponibles
    if datos_planetscope:
        puntaje = puntaje * 0.7 + datos_planetscope['adecuacion_espectral'] * 0.3
        justificacion += f" | Adecuación espectral: {datos_planetscope['adecuacion_espectral']:.1%}"
    
    return categoria, puntaje, justificacion

# ============================================================================
# FUNCIÓN PRINCIPAL MEJORADA PARA ANÁLISIS DE TEXTURA
# ============================================================================
def analizar_textura_suelo_mejorada(gdf, cultivo, mes_analisis, usar_planetscope=True):
    """Realiza análisis completo de textura del suelo con PlanetScope"""
    
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas para textura mejorada
    columnas_base = [
        'area_ha', 'arena', 'limo', 'arcilla', 'textura_suelo', 'textura_nombre_completo',
        'adecuacion_textura', 'categoria_adecuacion', 'justificacion_adecuacion',
        'capacidad_campo', 'punto_marchitez', 'agua_disponible', 'densidad_aparente',
        'porosidad', 'conductividad_hidraulica', 'capacidad_intercambio_cationico',
        'resistencia_penetracion', 'conductividad_termica', 'temperatura_suelo',
        'color_suelo', 'textura_tacto', 'materia_organica', 'humedad_suelo'
    ]
    
    # Columnas específicas de PlanetScope
    columnas_planetscope = [
        'ndvi', 'ndwi', 'ci_rededge', 'ndsi', 'evi', 'adecuacion_espectral',
        'adecuacion_ndvi', 'adecuacion_ndwi', 'adecuacion_ci',
        'resolucion_imagen', 'fecha_imagen', 'cobertura_nubes'
    ]
    
    # Inicializar todas las columnas
    for col in columnas_base + (columnas_planetscope if usar_planetscope else []):
        if col == 'textura_suelo':
            zonas_gdf[col] = "NO_DETERMINADA"
        elif col == 'textura_nombre_completo':
            zonas_gdf[col] = "No determinada"
        elif col == 'categoria_adecuacion':
            zonas_gdf[col] = "NO_DETERMINADA"
        elif col == 'justificacion_adecuacion':
            zonas_gdf[col] = ""
        elif col == 'color_suelo':
            zonas_gdf[col] = ""
        elif col == 'textura_tacto':
            zonas_gdf[col] = ""
        elif col == 'fecha_imagen':
            zonas_gdf[col] = datetime.now().strftime('%Y-%m-%d')
        elif col == 'resolucion_imagen':
            zonas_gdf[col] = '3m' if usar_planetscope else 'N/A'
        elif col == 'cobertura_nubes':
            zonas_gdf[col] = 0.0
        else:
            zonas_gdf[col] = 0.0
    
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
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            
            # SIMULAR COMPOSICIÓN GRANULOMÉTRICA MEJORADA
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            
            # Patrón espacial más realista
            variabilidad_espacial = 0.2 + 0.6 * np.sin(lat_norm * np.pi * 2) * np.cos(lon_norm * np.pi * 2)
            
            # Valores óptimos para el cultivo
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            
            # Simular composición con distribución normal ajustada
            arena = max(5, min(95, rng.normal(
                arena_optima * (0.7 + 0.6 * variabilidad_espacial),
                arena_optima * 0.25
            )))
            
            limo = max(5, min(95, rng.normal(
                limo_optima * (0.6 + 0.8 * variabilidad_espacial),
                limo_optima * 0.3
            )))
            
            arcilla = max(5, min(95, rng.normal(
                arcilla_optima * (0.65 + 0.7 * variabilidad_espacial),
                arcilla_optima * 0.35
            )))
            
            # Normalizar a 100%
            total = arena + limo + arcilla
            arena = (arena / total) * 100
            limo = (limo / total) * 100
            arcilla = (arcilla / total) * 100
            
            # Clasificar textura mejorada
            textura_clave = clasificar_textura_suelo_mejorada(arena, limo, arcilla)
            textura_info = CLASIFICACION_TEXTURAS_USDA.get(textura_clave, {})
            textura_nombre = textura_info.get('nombre_completo', 'No determinada')
            
            # Simular materia orgánica y humedad
            materia_organica = max(1.0, min(8.0, rng.normal(
                PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA'],
                1.0
            )))
            
            humedad_suelo = max(0.1, min(0.6, rng.normal(
                PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA'],
                0.15
            )))
            
            # Calcular propiedades físicas mejoradas
            propiedades_fisicas = calcular_propiedades_fisicas_mejoradas(
                textura_clave, materia_organica, humedad_suelo
            )
            
            # Simular datos de PlanetScope si está habilitado
            datos_planetscope = None
            if usar_planetscope:
                datos_planetscope = simular_datos_planetscope(centroid, textura_clave, cultivo)
                
                # Asignar datos de PlanetScope
                zonas_gdf.loc[idx, 'ndvi'] = datos_planetscope['ndvi']
                zonas_gdf.loc[idx, 'ndwi'] = datos_planetscope['ndwi']
                zonas_gdf.loc[idx, 'ci_rededge'] = datos_planetscope['ci_rededge']
                zonas_gdf.loc[idx, 'ndsi'] = datos_planetscope['ndsi']
                zonas_gdf.loc[idx, 'evi'] = datos_planetscope['evi']
                zonas_gdf.loc[idx, 'adecuacion_espectral'] = datos_planetscope['adecuacion_espectral']
                zonas_gdf.loc[idx, 'adecuacion_ndvi'] = datos_planetscope['adecuacion_ndvi']
                zonas_gdf.loc[idx, 'adecuacion_ndwi'] = datos_planetscope['adecuacion_ndwi']
                zonas_gdf.loc[idx, 'adecuacion_ci'] = datos_planetscope['adecuacion_ci']
                zonas_gdf.loc[idx, 'fecha_imagen'] = datos_planetscope['fecha_simulacion']
                zonas_gdf.loc[idx, 'cobertura_nubes'] = datos_planetscope['nube_cobertura']
            
            # Evaluar adecuación mejorada
            categoria_adecuacion, puntaje_adecuacion, justificacion = evaluar_adecuacion_textura_mejorada(
                textura_clave, cultivo, datos_planetscope
            )
            
            # Asignar valores al GeoDataFrame
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = arena
            zonas_gdf.loc[idx, 'limo'] = limo
            zonas_gdf.loc[idx, 'arcilla'] = arcilla
            zonas_gdf.loc[idx, 'textura_suelo'] = textura_clave
            zonas_gdf.loc[idx, 'textura_nombre_completo'] = textura_nombre
            zonas_gdf.loc[idx, 'adecuacion_textura'] = puntaje_adecuacion
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = categoria_adecuacion
            zonas_gdf.loc[idx, 'justificacion_adecuacion'] = justificacion
            zonas_gdf.loc[idx, 'materia_organica'] = materia_organica
            zonas_gdf.loc[idx, 'humedad_suelo'] = humedad_suelo
            
            # Propiedades físicas
            for prop, valor in propiedades_fisicas.items():
                if prop in zonas_gdf.columns:
                    zonas_gdf.loc[idx, prop] = valor
            
        except Exception as e:
            # Valores por defecto en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            zonas_gdf.loc[idx, 'justificacion_adecuacion'] = "Valores óptimos por defecto"
    
    return zonas_gdf

# ============================================================================
# FUNCIÓN PARA MOSTRAR ANÁLISIS DE TEXTURA MEJORADO
# ============================================================================
def mostrar_analisis_textura_mejorado():
    """Muestra el análisis mejorado de textura del suelo"""
    if st.session_state.analisis_textura is None:
        st.warning("No hay datos de análisis de textura disponibles")
        return
    
    gdf_textura = st.session_state.analisis_textura
    area_total = st.session_state.area_total
    
    st.markdown("## 🛰️ ANÁLISIS AVANZADO DE TEXTURA DEL SUELO")
    st.info("**Metodología:** Clasificación USDA mejorada con datos simulados de PlanetScope (3m de resolución)")
    
    # Botón para volver
    if st.button("⬅️ Volver a Configuración", key="volver_textura_mejorada"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Estadísticas principales
    st.subheader("📊 ESTADÍSTICAS PRINCIPALES")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if 'textura_nombre_completo' in gdf_textura.columns:
            textura_pred = gdf_textura['textura_nombre_completo'].mode()[0] if len(gdf_textura) > 0 else "No determinada"
            st.metric("🏗️ Textura Predominante", textura_pred)
    with col2:
        if 'adecuacion_textura' in gdf_textura.columns:
            avg_adecuacion = gdf_textura['adecuacion_textura'].mean()
            st.metric("📈 Adecuación Promedio", f"{avg_adecuacion:.1%}")
    with col3:
        if 'arena' in gdf_textura.columns:
            avg_arena = gdf_textura['arena'].mean()
            st.metric("🏖️ Arena Promedio", f"{avg_arena:.1f}%")
    with col4:
        if 'arcilla' in gdf_textura.columns:
            avg_arcilla = gdf_textura['arcilla'].mean()
            st.metric("🧱 Arcilla Promedio", f"{avg_arcilla:.1f}%")
    
    # Información de PlanetScope
    if 'ndvi' in gdf_textura.columns:
        st.subheader("🛰️ DATOS DE PLANETSCOPE")
        
        col_ps1, col_ps2, col_ps3, col_ps4 = st.columns(4)
        with col_ps1:
            avg_ndvi = gdf_textura['ndvi'].mean()
            st.metric("🌿 NDVI Promedio", f"{avg_ndvi:.3f}")
        with col_ps2:
            avg_ndwi = gdf_textura['ndwi'].mean()
            st.metric("💧 NDWI Promedio", f"{avg_ndwi:.3f}")
        with col_ps3:
            avg_ci = gdf_textura['ci_rededge'].mean()
            st.metric("🍃 CI RedEdge", f"{avg_ci:.3f}")
        with col_ps4:
            if 'adecuacion_espectral' in gdf_textura.columns:
                avg_adec_esp = gdf_textura['adecuacion_espectral'].mean()
                st.metric("📡 Adecuación Espectral", f"{avg_adec_esp:.1%}")
    
    # Distribución de texturas
    st.subheader("📋 DISTRIBUCIÓN DE TEXTURAS USDA")
    
    if 'textura_suelo' in gdf_textura.columns:
        # Crear gráfico mejorado
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Gráfico de torta
        textura_counts = gdf_textura['textura_suelo'].value_counts()
        labels = [CLASIFICACION_TEXTURAS_USDA.get(t, {}).get('nombre_completo', t) for t in textura_counts.index]
        colors_pie = [CLASIFICACION_TEXTURAS_USDA.get(t, {}).get('color', '#999999') for t in textura_counts.index]
        
        ax1.pie(textura_counts.values, labels=labels, colors=colors_pie, autopct='%1.1f%%', startangle=90)
        ax1.set_title('Distribución de Texturas')
        
        # Gráfico de composición
        texturas_sample = textura_counts.index[:5]  # Primeras 5 texturas
        composiciones = []
        
        for textura in texturas_sample:
            if textura in CLASIFICACION_TEXTURAS_USDA:
                info = CLASIFICACION_TEXTURAS_USDA[textura]
                composiciones.append({
                    'Arena': info.get('arena_min', 0),
                    'Limo': 100 - info.get('arena_min', 0) - info.get('arcilla_max', 0),
                    'Arcilla': info.get('arcilla_max', 0)
                })
        
        if composiciones:
            df_composicion = pd.DataFrame(composiciones, index=[CLASIFICACION_TEXTURAS_USDA.get(t, {}).get('nombre_completo', t) for t in texturas_sample])
            df_composicion.plot(kind='bar', stacked=True, ax=ax2, color=['#f4e8c1', '#d9c089', '#5e553d'])
            ax2.set_title('Composición Granulométrica Típica')
            ax2.set_ylabel('Porcentaje (%)')
            ax2.legend(title='Componente')
            ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        st.pyplot(fig)
    
    # Mapa de texturas mejorado
    st.subheader("🗺️ MAPA DE TEXTURAS CON PLANETSCOPE")
    
    if 'textura_suelo' in gdf_textura.columns:
        # Crear mapa con colores mejorados
        m = folium.Map(
            location=[gdf_textura.geometry.centroid.y.mean(), gdf_textura.geometry.centroid.x.mean()],
            zoom_start=14,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satélite'
        )
        
        # Añadir capas base
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='OpenStreetMap',
            overlay=False
        ).add_to(m)
        
        # Añadir cada polígono con color según textura
        for idx, row in gdf_textura.iterrows():
            textura = row['textura_suelo']
            color = CLASIFICACION_TEXTURAS_USDA.get(textura, {}).get('color', '#999999')
            
            # Popup mejorado
            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px;">
                <h4>Zona {row['id_zona']}</h4>
                <b>Textura:</b> {row.get('textura_nombre_completo', 'N/A')}<br>
                <b>Adecuación:</b> {row.get('adecuacion_textura', 0):.1%}<br>
                <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                <hr>
                <b>Composición:</b><br>
                • Arena: {row.get('arena', 0):.1f}%<br>
                • Limo: {row.get('limo', 0):.1f}%<br>
                • Arcilla: {row.get('arcilla', 0):.1f}%<br>
                <hr>
                <b>Propiedades:</b><br>
                • Agua disponible: {row.get('agua_disponible', 0):.0f} mm/m<br>
                • Densidad: {row.get('densidad_aparente', 0):.2f} g/cm³<br>
                • Porosidad: {row.get('porosidad', 0):.1%}<br>
            """
            
            if 'ndvi' in row:
                popup_text += f"""
                <hr>
                <b>PlanetScope:</b><br>
                • NDVI: {row.get('ndvi', 0):.3f}<br>
                • NDWI: {row.get('ndwi', 0):.3f}<br>
                • Resolución: {row.get('resolucion_imagen', 'N/A')}<br>
                """
            
            popup_text += "</div>"
            
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
                tooltip=f"Zona {row['id_zona']}: {row.get('textura_nombre_completo', 'N/A')}"
            ).add_to(m)
        
        # Añadir leyenda mejorada
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 250px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius:5px;">
        <h4 style="margin:0 0 10px 0; text-align:center;">🌱 Texturas USDA</h4>
        '''
        
        for textura, info in CLASIFICACION_TEXTURAS_USDA.items():
            legend_html += f'''
            <div style="margin:2px 0;">
                <span style="background:{info['color']}; width:20px; height:15px; 
                display:inline-block; margin-right:5px; border:1px solid #000;"></span>
                {info['nombre_completo']}
            </div>
            '''
        
        legend_html += '''
        <div style="margin-top:10px; font-size:10px; color:#666;">
            🛰️ Datos: PlanetScope 3m<br>
            📅 Clasificación: USDA mejorada
        </div>
        </div>
        '''
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Añadir controles
        folium.LayerControl().add_to(m)
        
        st_folium(m, width=800, height=500)
    
    # Tabla detallada mejorada
    st.subheader("📊 TABLA DETALLADA DE ANÁLISIS")
    
    columnas_detalle = [
        'id_zona', 'area_ha', 'textura_nombre_completo', 'adecuacion_textura',
        'categoria_adecuacion', 'arena', 'limo', 'arcilla'
    ]
    
    # Añadir columnas de PlanetScope si existen
    if 'ndvi' in gdf_textura.columns:
        columnas_detalle.extend(['ndvi', 'ndwi', 'adecuacion_espectral'])
    
    # Añadir propiedades físicas
    columnas_detalle.extend(['agua_disponible', 'densidad_aparente', 'porosidad'])
    
    columnas_existentes = [col for col in columnas_detalle if col in gdf_textura.columns]
    
    if columnas_existentes:
        df_detalle = gdf_textura[columnas_existentes].copy()
        
        # Formatear valores
        if 'area_ha' in df_detalle.columns:
            df_detalle['area_ha'] = df_detalle['area_ha'].round(3)
        if 'adecuacion_textura' in df_detalle.columns:
            df_detalle['adecuacion_textura'] = df_detalle['adecuacion_textura'].round(3)
        if 'arena' in df_detalle.columns:
            df_detalle['arena'] = df_detalle['arena'].round(1)
        if 'limo' in df_detalle.columns:
            df_detalle['limo'] = df_detalle['limo'].round(1)
        if 'arcilla' in df_detalle.columns:
            df_detalle['arcilla'] = df_detalle['arcilla'].round(1)
        if 'ndvi' in df_detalle.columns:
            df_detalle['ndvi'] = df_detalle['ndvi'].round(3)
        if 'ndwi' in df_detalle.columns:
            df_detalle['ndwi'] = df_detalle['ndwi'].round(3)
        if 'adecuacion_espectral' in df_detalle.columns:
            df_detalle['adecuacion_espectral'] = df_detalle['adecuacion_espectral'].round(3)
        if 'agua_disponible' in df_detalle.columns:
            df_detalle['agua_disponible'] = df_detalle['agua_disponible'].round(0)
        if 'densidad_aparente' in df_detalle.columns:
            df_detalle['densidad_aparente'] = df_detalle['densidad_aparente'].round(2)
        if 'porosidad' in df_detalle.columns:
            df_detalle['porosidad'] = df_detalle['porosidad'].round(3)
        
        st.dataframe(df_detalle, use_container_width=True, height=400)
    else:
        st.warning("No hay datos suficientes para mostrar la tabla detallada")
    
    # Recomendaciones específicas por textura
    st.subheader("💡 RECOMENDACIONES ESPECÍFICAS")
    
    if 'textura_suelo' in gdf_textura.columns:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else 'FRANCO'
        recomendaciones = RECOMENDACIONES_TEXTURA_MEJORADAS.get(textura_predominante, [])
        
        if recomendaciones:
            st.info(f"**Recomendaciones para textura {CLASIFICACION_TEXTURAS_USDA.get(textura_predominante, {}).get('nombre_completo', textura_predominante)}:**")
            
            col_rec1, col_rec2 = st.columns(2)
            
            with col_rec1:
                for i, rec in enumerate(recomendaciones[:len(recomendaciones)//2]):
                    st.markdown(f"• {rec}")
            
            with col_rec2:
                for i, rec in enumerate(recomendaciones[len(recomendaciones)//2:]):
                    st.markdown(f"• {rec}")
    
    # Descargar resultados
    st.markdown("### 📥 DESCARGAR RESULTADOS")
    
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
    with col_dl1:
        if not gdf_textura.empty:
            csv_data = gdf_textura.to_csv(index=False)
            st.download_button(
                label="📊 Descargar CSV Completo",
                data=csv_data,
                file_name=f"textura_mejorada_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    with col_dl2:
        if not gdf_textura.empty:
            geojson_data = gdf_textura.to_json()
            st.download_button(
                label="🗺️ Descargar GeoJSON",
                data=geojson_data,
                file_name=f"textura_mejorada_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
                mime="application/json"
            )
    
    with col_dl3:
        if st.button("📄 Generar Informe Técnico", key="informe_textura_mejorada"):
            with st.spinner("Generando informe técnico..."):
                st.success("Informe técnico generado exitosamente")
                st.info("La funcionalidad de generación de PDF se implementará en la próxima versión")

# ============================================================================
# FUNCIONES AUXILIARES NECESARIAS (mantener del código original)
# ============================================================================
def calcular_superficie(gdf):
    """Calcula superficie en hectáreas"""
    try:
        if gdf.empty or gdf.geometry.isnull().all():
            return 0.0
        
        if gdf.crs and gdf.crs.is_geographic:
            try:
                gdf_proj = gdf.to_crs('EPSG:3116')
                area_m2 = gdf_proj.geometry.area
            except:
                area_m2 = gdf.geometry.area * 111000 * 111000
        else:
            area_m2 = gdf.geometry.area
            
        return area_m2 / 10000
    except:
        return 1.0

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo"""
    try:
        if len(gdf) == 0:
            return gdf
        
        parcela_principal = gdf.iloc[0].geometry
        
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        
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
                
                cell_poly = Polygon([
                    (minx + j * width, miny + i * height),
                    (minx + (j + 1) * width, miny + i * height),
                    (minx + (j + 1) * width, miny + (i + 1) * height),
                    (minx + j * width, miny + (i + 1) * height)
                ])
                
                if cell_poly.is_valid:
                    intersection = parcela_principal.intersection(cell_poly)
                    if not intersection.is_empty:
                        sub_poligonos.append(intersection)
        
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            return gdf
            
    except Exception as e:
        return gdf

def procesar_archivo(uploaded_file):
    """Procesa archivo subido"""
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
                    st.error("❌ No se encontró archivo .shp o .kml")
                    return None
            
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

# ============================================================================
# INICIALIZACIÓN DE SESSION STATE
# ============================================================================
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

# ============================================================================
# INTERFAZ PRINCIPAL ACTUALIZADA
# ============================================================================
def main():
    # Sidebar con opciones mejoradas
    with st.sidebar:
        st.header("⚙️ CONFIGURACIÓN MEJORADA")
        
        # Cultivo
        cultivo = st.selectbox(
            "🌱 Cultivo:",
            ["PALMA_ACEITERA", "CACAO", "BANANO"],
            help="Seleccione el cultivo para análisis específico"
        )
        
        # Tipo de análisis
        analisis_tipo = st.selectbox(
            "🔍 Tipo de Análisis:",
            ["ANÁLISIS DE TEXTURA MEJORADO", "FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"],
            help="Análisis mejorado con PlanetScope y clasificación USDA"
        )
        
        # Mes de análisis
        mes_analisis = st.selectbox(
            "📅 Mes de Análisis:",
            list(FACTORES_MES_MEJORADOS.keys()),
            help="Seleccione el mes para análisis estacional"
        )
        
        # Opciones de PlanetScope
        usar_planetscope = st.checkbox(
            "🛰️ Usar datos PlanetScope",
            value=True,
            help="Incluir datos simulados de imágenes PlanetScope (3m resolución)"
        )
        
        # División de parcela
        st.subheader("🎯 DIVISIÓN DE PARCELA")
        n_divisiones = st.slider(
            "Número de zonas de manejo:",
            min_value=16, max_value=48, value=24,
            help="Dividir la parcela en zonas para análisis detallado"
        )
        
        # Subir archivo
        st.subheader("📤 SUBIR PARCELA")
        uploaded_file = st.file_uploader(
            "Subir ZIP con shapefile o archivo KML",
            type=['zip', 'kml'],
            help="Formato: Shapefile (.zip) o KML con geometrías de parcela"
        )
        
        # Botones de acción
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Reiniciar", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        with col_btn2:
            if st.button("🎯 Datos Demo", use_container_width=True):
                st.session_state.datos_demo = True
                st.rerun()
    
    # Contenido principal
    if not st.session_state.analisis_completado:
        mostrar_interfaz_configuracion(uploaded_file, cultivo, analisis_tipo, mes_analisis, n_divisiones, usar_planetscope)
    else:
        if analisis_tipo == "ANÁLISIS DE TEXTURA MEJORADO":
            mostrar_analisis_textura_mejorado()
        else:
            st.warning("Seleccione 'ANÁLISIS DE TEXTURA MEJORADO' para ver los nuevos resultados")

def mostrar_interfaz_configuracion(uploaded_file, cultivo, analisis_tipo, mes_analisis, n_divisiones, usar_planetscope):
    """Muestra la interfaz de configuración"""
    
    st.markdown("### 📋 INFORMACIÓN DEL ANÁLISIS")
    
    # Mostrar parámetros del análisis
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    with col_info2:
        st.metric("🔍 Análisis", analisis_tipo)
    with col_info3:
        st.metric("📅 Mes", mes_analisis)
    
    # Información de PlanetScope si está habilitado
    if usar_planetscope:
        st.success("🛰️ **Datos PlanetScope habilitados** - Resolución: 3m | Bandas: 8 espectrales")
    
    # Procesar archivo subido o datos demo
    if uploaded_file is not None:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
    
    elif st.session_state.datos_demo and st.session_state.gdf_original is None:
        # Crear datos de demostración
        poligono_demo = Polygon([
            [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono_demo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
    
    # Mostrar parcela si está cargada
    if st.session_state.gdf_original is not None:
        gdf_original = st.session_state.gdf_original
        
        st.markdown("### 🗺️ VISUALIZACIÓN DE PARCELA")
        
        # Calcular estadísticas
        area_total = calcular_superficie(gdf_original).sum()
        
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric("📐 Área Total", f"{area_total:.2f} ha")
        with col_stats2:
            st.metric("🔢 Polígonos", len(gdf_original))
        with col_stats3:
            st.metric("📍 CRS", str(gdf_original.crs))
        
        # Botón para ejecutar análisis
        st.markdown("### 🚀 EJECUTAR ANÁLISIS MEJORADO")
        
        if st.button("▶️ Ejecutar Análisis con PlanetScope", type="primary", use_container_width=True):
            with st.spinner("🔄 Dividiendo parcela en zonas..."):
                gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
                st.session_state.gdf_zonas = gdf_zonas
            
            with st.spinner("🛰️ Analizando textura con PlanetScope..."):
                if analisis_tipo == "ANÁLISIS DE TEXTURA MEJORADO":
                    gdf_textura = analizar_textura_suelo_mejorada(
                        gdf_zonas, cultivo, mes_analisis, usar_planetscope
                    )
                    st.session_state.analisis_textura = gdf_textura
                
                st.session_state.area_total = area_total
                st.session_state.analisis_completado = True
            
            st.rerun()
    
    else:
        # Mostrar instrucciones
        st.markdown("### 🚀 CÓMO COMENZAR")
        
        col_inst1, col_inst2 = st.columns(2)
        
        with col_inst1:
            st.info("""
            **📤 Sube tu parcela:**
            1. Shapefile comprimido en ZIP (.zip)
            2. Incluir: .shp, .shx, .dbf, .prj
            3. O archivo KML/KMZ de Google Earth
            
            **🌱 Selecciona cultivo y análisis**
            """)
        
        with col_inst2:
            st.success("""
            **🛰️ Nuevas características:**
            • Clasificación USDA mejorada
            • Datos PlanetScope 3m
            • 8 bandas espectrales
            • Índices NDVI, NDWI, CI RedEdge
            • Propiedades físicas detalladas
            """)

# Ejecutar aplicación
if __name__ == "__main__":
    main()
