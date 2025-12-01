# analizador_cultivos_completo.py
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
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA COMPLETA")
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
if 'analisis_fertilidad' not in st.session_state:
    st.session_state.analisis_fertilidad = None
if 'cultivo_seleccionado' not in st.session_state:
    st.session_state.cultivo_seleccionado = "PALMA_ACEITERA"
if 'usar_planetscope' not in st.session_state:
    st.session_state.usar_planetscope = True
if 'mes_analisis' not in st.session_state:
    st.session_state.mes_analisis = "ENERO"

# ============================================================================
# PARÁMETROS DE PLANETSCOPE
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
    }
}

# ============================================================================
# CLASIFICACIÓN ESPECÍFICA PARA PALMA ACEITERA
# ============================================================================
CLASIFICACION_TEXTURAS_PALMA = {
    'FRANCO': {
        'nombre_completo': 'Franco',
        'descripcion': 'Equilibrio arena-limo-arcilla. Buena aireación y drenaje.',
        'arena_min': 40,
        'arena_max': 60,
        'limo_min': 30,
        'limo_max': 50,
        'arcilla_min': 10,
        'arcilla_max': 25,
        'color': '#4a7c59',
        'limitantes': [
            'Puede compactarse con maquinaria pesada',
            'Erosión en pendientes si no hay cobertura'
        ]
    },
    'FRANCO_ARCILLOSO': {
        'nombre_completo': 'Franco Arcilloso',
        'descripcion': 'Mayor proporción de arcilla (25-35%). Alta retención de agua.',
        'arena_min': 20,
        'arena_max': 40,
        'limo_min': 30,
        'limo_max': 50,
        'arcilla_min': 25,
        'arcilla_max': 35,
        'color': '#8b4513',
        'limitantes': [
            'Riesgo de encharcamiento',
            'Compactación fácil',
            'Menor oxigenación radicular'
        ]
    },
    'FRANCO_ARCILLOSO_ARENOSO': {
        'nombre_completo': 'Franco Arcilloso-Arenoso',
        'descripcion': 'Arena 40-50%, arcilla 20-30%. Buen desarrollo radicular.',
        'arena_min': 40,
        'arena_max': 50,
        'limo_min': 20,
        'limo_max': 30,
        'arcilla_min': 20,
        'arcilla_max': 30,
        'color': '#d2b48c',
        'limitantes': [
            'Riesgo de lixiviación de nutrientes',
            'Estrés hídrico en veranos'
        ]
    }
}

# ============================================================================
# PARÁMETROS COMPLETOS DE FERTILIDAD POR CULTIVO
# ============================================================================
PARAMETROS_FERTILIDAD = {
    'PALMA_ACEITERA': {
        'MACRONUTRIENTES': {
            'NITROGENO': {'min': 1.5, 'max': 2.5, 'optimo': 2.0, 'unidad': '%'},
            'FOSFORO': {'min': 15, 'max': 30, 'optimo': 22, 'unidad': 'ppm'},
            'POTASIO': {'min': 0.25, 'max': 0.40, 'optimo': 0.32, 'unidad': 'cmol/kg'},
            'CALCIO': {'min': 3.0, 'max': 6.0, 'optimo': 4.5, 'unidad': 'cmol/kg'},
            'MAGNESIO': {'min': 1.0, 'max': 2.0, 'optimo': 1.5, 'unidad': 'cmol/kg'},
            'AZUFRE': {'min': 10, 'max': 20, 'optimo': 15, 'unidad': 'ppm'}
        },
        'MICRONUTRIENTES': {
            'HIERRO': {'min': 50, 'max': 100, 'optimo': 75, 'unidad': 'ppm'},
            'MANGANESO': {'min': 20, 'max': 50, 'optimo': 35, 'unidad': 'ppm'},
            'ZINC': {'min': 2, 'max': 10, 'optimo': 6, 'unidad': 'ppm'},
            'COBRE': {'min': 1, 'max': 5, 'optimo': 3, 'unidad': 'ppm'},
            'BORO': {'min': 0.5, 'max': 2.0, 'optimo': 1.2, 'unidad': 'ppm'}
        },
        'PROPIEDADES_QUIMICAS': {
            'MATERIA_ORGANICA': {'min': 2.5, 'max': 4.5, 'optimo': 3.5, 'unidad': '%'},
            'pH': {'min': 5.0, 'max': 6.0, 'optimo': 5.5, 'unidad': ''},
            'CONDUCTIVIDAD': {'min': 0.8, 'max': 1.5, 'optimo': 1.2, 'unidad': 'dS/m'},
            'CIC': {'min': 10, 'max': 20, 'optimo': 15, 'unidad': 'cmol/kg'}
        }
    },
    'CACAO': {
        'MACRONUTRIENTES': {
            'NITROGENO': {'min': 1.8, 'max': 2.8, 'optimo': 2.3, 'unidad': '%'},
            'FOSFORO': {'min': 20, 'max': 35, 'optimo': 27, 'unidad': 'ppm'},
            'POTASIO': {'min': 0.30, 'max': 0.50, 'optimo': 0.40, 'unidad': 'cmol/kg'},
            'CALCIO': {'min': 4.0, 'max': 7.0, 'optimo': 5.5, 'unidad': 'cmol/kg'},
            'MAGNESIO': {'min': 1.2, 'max': 2.2, 'optimo': 1.7, 'unidad': 'cmol/kg'},
            'AZUFRE': {'min': 12, 'max': 25, 'optimo': 18, 'unidad': 'ppm'}
        },
        'MICRONUTRIENTES': {
            'HIERRO': {'min': 60, 'max': 120, 'optimo': 90, 'unidad': 'ppm'},
            'MANGANESO': {'min': 25, 'max': 60, 'optimo': 42, 'unidad': 'ppm'},
            'ZINC': {'min': 3, 'max': 12, 'optimo': 7, 'unidad': 'ppm'},
            'COBRE': {'min': 1.5, 'max': 6.0, 'optimo': 3.5, 'unidad': 'ppm'},
            'BORO': {'min': 0.6, 'max': 2.5, 'optimo': 1.5, 'unidad': 'ppm'}
        },
        'PROPIEDADES_QUIMICAS': {
            'MATERIA_ORGANICA': {'min': 3.0, 'max': 5.0, 'optimo': 4.0, 'unidad': '%'},
            'pH': {'min': 5.5, 'max': 6.5, 'optimo': 6.0, 'unidad': ''},
            'CONDUCTIVIDAD': {'min': 0.6, 'max': 1.2, 'optimo': 0.9, 'unidad': 'dS/m'},
            'CIC': {'min': 12, 'max': 25, 'optimo': 18, 'unidad': 'cmol/kg'}
        }
    },
    'BANANO': {
        'MACRONUTRIENTES': {
            'NITROGENO': {'min': 2.0, 'max': 3.0, 'optimo': 2.5, 'unidad': '%'},
            'FOSFORO': {'min': 25, 'max': 40, 'optimo': 32, 'unidad': 'ppm'},
            'POTASIO': {'min': 0.35, 'max': 0.60, 'optimo': 0.48, 'unidad': 'cmol/kg'},
            'CALCIO': {'min': 5.0, 'max': 8.0, 'optimo': 6.5, 'unidad': 'cmol/kg'},
            'MAGNESIO': {'min': 1.5, 'max': 2.5, 'optimo': 2.0, 'unidad': 'cmol/kg'},
            'AZUFRE': {'min': 15, 'max': 30, 'optimo': 22, 'unidad': 'ppm'}
        },
        'MICRONUTRIENTES': {
            'HIERRO': {'min': 70, 'max': 150, 'optimo': 110, 'unidad': 'ppm'},
            'MANGANESO': {'min': 30, 'max': 70, 'optimo': 50, 'unidad': 'ppm'},
            'ZINC': {'min': 4, 'max': 15, 'optimo': 9, 'unidad': 'ppm'},
            'COBRE': {'min': 2.0, 'max': 8.0, 'optimo': 5.0, 'unidad': 'ppm'},
            'BORO': {'min': 0.8, 'max': 3.0, 'optimo': 1.8, 'unidad': 'ppm'}
        },
        'PROPIEDADES_QUIMICAS': {
            'MATERIA_ORGANICA': {'min': 3.5, 'max': 5.5, 'optimo': 4.5, 'unidad': '%'},
            'pH': {'min': 5.8, 'max': 6.8, 'optimo': 6.3, 'unidad': ''},
            'CONDUCTIVIDAD': {'min': 1.0, 'max': 1.8, 'optimo': 1.4, 'unidad': 'dS/m'},
            'CIC': {'min': 15, 'max': 30, 'optimo': 22, 'unidad': 'cmol/kg'}
        }
    }
}

# ============================================================================
# RECOMENDACIONES DE FERTILIZACIÓN POR DEFICIENCIA
# ============================================================================
RECOMENDACIONES_FERTILIZACION = {
    'PALMA_ACEITERA': {
        'DEFICIENCIA_NITROGENO': [
            "Aplicar 150-200 kg/ha de urea (46% N) en 2-3 fracciones",
            "Incorporar leguminosas de cobertura (Mucuna, Canavalia)",
            "Aplicar compost enriquecido (3-5 ton/ha)",
            "Considerar fertilizantes de liberación lenta"
        ],
        'DEFICIENCIA_FOSFORO': [
            "Aplicar 100-150 kg/ha de superfosfato triple (46% P2O5)",
            "Incorporar roca fosfórica en suelos ácidos",
            "Aplicar fosfato diamónico en presiembra",
            "Usar inoculantes microbianos (micorrizas)"
        ],
        'DEFICIENCIA_POTASIO': [
            "Aplicar 200-300 kg/ha de cloruro de potasio (60% K2O)",
            "Fraccionar aplicación: 40% pre-siembra, 60% en crecimiento",
            "Evitar aplicación simultánea con nitrógeno",
            "Monitorear niveles de magnesio para mantener balance"
        ],
        'DEFICIENCIA_MAGNESIO': [
            "Aplicar 50-100 kg/ha de sulfato de magnesio",
            "Corregir con dolomita en suelos ácidos",
            "Evitar exceso de potasio que antagoniza Mg",
            "Foliar: sulfato de magnesio al 2%"
        ],
        'DEFICIENCIA_CALCIO': [
            "Aplicar 1-2 ton/ha de cal agrícola",
            "Enmiendas calcáreas en presiembra",
            "Yeso agrícola en suelos sódicos",
            "Evitar exceso de nitrógeno amoniacal"
        ],
        'DEFICIENCIA_MICRONUTRIENTES': [
            "Aplicación foliar de quelatos: Zn, B, Cu",
            "Sulfato de zinc: 10-20 kg/ha",
            "Bórax: 5-10 kg/ha cada 2 años",
            "Correctivos edáficos con micronutrientes"
        ]
    },
    'CACAO': {
        'DEFICIENCIA_NITROGENO': [
            "Aplicar 100-150 kg/ha de sulfato de amonio",
            "Fertilización orgánica con compost de pulpa",
            "Coberturas leguminosas en calles",
            "Fraccionamiento: 3 aplicaciones/año"
        ],
        'DEFICIENCIA_FOSFORO': [
            "Aplicar 80-120 kg/ha de fosfato diamónico",
            "Roca fosfórica en suelos ácidos",
            "Fosfato natural reactivo",
            "Inoculación con hongos micorrízicos"
        ]
    },
    'BANANO': {
        'DEFICIENCIA_POTASIO': [
            "Aplicar 300-400 kg/ha de cloruro de potasio",
            "Fraccionar: 25% siembra, 50% crecimiento, 25% floración",
            "Sulfato de potasio en suelos salinos",
            "Balance con nitrógeno 1:1.5 (N:K)"
        ]
    }
}

# ============================================================================
# FACTORES ESTACIONALES TROPICALES
# ============================================================================
FACTORES_MES_TROPICALES = {
    "ENERO": {'factor': 0.9, 'precipitacion': 'Baja', 'temperatura': 'Alta'},
    "FEBRERO": {'factor': 0.85, 'precipitacion': 'Muy baja', 'temperatura': 'Alta'},
    "MARZO": {'factor': 0.95, 'precipitacion': 'Baja', 'temperatura': 'Alta'},
    "ABRIL": {'factor': 1.1, 'precipitacion': 'Media', 'temperatura': 'Alta'},
    "MAYO": {'factor': 1.2, 'precipitacion': 'Alta', 'temperatura': 'Media'},
    "JUNIO": {'factor': 1.1, 'precipitacion': 'Alta', 'temperatura': 'Media'},
    "JULIO": {'factor': 1.0, 'precipitacion': 'Media', 'temperatura': 'Media'},
    "AGOSTO": {'factor': 0.95, 'precipitacion': 'Media', 'temperatura': 'Media'},
    "SEPTIEMBRE": {'factor': 0.9, 'precipitacion': 'Baja', 'temperatura': 'Alta'},
    "OCTUBRE": {'factor': 0.85, 'precipitacion': 'Baja', 'temperatura': 'Alta'},
    "NOVIEMBRE": {'factor': 1.0, 'precipitacion': 'Alta', 'temperatura': 'Media'},
    "DICIEMBRE": {'factor': 0.95, 'precipitacion': 'Media', 'temperatura': 'Media'}
}

# ============================================================================
# FUNCIONES AUXILIARES ROBUSTAS
# ============================================================================
def calcular_superficie(gdf):
    """Calcula superficie en hectáreas"""
    try:
        if gdf is None or gdf.empty or gdf.geometry.isnull().all():
            return 0.0
        
        gdf_temp = gdf.copy()
        gdf_temp.geometry = gdf_temp.geometry.make_valid()
        
        def get_main_polygon(geom):
            if isinstance(geom, MultiPolygon):
                areas = [g.area for g in geom.geoms]
                if areas:
                    return geom.geoms[areas.index(max(areas))]
            return geom
        
        gdf_temp.geometry = gdf_temp.geometry.apply(get_main_polygon)
        
        if gdf_temp.crs and gdf_temp.crs.is_geographic:
            try:
                gdf_proj = gdf_temp.to_crs('EPSG:3116')
                area_m2 = gdf_proj.geometry.area.sum()
            except:
                area_m2 = gdf_temp.geometry.area.sum() * 111000 * 111000
        else:
            area_m2 = gdf_temp.geometry.area.sum()
            
        return area_m2 / 10000.0
    
    except Exception as e:
        st.warning(f"⚠️ Advertencia al calcular superficie: {str(e)}")
        return 0.0

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo"""
    try:
        if gdf is None or len(gdf) == 0:
            return gdf
        
        parcela_principal = gdf.iloc[0].geometry
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        
        bounds = parcela_principal.bounds
        minx, miny, maxx, maxy = bounds
        
        n_cols = max(1, math.ceil(math.sqrt(n_zonas)))
        n_rows = max(1, math.ceil(n_zonas / n_cols))
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        sub_poligonos = []
        
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
                    try:
                        intersection = parcela_principal.intersection(cell_poly)
                        if not intersection.is_empty:
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
            gdf['id_zona'] = range(1, len(gdf) + 1)
            return gdf
            
    except Exception as e:
        st.error(f"❌ Error al dividir parcela: {str(e)}")
        gdf['id_zona'] = range(1, len(gdf) + 1)
        return gdf

def procesar_archivo(uploaded_file):
    """Procesa archivo subido"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            file_ext = uploaded_file.name.lower()
            
            if file_ext.endswith('.kml'):
                gdf = gpd.read_file(file_path, driver='KML')
            elif file_ext.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                shp_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.kml')]
                
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                elif kml_files:
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    gdf = gpd.read_file(kml_path, driver='KML')
                else:
                    st.error("❌ No se encontró archivo .shp o .kml en el ZIP")
                    return None
            elif file_ext.endswith('.shp'):
                gdf = gpd.read_file(file_path)
            else:
                st.error("❌ Formato de archivo no soportado")
                return None
            
            if not gdf.empty:
                gdf.geometry = gdf.geometry.make_valid()
                gdf = gdf[~gdf.geometry.is_empty]
                
                if len(gdf) == 0:
                    st.error("❌ No se encontraron geometrías válidas")
                    return None
                
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
# FUNCIONES PARA ANÁLISIS DE TEXTURA
# ============================================================================
def clasificar_textura_palma(arena, limo, arcilla):
    """Clasifica la textura según sistema específico"""
    try:
        total = arena + limo + arcilla
        if total <= 0:
            return "NO_DETERMINADA"
        
        arena_pct = (arena / total) * 100
        limo_pct = (limo / total) * 100
        arcilla_pct = (arcilla / total) * 100
        
        if arena_pct >= 40 and arena_pct <= 50 and arcilla_pct >= 20 and arcilla_pct <= 30:
            return "FRANCO_ARCILLOSO_ARENOSO"
        elif arcilla_pct >= 25 and arcilla_pct <= 35:
            return "FRANCO_ARCILLOSO"
        elif (arena_pct >= 40 and arena_pct <= 60 and 
              limo_pct >= 30 and limo_pct <= 50 and 
              arcilla_pct >= 10 and arcilla_pct <= 25):
            return "FRANCO"
        else:
            distancias = {}
            distancias["FRANCO"] = abs(arena_pct - 50) + abs(limo_pct - 40) + abs(arcilla_pct - 15)
            distancias["FRANCO_ARCILLOSO"] = abs(arena_pct - 30) + abs(limo_pct - 40) + abs(arcilla_pct - 30)
            distancias["FRANCO_ARCILLOSO_ARENOSO"] = abs(arena_pct - 45) + abs(limo_pct - 25) + abs(arcilla_pct - 25)
            
            return min(distancias, key=distancias.get)
            
    except Exception as e:
        return "NO_DETERMINADA"

def analizar_textura_suelo(gdf, cultivo, mes_analisis):
    """Realiza análisis de textura del suelo"""
    try:
        zonas_gdf = gdf.copy()
        
        columnas_base = [
            'id_zona', 'area_ha', 'arena', 'limo', 'arcilla', 'textura_suelo', 
            'textura_nombre_completo', 'materia_organica', 'humedad_suelo'
        ]
        
        for col in columnas_base:
            if col == 'id_zona' and col not in zonas_gdf.columns:
                zonas_gdf[col] = range(1, len(zonas_gdf) + 1)
            elif col == 'textura_suelo':
                zonas_gdf[col] = "NO_DETERMINADA"
            elif col == 'textura_nombre_completo':
                zonas_gdf[col] = "No determinada"
            elif col not in zonas_gdf.columns:
                zonas_gdf[col] = 0.0
        
        for idx, row in zonas_gdf.iterrows():
            try:
                area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
                
                if hasattr(row.geometry, 'centroid') and not row.geometry.is_empty:
                    centroid = row.geometry.centroid
                else:
                    centroid = row.geometry.representative_point()
                
                seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
                rng = np.random.RandomState(seed_value)
                
                lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
                lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
                variabilidad_espacial = 0.2 + 0.6 * np.sin(lat_norm * np.pi * 2) * np.cos(lon_norm * np.pi * 2)
                
                arena = max(5, min(95, rng.normal(45 * (0.7 + 0.6 * variabilidad_espacial), 45 * 0.25)))
                limo = max(5, min(95, rng.normal(25 * (0.6 + 0.8 * variabilidad_espacial), 25 * 0.3)))
                arcilla = max(5, min(95, rng.normal(25 * (0.65 + 0.7 * variabilidad_espacial), 25 * 0.35)))
                
                total = arena + limo + arcilla
                arena = (arena / total) * 100
                limo = (limo / total) * 100
                arcilla = (arcilla / total) * 100
                
                textura_clave = clasificar_textura_palma(arena, limo, arcilla)
                textura_info = CLASIFICACION_TEXTURAS_PALMA.get(textura_clave, {})
                textura_nombre = textura_info.get('nombre_completo', 'No determinada')
                
                materia_organica = max(1.0, min(8.0, rng.normal(3.5, 1.0)))
                humedad_suelo = max(0.1, min(0.6, rng.normal(0.35, 0.15)))
                
                zonas_gdf.loc[idx, 'area_ha'] = area_ha
                zonas_gdf.loc[idx, 'arena'] = arena
                zonas_gdf.loc[idx, 'limo'] = limo
                zonas_gdf.loc[idx, 'arcilla'] = arcilla
                zonas_gdf.loc[idx, 'textura_suelo'] = textura_clave
                zonas_gdf.loc[idx, 'textura_nombre_completo'] = textura_nombre
                zonas_gdf.loc[idx, 'materia_organica'] = materia_organica
                zonas_gdf.loc[idx, 'humedad_suelo'] = humedad_suelo
                
            except Exception as e:
                zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
                zonas_gdf.loc[idx, 'arena'] = 45
                zonas_gdf.loc[idx, 'limo'] = 25
                zonas_gdf.loc[idx, 'arcilla'] = 25
                zonas_gdf.loc[idx, 'textura_suelo'] = "FRANCO_ARCILLOSO_ARENOSO"
                zonas_gdf.loc[idx, 'textura_nombre_completo'] = "Franco Arcilloso-Arenoso"
                zonas_gdf.loc[idx, 'materia_organica'] = 3.5
                zonas_gdf.loc[idx, 'humedad_suelo'] = 0.35
        
        return zonas_gdf
    
    except Exception as e:
        st.error(f"❌ Error en análisis de textura: {str(e)}")
        return gdf

# ============================================================================
# FUNCIONES PARA ANÁLISIS DE FERTILIDAD INTEGRAL
# ============================================================================
def simular_analisis_laboratorio(centroid, cultivo):
    """Simula análisis de laboratorio de suelo"""
    try:
        seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_fert")) % (2**32)
        rng = np.random.RandomState(seed_value)
        
        params = PARAMETROS_FERTILIDAD[cultivo]
        resultados = {}
        
        # Simular macronutrientes
        for nutriente, valores in params['MACRONUTRIENTES'].items():
            optimo = valores['optimo']
            desviacion = optimo * 0.3  # 30% de desviación
            valor = max(0, rng.normal(optimo, desviacion))
            resultados[nutriente] = {
                'valor': valor,
                'unidad': valores['unidad'],
                'optimo': optimo,
                'min': valores['min'],
                'max': valores['max']
            }
        
        # Simular micronutrientes
        for nutriente, valores in params['MICRONUTRIENTES'].items():
            optimo = valores['optimo']
            desviacion = optimo * 0.4
            valor = max(0, rng.normal(optimo, desviacion))
            resultados[nutriente] = {
                'valor': valor,
                'unidad': valores['unidad'],
                'optimo': optimo,
                'min': valores['min'],
                'max': valores['max']
            }
        
        # Simular propiedades químicas
        for propiedad, valores in params['PROPIEDADES_QUIMICAS'].items():
            optimo = valores['optimo']
            desviacion = optimo * 0.2
            if propiedad == 'pH':
                valor = max(4.0, min(8.0, rng.normal(optimo, 0.5)))
            else:
                valor = max(0, rng.normal(optimo, desviacion))
            resultados[propiedad] = {
                'valor': valor,
                'unidad': valores['unidad'],
                'optimo': optimo,
                'min': valores['min'],
                'max': valores['max']
            }
        
        return resultados
        
    except Exception as e:
        return {}

def calcular_indice_fertilidad(resultados, cultivo):
    """Calcula índice de fertilidad basado en análisis"""
    try:
        if not resultados:
            return 0.0, "NO DISPONIBLE", []
        
        params = PARAMETROS_FERTILIDAD[cultivo]
        deficiencias = []
        puntajes = []
        
        # Evaluar cada parámetro
        for categoria in ['MACRONUTRIENTES', 'MICRONUTRIENTES', 'PROPIEDADES_QUIMICAS']:
            for parametro in params[categoria]:
                if parametro in resultados:
                    valor = resultados[parametro]['valor']
                    optimo = resultados[parametro]['optimo']
                    minimo = resultados[parametro]['min']
                    maximo = resultados[parametro]['max']
                    
                    # Calcular puntaje (0-1)
                    if valor <= minimo:
                        puntaje = 0.1
                        deficiencias.append(f"{parametro}: MUY DEFICIENTE ({valor:.2f} vs {optimo:.2f})")
                    elif valor >= maximo:
                        puntaje = 0.8
                    else:
                        # Puntaje proporcional a la cercanía al óptimo
                        if valor <= optimo:
                            puntaje = 0.3 + 0.5 * ((valor - minimo) / (optimo - minimo))
                        else:
                            puntaje = 0.8 + 0.2 * ((maximo - valor) / (maximo - optimo))
                    
                    puntajes.append(puntaje)
        
        if puntajes:
            indice = np.mean(puntajes)
            
            if indice >= 0.8:
                categoria = "EXCELENTE"
            elif indice >= 0.6:
                categoria = "BUENA"
            elif indice >= 0.4:
                categoria = "MODERADA"
            elif indice >= 0.2:
                categoria = "BAJA"
            else:
                categoria = "MUY BAJA"
            
            return indice, categoria, deficiencias
        else:
            return 0.0, "NO DISPONIBLE", []
        
    except Exception as e:
        return 0.0, "ERROR", [f"Error en cálculo: {str(e)}"]

def generar_recomendaciones_fertilidad(resultados, cultivo, deficiencias):
    """Genera recomendaciones de fertilización"""
    try:
        recomendaciones = []
        
        # Recomendaciones basadas en deficiencias
        for deficiencia in deficiencias:
            if "NITROGENO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION[cultivo].get('DEFICIENCIA_NITROGENO', []))
            
            if "FOSFORO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION[cultivo].get('DEFICIENCIA_FOSFORO', []))
            
            if "POTASIO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION[cultivo].get('DEFICIENCIA_POTASIO', []))
        
        # Recomendaciones generales
        if cultivo == "PALMA_ACEITERA":
            recomendaciones.extend([
                "Programa anual de fertilización: 3-4 aplicaciones",
                "Balance NPK recomendado: 12-6-18 + 3MgO",
                "Época principal: inicio de lluvias",
                "Incorporar materia orgánica anualmente"
            ])
        elif cultivo == "CACAO":
            recomendaciones.extend([
                "Fertilización orgánica preferible",
                "Balance NPK: 15-10-15",
                "Aplicar después de podas",
                "Evitar aplicación en suelo seco"
            ])
        elif cultivo == "BANANO":
            recomendaciones.extend([
                "Alta demanda de potasio",
                "Balance NPK: 8-4-24",
                "Fertirrigación recomendada",
                "Monitorear niveles de magnesio"
            ])
        
        return list(set(recomendaciones))[:8]  # Limitar a 8 recomendaciones únicas
        
    except Exception as e:
        return ["Error generando recomendaciones"]

def analizar_fertilidad_integral(gdf, cultivo, mes_analisis):
    """Realiza análisis integral de fertilidad"""
    try:
        zonas_gdf = gdf.copy()
        
        # Columnas base
        columnas_base = ['id_zona', 'area_ha']
        
        # Agregar columnas para cada parámetro de fertilidad
        params = PARAMETROS_FERTILIDAD[cultivo]
        
        for categoria in ['MACRONUTRIENTES', 'MICRONUTRIENTES', 'PROPIEDADES_QUIMICAS']:
            for parametro in params[categoria]:
                columnas_base.append(f"{parametro}_valor")
                columnas_base.append(f"{parametro}_unidad")
        
        columnas_base.extend([
            'indice_fertilidad', 'categoria_fertilidad',
            'deficiencias', 'recomendaciones'
        ])
        
        # Inicializar columnas
        for col in columnas_base:
            if col == 'id_zona' and col not in zonas_gdf.columns:
                zonas_gdf[col] = range(1, len(zonas_gdf) + 1)
            elif col not in zonas_gdf.columns:
                if 'deficiencias' in col or 'recomendaciones' in col:
                    zonas_gdf[col] = ""
                else:
                    zonas_gdf[col] = 0.0
        
        for idx, row in zonas_gdf.iterrows():
            try:
                area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
                zonas_gdf.loc[idx, 'area_ha'] = area_ha
                
                if hasattr(row.geometry, 'centroid') and not row.geometry.is_empty:
                    centroid = row.geometry.centroid
                else:
                    centroid = row.geometry.representative_point()
                
                # Simular análisis de laboratorio
                resultados = simular_analisis_laboratorio(centroid, cultivo)
                
                if resultados:
                    # Guardar valores
                    for parametro, datos in resultados.items():
                        if f"{parametro}_valor" in zonas_gdf.columns:
                            zonas_gdf.loc[idx, f"{parametro}_valor"] = datos['valor']
                        if f"{parametro}_unidad" in zonas_gdf.columns:
                            zonas_gdf.loc[idx, f"{parametro}_unidad"] = datos['unidad']
                    
                    # Calcular índice de fertilidad
                    indice, categoria, deficiencias = calcular_indice_fertilidad(resultados, cultivo)
                    zonas_gdf.loc[idx, 'indice_fertilidad'] = indice
                    zonas_gdf.loc[idx, 'categoria_fertilidad'] = categoria
                    zonas_gdf.loc[idx, 'deficiencias'] = '; '.join(deficiencias[:3])
                    
                    # Generar recomendaciones
                    recomendaciones = generar_recomendaciones_fertilidad(resultados, cultivo, deficiencias)
                    zonas_gdf.loc[idx, 'recomendaciones'] = '; '.join(recomendaciones[:5])
                
            except Exception as e:
                zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]])
                zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.5
                zonas_gdf.loc[idx, 'categoria_fertilidad'] = "MODERADA"
                zonas_gdf.loc[idx, 'deficiencias'] = "Error en análisis"
                zonas_gdf.loc[idx, 'recomendaciones'] = "Consulte con especialista"
        
        return zonas_gdf
    
    except Exception as e:
        st.error(f"❌ Error en análisis de fertilidad: {str(e)}")
        return gdf

# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================
def mostrar_analisis_textura():
    """Muestra análisis de textura"""
    try:
        if st.session_state.analisis_textura is None:
            st.warning("No hay datos de análisis de textura")
            return
        
        gdf_textura = st.session_state.analisis_textura
        
        st.markdown("## 🏗️ ANÁLISIS DE TEXTURA DEL SUELO")
        
        if st.button("⬅️ Volver", key="volver_textura"):
            st.session_state.analisis_completado = False
            st.rerun()
        
        # Estadísticas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if 'textura_nombre_completo' in gdf_textura.columns and len(gdf_textura) > 0:
                textura_pred = gdf_textura['textura_nombre_completo'].mode()[0] if not gdf_textura['textura_nombre_completo'].mode().empty else "N/A"
                st.metric("🏗️ Textura Predominante", textura_pred)
        with col2:
            if 'arena' in gdf_textura.columns:
                avg_arena = gdf_textura['arena'].mean()
                st.metric("🏖️ Arena Promedio", f"{avg_arena:.1f}%")
        with col3:
            if 'limo' in gdf_textura.columns:
                avg_limo = gdf_textura['limo'].mean()
                st.metric("🌫️ Limo Promedio", f"{avg_limo:.1f}%")
        with col4:
            if 'arcilla' in gdf_textura.columns:
                avg_arcilla = gdf_textura['arcilla'].mean()
                st.metric("🧱 Arcilla Promedio", f"{avg_arcilla:.1f}%")
        
        # Mapa
        st.subheader("🗺️ MAPA DE TEXTURAS")
        
        if 'textura_suelo' in gdf_textura.columns and len(gdf_textura) > 0:
            try:
                centroids = gdf_textura.geometry.centroid
                center_lat = centroids.y.mean()
                center_lon = centroids.x.mean()
                
                m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
                
                for idx, row in gdf_textura.iterrows():
                    textura = row['textura_suelo']
                    color = CLASIFICACION_TEXTURAS_PALMA.get(textura, {}).get('color', '#999999')
                    
                    popup_text = f"""
                    <div style="font-size:12px">
                        <b>Zona {row.get('id_zona', 'N/A')}</b><br>
                        Textura: {row.get('textura_nombre_completo', 'N/A')}<br>
                        Arena: {row.get('arena', 0):.1f}%<br>
                        Limo: {row.get('limo', 0):.1f}%<br>
                        Arcilla: {row.get('arcilla', 0):.1f}%<br>
                        Área: {row.get('area_ha', 0):.2f} ha
                    </div>
                    """
                    
                    folium.GeoJson(
                        row.geometry.__geo_interface__,
                        style_function=lambda x, color=color: {
                            'fillColor': color,
                            'color': 'black',
                            'weight': 1,
                            'fillOpacity': 0.7
                        },
                        popup=folium.Popup(popup_text, max_width=200)
                    ).add_to(m)
                
                st_folium(m, width=800, height=400)
                
            except Exception as e:
                st.warning(f"No se pudo generar el mapa: {str(e)}")
        
        # Tabla de datos
        st.subheader("📊 DATOS DE TEXTURA")
        
        columnas = ['id_zona', 'area_ha', 'textura_nombre_completo', 'arena', 'limo', 'arcilla', 'materia_organica']
        columnas_existentes = [c for c in columnas if c in gdf_textura.columns]
        
        if columnas_existentes:
            df = gdf_textura[columnas_existentes].copy()
            df['area_ha'] = df['area_ha'].round(3)
            df['arena'] = df['arena'].round(1)
            df['limo'] = df['limo'].round(1)
            df['arcilla'] = df['arcilla'].round(1)
            df['materia_organica'] = df['materia_organica'].round(2)
            
            st.dataframe(df, height=300)
        
        # Descarga
        st.subheader("📥 DESCARGAR RESULTADOS")
        
        col1, col2 = st.columns(2)
        with col1:
            if not gdf_textura.empty:
                csv_data = gdf_textura.to_csv(index=False)
                st.download_button(
                    label="📊 Descargar CSV",
                    data=csv_data,
                    file_name=f"textura_{st.session_state.cultivo_seleccionado}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
    except Exception as e:
        st.error(f"Error mostrando análisis: {str(e)}")

def mostrar_analisis_fertilidad():
    """Muestra análisis integral de fertilidad"""
    try:
        if st.session_state.analisis_fertilidad is None:
            st.warning("No hay datos de análisis de fertilidad")
            return
        
        gdf_fertilidad = st.session_state.analisis_fertilidad
        cultivo = st.session_state.cultivo_seleccionado
        
        st.markdown("## 🌿 ANÁLISIS INTEGRAL DE FERTILIDAD")
        
        if st.button("⬅️ Volver", key="volver_fertilidad"):
            st.session_state.analisis_completado = False
            st.rerun()
        
        # Estadísticas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if 'indice_fertilidad' in gdf_fertilidad.columns:
                indice_prom = gdf_fertilidad['indice_fertilidad'].mean()
                st.metric("📈 Índice de Fertilidad", f"{indice_prom:.2f}")
        with col2:
            if 'categoria_fertilidad' in gdf_fertilidad.columns:
                categoria = gdf_fertilidad['categoria_fertilidad'].mode()[0] if not gdf_fertilidad['categoria_fertilidad'].mode().empty else "N/A"
                st.metric("🏆 Categoría", categoria)
        with col3:
            if 'NITROGENO_valor' in gdf_fertilidad.columns:
                n_prom = gdf_fertilidad['NITROGENO_valor'].mean()
                st.metric("🟢 Nitrógeno Prom.", f"{n_prom:.2f}%")
        with col4:
            if 'POTASIO_valor' in gdf_fertilidad.columns:
                k_prom = gdf_fertilidad['POTASIO_valor'].mean()
                st.metric("🟤 Potasio Prom.", f"{k_prom:.3f} cmol/kg")
        
        # Gráfico de índices
        st.subheader("📊 DISTRIBUCIÓN DE ÍNDICES DE FERTILIDAD")
        
        if 'indice_fertilidad' in gdf_fertilidad.columns:
            fig, ax = plt.subplots(figsize=(10, 4))
            indices = gdf_fertilidad['indice_fertilidad'].dropna()
            
            if len(indices) > 0:
                ax.hist(indices, bins=10, color='#4caf50', edgecolor='black', alpha=0.7)
                ax.axvline(x=indices.mean(), color='red', linestyle='--', label=f'Promedio: {indices.mean():.2f}')
                ax.set_xlabel('Índice de Fertilidad (0-1)')
                ax.set_ylabel('Número de Zonas')
                ax.set_title('Distribución de Índices de Fertilidad')
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                st.pyplot(fig)
        
        # Mapa de fertilidad
        st.subheader("🗺️ MAPA DE FERTILIDAD")
        
        if 'indice_fertilidad' in gdf_fertilidad.columns and len(gdf_fertilidad) > 0:
            try:
                centroids = gdf_fertilidad.geometry.centroid
                center_lat = centroids.y.mean()
                center_lon = centroids.x.mean()
                
                m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
                
                for idx, row in gdf_fertilidad.iterrows():
                    indice = row.get('indice_fertilidad', 0.5)
                    
                    # Color basado en índice
                    if indice >= 0.8:
                        color = '#006400'  # Verde oscuro
                    elif indice >= 0.6:
                        color = '#32cd32'  # Verde
                    elif indice >= 0.4:
                        color = '#ffd700'  # Amarillo
                    elif indice >= 0.2:
                        color = '#ff8c00'  # Naranja
                    else:
                        color = '#8b0000'  # Rojo oscuro
                    
                    popup_text = f"""
                    <div style="font-size:12px">
                        <b>Zona {row.get('id_zona', 'N/A')}</b><br>
                        Índice: {indice:.2f}<br>
                        Categoría: {row.get('categoria_fertilidad', 'N/A')}<br>
                        N: {row.get('NITROGENO_valor', 0):.2f}%<br>
                        P: {row.get('FOSFORO_valor', 0):.0f} ppm<br>
                        K: {row.get('POTASIO_valor', 0):.3f} cmol/kg<br>
                        Área: {row.get('area_ha', 0):.2f} ha
                    </div>
                    """
                    
                    folium.GeoJson(
                        row.geometry.__geo_interface__,
                        style_function=lambda x, color=color: {
                            'fillColor': color,
                            'color': 'black',
                            'weight': 1,
                            'fillOpacity': 0.7
                        },
                        popup=folium.Popup(popup_text, max_width=200)
                    ).add_to(m)
                
                # Leyenda
                legend_html = '''
                <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; 
                            background: white; padding: 10px; border: 2px solid grey; z-index: 9999;">
                    <b>🌿 Índice de Fertilidad</b><br>
                    <i style="background: #006400; width: 20px; height: 20px; display: inline-block;"></i> ≥ 0.8 (Excelente)<br>
                    <i style="background: #32cd32; width: 20px; height: 20px; display: inline-block;"></i> 0.6-0.8 (Buena)<br>
                    <i style="background: #ffd700; width: 20px; height: 20px; display: inline-block;"></i> 0.4-0.6 (Moderada)<br>
                    <i style="background: #ff8c00; width: 20px; height: 20px; display: inline-block;"></i> 0.2-0.4 (Baja)<br>
                    <i style="background: #8b0000; width: 20px; height: 20px; display: inline-block;"></i> < 0.2 (Muy Baja)
                </div>
                '''
                
                m.get_root().html.add_child(folium.Element(legend_html))
                st_folium(m, width=800, height=400)
                
            except Exception as e:
                st.warning(f"No se pudo generar el mapa: {str(e)}")
        
        # Tabla de nutrientes principales
        st.subheader("📋 NUTRIENTES PRINCIPALES")
        
        nutrientes_cols = ['id_zona', 'area_ha', 'indice_fertilidad', 'categoria_fertilidad',
                          'NITROGENO_valor', 'FOSFORO_valor', 'POTASIO_valor',
                          'MATERIA_ORGANICA_valor', 'pH_valor']
        
        cols_existentes = [c for c in nutrientes_cols if c in gdf_fertilidad.columns]
        
        if cols_existentes:
            df_nutrientes = gdf_fertilidad[cols_existentes].copy()
            
            # Formatear valores
            if 'NITROGENO_valor' in df_nutrientes.columns:
                df_nutrientes['NITROGENO_valor'] = df_nutrientes['NITROGENO_valor'].apply(lambda x: f"{x:.2f}%")
            if 'FOSFORO_valor' in df_nutrientes.columns:
                df_nutrientes['FOSFORO_valor'] = df_nutrientes['FOSFORO_valor'].apply(lambda x: f"{x:.0f} ppm")
            if 'POTASIO_valor' in df_nutrientes.columns:
                df_nutrientes['POTASIO_valor'] = df_nutrientes['POTASIO_valor'].apply(lambda x: f"{x:.3f}")
            if 'MATERIA_ORGANICA_valor' in df_nutrientes.columns:
                df_nutrientes['MATERIA_ORGANICA_valor'] = df_nutrientes['MATERIA_ORGANICA_valor'].apply(lambda x: f"{x:.1f}%")
            if 'pH_valor' in df_nutrientes.columns:
                df_nutrientes['pH_valor'] = df_nutrientes['pH_valor'].apply(lambda x: f"{x:.1f}")
            if 'indice_fertilidad' in df_nutrientes.columns:
                df_nutrientes['indice_fertilidad'] = df_nutrientes['indice_fertilidad'].apply(lambda x: f"{x:.2f}")
            if 'area_ha' in df_nutrientes.columns:
                df_nutrientes['area_ha'] = df_nutrientes['area_ha'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(df_nutrientes.head(15), height=400)
        
        # Recomendaciones generales
        st.subheader("💡 RECOMENDACIONES GENERALES")
        
        if 'recomendaciones' in gdf_fertilidad.columns and len(gdf_fertilidad) > 0:
            try:
                # Tomar recomendaciones de la primera zona como ejemplo
                rec_text = gdf_fertilidad.iloc[0]['recomendaciones']
                if rec_text:
                    recomendaciones = rec_text.split('; ')
                    for i, rec in enumerate(recomendaciones[:5]):
                        st.markdown(f"• {rec}")
            except:
                pass
            
            # Recomendaciones específicas por cultivo
            st.markdown("#### 📅 Recomendaciones por Cultivo")
            if cultivo == "PALMA_ACEITERA":
                st.info("""
                **Para Palma Aceitera:**
                • Época de fertilización: inicio de lluvias
                • Fraccionamiento: 3-4 aplicaciones anuales
                • Balance NPK recomendado: 12-6-18 + 3MgO
                • Materia orgánica: 3-5 ton/ha anual
                """)
            elif cultivo == "CACAO":
                st.info("""
                **Para Cacao:**
                • Fertilización orgánica preferible
                • Época: después de podas
                • Balance NPK: 15-10-15
                • Evitar aplicación en suelo seco
                """)
        
        # Descarga
        st.subheader("📥 DESCARGAR RESULTADOS")
        
        col1, col2 = st.columns(2)
        with col1:
            if not gdf_fertilidad.empty:
                csv_data = gdf_fertilidad.to_csv(index=False)
                st.download_button(
                    label="📊 Descargar CSV Completo",
                    data=csv_data,
                    file_name=f"fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
    except Exception as e:
        st.error(f"Error mostrando análisis: {str(e)}")

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CONFIGURACIÓN")
        
        # Cultivo
        st.session_state.cultivo_seleccionado = st.selectbox(
            "🌱 Cultivo:",
            ["PALMA_ACEITERA", "CACAO", "BANANO"],
            index=0
        )
        
        # Tipo de análisis
        tipo_analisis = st.selectbox(
            "🔍 Tipo de Análisis:",
            ["ANÁLISIS DE TEXTURA", "FERTILIDAD INTEGRAL", "RECOMENDACIONES COMPLETAS"],
            index=0
        )
        
        # Mes
        st.session_state.mes_analisis = st.selectbox(
            "📅 Mes:",
            list(FACTORES_MES_TROPICALES.keys()),
            index=0
        )
        
        # Opciones
        st.session_state.usar_planetscope = st.checkbox(
            "🛰️ Incluir datos satelitales",
            value=True
        )
        
        # División
        st.subheader("🎯 DIVISIÓN DE PARCELA")
        n_divisiones = st.slider(
            "Número de zonas:",
            12, 36, 24
        )
        
        # Subir archivo
        st.subheader("📤 SUBIR PARCELA")
        uploaded_file = st.file_uploader(
            "Subir archivo (ZIP/KML/SHP)",
            type=['zip', 'kml', 'shp']
        )
        
        # Botones
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reiniciar"):
                for key in list(st.session_state.keys()):
                    if key not in ['_secrets', '_user_info']:
                        del st.session_state[key]
                st.rerun()
        
        with col2:
            if st.button("🎯 Datos Demo"):
                st.session_state.datos_demo = True
                st.session_state.gdf_original = None
                st.rerun()
    
    # Contenido principal
    if not st.session_state.analisis_completado:
        mostrar_interfaz_configuracion(uploaded_file, n_divisiones, tipo_analisis)
    else:
        if tipo_analisis == "ANÁLISIS DE TEXTURA":
            mostrar_analisis_textura()
        elif tipo_analisis == "FERTILIDAD INTEGRAL":
            mostrar_analisis_fertilidad()
        else:
            st.warning("Seleccione un tipo de análisis válido")

def mostrar_interfaz_configuracion(uploaded_file, n_divisiones, tipo_analisis):
    """Muestra interfaz de configuración"""
    
    st.markdown("### 📋 CONFIGURACIÓN DEL ANÁLISIS")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🌱 Cultivo", st.session_state.cultivo_seleccionado.replace('_', ' '))
    with col2:
        st.metric("🔍 Análisis", tipo_analisis)
    with col3:
        st.metric("📅 Mes", st.session_state.mes_analisis)
    
    # Procesar archivo
    if uploaded_file is not None:
        with st.spinner("Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
                st.success("✅ Archivo procesado")
    
    elif st.session_state.datos_demo and st.session_state.gdf_original is None:
        # Datos demo
        poligono = Polygon([
            [-73.5, 5.0], [-73.4, 5.0], [-73.4, 5.1], [-73.5, 5.1], [-73.5, 5.0]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.success("✅ Datos demo creados")
    
    # Mostrar parcela
    if st.session_state.gdf_original is not None:
        gdf_original = st.session_state.gdf_original
        
        st.markdown("### 🗺️ PARCELA CARGADA")
        
        area_total = calcular_superficie(gdf_original)
        st.session_state.area_total = area_total
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📐 Área Total", f"{area_total:.2f} ha")
        with col2:
            st.metric("🔢 N° Polígonos", len(gdf_original))
        
        # Botón de ejecución
        st.markdown("### 🚀 EJECUTAR ANÁLISIS")
        
        if st.button("▶️ Iniciar Análisis", type="primary", use_container_width=True):
            with st.spinner("Dividiendo parcela..."):
                gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
                st.session_state.gdf_zonas = gdf_zonas
            
            with st.spinner("Realizando análisis..."):
                if tipo_analisis == "ANÁLISIS DE TEXTURA":
                    gdf_resultado = analizar_textura_suelo(
                        gdf_zonas, 
                        st.session_state.cultivo_seleccionado, 
                        st.session_state.mes_analisis
                    )
                    st.session_state.analisis_textura = gdf_resultado
                
                elif tipo_analisis == "FERTILIDAD INTEGRAL":
                    gdf_resultado = analizar_fertilidad_integral(
                        gdf_zonas,
                        st.session_state.cultivo_seleccionado,
                        st.session_state.mes_analisis
                    )
                    st.session_state.analisis_fertilidad = gdf_resultado
                
                st.session_state.analisis_completado = True
            
            st.rerun()
    
    else:
        # Instrucciones
        st.markdown("### 🚀 CÓMO COMENZAR")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("""
            **📤 Para comenzar:**
            1. Sube tu archivo de parcela
            2. Selecciona cultivo y análisis
            3. Configura las opciones
            4. Haz clic en 'Iniciar Análisis'
            
            **📄 Formatos soportados:**
            • Shapefile (.zip)
            • Archivo KML
            • Shapefile individual
            """)
        
        with col2:
            st.success("""
            **🔬 Funcionalidades:**
            • Análisis de textura específico
            • Fertilidad integral completa
            • Mapas interactivos
            • Recomendaciones técnicas
            • Descarga de resultados
            """)

# Ejecutar
if __name__ == "__main__":
    main()
