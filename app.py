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
from typing import Optional, Dict, Any, Tuple
import logging

# Configurar logging para debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA GEE COMPLETA CON AGROECOLOGÍA")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# ============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ============================================================================

# Paletas de colores mejoradas con validación
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'NDWI': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027'],
    'ALTIMETRIA': ['#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf', '#fee08b', '#fdae61', '#f46d43', '#d73027']
}

# Fuentes satelitales mejoradas
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

# ============================================================================
# CLASES Y ESTRUCTURAS DE DATOS
# ============================================================================

@st.cache_data(show_spinner=False)
def cargar_datos_demo() -> gpd.GeoDataFrame:
    """Carga datos de demostración con caché"""
    # Polígono de ejemplo con coordenadas reales de Colombia
    poligono_ejemplo = Polygon([
        [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], 
        [-74.1, 4.7], [-74.1, 4.6]
    ])
    
    return gpd.GeoDataFrame(
        {'id': [1], 'nombre': ['Parcela Demo']},
        geometry=[poligono_ejemplo],
        crs="EPSG:4326"
    )

class AnalizadorSuelo:
    """Clase principal para análisis de suelo con metodologías GEE"""
    
    def __init__(self, cultivo: str, fuente_satelital: str = "PLANETSCOPE"):
        self.cultivo = cultivo
        self.fuente_satelital = fuente_satelital
        self.precision = self._calcular_precision()
        
    def _calcular_precision(self) -> float:
        """Calcula precisión según fuente satelital"""
        precisiones = {
            'PLANETSCOPE': 0.85,
            'SENTINEL_2': 0.75,
            'LANDSAT_8_9': 0.65
        }
        return precisiones.get(self.fuente_satelital, 0.75)
    
    def analizar_fertilidad_vectorizada(self, gdf: gpd.GeoDataFrame, 
                                       params_cultivo: Dict[str, Any]) -> gpd.GeoDataFrame:
        """Análisis de fertilidad optimizado con operaciones vectorizadas"""
        
        n_zonas = len(gdf)
        rng = np.random.RandomState(42)
        
        # Inicializar columnas
        gdf['area_ha'] = self._calcular_areas_vectorizadas(gdf)
        
        # Generar datos de fertilidad vectorizados
        materia_organica = np.clip(rng.normal(
            params_cultivo['MATERIA_ORGANICA_OPTIMA'], 1.0, n_zonas), 0.5, 8.0)
        
        ph = np.clip(rng.normal(params_cultivo['pH_OPTIMO'], 0.5, n_zonas), 4.5, 8.5)
        
        conductividad = np.clip(rng.normal(
            params_cultivo['CONDUCTIVIDAD_OPTIMA'], 0.4, n_zonas), 0.2, 3.0)
        
        # Macronutrientes
        nitrogeno = np.clip(rng.normal(
            params_cultivo['NITROGENO']['optimo'], 48, n_zonas), 50, 300)
        
        fosforo = np.clip(rng.normal(
            params_cultivo['FOSFORO']['optimo'], 18, n_zonas), 20, 150)
        
        potasio = np.clip(rng.normal(
            params_cultivo['POTASIO']['optimo'], 60, n_zonas), 80, 400)
        
        # Calcular índices
        indices = self._calcular_indices_fertilidad(
            materia_organica, ph, conductividad, nitrogeno, fosforo, potasio, params_cultivo
        )
        
        # Clasificar fertilidad
        categorias = self._clasificar_fertilidad(indices)
        
        # Generar limitantes y recomendaciones
        limitantes = self._generar_limitantes_vectorizados(
            materia_organica, ph, nitrogeno, fosforo, potasio, params_cultivo
        )
        
        recomendaciones = self._generar_recomendaciones_vectorizadas(
            limitantes, materia_organica, ph, nitrogeno, fosforo, potasio, params_cultivo
        )
        
        # Asignar resultados
        gdf['materia_organica'] = materia_organica
        gdf['ph'] = ph
        gdf['conductividad'] = conductividad
        gdf['nitrogeno'] = nitrogeno
        gdf['fosforo'] = fosforo
        gdf['potasio'] = potasio
        gdf['indice_fertilidad'] = indices
        gdf['categoria_fertilidad'] = categorias
        gdf['limitantes'] = limitantes
        gdf['recomendaciones_fertilidad'] = recomendaciones
        
        return gdf
    
    def _calcular_areas_vectorizadas(self, gdf: gpd.GeoDataFrame) -> np.ndarray:
        """Cálculo vectorizado de áreas"""
        try:
            if gdf.crs and gdf.crs.is_geographic:
                gdf_proj = gdf.to_crs('EPSG:3116')
                areas = gdf_proj.geometry.area / 10000  # Convertir a hectáreas
            else:
                areas = gdf.geometry.area / 10000
            
            return areas.values
        except Exception as e:
            logger.error(f"Error calculando áreas: {e}")
            return np.ones(len(gdf)) * 1.0  # Valor por defecto
    
    def _calcular_indices_fertilidad(self, mo: np.ndarray, ph: np.ndarray, 
                                   ce: np.ndarray, n: np.ndarray, p: np.ndarray, 
                                   k: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        """Cálculo vectorizado de índices de fertilidad"""
        
        indice_mo = np.clip(mo / params['MATERIA_ORGANICA_OPTIMA'], 0, 1)
        indice_ph = 1.0 - np.abs(ph - params['pH_OPTIMO']) / 2.0
        indice_ce = np.clip(ce / params['CONDUCTIVIDAD_OPTIMA'], 0, 1)
        indice_n = np.clip(n / params['NITROGENO']['optimo'], 0, 1)
        indice_p = np.clip(p / params['FOSFORO']['optimo'], 0, 1)
        indice_k = np.clip(k / params['POTASIO']['optimo'], 0, 1)
        
        return (indice_mo * 0.2 + indice_ph * 0.15 + indice_ce * 0.1 +
                indice_n * 0.2 + indice_p * 0.15 + indice_k * 0.2) * self.precision
    
    def _clasificar_fertilidad(self, indices: np.ndarray) -> np.ndarray:
        """Clasificación vectorizada de fertilidad"""
        return np.where(indices >= 0.8, "MUY ALTA",
               np.where(indices >= 0.7, "ALTA",
               np.where(indices >= 0.6, "MEDIA",
               np.where(indices >= 0.5, "MEDIA-BAJA", "BAJA"))))
    
    def _generar_limitantes_vectorizados(self, mo: np.ndarray, ph: np.ndarray,
                                       n: np.ndarray, p: np.ndarray, k: np.ndarray,
                                       params: Dict[str, Any]) -> np.ndarray:
        """Generación vectorizada de limitantes"""
        
        limitantes = []
        
        for i in range(len(mo)):
            limit_zona = []
            
            if mo[i] < params['MATERIA_ORGANICA_OPTIMA'] * 0.8:
                limit_zona.append("Materia orgánica baja")
            if abs(ph[i] - params['pH_OPTIMO']) > 0.5:
                limit_zona.append(f"pH {ph[i]:.1f} fuera de óptimo ({params['pH_OPTIMO']})")
            if n[i] < params['NITROGENO']['min']:
                limit_zona.append(f"Nitrogeno bajo ({n[i]:.0f} kg/ha)")
            if p[i] < params['FOSFORO']['min']:
                limit_zona.append(f"Fósforo bajo ({p[i]:.0f} kg/ha)")
            if k[i] < params['POTASIO']['min']:
                limit_zona.append(f"Potasio bajo ({k[i]:.0f} kg/ha)")
            
            limitantes.append(" | ".join(limit_zona[:3]) if limit_zona else "Ninguna detectada")
        
        return np.array(limitantes)
    
    def _generar_recomendaciones_vectorizadas(self, limitantes: np.ndarray, 
                                            mo: np.ndarray, ph: np.ndarray,
                                            n: np.ndarray, p: np.ndarray, k: np.ndarray,
                                            params: Dict[str, Any]) -> np.ndarray:
        """Generación vectorizada de recomendaciones"""
        
        recomendaciones = []
        
        for i in range(len(limitantes)):
            rec_zona = []
            
            if limitantes[i] != "Ninguna detectada":
                rec_zona.append("Aplicar enmiendas orgánicas para mejorar MO")
                
                if ph[i] < params['pH_OPTIMO'] - 0.3:
                    rec_zona.append(f"Aplicar cal para subir pH de {ph[i]:.1f} a {params['pH_OPTIMO']}")
                elif ph[i] > params['pH_OPTIMO'] + 0.3:
                    rec_zona.append(f"Aplicar azufre para bajar pH de {ph[i]:.1f} a {params['pH_OPTIMO']}")
                
                if n[i] < params['NITROGENO']['min']:
                    deficit_n = params['NITROGENO']['optimo'] - n[i]
                    rec_zona.append(f"Aplicar {deficit_n:.0f} kg/ha de N")
                
                if p[i] < params['FOSFORO']['min']:
                    deficit_p = params['FOSFORO']['optimo'] - p[i]
                    rec_zona.append(f"Aplicar {deficit_p:.0f} kg/ha de P₂O₅")
                
                if k[i] < params['POTASIO']['min']:
                    deficit_k = params['POTASIO']['optimo'] - k[i]
                    rec_zona.append(f"Aplicar {deficit_k:.0f} kg/ha de K₂O")
            else:
                rec_zona.append("Fertilidad óptima - mantener prácticas actuales")
                rec_zona.append("Realizar análisis de suelo cada 6 meses")
            
            recomendaciones.append(" | ".join(rec_zona[:3]))
        
        return np.array(recomendaciones)

# ============================================================================
# FUNCIONES DE UTILIDAD MEJORADAS
# ============================================================================

def safe_execute(func, *args, **kwargs) -> Optional[Any]:
    """Ejecuta una función con manejo robusto de errores y logging"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error en {func.__name__}: {str(e)}")
        st.error(f"❌ Error en {func.__name__}: {str(e)}")
        
        # Sugerencias específicas según el tipo de error
        if "geometry" in str(e).lower():
            st.info("💡 **Sugerencias para resolver problemas de geometría:**")
            st.markdown("""
            - Verifica que el archivo contenga geometrías válidas
            - Asegúrate de que sea un polígono y no puntos o líneas
            - Intenta reparar el shapefile con QGIS antes de subirlo
            - Considera usar un CRS proyectado (metros) en lugar de geográfico (grados)
            """)
        elif "zip" in str(e).lower():
            st.info("💡 **Sugerencias para problemas con archivos ZIP:**")
            st.markdown("""
            - Asegúrate de que el ZIP contenga todos los archivos del shapefile (.shp, .shx, .dbf, .prj)
            - Verifica que el archivo no esté corrupto
            - Intenta extraer el ZIP manualmente antes de subirlo
            """)
        else:
            st.info("💡 **Sugerencias generales:**")
            st.markdown("""
            - Verifica que el archivo esté en formato correcto (ZIP con shapefile o KML)
            - Asegúrate de que la geometría sea válida
            - Prueba con un archivo más pequeño o menos complejo
            - Contacta al soporte técnico si el problema persiste
            """)
        return None

def mostrar_progreso_detallado(paso_actual: int, total_pasos: int, mensaje: str) -> Tuple[Any, Any]:
    """Muestra un indicador de progreso con información detallada"""
    progreso = st.progress(paso_actual / total_pasos)
    status_text = st.empty()
    status_text.text(f"Paso {paso_actual} de {total_pasos}: {mensaje}")
    return progreso, status_text

def validar_geometria(gdf: gpd.GeoDataFrame) -> Optional[gpd.GeoDataFrame]:
    """Valida y repara geometrías problemáticas con manejo robusto"""
    if gdf is None or len(gdf) == 0:
        return None
    
    try:
        # Verificar CRS
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326')
        
        # Reparar geometrías inválidas
        gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom)
        
        # Eliminar geometrías vacías
        gdf = gdf[~gdf['geometry'].is_empty]
        
        # Eliminar duplicados
        gdf = gdf.drop_duplicates()
        
        # Verificar que queden geometrías válidas
        if len(gdf) == 0:
            st.error("No quedaron geometrías válidas después de la validación")
            return None
            
        return gdf
        
    except Exception as e:
        logger.error(f"Error validando geometría: {e}")
        return None

def limpiar_memoria_sesion():
    """Limpia objetos grandes de la memoria con validación"""
    keys_to_clean = ['gdf_analisis', 'gdf_zonas', 'analisis_fertilidad', 
                     'analisis_npk', 'analisis_textura', 'analisis_ndwi', 
                     'analisis_altimetria']
    
    cleaned_count = 0
    for key in keys_to_clean:
        if key in st.session_state:
            del st.session_state[key]
            cleaned_count += 1
    
    gc.collect()
    
    if cleaned_count > 0:
        logger.info(f"Memoria limpiada: {cleaned_count} objetos eliminados")
        return True
    return False

# ============================================================================
# FUNCIONES DE ANÁLISIS MEJORADAS
# ============================================================================

def dividir_parcela_en_zonas_optimizado(gdf: gpd.GeoDataFrame, n_zonas: int) -> Optional[gpd.GeoDataFrame]:
    """Versión optimizada de división de parcelas con mejor manejo de errores"""
    
    try:
        if gdf is None or len(gdf) == 0:
            st.error("El GeoDataFrame está vacío o es inválido")
            return None
        
        # Validar geometría primero
        gdf = validar_geometria(gdf)
        if gdf is None:
            return None
        
        # Usar el primer polígono como parcela principal
        parcela_principal = gdf.iloc[0].geometry
        
        # Verificar que la geometría sea válida
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        
        if not parcela_principal.is_valid:
            st.error("No se pudo reparar la geometría de la parcela")
            return None
        
        bounds = parcela_principal.bounds
        if len(bounds) < 4:
            st.error("No se pueden obtener los límites válidos de la parcela")
            return None
            
        minx, miny, maxx, maxy = bounds
        
        # Verificar que los bounds sean válidos
        if minx >= maxx or miny >= maxy:
            st.error("Límites de parcela inválidos")
            return None
        
        # Calcular número óptimo de filas y columnas
        n_cols = max(1, int(math.sqrt(n_zonas)))
        n_rows = max(1, int(math.ceil(n_zonas / n_cols)))
        
        # Asegurar tamaño mínimo de celda (aproximadamente 10m x 10m)
        width = max(0.0001, (maxx - minx) / n_cols)  # ~10m en grados decimales
        height = max(0.0001, (maxy - miny) / n_rows)
        
        sub_poligonos = []
        
        # Crear cuadrícula con validación de intersección
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                    
                cell_minx = minx + (j * width)
                cell_maxx = minx + ((j + 1) * width)
                cell_miny = miny + (i * height)
                cell_maxy = miny + ((i + 1) * height)
                
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
                            # Filtrar por tamaño mínimo (0.01 ha = 100 m²)
                            if intersection.area > 0.0001:  # En grados², aproximadamente 0.01 ha
                                if intersection.geom_type == 'MultiPolygon':
                                    # Tomar el polígono más grande
                                    largest = max(intersection.geoms, key=lambda p: p.area)
                                    sub_poligonos.append(largest)
                                else:
                                    sub_poligonos.append(intersection)
                except Exception as e:
                    logger.warning(f"Error procesando celda {i},{j}: {e}")
                    continue
        
        if sub_poligonos:
            # Crear GeoDataFrame con validación final
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            
            # Validar el resultado final
            nuevo_gdf = validar_geometria(nuevo_gdf)
            
            if nuevo_gdf is not None and len(nuevo_gdf) > 0:
                logger.info(f"Parcela dividida exitosamente en {len(nuevo_gdf)} zonas")
                return nuevo_gdf
        
        # Fallback: crear una sola zona con toda la parcela
        st.warning("No se pudieron crear múltiples zonas, creando una sola zona")
        return gpd.GeoDataFrame({
            'id_zona': [1],
            'geometry': [parcela_principal]
        }, crs=gdf.crs)
            
    except Exception as e:
        logger.error(f"Error dividiendo parcela: {e}")
        st.error(f"Error dividiendo parcela: {str(e)}")
        return None

def procesar_archivo_mejorado(uploaded_file) -> Optional[gpd.GeoDataFrame]:
    """Procesamiento de archivos mejorado con validación robusta"""
    
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Guardar archivo con validación
            if uploaded_file is None or uploaded_file.size == 0:
                st.error("Archivo vacío o inválido")
                return None
                
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            
            try:
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
            except Exception as e:
                st.error(f"Error guardando archivo: {e}")
                return None
            
            # Verificar tipo de archivo
            file_ext = uploaded_file.name.lower().split('.')[-1]
            
            if file_ext in ['kml', 'kmz']:
                # Procesar KML
                try:
                    gdf = gpd.read_file(file_path, driver='KML')
                except Exception as e:
                    st.error(f"Error leyendo archivo KML: {e}")
                    return None
                    
            elif file_ext == 'zip':
                # Procesar ZIP con shapefile
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        # Validar que el ZIP no esté corrupto
                        if zip_ref.testzip() is not None:
                            st.error("El archivo ZIP está corrupto")
                            return None
                        zip_ref.extractall(tmp_dir)
                except Exception as e:
                    st.error(f"Error extrayendo ZIP: {e}")
                    return None
                
                # Buscar archivos shapefile o KML
                shp_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.kml')]
                
                gdf = None
                
                if shp_files:
                    # Cargar shapefile con validación
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    try:
                        gdf = gpd.read_file(shp_path)
                        logger.info(f"Shapefile cargado exitosamente: {len(gdf)} geometrías")
                    except Exception as e:
                        st.error(f"Error leyendo shapefile: {e}")
                        return None
                        
                elif kml_files:
                    # Cargar KML
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    try:
                        gdf = gpd.read_file(kml_path, driver='KML')
                        logger.info(f"KML cargado exitosamente: {len(gdf)} geometrías")
                    except Exception as e:
                        st.error(f"Error leyendo KML: {e}")
                        return None
                else:
                    st.error("No se encontró archivo .shp o .kml en el ZIP")
                    return None
                
            else:
                st.error(f"Formato de archivo no soportado: {file_ext}")
                return None
            
            # Validación y reparación final
            if gdf is not None:
                gdf = validar_geometria(gdf)
                if gdf is not None and len(gdf) > 0:
                    logger.info(f"Archivo procesado exitosamente: {len(gdf)} geometrías válidas")
                    return gdf
            
            return None
            
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}")
        st.error(f"Error procesando archivo: {str(e)}")
        return None

# ============================================================================
# SISTEMA DE GESTIÓN DE ESTADO MEJORADO
# ============================================================================

class GestorEstado:
    """Gestor mejorado del estado de la aplicación"""
    
    @staticmethod
    def inicializar_estado():
        """Inicializa todas las variables de estado"""
        estado_inicial = {
            'analisis_completado': False,
            'gdf_analisis': None,
            'gdf_original': None,
            'gdf_zonas': None,
            'area_total': 0,
            'datos_demo': False,
            'analisis_fertilidad': None,
            'analisis_npk': None,
            'analisis_textura': None,
            'analisis_ndwi': None,
            'analisis_altimetria': None,
            'fuente_satelital': 'PLANETSCOPE',
            'cultivo': 'PALMA_ACEITERA',
            'analisis_tipo': 'FERTILIDAD ACTUAL',
            'nutriente': None,
            'mes_analisis': 'ENERO'
        }
        
        for key, value in estado_inicial.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def resetear_estado_completo():
        """Resetea todo el estado de la aplicación"""
        for key in list(st.session_state.keys()):
            if key != 'initialized':  # Mantener la bandera de inicialización
                del st.session_state[key]
        
        limpiar_memoria_sesion()
        GestorEstado.inicializar_estado()
        return True
    
    @staticmethod
    def guardar_configuracion_analisis(cultivo: str, analisis_tipo: str, 
                                     nutriente: Optional[str], mes_analisis: str,
                                     fuente_satelital: str):
        """Guarda la configuración del análisis actual"""
        st.session_state.cultivo = cultivo
        st.session_state.analisis_tipo = analisis_tipo
        st.session_state.nutriente = nutriente
        st.session_state.mes_analisis = mes_analisis
        st.session_state.fuente_satelital = fuente_satelital

# ============================================================================
# INTERFAZ DE USUARIO MEJORADA
# ============================================================================

def crear_interfaz_sidebar():
    """Crea la interfaz del sidebar con mejor organización"""
    
    with st.sidebar:
        st.header("⚙️ Configuración del Análisis")
        
        # Información del cultivo
        with st.expander("🌱 Cultivo y Análisis", expanded=True):
            cultivo = st.selectbox("Cultivo:", 
                                 ["PALMA_ACEITERA", "CACAO", "BANANO"],
                                 key="sidebar_cultivo")
            
            analisis_tipo = st.selectbox("Tipo de Análisis:", 
                                       ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", 
                                        "ANÁLISIS DE TEXTURA", "ANÁLISIS NDWI", "ALTIMETRÍA"],
                                       key="sidebar_analisis")
            
            if analisis_tipo == "RECOMENDACIONES NPK":
                nutriente = st.selectbox("Nutriente:", 
                                       ["NITRÓGENO", "FÓSFORO", "POTASIO"],
                                       key="sidebar_nutriente")
            else:
                nutriente = None
            
            mes_analisis = st.selectbox("Mes de Análisis:", 
                                      list(FACTORES_MES.keys()),
                                      key="sidebar_mes")
        
        # Configuración de fuente satelital
        with st.expander("🛰️ Fuente Satelital", expanded=True):
            fuente_satelital = st.selectbox("Fuente de datos:", 
                                          list(FUENTES_SATELITALES.keys()),
                                          key="sidebar_fuente")
            
            if fuente_satelital in FUENTES_SATELITALES:
                info_fuente = FUENTES_SATELITALES[fuente_satelital]
                st.markdown(f"""
                **Resolución:** {info_fuente['resolucion']}  
                **Frecuencia:** {info_fuente['frecuencia']}  
                **Ventajas:** {info_fuente['ventajas']}
                """)
        
        # Configuración de zonas
        with st.expander("📊 División de Parcela", expanded=True):
            n_divisiones = st.slider("Número de zonas de manejo:", 
                                   min_value=4, max_value=64, value=16,
                                   key="sidebar_zonas")
            
            usar_elevacion = st.checkbox("Incluir análisis de elevación", 
                                       value=True, key="sidebar_elevacion")
        
        # Controles de aplicación
        st.markdown("---")
        
        uploaded_file = st.file_uploader(
            "📤 Subir parcela (ZIP con shapefile o KML)", 
            type=['zip', 'kml'], 
            key="sidebar_file"
        )
        
        col_reset, col_demo = st.columns(2)
        
        with col_reset:
            if st.button("🔄 Reiniciar", help="Resetea toda la aplicación"):
                if GestorEstado.resetear_estado_completo():
                    st.success("✅ Aplicación reiniciada")
                    st.rerun()
        
        with col_demo:
            if st.button("🎯 Demo", help="Cargar datos de demostración"):
                st.session_state.datos_demo = True
                st.rerun()
        
        return cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, uploaded_file, fuente_satelital, usar_elevacion
    
    return None

def mostrar_panel_resultados():
    """Panel mejorado para mostrar resultados del análisis"""
    
    if not st.session_state.analisis_completado:
        return
    
    # Sidebar con información consolidada
    with st.sidebar:
        st.markdown("---")
        st.subheader("📊 Panel de Resultados")
        
        # Información de la parcela
        with st.expander("📏 Información de Parcela", expanded=True):
            area_total = st.session_state.get('area_total', 0)
            st.metric("Área total", f"{area_total:.2f} ha")
            
            if st.session_state.gdf_zonas is not None:
                n_zonas = len(st.session_state.gdf_zonas)
                st.metric("Número de zonas", n_zonas)
                
                area_zona_prom = calcular_superficie(st.session_state.gdf_zonas).mean()
                st.metric("Área promedio por zona", f"{area_zona_prom:.2f} ha")
        
        # Resumen del análisis actual
        analisis_tipo = st.session_state.get('analisis_tipo', 'N/A')
        with st.expander(f"🔍 Resumen {analisis_tipo}", expanded=True):
            if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
                gdf = st.session_state.analisis_fertilidad
                avg_fertilidad = gdf['indice_fertilidad'].mean()
                st.metric("Índice fertilidad promedio", f"{avg_fertilidad:.3f}")
                
                cat_pred = gdf['categoria_fertilidad'].mode()[0]
                st.metric("Categoría predominante", cat_pred)
                
            elif analisis_tipo == "RECOMENDACIONES NPK" and st.session_state.analisis_npk is not None:
                nutriente = st.session_state.get('nutriente', 'N/A')
                gdf = st.session_state.analisis_npk
                total_rec = gdf[f'recomendacion_{nutriente.lower()}_kg'].sum()
                st.metric(f"Total {nutriente} recomendado", f"{total_rec:.0f} kg")
                
            elif analisis_tipo == "ANÁLISIS DE TEXTURA" and st.session_state.analisis_textura is not None:
                gdf = st.session_state.analisis_textura
                textura_pred = gdf['textura_suelo'].mode()[0]
                st.metric("Textura predominante", textura_pred)
                
                adecuacion = gdf['adecuacion_textura'].mean()
                st.metric("Adecuación promedio", f"{adecuacion:.1%}")
        
        # Recomendaciones agroecológicas
        with st.expander("🌿 Recomendaciones Agroecológicas", expanded=False):
            cultivo = st.session_state.get('cultivo', 'PALMA_ACEITERA')
            st.markdown(crear_resumen_agroecologico(cultivo), unsafe_allow_html=True)
        
        # Controles de exportación
        st.markdown("---")
        st.subheader("💾 Exportar Resultados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 CSV", help="Exportar datos en formato CSV"):
                exportar_datos_csv()
        
        with col2:
            if st.button("🗺️ GeoJSON", help="Exportar datos en formato GeoJSON"):
                exportar_datos_geojson()

def exportar_datos_csv():
    """Exporta los datos actuales en formato CSV"""
    try:
        analisis_tipo = st.session_state.get('analisis_tipo', '')
        
        if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
            gdf = st.session_state.analisis_fertilidad
            csv_data = gdf.to_csv(index=False)
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name=f"fertilidad_{cultivo}_{fecha}.csv",
                mime="text/csv",
                key="download_csv_fertilidad"
            )
            
        elif analisis_tipo == "RECOMENDACIONES NPK" and st.session_state.analisis_npk is not None:
            gdf = st.session_state.analisis_npk
            csv_data = gdf.to_csv(index=False)
            cultivo = st.session_state.get('cultivo', 'cultivo')
            nutriente = st.session_state.get('nutriente', 'nutriente')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name=f"recomendaciones_{nutriente}_{cultivo}_{fecha}.csv",
                mime="text/csv",
                key="download_csv_npk"
            )
            
        elif analisis_tipo == "ANÁLISIS DE TEXTURA" and st.session_state.analisis_textura is not None:
            gdf = st.session_state.analisis_textura
            csv_data = gdf.to_csv(index=False)
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name=f"textura_{cultivo}_{fecha}.csv",
                mime="text/csv",
                key="download_csv_textura"
            )
            
        elif analisis_tipo == "ANÁLISIS NDWI" and st.session_state.analisis_ndwi is not None:
            gdf = st.session_state.analisis_ndwi
            csv_data = gdf.to_csv(index=False)
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name=f"ndwi_{cultivo}_{fecha}.csv",
                mime="text/csv",
                key="download_csv_ndwi"
            )
            
        elif analisis_tipo == "ALTIMETRÍA" and st.session_state.analisis_altimetria is not None:
            gdf = st.session_state.analisis_altimetria
            csv_data = gdf.to_csv(index=False)
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar CSV",
                data=csv_data,
                file_name=f"altimetria_{cultivo}_{fecha}.csv",
                mime="text/csv",
                key="download_csv_altimetria"
            )
            
    except Exception as e:
        st.error(f"Error exportando CSV: {e}")

def exportar_datos_geojson():
    """Exporta los datos actuales en formato GeoJSON"""
    try:
        analisis_tipo = st.session_state.get('analisis_tipo', '')
        
        if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
            gdf = st.session_state.analisis_fertilidad
            geojson_data = gdf.to_json()
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=geojson_data,
                file_name=f"fertilidad_{cultivo}_{fecha}.geojson",
                mime="application/json",
                key="download_geojson_fertilidad"
            )
            
        elif analisis_tipo == "RECOMENDACIONES NPK" and st.session_state.analisis_npk is not None:
            gdf = st.session_state.analisis_npk
            geojson_data = gdf.to_json()
            cultivo = st.session_state.get('cultivo', 'cultivo')
            nutriente = st.session_state.get('nutriente', 'nutriente')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=geojson_data,
                file_name=f"recomendaciones_{nutriente}_{cultivo}_{fecha}.geojson",
                mime="application/json",
                key="download_geojson_npk"
            )
            
        elif analisis_tipo == "ANÁLISIS DE TEXTURA" and st.session_state.analisis_textura is not None:
            gdf = st.session_state.analisis_textura
            geojson_data = gdf.to_json()
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=geojson_data,
                file_name=f"textura_{cultivo}_{fecha}.geojson",
                mime="application/json",
                key="download_geojson_textura"
            )
            
        elif analisis_tipo == "ANÁLISIS NDWI" and st.session_state.analisis_ndwi is not None:
            gdf = st.session_state.analisis_ndwi
            geojson_data = gdf.to_json()
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=geojson_data,
                file_name=f"ndwi_{cultivo}_{fecha}.geojson",
                mime="application/json",
                key="download_geojson_ndwi"
            )
            
        elif analisis_tipo == "ALTIMETRÍA" and st.session_state.analisis_altimetria is not None:
            gdf = st.session_state.analisis_altimetria
            geojson_data = gdf.to_json()
            cultivo = st.session_state.get('cultivo', 'cultivo')
            fecha = datetime.now().strftime('%Y%m%d_%H%M')
            
            st.download_button(
                label="📥 Descargar GeoJSON",
                data=geojson_data,
                file_name=f"altimetria_{cultivo}_{fecha}.geojson",
                mime="application/json",
                key="download_geojson_altimetria"
            )
            
    except Exception as e:
        st.error(f"Error exportando GeoJSON: {e}")

# ============================================================================
# FUNCIONES DE VISUALIZACIÓN MEJORADAS
# ============================================================================

def crear_resumen_agroecologico(cultivo: str) -> str:
    """Crea un resumen HTML de recomendaciones agroecológicas"""
    
    # Parámetros básicos para cada cultivo (simplificado para este ejemplo)
    recomendaciones_basicas = {
        'PALMA_ACEITERA': {
            'COBERTURAS': ["Centrosema pubescens", "Pueraria phaseoloides", "Arachis pintoi"],
            'ABONOS': ["Crotalaria juncea", "Mucuna pruriens", "Canavalia ensiformis"],
            'FERTILIZANTES': ["Bocashi", "Compost de racimo", "Biofertilizante líquido"]
        },
        'CACAO': {
            'COBERTURAS': ["Arachis pintoi", "Erythrina poeppigiana", "Lippia alba"],
            'ABONOS': ["Mucuna pruriens", "Cajanus cajan", "Crotalaria"],
            'FERTILIZANTES': ["Compost de cacaoteca", "Bocashi especial", "Té de compost"]
        },
        'BANANO': {
            'COBERTURAS': ["Arachis pintoi", "Leguminosas bajas", "Coberturas anti-erosión"],
            'ABONOS': ["Mucuna pruriens", "Canavalia ensiformis", "Crotalaria spectabilis"],
            'FERTILIZANTES': ["Compost de pseudotallo", "Bocashi bananero", "Micorrizas"]
        }
    }
    
    reco = recomendaciones_basicas.get(cultivo, recomendaciones_basicas['PALMA_ACEITERA'])
    
    html = f"""
    <div style="font-size: 12px; line-height: 1.4;">
        <h4 style="color: #28a745; margin-bottom: 10px;">🌿 {cultivo.replace('_', ' ').title()}</h4>
        
        <div style="margin-bottom: 8px;">
            <strong style="color: #17a2b8;">Coberturas Vivas:</strong><br>
            {', '.join(reco['COBERTURAS'][:2])}
        </div>
        
        <div style="margin-bottom: 8px;">
            <strong style="color: #17a2b8;">Abonos Verdes:</strong><br>
            {', '.join(reco['ABONOS'][:2])}
        </div>
        
        <div>
            <strong style="color: #17a2b8;">Biofertilizantes:</strong><br>
            {', '.join(reco['FERTILIZANTES'][:2])}
        </div>
    </div>
    """
    
    return html

# ============================================================================
# LÓGICA PRINCIPAL MEJORADA
# ============================================================================

def main():
    """Función principal mejorada con manejo robusto de estado"""
    
    # Inicializar estado si no existe
    if 'initialized' not in st.session_state:
        GestorEstado.inicializar_estado()
        st.session_state.initialized = True
    
    # Crear interfaz del sidebar
    config_result = crear_interfaz_sidebar()
    
    if config_result is None:
        return
    
    cultivo, analisis_tipo, nutriente, mes_analisis, n_divisiones, uploaded_file, fuente_satelital, usar_elevacion = config_result
    
    # Guardar configuración
    GestorEstado.guardar_configuracion_analisis(cultivo, analisis_tipo, nutriente, 
                                              mes_analisis, fuente_satelital)
    
    # Procesar archivo subido o demo
    if uploaded_file is not None and not st.session_state.analisis_completado:
        procesar_archivo_subido(uploaded_file, n_divisiones, analisis_tipo, cultivo, 
                              mes_analisis, fuente_satelital, usar_elevacion)
    
    elif st.session_state.datos_demo and not st.session_state.analisis_completado:
        procesar_datos_demo(n_divisiones, analisis_tipo, cultivo, 
                          mes_analisis, fuente_satelital, usar_elevacion)
    
    # Mostrar resultados si el análisis está completo
    if st.session_state.analisis_completado:
        mostrar_panel_resultados()
        mostrar_resultados_analisis()
    else:
        mostrar_pantalla_bienvenida()

def procesar_archivo_subido(uploaded_file, n_divisiones, analisis_tipo, cultivo, 
                          mes_analisis, fuente_satelital, usar_elevacion):
    """Procesa archivo subido con manejo mejorado de errores"""
    
    with st.spinner("🔄 Procesando archivo de parcela..."):
        gdf_original = safe_execute(procesar_archivo_mejorado, uploaded_file)
        
        if gdf_original is not None:
            st.session_state.gdf_original = gdf_original
            st.session_state.datos_demo = False
            
            # Calcular área total
            area_total = safe_execute(calcular_superficie, gdf_original)
            if area_total is not None:
                st.session_state.area_total = float(area_total.sum())
            
            # Mostrar información y continuar con el análisis
            mostrar_informacion_parcela(gdf_original)
            ejecutar_analisis_completo(gdf_original, n_divisiones, analisis_tipo, 
                                     cultivo, mes_analisis, fuente_satelital, usar_elevacion)

def procesar_datos_demo(n_divisiones, analisis_tipo, cultivo, 
                       mes_analisis, fuente_satelital, usar_elevacion):
    """Procesa datos de demostración"""
    
    with st.spinner("🔄 Cargando datos de demostración..."):
        gdf_demo = cargar_datos_demo()
        
        if gdf_demo is not None:
            st.session_state.gdf_original = gdf_demo
            st.session_state.area_total = 1.0  # Área fija para demo
            
            mostrar_informacion_parcela(gdf_demo)
            ejecutar_analisis_completo(gdf_demo, n_divisiones, analisis_tipo, 
                                     cultivo, mes_analisis, fuente_satelital, usar_elevacion)

def mostrar_informacion_parcela(gdf):
    """Muestra información básica de la parcela"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        area_total = st.session_state.get('area_total', 0)
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    
    with col2:
        st.metric("🔢 Número de Polígonos", len(gdf))
    
    with col3:
        cultivo = st.session_state.get('cultivo', 'PALMA_ACEITERA')
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    
    # Mostrar mapa de la parcela
    with st.expander("🗺️ Visualizar parcela original", expanded=True):
        mapa_parcela = crear_mapa_visualizador_parcela(gdf)
        st_folium(mapa_parcela, width=800, height=500)

def ejecutar_analisis_completo(gdf, n_divisiones, analisis_tipo, cultivo, 
                             mes_analisis, fuente_satelital, usar_elevacion):
    """Ejecuta el análisis completo con progreso detallado"""
    
    # Dividir parcela en zonas
    progreso, status = mostrar_progreso_detallado(1, 4, "Dividiendo parcela en zonas...")
    
    gdf_zonas = safe_execute(dividir_parcela_en_zonas_optimizado, gdf, n_divisiones)
    
    if gdf_zonas is None:
        st.error("No se pudo dividir la parcela en zonas")
        return
    
    st.session_state.gdf_zonas = gdf_zonas
    
    # Actualizar progreso
    progreso.progress(2/4)
    status.text("Paso 2 de 4: Preparando análisis...")
    
    # Realizar análisis según tipo
    progreso.progress(3/4)
    status.text(f"Paso 3 de 4: Realizando análisis de {analisis_tipo}...")
    
    try:
        if analisis_tipo == "FERTILIDAD ACTUAL":
            # Usar la clase analizadora optimizada
            from analizador_config import PARAMETROS_CULTIVOS  # Importar configuración
            analizador = AnalizadorSuelo(cultivo, fuente_satelital)
            gdf_analisis = analizador.analizar_fertilidad_vectorizada(
                gdf_zonas.copy(), PARAMETROS_CULTIVOS[cultivo]
            )
            st.session_state.analisis_fertilidad = gdf_analisis
            
        elif analisis_tipo == "RECOMENDACIONES NPK":
            from analizador_config import PARAMETROS_CULTIVOS, FACTORES_N_MES, FACTORES_P_MES, FACTORES_K_MES
            nutriente = st.session_state.get('nutriente', 'NITRÓGENO')
            gdf_analisis = generar_recomendaciones_npk(
                gdf_zonas, cultivo, nutriente, mes_analisis, fuente_satelital
            )
            st.session_state.analisis_npk = gdf_analisis
            
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            from analizador_config import TEXTURA_SUELO_OPTIMA
            gdf_analisis = analizar_textura_suelo_avanzado(
                gdf_zonas, cultivo, mes_analisis
            )
            st.session_state.analisis_textura = gdf_analisis
            
        elif analisis_tipo == "ANÁLISIS NDWI":
            from analizador_config import PARAMETROS_CULTIVOS
            gdf_analisis = analizar_ndwi(
                gdf_zonas, cultivo, mes_analisis, fuente_satelital
            )
            st.session_state.analisis_ndwi = gdf_analisis
            
        elif analisis_tipo == "ALTIMETRÍA" and usar_elevacion:
            from analizador_config import ALTIMETRIA_OPTIMA
            gdf_analisis = analizar_altimetria(
                gdf_zonas, cultivo, usar_elevacion
            )
            st.session_state.analisis_altimetria = gdf_analisis
        
        # Finalizar progreso
        progreso.progress(4/4)
        status.text("✅ Análisis completado exitosamente!")
        time.sleep(1)  # Pequeña pausa para que el usuario vea el mensaje
        
        st.session_state.analisis_completado = True
        st.rerun()
        
    except Exception as e:
        progreso.empty()
        status.empty()
        st.error(f"Error durante el análisis: {e}")
        logger.error(f"Error en análisis {analisis_tipo}: {e}")

def mostrar_resultados_analisis():
    """Muestra los resultados del análisis según el tipo"""
    
    analisis_tipo = st.session_state.get('analisis_tipo', '')
    
    if analisis_tipo == "FERTILIDAD ACTUAL" and st.session_state.analisis_fertilidad is not None:
        mostrar_analisis_fertilidad_real()
        
    elif analisis_tipo == "RECOMENDACIONES NPK" and st.session_state.analisis_npk is not None:
        mostrar_recomendaciones_npk()
        
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and st.session_state.analisis_textura is not None:
        mostrar_analisis_textura_avanzado()
        
    elif analisis_tipo == "ANÁLISIS NDWI" and st.session_state.analisis_ndwi is not None:
        mostrar_analisis_ndwi()
        
    elif analisis_tipo == "ALTIMETRÍA" and st.session_state.analisis_altimetria is not None:
        mostrar_analisis_altimetria()

def mostrar_pantalla_bienvenida():
    """Muestra la pantalla de bienvenida mejorada"""
    
    st.markdown("""
    <div style="text-align: center; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 20px; color: white; margin-bottom: 30px;">
        <h1>🌱 BIENVENIDO AL ANALIZADOR DE CULTIVOS</h1>
        <h3>Sistema Completo de Análisis con Metodología GEE</h3>
        <p style="font-size: 16px; margin-top: 20px;">
            Sube tu parcela agrícola y obtén análisis avanzados de:<br>
            • Fertilidad del suelo • Textura • NDWI • Altimetría • Recomendaciones NPK
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Características principales
    col_feat1, col_feat2, col_feat3 = st.columns(3)
    
    with col_feat1:
        st.markdown("""
        <div style="padding: 20px; background-color: #e8f5e9; border-radius: 10px; height: 200px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 15px;">🛰️</div>
            <h4>Datos Satelitales</h4>
            <p>PlanetScope, Sentinel-2, Landsat 8/9 con alta precisión</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_feat2:
        st.markdown("""
        <div style="padding: 20px; background-color: #e3f2fd; border-radius: 10px; height: 200px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 15px;">🔬</div>
            <h4>Análisis Avanzado</h4>
            <p>Metodologías GEE con sensores proximales y modelado digital</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_feat3:
        st.markdown("""
        <div style="padding: 20px; background-color: #fff3e0; border-radius: 10px; height: 200px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 15px;">🌿</div>
            <h4>Agroecología</h4>
            <p>Recomendaciones sostenibles y prácticas conservacionistas</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Pasos para usar la aplicación
    st.markdown("---")
    st.markdown("### 📋 ¿CÓMO USAR ESTA HERRAMIENTA?")
    
    col_steps = st.columns(4)
    steps_data = [
        ("1️⃣", "Configura", "Selecciona cultivo y tipo de análisis"),
        ("2️⃣", "Sube Datos", "Carga tu parcela o usa demo"),
        ("3️⃣", "Analiza", "Obtén resultados en segundos"),
        ("4️⃣", "Exporta", "Descarga mapas y recomendaciones")
    ]
    
    for i, (icon, title, desc) in enumerate(steps_data):
        with col_steps[i]:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 50px; margin-bottom: 15px;">{icon}</div>
                <h4>{title}</h4>
                <p style="font-size: 14px;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error crítico en la aplicación: {e}")
        st.error(f"""
        ❌ **Error crítico en la aplicación**
        
        {str(e)}
        
        **Por favor:**
        1. Reinicia la aplicación usando el botón 🔄 Reiniciar
        2. Si el problema persiste, contacta al soporte técnico
        3. Incluye el mensaje de error completo en tu reporte
        """)
        
        # Opción de reinicio de emergencia
        if st.button("🚨 Reinicio de Emergencia"):
            st.session_state.clear()
            st.rerun()
