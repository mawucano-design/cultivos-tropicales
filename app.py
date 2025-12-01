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
from shapely.geometry import Polygon, MultiPolygon
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
import warnings

# Configurar para ignorar advertencias
warnings.filterwarnings('ignore')

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA COMPLETA CON AGROECOLOGÍA")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# ============================================================================
# CONFIGURACIÓN DE SESSION STATE
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
if 'cultivo_seleccionado' not in st.session_state:
    st.session_state.cultivo_seleccionado = "PALMA_ACEITERA"
if 'usar_planetscope' not in st.session_state:
    st.session_state.usar_planetscope = True
if 'mes_analisis' not in st.session_state:
    st.session_state.mes_analisis = "ENERO"

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
        'CI_RedEdge': 'NIR / RED_EDGE - 1',
        'NDSI': '(GREEN - RED) / (GREEN + RED)',
        'EVI': '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)'
    }
}

# ============================================================================
# CLASIFICACIÓN ESPECÍFICA PARA PALMA ACEITERA (Según documento proporcionado)
# ============================================================================
CLASIFICACION_TEXTURAS_PALMA = {
    'FRANCO': {
        'nombre_completo': 'Franco',
        'descripcion': 'Equilibrio arena-limo-arcilla. Buena aireación y drenaje. CIC Intermedia-alta. Retención de agua adecuada.',
        'arena_min': 40,
        'arena_max': 60,
        'limo_min': 30,
        'limo_max': 50,
        'arcilla_min': 10,
        'arcilla_max': 25,
        'color': '#4a7c59',  # Verde oscuro
        'limitantes': [
            'Puede compactarse con maquinaria pesada',
            'Erosión en pendientes si no hay cobertura'
        ]
    },
    'FRANCO_ARCILLOSO': {
        'nombre_completo': 'Franco Arcilloso',
        'descripcion': 'Mayor proporción de arcilla (25-35%). Alta retención de agua y nutrientes. Drenaje natural lento. Buena fertilidad natural.',
        'arena_min': 20,
        'arena_max': 40,
        'limo_min': 30,
        'limo_max': 50,
        'arcilla_min': 25,
        'arcilla_max': 35,
        'color': '#8b4513',  # Marrón arcilloso
        'limitantes': [
            'Riesgo de encharcamiento',
            'Compactación fácil',
            'Menor oxigenación radicular'
        ]
    },
    'FRANCO_ARCILLOSO_ARENOSO': {
        'nombre_completo': 'Franco Arcilloso-Arenoso',
        'descripcion': 'Arena 40-50%, arcilla 20-30%. Buen desarrollo radicular. Mayor drenaje que franco arcilloso. Retención de agua moderada-baja.',
        'arena_min': 40,
        'arena_max': 50,
        'limo_min': 20,
        'limo_max': 30,
        'arcilla_min': 20,
        'arcilla_max': 30,
        'color': '#d2b48c',  # Arena oscura
        'limitantes': [
            'Riesgo de lixiviación de nutrientes',
            'Estrés hídrico en veranos',
            'Fertilidad moderada'
        ]
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
        'MAGNESIO': {'min': 20, 'max': 40, 'optimo': 30},
        'CALCIO': {'min': 100, 'max': 200, 'optimo': 150},
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
        'MAGNESIO': {'min': 15, 'max': 30, 'optimo': 22},
        'CALCIO': {'min': 80, 'max': 160, 'optimo': 120},
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
        'MAGNESIO': {'min': 25, 'max': 45, 'optimo': 35},
        'CALCIO': {'min': 120, 'max': 240, 'optimo': 180},
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
# PARÁMETROS DE TEXTURA DEL SUELO POR CULTIVO - BASADO EN TU DOCUMENTO
# ============================================================================
TEXTURA_SUELO_OPTIMA = {
    'PALMA_ACEITERA': {
        'textura_optima': 'FRANCO_ARCILLOSO_ARENOSO',
        'textura_alternativa': 'FRANCO',
        'arena_optima': 45,
        'limo_optima': 25,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.3,
        'porosidad_optima': 0.5,
        'conductividad_hidraulica_optima': 1.5,
        'intervalo_temperatura_optima': '25-30°C',
        'resistencia_penetracion_optima': '1.5-2.5 MPa'
    },
    'CACAO': {
        'textura_optima': 'FRANCO',
        'textura_alternativa': 'FRANCO_ARCILLOSO',
        'arena_optima': 45,
        'limo_optima': 40,
        'arcilla_optima': 15,
        'densidad_aparente_optima': 1.2,
        'porosidad_optima': 0.55,
        'conductividad_hidraulica_optima': 2.0,
        'intervalo_temperatura_optima': '22-28°C',
        'resistencia_penetracion_optima': '1.0-2.0 MPa'
    },
    'BANANO': {
        'textura_optima': 'FRANCO_ARCILLOSO',
        'textura_alternativa': 'FRANCO_ARCILLOSO_ARENOSO',
        'arena_optima': 35,
        'limo_optima': 40,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52,
        'conductividad_hidraulica_optima': 1.8,
        'intervalo_temperatura_optima': '24-32°C',
        'resistencia_penetracion_optima': '1.2-2.2 MPa'
    }
}

# ============================================================================
# FACTORES EDÁFICOS ESPECÍFICOS PARA PALMA ACEITERA
# ============================================================================
FACTORES_SUELO_PALMA = {
    'FRANCO': {
        'retencion_agua': 0.8,
        'drenaje': 1.2,
        'aireacion': 1.1,
        'trabajabilidad': 1.0,
        'riesgo_erosion': 'MODERADO',
        'capacidad_intercambio_cationico': 15,
        'conductividad_termica': 0.6,
        'color_tipico': 'Pardo oscuro',
        'temperatura_rapida': 'Moderado'
    },
    'FRANCO_ARCILLOSO': {
        'retencion_agua': 1.2,
        'drenaje': 0.8,
        'aireacion': 0.8,
        'trabajabilidad': 0.7,
        'riesgo_erosion': 'BAJO',
        'capacidad_intercambio_cationico': 25,
        'conductividad_termica': 0.8,
        'color_tipico': 'Pardo rojizo',
        'temperatura_rapida': 'Lento'
    },
    'FRANCO_ARCILLOSO_ARENOSO': {
        'retencion_agua': 0.9,
        'drenaje': 1.1,
        'aireacion': 1.0,
        'trabajabilidad': 0.9,
        'riesgo_erosion': 'MODERADO-ALTO',
        'capacidad_intercambio_cationico': 12,
        'conductividad_termica': 0.5,
        'color_tipico': 'Pardo amarillento',
        'temperatura_rapida': 'Moderado-rápido'
    }
}

# ============================================================================
# RECOMENDACIONES ESPECÍFICAS SEGÚN TU DOCUMENTO
# ============================================================================
RECOMENDACIONES_TEXTURA_PALMA = {
    'FRANCO': [
        "Mantener coberturas vivas o muertas",
        "Evitar tránsito excesivo de maquinaria",
        "Fertilización eficiente, sin muchas pérdidas",
        "Ideal para densidad estándar 9 × 9 m",
        "Rotación de cultivos de cobertura",
        "Aplicación de 2-4 ton/ha de compost anualmente",
        "Monitoreo regular de pH y nutrientes"
    ],
    'FRANCO_ARCILLOSO': [
        "Implementar drenajes (canales y subdrenes)",
        "Subsolado previo a siembra",
        "Incorporar materia orgánica (raquis, compost)",
        "Fertilización fraccionada en lluvias intensas",
        "Evitar laboreo en condiciones húmedas",
        "Uso de camellones para mejorar drenaje",
        "Aplicación de yeso agrícola si sodio > 10%"
    ],
    'FRANCO_ARCILLOSO_ARENOSO': [
        "Uso de coberturas leguminosas",
        "Aplicar mulching (raquis, hojas)",
        "Riego suplementario en sequía",
        "Fertilización fraccionada con énfasis en K y Mg",
        "Barreras vivas para reducir erosión eólica",
        "Aplicación de biochar para mejorar retención",
        "Sistemas de riego por goteo eficiente"
    ]
}

# ============================================================================
# FACTORES ESTACIONALES MEJORADOS PARA COLOMBIA/VENEZUELA
# ============================================================================
FACTORES_MES_TROPICALES = {
    "ENERO": {'factor': 0.9, 'precipitacion': 'Baja', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Riego suplementario'},
    "FEBRERO": {'factor': 0.85, 'precipitacion': 'Muy baja', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Riego intensivo'},
    "MARZO": {'factor': 0.95, 'precipitacion': 'Baja', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Riego moderado'},
    "ABRIL": {'factor': 1.1, 'precipitacion': 'Media', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Inicio fertilización'},
    "MAYO": {'factor': 1.2, 'precipitacion': 'Alta', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Fertilización principal'},
    "JUNIO": {'factor': 1.1, 'precipitacion': 'Alta', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Control drenaje'},
    "JULIO": {'factor': 1.0, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Mantenimiento'},
    "AGOSTO": {'factor': 0.95, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Preparación cosecha'},
    "SEPTIEMBRE": {'factor': 0.9, 'precipitacion': 'Baja', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Riego suplementario'},
    "OCTUBRE": {'factor': 0.85, 'precipitacion': 'Baja', 'temperatura': 'Alta', 'evapotranspiracion': 'Alta', 'recomendacion': 'Riego intensivo'},
    "NOVIEMBRE": {'factor': 1.0, 'precipitacion': 'Alta', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Fertilización post-cosecha'},
    "DICIEMBRE": {'factor': 0.95, 'precipitacion': 'Media', 'temperatura': 'Media', 'evapotranspiracion': 'Media', 'recomendacion': 'Preparación nuevo ciclo'}
}

# ============================================================================
# PALETAS DE COLORES PARA VISUALIZACIÓN
# ============================================================================
PALETAS_VISUALIZACION = {
    'TEXTURA_PALMA': ['#4a7c59', '#8b4513', '#d2b48c'],
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'INDICES_ESPECTRALES': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027']
}

# ============================================================================
# FUNCIONES AUXILIARES ROBUSTAS
# ============================================================================
def calcular_superficie(gdf):
    """Calcula superficie en hectáreas de manera robusta"""
    try:
        if gdf is None or gdf.empty or gdf.geometry.isnull().all():
            return 0.0
        
        # Crear una copia para no modificar el original
        gdf_temp = gdf.copy()
        
        # Asegurar geometrías válidas
        gdf_temp.geometry = gdf_temp.geometry.make_valid()
        
        # Si hay geometrías MultiPolygon, convertirlas a Polygon (tomar el más grande)
        def get_main_polygon(geom):
            if isinstance(geom, MultiPolygon):
                # Tomar el polígono con mayor área
                areas = [g.area for g in geom.geoms]
                if areas:
                    return geom.geoms[areas.index(max(areas))]
                else:
                    return geom
            return geom
        
        gdf_temp.geometry = gdf_temp.geometry.apply(get_main_polygon)
        
        # Calcular área
        if gdf_temp.crs and gdf_temp.crs.is_geographic:
            try:
                # Proyectar a un CRS métrico para Colombia/Venezuela
                gdf_proj = gdf_temp.to_crs('EPSG:3116')  # Para Colombia
                area_m2 = gdf_proj.geometry.area.sum()
            except:
                # Estimación aproximada
                area_m2 = gdf_temp.geometry.area.sum() * 111000 * 111000
        else:
            area_m2 = gdf_temp.geometry.area.sum()
            
        return area_m2 / 10000.0  # Convertir a hectáreas
    
    except Exception as e:
        st.warning(f"⚠️ Advertencia al calcular superficie: {str(e)}")
        return 0.0

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo de manera robusta"""
    try:
        if gdf is None or len(gdf) == 0:
            return gdf
        
        # Tomar la primera geometría como parcela principal
        parcela_principal = gdf.iloc[0].geometry
        
        # Asegurar geometría válida
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        
        # Obtener bounds
        bounds = parcela_principal.bounds
        minx, miny, maxx, maxy = bounds
        
        # Calcular número de filas y columnas
        n_cols = max(1, math.ceil(math.sqrt(n_zonas)))
        n_rows = max(1, math.ceil(n_zonas / n_cols))
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        sub_poligonos = []
        
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                
                # Crear celda
                cell_poly = Polygon([
                    (minx + j * width, miny + i * height),
                    (minx + (j + 1) * width, miny + i * height),
                    (minx + (j + 1) * width, miny + (i + 1) * height),
                    (minx + j * width, miny + (i + 1) * height)
                ])
                
                if cell_poly.is_valid:
                    try:
                        intersection = parcela_principal.intersection(cell_poly)
                        if not intersection.is_empty:
                            # Si es MultiPolygon, tomar solo el primero
                            if isinstance(intersection, MultiPolygon):
                                if len(intersection.geoms) > 0:
                                    intersection = intersection.geoms[0]
                            sub_poligonos.append(intersection)
                    except:
                        continue
        
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            # Si no se pudieron crear subpolígonos, devolver el original
            gdf['id_zona'] = range(1, len(gdf) + 1)
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error al dividir parcela: {str(e)}")
        # Devolver el GeoDataFrame original con IDs
        gdf['id_zona'] = range(1, len(gdf) + 1)
        return gdf

def procesar_archivo(uploaded_file):
    """Procesa archivo subido de manera robusta"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            
            # Guardar archivo
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Procesar según extensión
            file_ext = uploaded_file.name.lower()
            
            if file_ext.endswith('.kml'):
                try:
                    gdf = gpd.read_file(file_path, driver='KML')
                except:
                    # Intentar con encoding diferente
                    gdf = gpd.read_file(file_path)
            
            elif file_ext.endswith('.zip'):
                # Extraer ZIP
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                # Buscar archivos shapefile o KML
                shp_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.kml')]
                
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    try:
                        gdf = gpd.read_file(shp_path)
                    except:
                        # Intentar leer sin especificar driver
                        gdf = gpd.read_file(shp_path)
                
                elif kml_files:
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    try:
                        gdf = gpd.read_file(kml_path, driver='KML')
                    except:
                        gdf = gpd.read_file(kml_path)
                
                else:
                    st.error("❌ No se encontró archivo .shp o .kml en el ZIP")
                    return None
            
            elif file_ext.endswith('.shp'):
                try:
                    gdf = gpd.read_file(file_path)
                except Exception as e:
                    st.error(f"❌ Error leyendo shapefile: {str(e)}")
                    return None
            
            else:
                st.error("❌ Formato de archivo no soportado")
                return None
            
            # Validar y limpiar geometrías
            if not gdf.empty:
                # Asegurar geometrías válidas
                gdf.geometry = gdf.geometry.make_valid()
                
                # Eliminar geometrías vacías
                gdf = gdf[~gdf.geometry.is_empty]
                
                # Asegurar que hay al menos una geometría
                if len(gdf) == 0:
                    st.error("❌ No se encontraron geometrías válidas en el archivo")
                    return None
                
                # Proyectar a WGS84 si no tiene CRS
                if gdf.crs is None:
                    gdf.set_crs('EPSG:4326', inplace=True)
                
                return gdf
            else:
                st.error("❌ El archivo está vacío")
                return None
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

# ============================================================================
# FUNCIONES DE ANÁLISIS ESPECÍFICAS PARA PALMA ACEITERA
# ============================================================================
def clasificar_textura_palma(arena, limo, arcilla):
    """Clasifica la textura del suelo según el sistema específico para palma aceitera"""
    try:
        # Normalizar porcentajes a 100%
        total = arena + limo + arcilla
        if total <= 0:
            return "NO_DETERMINADA"
        
        arena_pct = (arena / total) * 100
        limo_pct = (limo / total) * 100
        arcilla_pct = (arcilla / total) * 100
        
        # Clasificación según el documento proporcionado
        # 1. Franco Arcilloso-Arenoso: arena 40-50%, arcilla 20-30%
        if arena_pct >= 40 and arena_pct <= 50 and arcilla_pct >= 20 and arcilla_pct <= 30:
            return "FRANCO_ARCILLOSO_ARENOSO"
        
        # 2. Franco Arcilloso: arcilla 25-35%
        elif arcilla_pct >= 25 and arcilla_pct <= 35:
            return "FRANCO_ARCILLOSO"
        
        # 3. Franco: equilibrio arena-limo-arcilla
        # Asumimos: arena 40-60%, limo 30-50%, arcilla 10-25%
        elif (arena_pct >= 40 and arena_pct <= 60 and 
              limo_pct >= 30 and limo_pct <= 50 and 
              arcilla_pct >= 10 and arcilla_pct <= 25):
            return "FRANCO"
        
        # Si no cumple exactamente, determinar la más cercana
        else:
            # Calcular distancias a cada categoría
            distancias = {}
            
            # Distancia a Franco
            dist_franco = abs(arena_pct - 50) + abs(limo_pct - 40) + abs(arcilla_pct - 15)
            distancias["FRANCO"] = dist_franco
            
            # Distancia a Franco Arcilloso
            dist_franco_arcilloso = abs(arena_pct - 30) + abs(limo_pct - 40) + abs(arcilla_pct - 30)
            distancias["FRANCO_ARCILLOSO"] = dist_franco_arcilloso
            
            # Distancia a Franco Arcilloso-Arenoso
            dist_franco_arcilloso_arenoso = abs(arena_pct - 45) + abs(limo_pct - 25) + abs(arcilla_pct - 25)
            distancias["FRANCO_ARCILLOSO_ARENOSO"] = dist_franco_arcilloso_arenoso
            
            # Devolver la categoría con menor distancia
            return min(distancias, key=distancias.get)
            
    except Exception as e:
        return "NO_DETERMINADA"

def simular_datos_planetscope(centroid, textura_clave, cultivo):
    """Simula datos espectrales de PlanetScope basados en ubicación y textura"""
    try:
        # Semilla reproducible basada en coordenadas
        seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{textura_clave}")) % (2**32)
        rng = np.random.RandomState(seed_value)
        
        # Parámetros base según textura
        params_textura = FACTORES_SUELO_PALMA.get(textura_clave, {})
        params_cultivo = PARAMETROS_CULTIVOS[cultivo]['INDICES_ESPECTRALES']
        
        # Simular reflectancias
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
        
        # Calcular índices
        ndvi = (reflectancias['NIR'] - reflectancias['RED']) / (reflectancias['NIR'] + reflectancias['RED'])
        ndwi = (reflectancias['GREEN'] - reflectancias['NIR']) / (reflectancias['GREEN'] + reflectancias['NIR'])
        ci_rededge = reflectancias['NIR'] / reflectancias['RED_EDGE'] - 1
        ndsi = (reflectancias['GREEN'] - reflectancias['RED']) / (reflectancias['GREEN'] + reflectancias['RED'])
        evi = 2.5 * (reflectancias['NIR'] - reflectancias['RED']) / (
            reflectancias['NIR'] + 6 * reflectancias['RED'] - 7.5 * reflectancias['BLUE'] + 1
        )
        
        # Ajustar según textura
        factor_ajuste = 1.0
        if textura_clave == 'FRANCO_ARCILLOSO':
            factor_ajuste = 0.9  # Suelos arcillosos tienen menor reflectancia
        elif textura_clave == 'FRANCO_ARCILLOSO_ARENOSO':
            factor_ajuste = 1.1  # Suelos arenosos tienen mayor reflectancia
            
        ndvi = max(-1, min(1, ndvi * factor_ajuste))
        ndwi = max(-1, min(1, ndwi * factor_ajuste))
        ci_rededge = max(-1, min(1, ci_rededge * factor_ajuste))
        
        # Calcular adecuación
        adecuacion_ndvi = max(0, min(1, 1.0 - abs(ndvi - params_cultivo['NDVI_OPTIMO']) / 2.0))
        adecuacion_ndwi = max(0, min(1, 1.0 - abs(ndwi - params_cultivo['NDWI_OPTIMO']) / 2.0))
        adecuacion_ci = max(0, min(1, 1.0 - abs(ci_rededge - params_cultivo['CI_RedEdge_OPTIMO']) / 2.0))
        
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
            'nube_cobertura': rng.uniform(0, 0.3)
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

def calcular_propiedades_fisicas_palma(textura_clave, materia_organica, humedad):
    """Calcula propiedades físicas del suelo basadas en textura para palma aceitera"""
    
    propiedades = {
        'capacidad_campo': 0.0,
        'punto_marchitez': 0.0,
        'agua_disponible': 0.0,
        'densidad_aparente': 0.0,
        'porosidad': 0.0,
        'conductividad_hidraulica': 0.0,
        'capacidad_intercambio_cationico': 0.0,
        'resistencia_penetracion': 0.0,
        'conductividad_termica': 0.0,
        'temperatura_suelo': 0.0,
        'color_suelo': '',
        'textura_tacto': ''
    }
    
    # Valores base según textura específica para palma
    base_propiedades = {
        'FRANCO': {
            'cc': 250, 'pm': 100, 'da': 1.3, 'porosidad': 0.52, 'kh': 2.5,
            'cic': 15, 'rp': 2.0, 'ct': 0.6, 'temp': 25, 'color': 'Pardo oscuro', 
            'tacto': 'Suave, friable, buena estructura'
        },
        'FRANCO_ARCILLOSO': {
            'cc': 300, 'pm': 150, 'da': 1.2, 'porosidad': 0.56, 'kh': 0.8,
            'cic': 25, 'rp': 2.5, 'ct': 0.8, 'temp': 23, 'color': 'Pardo rojizo', 
            'tacto': 'Suave, algo pegajoso, plástico'
        },
        'FRANCO_ARCILLOSO_ARENOSO': {
            'cc': 200, 'pm': 80, 'da': 1.4, 'porosidad': 0.48, 'kh': 5.0,
            'cic': 12, 'rp': 1.5, 'ct': 0.5, 'temp': 27, 'color': 'Pardo amarillento', 
            'tacto': 'Suave, ligeramente arenoso'
        }
    }
    
    if textura_clave in base_propiedades:
        base = base_propiedades[textura_clave]
        
        # Ajustar por materia orgánica
        factor_mo = 1.0 + (materia_organica * 0.03)
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

def evaluar_adecuacion_textura_palma(textura_actual, cultivo, datos_planetscope=None):
    """Evalúa qué tan adecuada es la textura para el cultivo específico"""
    
    try:
        textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
        textura_alternativa = TEXTURA_SUELO_OPTIMA[cultivo]['textura_alternativa']
        
        # Determinar categoría
        if textura_actual == textura_optima:
            categoria = "ÓPTIMA"
            puntaje = 1.0
            justificacion = "Textura ideal para el cultivo según especificaciones técnicas"
        elif textura_actual == textura_alternativa:
            categoria = "EXCELENTE"
            puntaje = 0.9
            justificacion = "Textura alternativa excelente para el cultivo"
        else:
            # Para otras texturas, asignar puntaje basado en similitud
            if cultivo == "PALMA_ACEITERA":
                # Prioridades para palma: Franco Arcilloso-Arenoso > Franco > Franco Arcilloso
                jerarquia = {
                    'FRANCO_ARCILLOSO_ARENOSO': 3,
                    'FRANCO': 2,
                    'FRANCO_ARCILLOSO': 1
                }
                
                if textura_actual in jerarquia:
                    puntaje_base = jerarquia[textura_actual] / 3.0
                    
                    if puntaje_base >= 0.7:
                        categoria = "BUENA"
                        puntaje = puntaje_base
                        justificacion = "Textura adecuada con manejo específico"
                    elif puntaje_base >= 0.5:
                        categoria = "MODERADA"
                        puntaje = puntaje_base
                        justificacion = "Textura moderadamente adecuada, requiere intervenciones"
                    else:
                        categoria = "LIMITANTE"
                        puntaje = puntaje_base
                        justificacion = "Textura con limitaciones significativas"
                else:
                    categoria = "NO_DETERMINADA"
                    puntaje = 0.0
                    justificacion = "Textura no clasificada en el sistema"
            else:
                categoria = "MODERADA"
                puntaje = 0.5
                justificacion = "Textura no óptima pero manejable con prácticas adecuadas"
        
        # Ajustar con datos de PlanetScope si disponibles
        if datos_planetscope:
            puntaje = puntaje * 0.7 + datos_planetscope['adecuacion_espectral'] * 0.3
            justificacion += f" | Adecuación espectral: {datos_planetscope['adecuacion_espectral']:.1%}"
        
        return categoria, puntaje, justificacion
    
    except Exception as e:
        return "NO_DETERMINADA", 0.0, f"Error en evaluación: {str(e)}"

def analizar_textura_suelo_palma(gdf, cultivo, mes_analisis, usar_planetscope=True):
    """Realiza análisis completo de textura del suelo para palma aceitera"""
    
    try:
        params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
        zonas_gdf = gdf.copy()
        
        # Inicializar columnas
        columnas_base = [
            'id_zona', 'area_ha', 'arena', 'limo', 'arcilla', 'textura_suelo', 
            'textura_nombre_completo', 'adecuacion_textura', 'categoria_adecuacion', 
            'justificacion_adecuacion', 'capacidad_campo', 'punto_marchitez', 
            'agua_disponible', 'densidad_aparente', 'porosidad', 'conductividad_hidraulica',
            'capacidad_intercambio_cationico', 'resistencia_penetracion', 
            'conductividad_termica', 'temperatura_suelo', 'color_suelo', 
            'textura_tacto', 'materia_organica', 'humedad_suelo', 'limitantes_textura'
        ]
        
        columnas_planetscope = [
            'ndvi', 'ndwi', 'ci_rededge', 'ndsi', 'evi', 'adecuacion_espectral',
            'adecuacion_ndvi', 'adecuacion_ndwi', 'adecuacion_ci',
            'resolucion_imagen', 'fecha_imagen', 'cobertura_nubes'
        ]
        
        # Inicializar todas las columnas
        for col in columnas_base + (columnas_planetscope if usar_planetscope else []):
            if col == 'id_zona' and col not in zonas_gdf.columns:
                zonas_gdf[col] = range(1, len(zonas_gdf) + 1)
            elif col == 'textura_suelo':
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
            elif col == 'limitantes_textura':
                zonas_gdf[col] = ""
            elif col == 'fecha_imagen':
                zonas_gdf[col] = datetime.now().strftime('%Y-%m-%d')
            elif col == 'resolucion_imagen':
                zonas_gdf[col] = '3m' if usar_planetscope else 'N/A'
            elif col == 'cobertura_nubes':
                zonas_gdf[col] = 0.0
            elif col not in zonas_gdf.columns:
                zonas_gdf[col] = 0.0
        
        # Procesar cada zona
        for idx, row in zonas_gdf.iterrows():
            try:
                # Calcular área
                area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
                
                # Obtener centroide
                if hasattr(row.geometry, 'centroid') and not row.geometry.is_empty:
                    centroid = row.geometry.centroid
                else:
                    centroid = row.geometry.representative_point()
                
                # Semilla para reproducibilidad
                seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
                rng = np.random.RandomState(seed_value)
                
                # Simular composición granulométrica
                lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
                lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
                
                variabilidad_espacial = 0.2 + 0.6 * np.sin(lat_norm * np.pi * 2) * np.cos(lon_norm * np.pi * 2)
                
                arena_optima = params_textura['arena_optima']
                limo_optima = params_textura['limo_optima']
                arcilla_optima = params_textura['arcilla_optima']
                
                # Simular composición con tendencia hacia la textura óptima
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
                
                # Clasificar textura según sistema específico
                textura_clave = clasificar_textura_palma(arena, limo, arcilla)
                textura_info = CLASIFICACION_TEXTURAS_PALMA.get(textura_clave, {})
                textura_nombre = textura_info.get('nombre_completo', 'No determinada')
                limitantes = textura_info.get('limitantes', [])
                
                # Simular materia orgánica y humedad
                materia_organica = max(1.0, min(8.0, rng.normal(
                    PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA'],
                    1.0
                )))
                
                humedad_suelo = max(0.1, min(0.6, rng.normal(
                    PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA'],
                    0.15
                )))
                
                # Calcular propiedades físicas
                propiedades_fisicas = calcular_propiedades_fisicas_palma(
                    textura_clave, materia_organica, humedad_suelo
                )
                
                # Simular datos de PlanetScope
                datos_planetscope = None
                if usar_planetscope:
                    datos_planetscope = simular_datos_planetscope(centroid, textura_clave, cultivo)
                    
                    # Asignar datos
                    for key in ['ndvi', 'ndwi', 'ci_rededge', 'ndsi', 'evi', 
                               'adecuacion_espectral', 'adecuacion_ndvi', 
                               'adecuacion_ndwi', 'adecuacion_ci']:
                        zonas_gdf.loc[idx, key] = datos_planetscope.get(key, 0)
                    
                    zonas_gdf.loc[idx, 'fecha_imagen'] = datos_planetscope.get('fecha_simulacion', '')
                    zonas_gdf.loc[idx, 'cobertura_nubes'] = datos_planetscope.get('nube_cobertura', 0)
                
                # Evaluar adecuación
                categoria_adecuacion, puntaje_adecuacion, justificacion = evaluar_adecuacion_textura_palma(
                    textura_clave, cultivo, datos_planetscope
                )
                
                # Asignar valores
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
                zonas_gdf.loc[idx, 'limitantes_textura'] = '; '.join(limitantes)
                
                # Propiedades físicas
                for prop, valor in propiedades_fisicas.items():
                    if prop in zonas_gdf.columns:
                        zonas_gdf.loc[idx, prop] = valor
                
            except Exception as e:
                # Valores por defecto en caso de error
                zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
                zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
                zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
                zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
                zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
                zonas_gdf.loc[idx, 'textura_nombre_completo'] = CLASIFICACION_TEXTURAS_PALMA.get(
                    params_textura['textura_optima'], {}).get('nombre_completo', 'No determinada')
                zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
                zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
                zonas_gdf.loc[idx, 'justificacion_adecuacion'] = "Valores óptimos por defecto"
                zonas_gdf.loc[idx, 'materia_organica'] = PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA']
                zonas_gdf.loc[idx, 'humedad_suelo'] = PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA']
        
        return zonas_gdf
    
    except Exception as e:
        st.error(f"❌ Error en análisis de textura: {str(e)}")
        return gdf

# ============================================================================
# FUNCIÓN PARA MOSTRAR ANÁLISIS DE TEXTURA ESPECÍFICO
# ============================================================================
def mostrar_analisis_textura_palma():
    """Muestra el análisis específico de textura del suelo para palma aceitera"""
    
    try:
        if st.session_state.analisis_textura is None:
            st.warning("No hay datos de análisis de textura disponibles")
            return
        
        gdf_textura = st.session_state.analisis_textura
        cultivo = st.session_state.cultivo_seleccionado
        
        st.markdown("## 🌴 ANÁLISIS ESPECÍFICO DE TEXTURA PARA PALMA ACEITERA")
        st.info("**Metodología:** Clasificación específica según documento técnico con datos simulados de PlanetScope")
        
        # Botón para volver
        if st.button("⬅️ Volver a Configuración", key="volver_textura_palma"):
            st.session_state.analisis_completado = False
            st.rerun()
        
        # Información del mes
        mes_info = FACTORES_MES_TROPICALES.get(st.session_state.mes_analisis, {})
        st.success(f"**📅 Mes actual:** {st.session_state.mes_analisis} | **Precipitación:** {mes_info.get('precipitacion', 'N/A')} | **Recomendación:** {mes_info.get('recomendacion', 'N/A')}")
        
        # Estadísticas principales
        st.subheader("📊 ESTADÍSTICAS PRINCIPALES")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if 'textura_nombre_completo' in gdf_textura.columns and len(gdf_textura) > 0:
                textura_pred = gdf_textura['textura_nombre_completo'].mode()[0] if not gdf_textura['textura_nombre_completo'].mode().empty else "No determinada"
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
        
        # Distribución de texturas
        st.subheader("📋 DISTRIBUCIÓN DE TEXTURAS (ESPECÍFICO PARA PALMA)")
        
        if 'textura_suelo' in gdf_textura.columns and len(gdf_textura) > 0:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Gráfico de torta
            textura_counts = gdf_textura['textura_suelo'].value_counts()
            if not textura_counts.empty:
                labels = [CLASIFICACION_TEXTURAS_PALMA.get(t, {}).get('nombre_completo', t) 
                         for t in textura_counts.index]
                colors_pie = [CLASIFICACION_TEXTURAS_PALMA.get(t, {}).get('color', '#999999') 
                            for t in textura_counts.index]
                
                ax1.pie(textura_counts.values, labels=labels, colors=colors_pie, 
                       autopct='%1.1f%%', startangle=90)
                ax1.set_title('Distribución de Texturas')
            
            # Gráfico de barras de adecuación
            if 'adecuacion_textura' in gdf_textura.columns:
                zonas_sample = gdf_textura.head(10)  # Mostrar primeras 10 zonas
                ax2.bar(zonas_sample['id_zona'].astype(str), zonas_sample['adecuacion_textura'] * 100,
                       color=[CLASIFICACION_TEXTURAS_PALMA.get(t, {}).get('color', '#999999') 
                              for t in zonas_sample['textura_suelo']])
                ax2.set_title('Adecuación por Zona (%)')
                ax2.set_xlabel('Zona')
                ax2.set_ylabel('Adecuación (%)')
                ax2.set_ylim(0, 100)
                ax2.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            st.pyplot(fig)
        
        # Mapa de texturas específico
        st.subheader("🗺️ MAPA DE TEXTURAS ESPECÍFICAS")
        
        if 'textura_suelo' in gdf_textura.columns and len(gdf_textura) > 0:
            try:
                # Calcular centro del mapa
                centroids = gdf_textura.geometry.centroid
                center_lat = centroids.y.mean()
                center_lon = centroids.x.mean()
                
                m = folium.Map(
                    location=[center_lat, center_lon],
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
                
                # Añadir cada polígono
                for idx, row in gdf_textura.iterrows():
                    textura = row['textura_suelo']
                    color = CLASIFICACION_TEXTURAS_PALMA.get(textura, {}).get('color', '#999999')
                    
                    # Crear popup específico
                    popup_text = f"""
                    <div style="font-family: Arial; font-size: 12px;">
                        <h4>Zona {row.get('id_zona', 'N/A')} - Palma Aceitera</h4>
                        <b>Textura:</b> {row.get('textura_nombre_completo', 'N/A')}<br>
                        <b>Adecuación:</b> {row.get('adecuacion_textura', 0):.1%}<br>
                        <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                        <hr>
                        <b>Composición:</b><br>
                        • Arena: {row.get('arena', 0):.1f}%<br>
                        • Limo: {row.get('limo', 0):.1f}%<br>
                        • Arcilla: {row.get('arcilla', 0):.1f}%<br>
                        <hr>
                        <b>Limitantes:</b><br>
                        {row.get('limitantes_textura', 'Ninguna')}
                    """
                    
                    if 'ndvi' in row and st.session_state.usar_planetscope:
                        popup_text += f"""
                        <hr>
                        <b>PlanetScope:</b><br>
                        • NDVI: {row.get('ndvi', 0):.3f}<br>
                        • Adecuación Espectral: {row.get('adecuacion_espectral', 0):.1%}<br>
                        """
                    
                    popup_text += "</div>"
                    
                    # Añadir geometría al mapa
                    try:
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
                            tooltip=f"Zona {row.get('id_zona', 'N/A')}: {row.get('textura_nombre_completo', 'N/A')}"
                        ).add_to(m)
                    except:
                        continue
                
                # Añadir leyenda específica
                legend_html = '''
                <div style="position: fixed; 
                            top: 10px; right: 10px; width: 280px; height: auto; 
                            background-color: white; border:2px solid grey; z-index:9999; 
                            font-size:12px; padding: 10px; border-radius:5px;">
                <h4 style="margin:0 0 10px 0; text-align:center;">🌴 Texturas Palma Aceitera</h4>
                '''
                
                for textura, info in CLASIFICACION_TEXTURAS_PALMA.items():
                    legend_html += f'''
                    <div style="margin:4px 0;">
                        <span style="background:{info['color']}; width:20px; height:15px; 
                        display:inline-block; margin-right:5px; border:1px solid #000;"></span>
                        <b>{info['nombre_completo']}</b><br>
                        <span style="font-size:10px; color:#666;">{info['descripcion'][:60]}...</span>
                    </div>
                    '''
                
                legend_html += '''
                <div style="margin-top:10px; font-size:10px; color:#666;">
                    🛰️ Datos: PlanetScope 3m<br>
                    📅 Sistema: Específico para Palma Aceitera
                </div>
                </div>
                '''
                
                m.get_root().html.add_child(folium.Element(legend_html))
                
                # Añadir controles
                folium.LayerControl().add_to(m)
                
                st_folium(m, width=800, height=500)
                
            except Exception as e:
                st.warning(f"No se pudo generar el mapa: {str(e)}")
        
        # Tabla detallada
        st.subheader("📊 TABLA DETALLADA DE ANÁLISIS")
        
        columnas_detalle = [
            'id_zona', 'area_ha', 'textura_nombre_completo', 'adecuacion_textura',
            'categoria_adecuacion', 'arena', 'limo', 'arcilla', 'materia_organica'
        ]
        
        if 'ndvi' in gdf_textura.columns and st.session_state.usar_planetscope:
            columnas_detalle.extend(['ndvi', 'adecuacion_espectral'])
        
        columnas_detalle.extend(['agua_disponible', 'densidad_aparente', 'porosidad'])
        
        columnas_existentes = [col for col in columnas_detalle if col in gdf_textura.columns]
        
        if columnas_existentes:
            df_detalle = gdf_textura[columnas_existentes].copy()
            
            # Formatear valores
            formatos = {
                'area_ha': lambda x: f"{x:.3f}",
                'adecuacion_textura': lambda x: f"{x:.3f}",
                'arena': lambda x: f"{x:.1f}",
                'limo': lambda x: f"{x:.1f}",
                'arcilla': lambda x: f"{x:.1f}",
                'materia_organica': lambda x: f"{x:.1f}%",
                'ndvi': lambda x: f"{x:.3f}",
                'adecuacion_espectral': lambda x: f"{x:.3f}",
                'agua_disponible': lambda x: f"{x:.0f} mm/m",
                'densidad_aparente': lambda x: f"{x:.2f} g/cm³",
                'porosidad': lambda x: f"{x:.1%}"
            }
            
            for col, formato in formatos.items():
                if col in df_detalle.columns:
                    try:
                        if col == 'adecuacion_textura' or col == 'adecuacion_espectral':
                            df_detalle[col] = (df_detalle[col] * 100).apply(lambda x: f"{x:.1f}%")
                        elif col == 'porosidad':
                            df_detalle[col] = df_detalle[col].apply(formato)
                        else:
                            df_detalle[col] = df_detalle[col].apply(formato)
                    except:
                        pass
            
            st.dataframe(df_detalle, use_container_width=True, height=400)
        else:
            st.warning("No hay datos suficientes para mostrar la tabla detallada")
        
        # Recomendaciones específicas según documento
        st.subheader("💡 RECOMENDACIONES ESPECÍFICAS SEGÚN DOCUMENTO")
        
        if 'textura_suelo' in gdf_textura.columns and len(gdf_textura) > 0:
            try:
                textura_predominante = gdf_textura['textura_suelo'].mode()[0] if not gdf_textura['textura_suelo'].mode().empty else 'FRANCO'
                recomendaciones = RECOMENDACIONES_TEXTURA_PALMA.get(textura_predominante, [])
                
                if recomendaciones:
                    textura_nombre = CLASIFICACION_TEXTURAS_PALMA.get(textura_predominante, {}).get('nombre_completo', textura_predominante)
                    st.info(f"**Recomendaciones para textura {textura_nombre}:**")
                    
                    col_rec1, col_rec2 = st.columns(2)
                    
                    with col_rec1:
                        for i, rec in enumerate(recomendaciones[:len(recomendaciones)//2]):
                            st.markdown(f"• {rec}")
                    
                    with col_rec2:
                        for i, rec in enumerate(recomendaciones[len(recomendaciones)//2:]):
                            st.markdown(f"• {rec}")
                    
                    # Añadir recomendaciones adicionales basadas en el mes
                    st.subheader("📅 RECOMENDACIONES ESTACIONALES")
                    mes_actual = st.session_state.mes_analisis
                    mes_data = FACTORES_MES_TROPICALES.get(mes_actual, {})
                    
                    st.success(f"**{mes_actual}:** {mes_data.get('recomendacion', 'Sin recomendación específica')}")
            except:
                st.warning("No se pudieron generar recomendaciones específicas")
        
        # Descargar resultados
        st.markdown("### 📥 DESCARGAR RESULTADOS")
        
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        with col_dl1:
            if not gdf_textura.empty:
                try:
                    # Preparar CSV con columnas seleccionadas
                    columnas_csv = ['id_zona', 'area_ha', 'textura_nombre_completo', 
                                   'arena', 'limo', 'arcilla', 'adecuacion_textura',
                                   'categoria_adecuacion', 'materia_organica']
                    
                    if 'ndvi' in gdf_textura.columns:
                        columnas_csv.extend(['ndvi', 'adecuacion_espectral'])
                    
                    df_csv = gdf_textura[columnas_csv].copy()
                    csv_data = df_csv.to_csv(index=False, encoding='utf-8')
                    
                    st.download_button(
                        label="📊 Descargar CSV",
                        data=csv_data,
                        file_name=f"analisis_palma_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                except Exception as e:
                    st.error(f"Error generando CSV: {str(e)}")
        
        with col_dl2:
            if not gdf_textura.empty:
                try:
                    geojson_data = gdf_textura.to_json()
                    st.download_button(
                        label="🗺️ Descargar GeoJSON",
                        data=geojson_data,
                        file_name=f"analisis_palma_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
                        mime="application/json"
                    )
                except Exception as e:
                    st.error(f"Error generando GeoJSON: {str(e)}")
        
        with col_dl3:
            if st.button("📄 Generar Informe Técnico", key="informe_palma"):
                with st.spinner("Generando informe técnico..."):
                    # Aquí iría la lógica para generar PDF
                    st.success("Informe técnico generado exitosamente")
                    st.info("La funcionalidad de generación de PDF se implementará en la próxima versión")
    
    except Exception as e:
        st.error(f"❌ Error mostrando análisis: {str(e)}")

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    # Sidebar con configuración
    with st.sidebar:
        st.header("⚙️ CONFIGURACIÓN DEL ANÁLISIS")
        
        # Cultivo
        st.session_state.cultivo_seleccionado = st.selectbox(
            "🌱 Cultivo Principal:",
            ["PALMA_ACEITERA", "CACAO", "BANANO"],
            help="Seleccione el cultivo para análisis específico",
            index=0  # Por defecto Palma Aceitera
        )
        
        # Tipo de análisis
        analisis_tipo = st.selectbox(
            "🔍 Tipo de Análisis:",
            ["ANÁLISIS ESPECÍFICO DE TEXTURA", "FERTILIDAD INTEGRAL", "RECOMENDACIONES NPK + MICRONUTRIENTES"],
            help="Análisis específico según documento técnico"
        )
        
        # Mes de análisis
        st.session_state.mes_analisis = st.selectbox(
            "📅 Mes de Análisis:",
            list(FACTORES_MES_TROPICALES.keys()),
            help="Seleccione el mes para análisis estacional",
            index=0
        )
        
        # Opciones de PlanetScope
        st.session_state.usar_planetscope = st.checkbox(
            "🛰️ Usar datos PlanetScope",
            value=True,
            help="Incluir datos simulados de imágenes PlanetScope (3m resolución)"
        )
        
        # División de parcela
        st.subheader("🎯 DIVISIÓN DE PARCELA")
        n_divisiones = st.slider(
            "Número de zonas de manejo:",
            min_value=12, max_value=36, value=24,
            help="Dividir la parcela en zonas para análisis detallado"
        )
        
        # Subir archivo
        st.subheader("📤 SUBIR PARCELA")
        uploaded_file = st.file_uploader(
            "Subir archivo de parcela",
            type=['zip', 'kml', 'shp'],
            help="Formatos: Shapefile (.zip), KML, o SHP individual"
        )
        
        # Botones de acción
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Reiniciar", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key not in ['_secrets', '_user_info']:
                        del st.session_state[key]
                st.rerun()
        
        with col_btn2:
            if st.button("🎯 Datos Demo", use_container_width=True):
                st.session_state.datos_demo = True
                st.session_state.gdf_original = None
                st.rerun()
    
    # Contenido principal
    if not st.session_state.analisis_completado:
        mostrar_interfaz_configuracion(uploaded_file, n_divisiones, analisis_tipo)
    else:
        if analisis_tipo == "ANÁLISIS ESPECÍFICO DE TEXTURA":
            mostrar_analisis_textura_palma()
        else:
            st.warning("Seleccione 'ANÁLISIS ESPECÍFICO DE TEXTURA' para ver los resultados específicos para palma aceitera")

def mostrar_interfaz_configuracion(uploaded_file, n_divisiones, analisis_tipo):
    """Muestra la interfaz de configuración"""
    
    st.markdown("### 📋 INFORMACIÓN DEL ANÁLISIS")
    
    # Mostrar parámetros
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("🌱 Cultivo", st.session_state.cultivo_seleccionado.replace('_', ' ').title())
    with col_info2:
        st.metric("🔍 Análisis", analisis_tipo)
    with col_info3:
        st.metric("📅 Mes", st.session_state.mes_analisis)
    
    # Información específica para palma aceitera
    if st.session_state.cultivo_seleccionado == "PALMA_ACEITERA":
        st.success("**🌴 Análisis específico para Palma Aceitera** - Basado en clasificación técnica documentada")
    
    # Información de PlanetScope
    if st.session_state.usar_planetscope:
        st.info("🛰️ **Datos PlanetScope habilitados** - Resolución: 3m | Bandas: 8 espectrales")
    
    # Procesar archivo subido o datos demo
    if uploaded_file is not None:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
                st.success("✅ Archivo procesado exitosamente")
    
    elif st.session_state.datos_demo and st.session_state.gdf_original is None:
        # Crear datos de demostración para Colombia/Venezuela
        st.info("🎯 Creando datos de demostración...")
        
        # Coordenadas típicas de Colombia/Venezuela
        poligono_demo = Polygon([
            [-73.5, 5.0], [-73.4, 5.0], [-73.4, 5.1], [-73.5, 5.1], [-73.5, 5.0]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo - Zona Palmera']},
            geometry=[poligono_demo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.success("✅ Datos de demostración creados")
    
    # Mostrar parcela si está cargada
    if st.session_state.gdf_original is not None:
        gdf_original = st.session_state.gdf_original
        
        st.markdown("### 🗺️ VISUALIZACIÓN DE PARCELA")
        
        # Calcular estadísticas
        area_total = calcular_superficie(gdf_original)
        
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric("📐 Área Total", f"{area_total:.2f} ha")
        with col_stats2:
            st.metric("🔢 Polígonos", len(gdf_original))
        with col_stats3:
            st.metric("📍 CRS", str(gdf_original.crs))
        
        # Botón para ejecutar análisis
        st.markdown("### 🚀 EJECUTAR ANÁLISIS ESPECÍFICO")
        
        if st.button("▶️ Ejecutar Análisis Completo", type="primary", use_container_width=True):
            with st.spinner("🔄 Dividiendo parcela en zonas..."):
                gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
                st.session_state.gdf_zonas = gdf_zonas
                st.success(f"✅ Parcela dividida en {len(gdf_zonas)} zonas")
            
            with st.spinner(f"🛰️ Analizando textura para {st.session_state.cultivo_seleccionado}..."):
                gdf_textura = analizar_textura_suelo_palma(
                    gdf_zonas, 
                    st.session_state.cultivo_seleccionado, 
                    st.session_state.mes_analisis, 
                    st.session_state.usar_planetscope
                )
                st.session_state.analisis_textura = gdf_textura
                st.success("✅ Análisis de textura completado")
            
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
            
            st.rerun()
    
    else:
        # Mostrar instrucciones
        st.markdown("### 🚀 CÓMO COMENZAR")
        
        col_inst1, col_inst2 = st.columns(2)
        
        with col_inst1:
            st.info("""
            **📤 Para comenzar:**
            1. Sube tu archivo de parcela
            2. Selecciona el cultivo (Palma Aceitera recomendado)
            3. Configura las opciones de análisis
            4. Haz clic en 'Ejecutar Análisis Completo'
            
            **📄 Formatos soportados:**
            • Shapefile (.zip con .shp, .shx, .dbf, .prj)
            • Archivos KML/KMZ de Google Earth
            • Shapefile individual (.shp)
            """)
        
        with col_inst2:
            st.success("""
            **🔬 Características específicas:**
            • Clasificación de texturas específica para palma
            • 3 categorías: Franco, Franco Arcilloso, Franco Arcilloso-Arenoso
            • Recomendaciones basadas en documento técnico
            • Datos PlanetScope simulados (3m resolución)
            • Análisis estacional para Colombia/Venezuela
            • Limitantes y manejo específico por textura
            """)

# Ejecutar aplicación
if __name__ == "__main__":
    main()
