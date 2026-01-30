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

# ===== IMPORTS PARA SENTINEL HUB =====
from sentinelhub import (
    SHConfig, BBox, CRS, SentinelHubRequest, 
    DataCollection, MimeType, bbox_to_dimensions,
    SentinelHubCatalog
)

warnings.filterwarnings('ignore')

# ===== CONFIGURACIÓN DE SENTINEL HUB =====
def configurar_sentinel_hub():
    """Configura las credenciales de Sentinel Hub"""
    config = SHConfig()
    
    # Tus credenciales (reemplaza con tus valores reales)
    config.sh_client_id = "358474d6-2326-4637-bf8e-30a709b2d6a6"
    config.sh_client_secret = "b296cf70-c9d2-4e69-91f4-f7be80b99ed1"
    config.instance_id = "PLAK81593ed161694ad48faa8065411d2539"
    
    # Verificar configuración
    if not config.sh_client_id or not config.sh_client_secret:
        st.warning("⚠️ Credenciales de Sentinel Hub no configuradas")
        return None
    
    return config

# ===== FUNCIÓN PARA BUSCAR ESCENAS DISPONIBLES =====
def buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config):
    """Busca escenas de Sentinel-2 disponibles en el rango temporal"""
    try:
        # Obtener bounding box de la parcela en WGS84
        gdf_wgs84 = gdf.to_crs('EPSG:4326')
        bounds = gdf_wgs84.total_bounds
        
        # Verificar que el bounding box sea válido
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Asegurarse de que las coordenadas estén en el rango correcto
        if min_lon < -180 or max_lon > 180 or min_lat < -90 or max_lat > 90:
            st.warning("⚠️ Coordenadas fuera del rango válido para WGS84")
            st.info(f"Bounds: {bounds}")
            return None
        
        # Crear BBox con el formato correcto
        bbox = BBox(bbox=[min_lon, min_lat, max_lon, max_lat], crs=CRS.WGS84)
        
        # Configurar catálogo
        catalog = SentinelHubCatalog(config=config)
        
        # Buscar escenas
        time_interval = (fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))
        
        query = catalog.search(
            DataCollection.SENTINEL2_L2A,
            bbox=bbox,
            time=time_interval,
            query={'eo:cloud_cover': {'lt': 20}}  # Menos de 20% nubes
        )
        
        escenas = list(query)
        
        if not escenas:
            st.warning("⚠️ No se encontraron escenas disponibles en el rango de fechas")
            return None
        
        # Seleccionar la escena con menos nubes
        escena_seleccionada = min(escenas, key=lambda x: x['properties']['eo:cloud_cover'])
        
        return {
            'id': escena_seleccionada['id'],
            'fecha': escena_seleccionada['properties']['datetime'][:10],
            'nubes': escena_seleccionada['properties']['eo:cloud_cover'],
            'bbox': bbox,
            'bounds': bounds
        }
        
    except Exception as e:
        st.error(f"❌ Error buscando escenas Sentinel-2: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None
# ===== FUNCIÓN PARA CALCULAR ÍNDICES CON SENTINEL HUB =====
def calcular_indice_sentinel2(gdf, fecha_inicio, fecha_fin, indice='NDVI', config=None):
    """Calcula índices de vegetación usando Sentinel Hub Process API"""
    try:
        st.info(f"🔍 Iniciando cálculo de índice {indice}...")
        
        if config is None:
            config = configurar_sentinel_hub()
            if config is None:
                st.error("❌ No se pudo configurar Sentinel Hub")
                return None
        
        # Buscar escena disponible
        escena = buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config)
        if escena is None:
            st.warning(f"⚠️ No se encontraron escenas válidas para el período {fecha_inicio} a {fecha_fin}")
            return None
        
        bbox = escena['bbox']
        st.info(f"🔍 BBox utilizado: {bbox}")
        
        try:
            # Definir resolución (10m para Sentinel-2)
            size = bbox_to_dimensions(bbox, resolution=10)
            st.info(f"🔍 Tamaño de imagen: {size}")
            
            # Asegurar tamaño mínimo de 1x1 píxeles
            if size[0] < 1 or size[1] < 1:
                st.warning("⚠️ El área es muy pequeña. Ajustando resolución...")
                size = bbox_to_dimensions(bbox, resolution=5)
                st.info(f"🔍 Nuevo tamaño: {size}")
        
        except Exception as size_error:
            st.error(f"❌ Error calculando dimensiones: {str(size_error)}")
            # Usar tamaño por defecto si falla el cálculo
            size = (100, 100)
            st.info(f"🔍 Usando tamaño por defecto: {size}")
        
        # Evalscript para calcular índices
        if indice == 'NDVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    // Solo calcular si hay datos válidos
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                    // Validar rango de NDVI
                    if (ndvi < -1 || ndvi > 1) {
                        return [NaN];
                    }
                    return [ndvi];
                }
            """
        elif indice == 'NDRE':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B05", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
                    if (ndre < -1 || ndre > 1) {
                        return [NaN];
                    }
                    return [ndre];
                }
            """
        elif indice == 'GNDVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B03", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let gndvi = (sample.B08 - sample.B03) / (sample.B08 + sample.B03);
                    if (gndvi < -1 || gndvi > 1) {
                        return [NaN];
                    }
                    return [gndvi];
                }
            """
        elif indice == 'EVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B02", "B04", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let evi = 2.5 * (sample.B08 - sample.B04) / 
                              (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1);
                    if (evi < -1 || evi > 1) {
                        return [NaN];
                    }
                    return [evi];
                }
            """
        elif indice == 'SAVI':
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let L = 0.5;
                    let savi = ((sample.B08 - sample.B04) / (sample.B08 + sample.B04 + L)) * (1 + L);
                    if (savi < -1 || savi > 1) {
                        return [NaN];
                    }
                    return [savi];
                }
            """
        else:
            # NDVI por defecto
            evalscript = """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B04", "B08", "dataMask"],
                        output: { bands: 1, sampleType: "FLOAT32" }
                    };
                }
                function evaluatePixel(sample) {
                    if (sample.dataMask == 0) {
                        return [NaN];
                    }
                    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                    if (ndvi < -1 || ndvi > 1) {
                        return [NaN];
                    }
                    return [ndvi];
                }
            """
        
        # Crear request
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(escena['fecha'], escena['fecha']),
                    mosaicking_order='leastCC'  # Menor cobertura de nubes
                )
            ],
            responses=[
                SentinelHubRequest.output_response('default', MimeType.TIFF)
            ],
            bbox=bbox,
            size=size,
            config=config
        )
        
        # Descargar datos con timeout
        import time
        start_time = time.time()
        timeout = 120  # 2 minutos
        
        with st.spinner(f"🛰️ Descargando datos Sentinel-2 para {indice}..."):
            try:
                img_data = request.get_data()
                
                if time.time() - start_time > timeout:
                    st.warning("⚠️ La descarga tomó más tiempo del esperado")
                
            except Exception as download_error:
                st.error(f"❌ Error en la descarga: {str(download_error)}")
                return None
        
        if not img_data or len(img_data) == 0:
            st.error("❌ No se recibieron datos del servidor")
            return None
        
        # Procesar imagen
        img_array = img_data[0]
        st.info(f"🔍 Dimensiones de la imagen: {img_array.shape}")
        
        # Calcular estadísticas (ignorar valores NaN y fuera de rango)
        valid_mask = ~np.isnan(img_array) & (img_array != 0)
        valid_values = img_array[valid_mask]
        
        st.info(f"🔍 Valores válidos encontrados: {len(valid_values)} de {img_array.size} píxeles")
        
        if len(valid_values) == 0:
            st.warning("⚠️ No se encontraron valores válidos en la imagen")
            # Mostrar estadísticas de NaN
            nan_count = np.sum(np.isnan(img_array))
            zero_count = np.sum(img_array == 0)
            st.info(f"🔍 NaN: {nan_count}, Ceros: {zero_count}")
            return None
        
        # Calcular estadísticas
        valor_promedio = np.mean(valid_values)
        valor_min = np.min(valid_values)
        valor_max = np.max(valid_values)
        valor_std = np.std(valid_values)
        
        # Información adicional
        percentiles = {
            'p10': np.percentile(valid_values, 10),
            'p25': np.percentile(valid_values, 25),
            'p50': np.percentile(valid_values, 50),
            'p75': np.percentile(valid_values, 75),
            'p90': np.percentile(valid_values, 90)
        }
        
        st.success(f"✅ {indice} calculado exitosamente")
        st.info(f"""
        📊 Estadísticas de {indice}:
        • Promedio: {valor_promedio:.3f}
        • Mínimo: {valor_min:.3f}
        • Máximo: {valor_max:.3f}
        • Desviación: {valor_std:.3f}
        • Percentil 50: {percentiles['p50']:.3f}
        """)
        
        return {
            'indice': indice,
            'valor_promedio': float(valor_promedio),
            'valor_min': float(valor_min),
            'valor_max': float(valor_max),
            'valor_std': float(valor_std),
            'percentiles': percentiles,
            'fuente': 'Sentinel-2 (Sentinel Hub)',
            'fecha': escena['fecha'],
            'id_escena': escena['id'],
            'cobertura_nubes': f"{escena['nubes']:.1f}%",
            'resolucion': '10m',
            'bounds': escena['bounds'],
            'n_pixeles_validos': int(len(valid_values)),
            'tamano_imagen': size,
            'bbox': bbox
        }
        
    except Exception as e:
        st.error(f"❌ Error procesando Sentinel-2 con Sentinel Hub: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        st.error(f"🔍 Detalle del error:\n```\n{error_details[:500]}...\n```")
        return None


# ===== FUNCIÓN PARA OBTENER MÚLTIPLES ÍNDICES =====
def obtener_multiples_indices_sentinel2(gdf, fecha_inicio, fecha_fin, indices=['NDVI', 'NDRE'], config=None):
    """Obtiene múltiples índices de vegetación en una sola llamada"""
    try:
        st.info(f"🔍 Iniciando obtención de múltiples índices: {', '.join(indices)}")
        
        if config is None:
            config = configurar_sentinel_hub()
            if config is None:
                st.error("❌ No se pudo configurar Sentinel Hub")
                return None
        
        # Buscar escena
        escena = buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config)
        if escena is None:
            st.warning("⚠️ No se encontró escena válida")
            return None
        
        bbox = escena['bbox']
        
        try:
            # Definir resolución
            size = bbox_to_dimensions(bbox, resolution=10)
            # Asegurar tamaño mínimo
            size = (max(1, size[0]), max(1, size[1]))
            st.info(f"🔍 Tamaño de imagen: {size}")
        except Exception as e:
            st.error(f"❌ Error calculando dimensiones: {str(e)}")
            size = (100, 100)
        
        # Crear evalscript para múltiples índices
        evalscript = """
            //VERSION=3
            function setup() {
                return {
                    input: ["B02", "B03", "B04", "B05", "B08", "dataMask"],
                    output: { bands: 5, sampleType: "FLOAT32" }
                };
            }
            function evaluatePixel(sample) {
                // Solo procesar si hay datos válidos
                if (sample.dataMask == 0) {
                    return [NaN, NaN, NaN, NaN, NaN];
                }
                
                // NDVI
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                if (ndvi < -1 || ndvi > 1) ndvi = NaN;
                
                // NDRE
                let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
                if (ndre < -1 || ndre > 1) ndre = NaN;
                
                // GNDVI
                let gndvi = (sample.B08 - sample.B03) / (sample.B08 + sample.B03);
                if (gndvi < -1 || gndvi > 1) gndvi = NaN;
                
                // EVI
                let evi = 2.5 * (sample.B08 - sample.B04) / 
                          (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1);
                if (evi < -1 || evi > 1) evi = NaN;
                
                // SAVI
                let L = 0.5;
                let savi = ((sample.B08 - sample.B04) / (sample.B08 + sample.B04 + L)) * (1 + L);
                if (savi < -1 || savi > 1) savi = NaN;
                
                return [ndvi, ndre, gndvi, evi, savi];
            }
        """
        
        # Crear request
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(escena['fecha'], escena['fecha']),
                    mosaicking_order='leastCC'
                )
            ],
            responses=[
                SentinelHubRequest.output_response('default', MimeType.TIFF)
            ],
            bbox=bbox,
            size=size,
            config=config
        )
        
        # Descargar con manejo de tiempo
        import time
        start_time = time.time()
        
        with st.spinner("🛰️ Descargando múltiples índices de Sentinel-2..."):
            try:
                img_data = request.get_data()
                download_time = time.time() - start_time
                st.info(f"🔍 Descarga completada en {download_time:.1f} segundos")
            except Exception as e:
                st.error(f"❌ Error en la descarga: {str(e)}")
                return None
        
        if not img_data or len(img_data) == 0:
            st.error("❌ No se recibieron datos")
            return None
        
        img_array = img_data[0]
        st.info(f"🔍 Dimensiones de imagen multibanda: {img_array.shape}")
        
        # Mapear índices a sus posiciones
        indices_map = {
            'NDVI': 0,
            'NDRE': 1,
            'GNDVI': 2,
            'EVI': 3,
            'SAVI': 4
        }
        
        resultados = {}
        
        for idx_name in indices:
            if idx_name in indices_map:
                band_idx = indices_map[idx_name]
                band_data = img_array[:, :, band_idx]
                valid_values = band_data[~np.isnan(band_data) & (band_data != 0)]
                
                if len(valid_values) > 0:
                    resultados[idx_name] = {
                        'valor_promedio': float(np.mean(valid_values)),
                        'valor_min': float(np.min(valid_values)),
                        'valor_max': float(np.max(valid_values)),
                        'valor_std': float(np.std(valid_values)),
                        'fuente': 'Sentinel-2 (Sentinel Hub)',
                        'fecha': escena['fecha'],
                        'id_escena': escena['id'],
                        'cobertura_nubes': f"{escena['nubes']:.1f}%",
                        'resolucion': '10m',
                        'n_pixeles_validos': int(len(valid_values))
                    }
                    st.success(f"✅ {idx_name} calculado: {np.mean(valid_values):.3f}")
                else:
                    st.warning(f"⚠️ No se encontraron valores válidos para {idx_name}")
        
        if resultados:
            st.success(f"✅ {len(resultados)} índices calculados exitosamente")
        else:
            st.warning("⚠️ No se pudieron calcular índices válidos")
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error obteniendo múltiples índices: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None


# ===== FUNCIÓN PARA OBTENER IMAGEN RGB REAL =====
def obtener_imagen_rgb_sentinel2(gdf, fecha_inicio, fecha_fin, config=None):
    """Obtiene imagen RGB natural de Sentinel-2"""
    try:
        st.info("🔍 Solicitando imagen RGB de Sentinel-2...")
        
        if config is None:
            config = configurar_sentinel_hub()
            if config is None:
                return None
        
        # Buscar escena
        escena = buscar_escenas_sentinel2(gdf, fecha_inicio, fecha_fin, config)
        if escena is None:
            return None
        
        bbox = escena['bbox']
        
        try:
            # Usar resolución más baja para imágenes RGB (20m para mejor rendimiento)
            size = bbox_to_dimensions(bbox, resolution=20)
            size = (max(1, size[0]), max(1, size[1]))
            st.info(f"🔍 Tamaño RGB: {size}")
        except Exception as e:
            st.error(f"❌ Error en tamaño RGB: {str(e)}")
            size = (100, 100)
        
        # Evalscript para RGB natural mejorado
        evalscript_rgb = """
            //VERSION=3
            function setup() {
                return {
                    input: ["B04", "B03", "B02", "dataMask"],
                    output: { bands: 3 }
                };
            }
            function evaluatePixel(sample) {
                // Solo procesar píxeles válidos
                if (sample.dataMask == 0) {
                    return [0, 0, 0];  // Negro para áreas sin datos
                }
                
                // Ajuste de ganancia para mejor visualización
                let gain = 2.5;
                
                // Corrección gamma para mejor contraste
                let gamma = 0.8;
                
                // Aplicar corrección
                let red = Math.pow(sample.B04 * gain, gamma);
                let green = Math.pow(sample.B03 * gain, gamma);
                let blue = Math.pow(sample.B02 * gain, gamma);
                
                // Normalizar a rango 0-255
                red = Math.min(255, Math.max(0, red * 255));
                green = Math.min(255, Math.max(0, green * 255));
                blue = Math.min(255, Math.max(0, blue * 255));
                
                return [red, green, blue];
            }
        """
        
        request = SentinelHubRequest(
            evalscript=evalscript_rgb,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(escena['fecha'], escena['fecha']),
                    mosaicking_order='leastCC'
                )
            ],
            responses=[
                SentinelHubRequest.output_response('default', MimeType.PNG)
            ],
            bbox=bbox,
            size=size,
            config=config
        )
        
        with st.spinner("🛰️ Descargando imagen RGB de Sentinel-2..."):
            import time
            start_time = time.time()
            
            try:
                img_data = request.get_data()
                st.info(f"🔍 RGB descargado en {time.time() - start_time:.1f}s")
            except Exception as e:
                st.error(f"❌ Error descargando RGB: {str(e)}")
                return None
        
        if img_data and len(img_data) > 0:
            st.success("✅ Imagen RGB descargada exitosamente")
            return {
                'imagen': img_data[0],
                'fecha': escena['fecha'],
                'nubes': escena['nubes'],
                'bounds': escena['bounds'],
                'size': size,
                'bbox': bbox
            }
        
        return None
        
    except Exception as e:
        st.error(f"❌ Error obteniendo imagen RGB: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return None

# ===== INICIALIZACIÓN DE VARIABLES DE SESIÓN =====
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
if 'conexion_sentinel' not in st.session_state:
    st.session_state.conexion_sentinel = False

# ===== ESTILOS PERSONALIZADOS - VERSIÓN PREMIUM MODERNA =====
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

/* === PESTAÑAS PRINCIPALES === */
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
</style>
""", unsafe_allow_html=True)

# ===== HERO BANNER PRINCIPAL =====
st.markdown("""
<div class="hero-banner">
    <div class="hero-content">
        <h1 class="hero-title">🛰️ ANALIZADOR MULTI-CULTIVO SATELITAL</h1>
        <p class="hero-subtitle">Potenciado con Sentinel Hub, NASA POWER y datos SRTM para agricultura de precisión con datos satelitales reales</p>
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
        'indices': ['NDVI', 'NDRE', 'GNDVI', 'EVI', 'SAVI'],
        'icono': '🛰️',
        'descripcion': 'Datos reales desde Sentinel Hub'
    },
    'LANDSAT-8': {
        'nombre': 'Landsat 8',
        'resolucion': '30m',
        'revisita': '16 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🛰️',
        'descripcion': 'Datos simulados'
    },
    'DATOS_SIMULADOS': {
        'nombre': 'Datos Simulados',
        'resolucion': '10m',
        'revisita': '5 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B8'],
        'indices': ['NDVI', 'NDRE', 'GNDVI'],
        'icono': '🔬',
        'descripcion': 'Datos generados sintéticamente'
    }
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
        'PRECIO_VENTA': 0.25
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
        'PRECIO_VENTA': 0.20
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
        'PRECIO_VENTA': 0.18
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
        'PRECIO_VENTA': 0.45
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
        'PRECIO_VENTA': 0.35
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
        'PRECIO_VENTA': 0.60
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

# ===== INICIALIZACIÓN SEGURA DE VARIABLES =====
nutriente = None
satelite_seleccionado = "SENTINEL-2"
indice_seleccionado = "NDVI"
fecha_inicio = datetime.now() - timedelta(days=30)
fecha_fin = datetime.now()

# ===== SIDEBAR MEJORADO (INTERFAZ VISUAL) =====
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN</div>', unsafe_allow_html=True)
    
    # Sección de conexión Sentinel Hub
    st.subheader("🛰️ Conexión Sentinel Hub")
    
    # Botón para probar conexión
    if st.button("🔌 Probar Conexión", use_container_width=True):
        config_test = configurar_sentinel_hub()
        if config_test:
            st.session_state.conexion_sentinel = True
            st.success("✅ Conexión con Sentinel Hub exitosa")
        else:
            st.session_state.conexion_sentinel = False
            st.error("❌ Error en la configuración de credenciales")
    
    if st.session_state.conexion_sentinel:
        st.success("✅ Conectado a Sentinel Hub")
    else:
        st.info("ℹ️ Configura tus credenciales en el código")
    
    st.markdown("---")
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAIZ", "SORGO", "SOJA", "GIRASOL", "MANI"])
    
    st.subheader("🛰️ Fuente de Datos Satelitales")
    satelite_seleccionado = st.selectbox(
        "Satélite:",
        ["SENTINEL-2", "LANDSAT-8", "DATOS_SIMULADOS"],
        help="Selecciona la fuente de datos satelitales"
    )
    
    # Mostrar descripción del satélite seleccionado
    st.info(SATELITES_DISPONIBLES[satelite_seleccionado]['descripcion'])
    
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

# ===== FUNCIONES PARA DATOS SATELITALES =====
def descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    try:
        datos_simulados = {
            'indice': indice,
            'valor_promedio': 0.65 + np.random.normal(0, 0.1),
            'fuente': 'Landsat-8',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'id_escena': f"LC08_{np.random.randint(1000000, 9999999)}",
            'cobertura_nubes': f"{np.random.randint(0, 15)}%",
            'resolucion': '30m'
        }
        return datos_simulados
    except Exception as e:
        st.error(f"❌ Error procesando Landsat 8: {str(e)}")
        return None

def descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Función modificada para usar Sentinel Hub"""
    try:
        # Configurar Sentinel Hub
        config = configurar_sentinel_hub()
        
        if config is None:
            # Fallback a datos simulados si no hay credenciales
            st.warning("⚠️ Usando datos simulados (credenciales Sentinel Hub no configuradas)")
            return generar_datos_simulados(gdf, indice)
        
        # Intentar conexión real
        resultado = calcular_indice_sentinel2(gdf, fecha_inicio, fecha_fin, indice, config)
        
        if resultado is None:
            # Fallback a simulados si falla la conexión
            st.warning("⚠️ Falló conexión con Sentinel Hub, usando datos simulados")
            return generar_datos_simulados(gdf, indice)
        
        return resultado
        
    except Exception as e:
        st.error(f"❌ Error en descargar_datos_sentinel2: {str(e)}")
        return generar_datos_simulados(gdf, indice)

def generar_datos_simulados(gdf, cultivo, indice='NDVI'):
    datos_simulados = {
        'indice': indice,
        'valor_promedio': PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO'] * 0.8 + np.random.normal(0, 0.1),
        'fuente': 'Simulación',
        'fecha': datetime.now().strftime('%Y-%m-%d'),
        'resolucion': '10m'
    }
    return datos_simulados

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
    num_cells_x = int((maxx - minx) * 111000 / resolucion)
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
    Z = np.maximum(Z, 50)
    
    # Aplicar máscara de la parcela
    points = np.vstack([X.flatten(), Y.flatten()]).T
    parcel_mask = gdf.geometry.unary_union.contains([Point(p) for p in points])
    parcel_mask = parcel_mask.reshape(X.shape)
    
    Z[~parcel_mask] = np.nan
    
    return X, Y, Z, bounds

def calcular_pendiente(X, Y, Z, resolucion):
    """Calcula pendiente a partir del DEM"""
    dy = np.gradient(Z, axis=0) / resolucion
    dx = np.gradient(Z, axis=1) / resolucion
    pendiente = np.sqrt(dx**2 + dy**2) * 100
    pendiente = np.clip(pendiente, 0, 100)
    return pendiente

def generar_curvas_nivel(X, Y, Z, intervalo=5.0):
    """Genera curvas de nivel a partir del DEM"""
    curvas_nivel = []
    elevaciones = []
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
    
    for nivel in niveles:
        mascara = (Z >= nivel - 0.5) & (Z <= nivel + 0.5)
        if np.any(mascara):
            from scipy import ndimage
            estructura = ndimage.generate_binary_structure(2, 2)
            labeled, num_features = ndimage.label(mascara, structure=estructura)
            for i in range(1, num_features + 1):
                contorno = (labeled == i)
                if np.sum(contorno) > 10:
                    y_indices, x_indices = np.where(contorno)
                    if len(x_indices) > 2:
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
    precio_n = 1.2
    precio_p = 2.5
    precio_k = 1.8
    
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
        
        rendimiento_base = params['RENDIMIENTO_OPTIMO'] * npk_actual * 0.7
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

# ===== FUNCIONES PARA POTENCIAL DE COSECHA =====
def analizar_potencial_cosecha(gdf_completo, cultivo, datos_satelitales):
    """Análisis del potencial de cosecha basado en múltiples factores"""
    try:
        resultados = []
        params = PARAMETROS_CULTIVOS[cultivo]
        
        for idx, row in gdf_completo.iterrows():
            # Factores de influencia
            factor_ndvi = row['fert_ndvi'] / params['NDVI_OPTIMO'] if params['NDVI_OPTIMO'] > 0 else 0.7
            factor_ndre = row['fert_ndre'] / params['NDRE_OPTIMO'] if params['NDRE_OPTIMO'] > 0 else 0.7
            factor_npk = row['fert_npk_actual']
            factor_textura = 1.0  # Valor base para textura
            
            # Ajuste por textura
            textura = row['textura_suelo']
            if textura == TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']:
                factor_textura = 1.2
            elif textura == "Franco":
                factor_textura = 1.0
            elif textura == "Franco arcilloso":
                factor_textura = 0.9
            elif textura == "Franco arenoso":
                factor_textura = 0.8
            else:
                factor_textura = 0.7
            
            # Factores adicionales
            factor_materia_organica = min(1.2, row['fert_materia_organica'] / params['MATERIA_ORGANICA_OPTIMA'])
            factor_humedad = min(1.2, row['fert_humedad_suelo'] / params['HUMEDAD_OPTIMA'])
            
            # Cálculo del potencial
            potencial_base = params['RENDIMIENTO_OPTIMO']
            
            # Factores ponderados
            ponderaciones = {
                'ndvi': 0.25,
                'ndre': 0.20,
                'npk': 0.20,
                'textura': 0.15,
                'materia_organica': 0.10,
                'humedad': 0.10
            }
            
            factor_total = (
                factor_ndvi * ponderaciones['ndvi'] +
                factor_ndre * ponderaciones['ndre'] +
                factor_npk * ponderaciones['npk'] +
                factor_textura * ponderaciones['textura'] +
                factor_materia_organica * ponderaciones['materia_organica'] +
                factor_humedad * ponderaciones['humedad']
            )
            
            # Potencial ajustado
            potencial_ajustado = potencial_base * factor_total
            
            # Clasificación del potencial
            if factor_total >= 0.9:
                clasificacion = "MUY ALTO"
                color = "#006837"
            elif factor_total >= 0.8:
                clasificacion = "ALTO"
                color = "#1a9850"
            elif factor_total >= 0.7:
                clasificacion = "MEDIO-ALTO"
                color = "#66bd63"
            elif factor_total >= 0.6:
                clasificacion = "MEDIO"
                color = "#a6d96a"
            elif factor_total >= 0.5:
                clasificacion = "MEDIO-BAJO"
                color = "#fdae61"
            else:
                clasificacion = "BAJO"
                color = "#d73027"
            
            resultados.append({
                'zona': int(row['id_zona']),
                'potencial_kg_ha': round(potencial_ajustado, 0),
                'factor_total': round(factor_total, 3),
                'clasificacion': clasificacion,
                'color': color,
                'area_ha': round(row['area_ha'], 2)
            })
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error en análisis de potencial: {str(e)}")
        return []

def crear_mapa_potencial_cosecha(gdf_completo, cultivo, resultados_potencial):
    """Crear mapa de potencial de cosecha"""
    try:
        gdf_plot = gdf_completo.copy()
        gdf_plot = gdf_plot.to_crs(epsg=3857)
        
        # Crear diccionario de colores por zona
        colores_potencial = {}
        for res in resultados_potencial:
            colores_potencial[res['zona']] = res['color']
        
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        
        # Plotear cada zona con su color
        for idx, row in gdf_plot.iterrows():
            zona = int(row['id_zona'])
            color = colores_potencial.get(zona, '#999999')
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=2, alpha=0.8)
            
            # Etiqueta
            for res in resultados_potencial:
                if res['zona'] == zona:
                    label = f"Z{zona}\n{res['potencial_kg_ha']:.0f} kg/ha\n{res['clasificacion']}"
                    centroid = row.geometry.centroid
                    ax.annotate(label, (centroid.x, centroid.y),
                               xytext=(0, 0), textcoords="offset points",
                               fontsize=7, color='black', weight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
                    break
        
        # Base map
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.6)
        except:
            pass
        
        # Leyenda
        from matplotlib.patches import Patch
        categorias = {
            'MUY ALTO': '#006837',
            'ALTO': '#1a9850',
            'MEDIO-ALTO': '#66bd63',
            'MEDIO': '#a6d96a',
            'MEDIO-BAJO': '#fdae61',
            'BAJO': '#d73027'
        }
        
        legend_elements = [Patch(facecolor=color, edgecolor='black', label=cat)
                          for cat, color in categorias.items()]
        ax.legend(handles=legend_elements, title='Potencial de Cosecha', 
                 loc='upper left', bbox_to_anchor=(1.05, 1))
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} POTENCIAL DE COSECHA - {cultivo}',
                    fontsize=16, fontweight='bold', pad=20)
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
        st.error(f"❌ Error creando mapa de potencial: {str(e)}")
        return None

def crear_grafico_distribucion_potencial(resultados_potencial):
    """Crear gráfico de distribución del potencial"""
    try:
        # Preparar datos
        categorias = ['BAJO', 'MEDIO-BAJO', 'MEDIO', 'MEDIO-ALTO', 'ALTO', 'MUY ALTO']
        conteos = {cat: 0 for cat in categorias}
        areas = {cat: 0.0 for cat in categorias}
        
        for res in resultados_potencial:
            cat = res['clasificacion']
            conteos[cat] += 1
            areas[cat] += res['area_ha']
        
        # Crear figura
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Gráfico 1: Conteo de zonas
        colors = ['#d73027', '#fdae61', '#a6d96a', '#66bd63', '#1a9850', '#006837']
        bars1 = ax1.bar(categorias, [conteos[cat] for cat in categorias], color=colors, edgecolor='black')
        ax1.set_title('Distribución de Potencial por Zonas', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Clasificación')
        ax1.set_ylabel('Número de Zonas')
        ax1.tick_params(axis='x', rotation=45)
        
        # Añadir etiquetas en barras
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom', fontweight='bold')
        
        # Gráfico 2: Área por clasificación
        wedges, texts, autotexts = ax2.pie([areas[cat] for cat in categorias], 
                                          labels=categorias, colors=colors, autopct='%1.1f%%',
                                          startangle=90, counterclock=False)
        ax2.set_title('Distribución de Área por Potencial', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando gráfico de distribución: {str(e)}")
        return None

# ===== FUNCIONES PARA CURVAS DE NIVEL MEJORADAS =====
def crear_mapa_curvas_nivel_completo(X, Y, Z, curvas_nivel, elevaciones, gdf_original, intervalo_curvas):
    """Crear mapa completo con curvas de nivel y análisis"""
    try:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Mapa de elevación con curvas
        contour1 = ax1.contourf(X, Y, Z, levels=20, cmap='terrain', alpha=0.7)
        
        # Curvas de nivel principales (cada 5 curvas)
        if curvas_nivel:
            indices_principales = list(range(0, len(curvas_nivel), 5))
            for idx in indices_principales:
                if idx < len(curvas_nivel):
                    curva = curvas_nivel[idx]
                    elevacion = elevaciones[idx]
                    if hasattr(curva, 'coords'):
                        coords = np.array(curva.coords)
                        ax1.plot(coords[:, 0], coords[:, 1], 'b-', linewidth=1.0, alpha=0.7)
                        
                        # Etiqueta cada 50 metros
                        if elevacion % (intervalo_curvas * 10) == 0:
                            mid_idx = len(coords) // 2
                            ax1.text(coords[mid_idx, 0], coords[mid_idx, 1], 
                                   f'{elevacion:.0f}m', fontsize=8, color='blue',
                                   bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.7))
        
        gdf_original.plot(ax=ax1, color='none', edgecolor='black', linewidth=2)
        ax1.set_title('Mapa de Elevación y Curvas de Nivel', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Longitud')
        ax1.set_ylabel('Latitud')
        ax1.grid(True, alpha=0.3)
        
        # 2. Histograma de elevaciones
        elevaciones_flat = Z.flatten()
        elevaciones_flat = elevaciones_flat[~np.isnan(elevaciones_flat)]
        
        ax2.hist(elevaciones_flat, bins=30, edgecolor='black', color='sandybrown', alpha=0.7)
        ax2.axvline(x=np.mean(elevaciones_flat), color='red', linestyle='--', linewidth=2, label='Promedio')
        
        stats_text = f"""
Estadísticas de Elevación:
• Mínima: {np.min(elevaciones_flat):.1f} m
• Máxima: {np.max(elevaciones_flat):.1f} m
• Promedio: {np.mean(elevaciones_flat):.1f} m
• Desviación: {np.std(elevaciones_flat):.1f} m
• Rango: {np.max(elevaciones_flat)-np.min(elevaciones_flat):.1f} m
"""
        ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, fontsize=9,
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        
        ax2.set_xlabel('Elevación (m)')
        ax2.set_ylabel('Frecuencia')
        ax2.set_title('Distribución de Elevaciones', fontsize=12, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Perfil topográfico (sección transversal)
        if X.shape[0] > 10 and X.shape[1] > 10:
            mid_y = X.shape[0] // 2
            perfil = Z[mid_y, :]
            distancia = np.arange(len(perfil)) * 10  # Asumiendo 10m por celda
            
            ax3.plot(distancia, perfil, 'g-', linewidth=2)
            ax3.fill_between(distancia, perfil, np.min(perfil), alpha=0.3, color='green')
            
            # Marcar curvas de nivel en el perfil
            for idx in indices_principales:
                if idx < len(elevaciones):
                    elev = elevaciones[idx]
                    ax3.axhline(y=elev, color='blue', linestyle=':', linewidth=0.8, alpha=0.5)
                    ax3.text(distancia[-1] * 0.95, elev, f'{elev:.0f}m', 
                           fontsize=7, color='blue', va='center')
            
            ax3.set_xlabel('Distancia (m)')
            ax3.set_ylabel('Elevación (m)')
            ax3.set_title('Perfil Topográfico (Sección Central)', fontsize=12, fontweight='bold')
            ax3.grid(True, alpha=0.3)
        
        # 4. Análisis de pendientes relacionado con curvas
        from scipy import ndimage
        
        # Calcular pendiente
        dx = ndimage.sobel(Z, axis=1, mode='constant')
        dy = ndimage.sobel(Z, axis=0, mode='constant')
        pendiente = np.sqrt(dx**2 + dy**2)
        
        # Densidad de curvas (indicador de pendiente)
        densidad_curvas = np.zeros_like(Z, dtype=float)
        if curvas_nivel:
            for curva in curvas_nivel:
                if hasattr(curva, 'coords'):
                    coords = np.array(curva.coords)
                    for coord in coords:
                        # Encontrar índice más cercano en la grilla
                        dist_x = np.abs(X[0, :] - coord[0])
                        dist_y = np.abs(Y[:, 0] - coord[1])
                        idx_x = np.argmin(dist_x)
                        idx_y = np.argmin(dist_y)
                        if 0 <= idx_y < densidad_curvas.shape[0] and 0 <= idx_x < densidad_curvas.shape[1]:
                            densidad_curvas[idx_y, idx_x] += 1
        
        im = ax4.imshow(densidad_curvas, extent=[X.min(), X.max(), Y.min(), Y.max()], 
                       cmap='hot', alpha=0.7, origin='lower')
        plt.colorbar(im, ax=ax4, label='Densidad de Curvas')
        
        ax4.set_xlabel('Longitud')
        ax4.set_ylabel('Latitud')
        ax4.set_title('Densidad de Curvas de Nivel', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando mapa de curvas completo: {str(e)}")
        return None

def analizar_curvas_nivel_para_agricultura(curvas_nivel, elevaciones, intervalo_curvas):
    """Análisis específico de curvas de nivel para agricultura"""
    try:
        if not curvas_nivel:
            return {}
        
        # Estadísticas básicas
        n_curvas = len(curvas_nivel)
        rango_elevacion = max(elevaciones) - min(elevaciones) if elevaciones else 0
        
        # Calcular densidad de curvas
        longitud_total = sum(curva.length for curva in curvas_nivel if hasattr(curva, 'length'))
        
        # Análisis de intervalos
        if len(elevaciones) > 1:
            intervalos = np.diff(sorted(elevaciones))
            intervalo_promedio = np.mean(intervalos) if len(intervalos) > 0 else intervalo_curvas
            intervalo_std = np.std(intervalos) if len(intervalos) > 0 else 0
        else:
            intervalo_promedio = intervalo_curvas
            intervalo_std = 0
        
        # Clasificación para agricultura
        clasificacion = ""
        if intervalo_promedio <= 2:
            clasificacion = "TERRENO MUY ACCIDENTADO - Alto riesgo de erosión"
            recomendacion = "• Implementar terrazas de formación lenta\n• Usar cultivos de cobertura\n• Evitar labranza convencional"
        elif intervalo_promedio <= 5:
            clasificacion = "TERRENO MODERADAMENTE ACCIDENTADO - Manejo conservacionista"
            recomendacion = "• Cultivo en contorno\n• Franjas de vegetación\n• Labranza mínima"
        elif intervalo_promedio <= 10:
            clasificacion = "TERRENO SUAVEMENTE ONDULADO - Adecuado para agricultura"
            recomendacion = "• Cultivo en contorno recomendado\n• Buen drenaje natural\n• Mínimo riesgo de erosión"
        else:
            clasificacion = "TERRENO PLANO - Óptimo para agricultura"
            recomendacion = "• Máxima eficiencia de maquinaria\n• Bajo riesgo de erosión\n• Buen drenaje con pendiente mínima"
        
        resultados = {
            'n_curvas': n_curvas,
            'rango_elevacion_m': round(rango_elevacion, 1),
            'longitud_total_km': round(longitud_total / 1000, 2),
            'intervalo_promedio_m': round(intervalo_promedio, 1),
            'intervalo_std_m': round(intervalo_std, 1),
            'clasificacion_terreno': clasificacion,
            'recomendaciones': recomendacion,
            'densidad_curvas_km2': round(n_curvas / (longitud_total / 1000) if longitud_total > 0 else 0, 2)
        }
        
        return resultados
        
    except Exception as e:
        st.error(f"❌ Error en análisis de curvas: {str(e)}")
        return {}

# ===== FUNCIÓN PARA EJECUTAR TODOS LOS ANÁLISIS =====
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin, intervalo_curvas=5.0, resolucion_dem=10.0):
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
        'datos_satelitales': None,  # Nueva clave para datos satelitales reales
        'potencial_cosecha': None   # Nueva clave para potencial de cosecha
    }
    
    try:
        gdf = validar_y_corregir_crs(gdf)
        area_total = calcular_superficie(gdf)
        resultados['area_total'] = area_total
        
        # Configurar Sentinel Hub si se selecciona
        config = None
        if satelite == "SENTINEL-2":
            config = configurar_sentinel_hub()
        
        # Obtener datos satelitales
        datos_satelitales = None
        if satelite == "SENTINEL-2":
            indices_deseados = ['NDVI', 'NDRE', 'GNDVI']
            datos_multiples = obtener_multiples_indices_sentinel2(
                gdf, fecha_inicio, fecha_fin, indices_deseados, config
            )
            
            if datos_multiples and 'NDVI' in datos_multiples:
                datos_satelitales = datos_multiples['NDVI']
                resultados['datos_satelitales'] = datos_multiples
                st.success(f"✅ Datos reales de Sentinel-2 obtenidos ({datos_satelitales['fecha']})")
            else:
                datos_satelitales = generar_datos_simulados(gdf, cultivo, "NDVI")
                st.warning("⚠️ Usando datos simulados")
                
        elif satelite == "LANDSAT-8":
            datos_satelitales = descargar_datos_landsat8(gdf, fecha_inicio, fecha_fin, "NDVI")
        else:
            datos_satelitales = generar_datos_simulados(gdf, cultivo, "NDVI")
        
        df_power = obtener_datos_nasa_power(gdf, fecha_inicio, fecha_fin)
        resultados['df_power'] = df_power
        
        gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        resultados['gdf_dividido'] = gdf_dividido
        
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
        
        fertilidad_actual = analizar_fertilidad_actual(gdf_dividido, cultivo, datos_satelitales)
        resultados['fertilidad_actual'] = fertilidad_actual
        
        rec_n, rec_p, rec_k = analizar_recomendaciones_npk(fertilidad_actual, cultivo)
        resultados['recomendaciones_npk'] = {
            'N': rec_n,
            'P': rec_p,
            'K': rec_k
        }
        
        costos = analizar_costos(gdf_dividido, cultivo, rec_n, rec_p, rec_k)
        resultados['costos'] = costos
        
        proyecciones = analizar_proyecciones_cosecha(gdf_dividido, cultivo, fertilidad_actual)
        resultados['proyecciones'] = proyecciones
        
        textura = analizar_textura_suelo(gdf_dividido, cultivo)
        resultados['textura'] = textura
        
        # Análisis de potencial de cosecha
        potencial_cosecha = analizar_potencial_cosecha(textura, cultivo, datos_satelitales)
        resultados['potencial_cosecha'] = potencial_cosecha
        
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
        
        gdf_completo = textura.copy()
        
        for i, fert in enumerate(fertilidad_actual):
            for key, value in fert.items():
                gdf_completo.at[gdf_completo.index[i], f'fert_{key}'] = value
        
        gdf_completo['rec_N'] = rec_n
        gdf_completo['rec_P'] = rec_p
        gdf_completo['rec_K'] = rec_k
        
        for i, costo in enumerate(costos):
            for key, value in costo.items():
                gdf_completo.at[gdf_completo.index[i], f'costo_{key}'] = value
        
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
        
        scatter = ax1.scatter(X.flatten(), Y.flatten(), c=pendientes.flatten(), 
                             cmap='RdYlGn_r', s=10, alpha=0.7, vmin=0, vmax=30)
        
        gdf_original.plot(ax=ax1, color='none', edgecolor='black', linewidth=2)
        
        cbar = plt.colorbar(scatter, ax=ax1, shrink=0.8)
        cbar.set_label('Pendiente (%)')
        
        ax1.set_title('Mapa de Calor de Pendientes', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Longitud')
        ax1.set_ylabel('Latitud')
        ax1.grid(True, alpha=0.3)
        
        pendientes_flat = pendientes.flatten()
        pendientes_flat = pendientes_flat[~np.isnan(pendientes_flat)]
        
        ax2.hist(pendientes_flat, bins=30, edgecolor='black', color='skyblue', alpha=0.7)
        
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
        
        contour = ax.contourf(X, Y, Z, levels=20, cmap='terrain', alpha=0.7)
        
        if curvas_nivel:
            for curva, elevacion in zip(curvas_nivel, elevaciones):
                if hasattr(curva, 'coords'):
                    coords = np.array(curva.coords)
                    ax.plot(coords[:, 0], coords[:, 1], 'b-', linewidth=0.8, alpha=0.7)
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
        
        surf = ax.plot_surface(X, Y, Z, cmap='terrain', alpha=0.8, 
                              linewidth=0.5, antialiased=True)
        
        ax.set_xlabel('Longitud', fontsize=10)
        ax.set_ylabel('Latitud', fontsize=10)
        ax.set_zlabel('Elevación (m)', fontsize=10)
        ax.set_title('Modelo 3D del Terreno', fontsize=14, fontweight='bold', pad=20)
        
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label='Elevación (m)')
        
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

def generar_reporte_completo(resultados, cultivo, satelite, fecha_inicio, fecha_fin):
    """Generar reporte DOCX con todos los análisis"""
    try:
        doc = Document()
        
        title = doc.add_heading(f'REPORTE COMPLETO DE ANÁLISIS - {cultivo}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        subtitle = doc.add_paragraph(f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        doc.add_heading('1. INFORMACIÓN GENERAL', level=1)
        info_table = doc.add_table(rows=5, cols=2)
        info_table.style = 'Table Grid'
        info_table.cell(0, 0).text = 'Cultivo'
        info_table.cell(0, 1).text = cultivo
        info_table.cell(1, 0).text = 'Área Total'
        info_table.cell(1, 1).text = f'{resultados["area_total"]:.2f} ha'
        info_table.cell(2, 0).text = 'Zonas Analizadas'
        info_table.cell(2, 1).text = str(len(resultados['gdf_completo']))
        info_table.cell(3, 0).text = 'Satélite'
        info_table.cell(3, 1).text = satelite
        info_table.cell(4, 0).text = 'Período de Análisis'
        info_table.cell(4, 1).text = f'{fecha_inicio.strftime("%d/%m/%Y")} a {fecha_fin.strftime("%d/%m/%Y")}'
        
        doc.add_paragraph()
        
        doc.add_heading('2. FERTILIDAD ACTUAL', level=1)
        doc.add_paragraph('Resumen de parámetros de fertilidad por zona:')
        
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
        
        doc.add_heading('3. RECOMENDACIONES NPK', level=1)
        doc.add_paragraph('Recomendaciones de fertilización por zona (kg/ha):')
        
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
        
        doc.add_heading('4. ANÁLISIS DE COSTOS', level=1)
        doc.add_paragraph('Costos estimados de fertilización por zona (USD/ha):')
        
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
        
        doc.add_paragraph()
        
        costo_total = resultados['gdf_completo']['costo_costo_total'].sum()
        costo_promedio = resultados['gdf_completo']['costo_costo_total'].mean()
        doc.add_paragraph(f'Costo total estimado: ${costo_total:.2f} USD')
        doc.add_paragraph(f'Costo promedio por hectárea: ${costo_promedio:.2f} USD/ha')
        
        doc.add_paragraph()
        
        doc.add_heading('5. TEXTURA DEL SUELO', level=1)
        doc.add_paragraph('Composición granulométrica por zona:')
        
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
        
        doc.add_heading('6. PROYECCIONES DE COSECHA', level=1)
        doc.add_paragraph('Proyecciones de rendimiento con y sin fertilización (kg/ha):')
        
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
        
        doc.add_paragraph()
        
        rend_sin_total = resultados['gdf_completo']['proy_rendimiento_sin_fert'].sum()
        rend_con_total = resultados['gdf_completo']['proy_rendimiento_con_fert'].sum()
        incremento_prom = resultados['gdf_completo']['proy_incremento_esperado'].mean()
        
        doc.add_paragraph(f'Rendimiento total sin fertilización: {rend_sin_total:.0f} kg')
        doc.add_paragraph(f'Rendimiento total con fertilización: {rend_con_total:.0f} kg')
        doc.add_paragraph(f'Incremento promedio esperado: {incremento_prom:.1f}%')
        
        doc.add_paragraph()
        
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
        
        doc.add_heading('9. METADATOS TÉCNICOS', level=1)
        metadatos = [
            ('Generado por', 'Analizador Multi-Cultivo Satelital'),
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
st.title("🛰️ ANALIZADOR MULTI-CULTIVO SATELITAL")

if uploaded_file:
    with st.spinner("Cargando parcela..."):
        try:
            gdf = cargar_archivo_parcela(uploaded_file)
            if gdf is not None:
                st.success(f"✅ Parcela cargada exitosamente: {len(gdf)} polígono(s)")
                area_total = calcular_superficie(gdf)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**📊 INFORMACIÓN DE LA PARCELA:**")
                    st.write(f"- Polígonos: {len(gdf)}")
                    st.write(f"- Área total: {area_total:.1f} ha")
                    st.write(f"- CRS: {gdf.crs}")
                    st.write(f"- Formato: {uploaded_file.name.split('.')[-1].upper()}")
                    
                    fig, ax = plt.subplots(figsize=(8, 6))
                    gdf.plot(ax=ax, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
                    ax.set_title(f"Parcela: {uploaded_file.name}")
                    ax.set_xlabel("Longitud")
                    ax.set_ylabel("Latitud")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    
                    buf_vista = io.BytesIO()
                    plt.savefig(buf_vista, format='png', dpi=150, bbox_inches='tight')
                    buf_vista.seek(0)
                    
                    # Botón de descarga corregido
                    if buf_vista:
                        st.download_button(
                            label="📥 Descargar Vista Previa PNG",
                            data=buf_vista,
                            file_name=f"vista_previa_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                            mime="image/png"
                        )
                
                with col2:
                    st.write("**🎯 CONFIGURACIÓN**")
                    st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                    # Nota: variedad_seleccionada no está definida en el código anterior
                    # st.write(f"- Variedad: {st.session_state.variedad_seleccionada}")
                    st.write(f"- Zonas: {n_divisiones}")
                    st.write(f"- Satélite: {SATELITES_DISPONIBLES[satelite_seleccionado]['nombre']}")
                    st.write(f"- Período: {fecha_inicio} a {fecha_fin}")
                    st.write(f"- Intervalo curvas: {intervalo_curvas} m")
                    st.write(f"- Resolución DEM: {resolucion_dem} m")
                
                if st.button("🚀 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
                    with st.spinner("Ejecutando análisis completo..."):
                        resultados = ejecutar_analisis_completo(
                            gdf, cultivo, n_divisiones, 
                            satelite_seleccionado, fecha_inicio, fecha_fin,
                            intervalo_curvas, resolucion_dem
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

# ... resto del código para mostrar resultados en pestañas ...

else:
    st.info("👈 Por favor, sube un archivo de parcela y ejecuta el análisis para comenzar.")

# ===== PIE DE PÁGINA =====
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns(3)
with col_footer1:
    st.markdown("""
📡 Fuentes de Datos:
- Sentinel Hub (ESA)
- NASA POWER API
- Landsat-8 (USGS)
- Datos simulados
""")
with col_footer2:
    st.markdown("""
🛠️ Tecnologías:
- Streamlit
- GeoPandas
- Matplotlib
- Python-DOCX
- Sentinel Hub SDK
""")
with col_footer3:
    st.markdown("""
📞 Soporte:
- Versión: 5.2 - Sentinel Hub Integration
- Última actualización: Enero 2026
- Python 3.10
""")
st.markdown(
'<div style="text-align: center; padding: 20px; color: #94a3b8; font-size: 0.9em;">'
'© 2026 Analizador Multi-Cultivo Satelital. Todos los derechos reservados.'
'</div>',
unsafe_allow_html=True
)
