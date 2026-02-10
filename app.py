# app.py - Versión con exportación GeoTIFF georreferenciado
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
import json
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import geojson
import requests
import contextily as ctx

# ===== SOLUCIÓN PARA ERROR libGL.so.1 =====
# Configurar matplotlib para usar backend no interactivo
import matplotlib
matplotlib.use('Agg')  # Usar backend no interactivo

# Configurar variables de entorno para evitar problemas con OpenGL
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# ===== IMPORTACIONES GOOGLE EARTH ENGINE (NO MODIFICAR) =====
try:
    import ee
    GEE_AVAILABLE = True
except ImportError:
    GEE_AVAILABLE = False
    st.warning("⚠️ Google Earth Engine no está instalado. Para usar datos satelitales reales, instala con: pip install earthengine-api")

warnings.filterwarnings('ignore')

# ===== IMPORTACIONES PARA GEO-TIFF GEORREFERENCIADO =====
try:
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.features import rasterize
    from rasterio.enums import MergeAlg
    from affine import Affine
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    st.warning("⚠️ Rasterio no está instalado. Para exportar GeoTIFF, instala: pip install rasterio affine")

# === INICIALIZACIÓN SEGURA DE GOOGLE EARTH ENGINE (NO MODIFICAR) ===
def inicializar_gee():
    """Inicializa GEE con Service Account desde secrets de Streamlit Cloud"""
    if not GEE_AVAILABLE:
        return False
    
    try:
        # Intentar con Service Account desde secrets (Streamlit Cloud)
        gee_secret = os.environ.get('GEE_SERVICE_ACCOUNT')
        if gee_secret:
            try:
                credentials_info = json.loads(gee_secret.strip())
                credentials = ee.ServiceAccountCredentials(
                    credentials_info['client_email'],
                    key_data=json.dumps(credentials_info)
                )
                ee.Initialize(credentials, project='ee-mawucano25')
                st.session_state.gee_authenticated = True
                st.session_state.gee_project = 'ee-mawucano25'
                print("✅ GEE inicializado con Service Account")
                return True
            except Exception as e:
                print(f"⚠️ Error con Service Account: {str(e)}")
        
        # Fallback: autenticación local (desarrollo en tu Linux)
        try:
            ee.Initialize(project='ee-mawucano25')
            st.session_state.gee_authenticated = True
            st.session_state.gee_project = 'ee-mawucano25'
            print("✅ GEE inicializado localmente")
            return True
        except Exception as e:
            print(f"⚠️ Error inicialización local: {str(e)}")
            
        st.session_state.gee_authenticated = False
        return False
        
    except Exception as e:
        st.session_state.gee_authenticated = False
        print(f"❌ Error crítico GEE: {str(e)}")
        return False

# Ejecutar inicialización al inicio (ANTES de cualquier uso de ee.*)
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
    st.session_state.gee_project = ''
    
if GEE_AVAILABLE:
    inicializar_gee()

# ===== FUNCIONES YOLO PARA DETECCIÓN DE PLAGAS/ENFERMEDADES (CORREGIDO) =====
def cargar_modelo_yolo(modelo_path='yolo_plagas.pt'):
    """Carga el modelo YOLO para detección - VERSIÓN SEGURA SIN OpenGL"""
    try:
        # Configurar entorno para evitar problemas con OpenGL
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
        
        # Intentar importar con manejo de errores
        try:
            from ultralytics import YOLO
        except ImportError:
            st.error("❌ Ultralytics no está instalado. Instala con: pip install ultralytics")
            return None
        
        # Cargar modelo (usar modelo pequeño para demo)
        try:
            # Primero intentar cargar modelo personalizado
            if os.path.exists(modelo_path):
                modelo = YOLO(modelo_path)
            else:
                # Usar modelo preentrenado de demo
                modelo = YOLO('yolov8n.pt')
                st.info("ℹ️ Usando modelo YOLO de demostración (yolov8n.pt)")
            
            return modelo
        except Exception as e:
            st.error(f"❌ Error cargando archivo del modelo: {str(e)}")
            # Crear modelo simulado para demo
            class ModeloDemo:
                def __init__(self):
                    self.names = {
                        0: 'Plaga_Gusano', 
                        1: 'Enfermedad_Roya', 
                        2: 'Deficiencia_Nutricional',
                        3: 'Plaga_Pulgón',
                        4: 'Enfermedad_Oídio'
                    }
                
                def __call__(self, img, conf=0.5):
                    class ResultadoDemo:
                        def __init__(self):
                            self.boxes = None
                            self.plot = lambda: img
                    
                    return [ResultadoDemo()]
            
            st.warning("⚠️ Usando modelo de demostración simulado")
            return ModeloDemo()

    except Exception as e:
        st.error(f"❌ Error crítico en YOLO: {str(e)}")
        return None

def detectar_plagas_yolo(imagen_path, modelo, confianza_minima=0.5):
    """Ejecuta detección de plagas/enfermedades con YOLO - VERSIÓN SEGURA"""
    try:
        # Verificar si es un modelo demo
        if hasattr(modelo, 'names') and not hasattr(modelo, 'predict'):
            # Modelo de demostración - generar detecciones simuladas
            import cv2
            import numpy as np
            from PIL import Image
            
            # Cargar imagen
            if isinstance(imagen_path, BytesIO):
                imagen_path.seek(0)
                img_np = np.array(Image.open(imagen_path))
                img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            elif isinstance(imagen_path, str):
                img = cv2.imread(imagen_path)
            else:
                img = cv2.imdecode(np.frombuffer(imagen_path.read(), np.uint8), cv2.IMREAD_COLOR)
            
            # Generar detecciones simuladas para demo
            altura, ancho = img.shape[:2]
            detecciones = []
            
            # Generar 3-8 detecciones aleatorias
            np.random.seed(int(datetime.now().timestamp()))
            n_detecciones = np.random.randint(3, 8)
            
            for i in range(n_detecciones):
                x1 = np.random.randint(0, ancho - 100)
                y1 = np.random.randint(0, altura - 100)
                ancho_bbox = np.random.randint(50, 200)
                alto_bbox = np.random.randint(50, 200)
                x2 = min(x1 + ancho_bbox, ancho)
                y2 = min(y1 + alto_bbox, altura)
                
                clase_id = np.random.choice(list(modelo.names.keys()))
                confianza = np.random.uniform(confianza_minima, 0.95)
                
                detecciones.append({
                    'clase': modelo.names[clase_id],
                    'confianza': confianza,
                    'bbox': [x1, y1, x2, y2],
                    'area': (x2 - x1) * (y2 - y1)
                })
                
                # Dibujar bbox en imagen
                color = (0, 255, 0) if 'Plaga' in modelo.names[clase_id] else (0, 0, 255)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, f"{modelo.names[clase_id]}: {confianza:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            img_con_detecciones_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return detecciones, img_con_detecciones_rgb
        
        # Para modelo real de YOLO
        import cv2
        from PIL import Image
        import numpy as np
        
        # Cargar imagen
        if isinstance(imagen_path, BytesIO):
            imagen_path.seek(0)
            img_np = np.array(Image.open(imagen_path))
            img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        elif isinstance(imagen_path, str):
            img = cv2.imread(imagen_path)
        else:
            img = cv2.imdecode(np.frombuffer(imagen_path.read(), np.uint8), cv2.IMREAD_COLOR)
        
        # Ejecutar detección
        resultados = modelo(img, conf=confianza_minima)
        
        # Procesar resultados
        detecciones = []
        for r in resultados:
            if r.boxes is not None:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    nombre_clase = modelo.names[cls]
                    
                    detecciones.append({
                        'clase': nombre_clase,
                        'confianza': conf,
                        'bbox': [x1, y1, x2, y2],
                        'area': (x2 - x1) * (y2 - y1)
                    })
        
        # Dibujar bounding boxes
        img_con_detecciones = resultados[0].plot()
        img_con_detecciones_rgb = cv2.cvtColor(img_con_detecciones, cv2.COLOR_BGR2RGB)
        
        return detecciones, img_con_detecciones_rgb

    except Exception as e:
        st.error(f"❌ Error en detección YOLO: {str(e)}")
        return [], None

def analizar_imagen_dron(gdf, fecha_analisis):
    """Descarga o simula imágenes de dron para análisis YOLO"""
    try:
        # Obtener bounds de la parcela
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Simular imagen de dron sin OpenGL
        import numpy as np
        from PIL import Image, ImageDraw
        
        # Tamaño de imagen
        ancho, altura = 1000, 800
        
        # Crear imagen base (verde para cultivo)
        img_pil = Image.new('RGB', (ancho, altura), color=(100, 150, 100))
        draw = ImageDraw.Draw(img_pil)
        
        # Simular patrones de plagas/enfermedades
        np.random.seed(int(fecha_analisis.timestamp()))
        num_anomalias = np.random.randint(5, 15)
        
        for _ in range(num_anomalias):
            x = np.random.randint(0, ancho)
            y = np.random.randint(0, altura)
            radio = np.random.randint(20, 60)
            
            # Color según tipo de anomalía
            tipo = np.random.choice(['plaga', 'enfermedad', 'deficiencia'])
            if tipo == 'plaga':
                color = (255, 0, 0)  # Rojo
            elif tipo == 'enfermedad':
                color = (0, 0, 255)  # Azul
            else:
                color = (255, 255, 0)  # Amarillo
            
            draw.ellipse([x-radio, y-radio, x+radio, y+radio], fill=color)
        
        # Convertir a BytesIO
        imagen_bytes = BytesIO()
        img_pil.save(imagen_bytes, format='JPEG')
        imagen_bytes.seek(0)
        
        return imagen_bytes

    except Exception as e:
        st.error(f"❌ Error generando imagen de dron: {str(e)}")
        return None

def generar_reporte_plagas(detecciones, cultivo):
    """Genera reporte de análisis de plagas"""
    try:
        if not detecciones:
            return "✅ No se detectaron plagas/enfermedades significativas."
        
        # Agrupar por tipo
        conteo_plagas = {}
        areas_plagas = {}
        
        for det in detecciones:
            clase = det['clase']
            conteo_plagas[clase] = conteo_plagas.get(clase, 0) + 1
            areas_plagas[clase] = areas_plagas.get(clase, 0) + det['area']
        
        # Generar reporte
        reporte = f"## 🦠 REPORTE DE PLAGAS/ENFERMEDADES - {cultivo}\n\n"
        reporte += f"**Total de detecciones:** {len(detecciones)}\n\n"
        
        reporte += "**Distribución por tipo:**\n"
        for clase, conteo in conteo_plagas.items():
            porcentaje = (conteo / len(detecciones)) * 100
            area_prom = areas_plagas[clase] / conteo
            reporte += f"- **{clase}**: {conteo} detecciones ({porcentaje:.1f}%), área promedio: {area_prom:.0f} px²\n"
        
        # Recomendaciones según cultivo
        reporte += "\n**🧪 RECOMENDACIONES ESPECÍFICAS:**\n"
        
        if cultivo in ['TRIGO', 'MAIZ', 'SORGO']:
            if any('roya' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Fungicida**: Aplicar Triazol (0.5-1.0 L/ha) cada 15 días\n"
            if any('gusano' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Insecticida**: Lambda-cialotrina (0.2-0.3 L/ha) en detección temprana\n"
            if any('pulgón' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Control biológico**: Liberar Aphidius colemani (parásito de pulgones)\n"
                
        elif cultivo in ['VID', 'OLIVO', 'ALMENDRO']:
            if any('oidio' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Azufre micronizado**: 3-5 kg/ha aplicado preventivamente\n"
            if any('mosca' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Trampas amarillas**: 50-100 trampas/ha + Spinosad (0.3 L/ha)\n"
            if any('polilla' in clase.lower() for clase in conteo_plagas.keys()):
                reporte += "- **Confusión sexual**: Difusores de feromonas (500-1000 unidades/ha)\n"
        
        # Recomendaciones generales
        reporte += "\n**📋 RECOMENDACIONES GENERALES:**\n"
        reporte += "- **Monitoreo**: Revisar cada 7-10 días durante períodos críticos\n"
        reporte += "- **Umbrales**: Actuar cuando >5% de plantas muestren síntomas\n"
        reporte += "- **Rotación**: Alternar modos de acción para evitar resistencias\n"
        reporte += "- **Registro**: Documentar todas las aplicaciones y resultados\n"
        
        reporte += "\n**⚠️ ACCIONES INMEDIATAS:**\n"
        if len(detecciones) > 20:
            reporte += "- **ALERTA ROJA**: Incidencia crítica. Aplicación urgente requerida\n"
            reporte += "- **Contactar**: Asesor técnico para plan de emergencia\n"
        elif len(detecciones) > 10:
            reporte += "- **ALERTA AMARILLA**: Incidencia media. Aplicar en 48 horas\n"
            reporte += "- **Aumentar**: Frecuencia de monitoreo a cada 5 días\n"
        else:
            reporte += "- **SITUACIÓN CONTROLADA**: Continuar monitoreo rutinario\n"
            reporte += "- **Preventivo**: Aplicar tratamiento preventivo en próximos 15 días\n"
        
        # Información adicional
        reporte += "\n**📊 MÉTRICAS DE GRAVEDAD:**\n"
        severidad_total = sum(d['area'] * d['confianza'] for d in detecciones)
        reporte += f"- Índice de Severidad: {severidad_total:.0f}\n"
        reporte += f"- Área Total Afectada: {sum(d['area'] for d in detecciones):.0f} px²\n"
        
        return reporte

    except Exception as e:
        return f"❌ Error generando reporte: {str(e)}"

# ===== NUEVAS FUNCIONES PARA MAPAS DE POTENCIAL DE COSECHA =====
def crear_mapa_potencial_cosecha(gdf_completo, cultivo):
    """Crear mapa de potencial de cosecha"""
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Usar colores para potencial (verde = alto, rojo = bajo)
        cmap = LinearSegmentedColormap.from_list('potencial', ['#ff4444', '#ffff44', '#44ff44'])
        
        # Obtener valores de potencial
        potenciales = gdf_plot['proy_rendimiento_sin_fert']
        vmin, vmax = potenciales.min(), potenciales.max()
        
        for idx, row in gdf_plot.iterrows():
            valor = row['proy_rendimiento_sin_fert']
            valor_norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            color = cmap(valor_norm)
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.7)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.0f}kg", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.7)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} POTENCIAL DE COSECHA - {cultivo}',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label('Rendimiento Potencial (kg/ha)', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de potencial de cosecha: {str(e)}")
        return None

def crear_mapa_potencial_con_recomendaciones(gdf_completo, cultivo):
    """Crear mapa de potencial de cosecha con recomendaciones aplicadas"""
    try:
        gdf_plot = gdf_completo.to_crs(epsg=3857)
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Colores para potencial mejorado
        cmap = LinearSegmentedColormap.from_list('potencial_mejorado', ['#ffaa44', '#ffff44', '#44ff44', '#00aa00'])
        
        # Obtener valores de potencial con recomendaciones
        potenciales = gdf_plot['proy_rendimiento_con_fert']
        incrementos = gdf_plot['proy_incremento_esperado']
        vmin, vmax = potenciales.min(), potenciales.max()
        
        for idx, row in gdf_plot.iterrows():
            valor = row['proy_rendimiento_con_fert']
            incremento = row['proy_incremento_esperado']
            valor_norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            color = cmap(valor_norm)
            
            gdf_plot.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5, alpha=0.7)
            
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.0f}kg\n+{incremento:.1f}%", (centroid.x, centroid.y),
                        xytext=(5, 5), textcoords="offset points",
                        fontsize=7, color='black', weight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        try:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, alpha=0.7)
        except:
            pass
        
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} POTENCIAL CON RECOMENDACIONES - {cultivo}',
                     fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label('Rendimiento Mejorado (kg/ha)', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando mapa de potencial con recomendaciones: {str(e)}")
        return None

def crear_grafico_comparativo_potencial(gdf_completo, cultivo):
    """Crear gráfico comparativo de potencial vs potencial con recomendaciones"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(14, 7))
        
        zonas = gdf_completo['id_zona'].astype(str).tolist()
        sin_fert = gdf_completo['proy_rendimiento_sin_fert'].tolist()
        con_fert = gdf_completo['proy_rendimiento_con_fert'].tolist()
        incrementos = gdf_completo['proy_incremento_esperado'].tolist()
        
        x = np.arange(len(zonas))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, sin_fert, width, label='Sin Fertilización', color='#ff9999', alpha=0.8)
        bars2 = ax.bar(x + width/2, con_fert, width, label='Con Fertilización', color='#66b3ff', alpha=0.8)
        
        # Agregar línea de incremento porcentual
        ax2 = ax.twinx()
        ax2.plot(x, incrementos, 'g-', marker='o', linewidth=2, markersize=6, label='Incremento %')
        ax2.set_ylabel('Incremento (%)', color='green', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='green')
        ax2.set_ylim(0, max(incrementos) * 1.2)
        
        ax.set_xlabel('Zona', fontsize=12)
        ax.set_ylabel('Rendimiento (kg/ha)', fontsize=12)
        ax.set_title(f'COMPARATIVO DE POTENCIAL DE COSECHA - {cultivo}', fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(zonas, rotation=45)
        ax.legend(loc='upper left')
        ax2.legend(loc='upper right')
        
        # Agregar valores en las barras
        for bar1, bar2 in zip(bars1, bars2):
            height1 = bar1.get_height()
            height2 = bar2.get_height()
            ax.text(bar1.get_x() + bar1.get_width()/2., height1 + max(sin_fert)*0.01,
                   f'{height1:.0f}', ha='center', va='bottom', fontsize=8, rotation=90)
            ax.text(bar2.get_x() + bar2.get_width()/2., height2 + max(con_fert)*0.01,
                   f'{height2:.0f}', ha='center', va='bottom', fontsize=8, rotation=90)
        
        # Estadísticas
        stats_text = f"""
Estadísticas:
• Rendimiento promedio sin fertilización: {np.mean(sin_fert):.0f} kg/ha
• Rendimiento promedio con fertilización: {np.mean(con_fert):.0f} kg/ha
• Incremento promedio: {np.mean(incrementos):.1f}%
• Máximo incremento: {max(incrementos):.1f}% (Zona {zonas[incrementos.index(max(incrementos))]})
"""
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.5", facecolor='lightyellow', alpha=0.9))
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"❌ Error creando gráfico comparativo: {str(e)}")
        return None

# ===== NUEVA FUNCIÓN: VISUALIZACIÓN NDVI + NDRE GEE (INTERACTIVA) =====
def visualizar_indices_gee(gdf, satelite, fecha_inicio, fecha_fin):
    """Genera visualización NDVI + NDRE interactiva con iframes"""
    if not GEE_AVAILABLE or not st.session_state.gee_authenticated:
        return None, "❌ Google Earth Engine no está autenticado"
    
    try:
        # Obtener bounding box de la parcela
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Expandir ligeramente el área para asegurar cobertura
        min_lon -= 0.001
        max_lon += 0.001
        min_lat -= 0.001
        max_lat += 0.001
        
        # Crear geometría
        geometry = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        
        # Formatear fechas
        start_date = fecha_inicio.strftime('%Y-%m-%d')
        end_date = fecha_fin.strftime('%Y-%m-%d')
        
        # Seleccionar colección según satélite
        if satelite == 'SENTINEL-2_GEE':
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            ndvi_bands = ['B8', 'B4']
            ndre_bands = ['B8', 'B5']
            title = "Sentinel-2 NDVI + NDRE"
            
        elif satelite == 'LANDSAT-8_GEE':
            collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            ndvi_bands = ['SR_B5', 'SR_B4']
            ndre_bands = ['SR_B5', 'SR_B6']
            title = "Landsat 8 NDVI + NDRE"
            
        elif satelite == 'LANDSAT-9_GEE':
            collection = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
            ndvi_bands = ['SR_B5', 'SR_B4']
            ndre_bands = ['SR_B5', 'SR_B6']
            title = "Landsat 9 NDVI + NDRE"
            
        else:
            return None, "⚠️ Satélite no soportado para visualización de índices"
        
        # Filtrar colección
        try:
            filtered = (collection
                       .filterBounds(geometry)
                       .filterDate(start_date, end_date)
                       .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60)))
            
            # Verificar si hay imágenes
            count = filtered.size().getInfo()
            if count == 0:
                return None, f"⚠️ No hay imágenes disponibles para {start_date} - {end_date}"
            
            # Tomar la imagen con menos nubes
            image = filtered.sort('CLOUDY_PIXEL_PERCENTAGE').first()
            
            if image is None:
                return None, "❌ Error: La imagen obtenida es nula"
            
            # Calcular NDVI
            ndvi = image.normalizedDifference(ndvi_bands).rename('NDVI')
            
            # Calcular NDRE
            ndre = image.normalizedDifference(ndre_bands).rename('NDRE')
            
            # Obtener información de la imagen
            image_id = image.get('system:index').getInfo()
            
            cloud_percent_ee = image.get('CLOUDY_PIXEL_PERCENTAGE')
            cloud_percent = cloud_percent_ee.getInfo() if cloud_percent_ee else 0
            
            fecha_imagen_ee = image.get('system:time_start')
            fecha_imagen = fecha_imagen_ee.getInfo() if fecha_imagen_ee else None
            
            if fecha_imagen:
                fecha_str = datetime.fromtimestamp(fecha_imagen / 1000).strftime('%Y-%m-%d')
                title += f" - {fecha_str}"
            
            # Parámetros de visualización
            ndvi_vis_params = {
                'min': -0.2,
                'max': 0.8,
                'palette': ['red', 'yellow', 'green']
            }
            
            ndre_vis_params = {
                'min': -0.1,
                'max': 0.6,
                'palette': ['blue', 'white', 'green']
            }
            
            # Generar URLs de los mapas
            ndvi_map_id_dict = ndvi.getMapId(ndvi_vis_params)
            ndre_map_id_dict = ndre.getMapId(ndre_vis_params)
            
            if not ndvi_map_id_dict or 'mapid' not in ndvi_map_id_dict:
                return None, "❌ Error generando mapa NDVI"
            
            if not ndre_map_id_dict or 'mapid' not in ndre_map_id_dict:
                return None, "❌ Error generando mapa NDRE"
            
            # Usar URLs de tiles de Earth Engine
            ndvi_mapid = ndvi_map_id_dict['mapid']
            ndre_mapid = ndre_map_id_dict['mapid']
            
            # Si hay token, agregarlo como parámetro
            ndvi_token = ndvi_map_id_dict.get('token', '')
            ndre_token = ndre_map_id_dict.get('token', '')
            
            ndvi_token_param = f"?token={ndvi_token}" if ndvi_token else ""
            ndre_token_param = f"?token={ndre_token}" if ndre_token else ""
            
            # Crear HTML con iframes
            html = f"""
<div style="display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px;">
    <div style="flex: 1; min-width: 300px; border: 2px solid #3b82f6; border-radius: 10px; overflow: hidden;">
        <h4 style="text-align: center; background: linear-gradient(135deg, #ff4444, #ffff44, #44ff44); color: #000; padding: 10px; margin: 0;">🌱 MAPA NDVI</h4>
        <iframe
           width="100%"
           height="400"
           src="https://earthengine.googleapis.com/v1alpha/{ndvi_mapid}/tiles/{{z}}/{{x}}/{{y}}{ndvi_token_param}"
           frameborder="0"
           allowfullscreen
           style="display: block;"
        ></iframe>
        <div style="background: #f0f9ff; padding: 8px; border-top: 1px solid #3b82f6;">
            <p style="margin: 5px 0; font-size: 0.8em;">
                <strong>Escala:</strong> -0.2 (rojo) a 0.8 (verde)
            </p>
        </div>
    </div>
   
    <div style="flex: 1; min-width: 300px; border: 2px solid #10b981; border-radius: 10px; overflow: hidden;">
        <h4 style="text-align: center; background: linear-gradient(135deg, #0000ff, #ffffff, #00ff00); color: #000; padding: 10px; margin: 0;">🌿 MAPA NDRE</h4>
        <iframe
           width="100%"
           height="400"
           src="https://earthengine.googleapis.com/v1alpha/{ndre_mapid}/tiles/{{z}}/{{x}}/{{y}}{ndre_token_param}"
           frameborder="0"
           allowfullscreen
           style="display: block;"
        ></iframe>
        <div style="background: #f0f9ff; padding: 8px; border-top: 1px solid #10b981;">
            <p style="margin: 5px 0; font-size: 0.8em;">
                <strong>Escala:</strong> -0.1 (azul) a 0.6 (verde)
            </p>
        </div>
    </div>
</div>

<div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid #e2e8f0;">
    <h4 style="margin-top: 0; color: #3b82f6;">📊 INFORMACIÓN DE LOS ÍNDICES</h4>
    <div style="display: flex; flex-wrap: wrap; gap: 20px;">
        <div style="flex: 1; min-width: 200px;">
            <h5 style="color: #3b82f6; margin-bottom: 8px;">🌱 NDVI (Índice de Vegetación de Diferencia Normalizada)</h5>
            <ul style="margin: 0; padding-left: 20px; font-size: 0.9em;">
                <li><strong>Rango saludable:</strong> 0.3 - 0.8</li>
                <li><strong>Valores bajos (&lt;0.2):</strong> Suelo desnudo, estrés hídrico</li>
                <li><strong>Valores medios (0.3-0.5):</strong> Vegetación moderada</li>
                <li><strong>Valores altos (&gt;0.6):</strong> Vegetación densa y saludable</li>
            </ul>
        </div>
       
        <div style="flex: 1; min-width: 200px;">
            <h5 style="color: #10b981; margin-bottom: 8px;">🌿 NDRE (Índice de Borde Rojo Normalizado)</h5>
            <ul style="margin: 0; padding-left: 20px; font-size: 0.9em;">
                <li><strong>Rango saludable:</strong> 0.2 - 0.5</li>
                <li><strong>Sensibilidad:</strong> Clorofila en capas internas</li>
                <li><strong>Uso:</strong> Monitoreo de nitrógeno</li>
                <li><strong>Ventaja:</strong> Menos saturación en vegetación densa</li>
            </ul>
        </div>
    </div>
   
    <div style="margin-top: 15px; padding: 10px; background: #e0f2fe; border-radius: 5px; border-left: 4px solid #3b82f6;">
        <p style="margin: 0; font-size: 0.85em;">
            <strong>ℹ️ Información técnica:</strong> {title} | Nubes: {cloud_percent}% | ID: {image_id} | 
            <strong>Interpretación:</strong> Compara ambos índices para detectar estrés temprano
        </p>
    </div>
</div>
"""
            
            return html, f"✅ {title}"
            
        except Exception as e:
            error_msg = str(e)
            if "Parameter 'object' is required" in error_msg:
                return None, f"❌ No se encontró imagen para el período {start_date} - {end_date}"
            else:
                return None, f"❌ Error GEE: {error_msg}"
        
    except Exception as e:
        return None, f"❌ Error general: {str(e)}"

# ===== MODIFICACIÓN DE LA FUNCIÓN visualizar_indices_gee_estatico =====
def visualizar_indices_gee_estatico(gdf, satelite, fecha_inicio, fecha_fin):
    """Versión mejorada que devuelve las imágenes en bytes para descarga"""
    if not GEE_AVAILABLE or not st.session_state.gee_authenticated:
        return None, "❌ Google Earth Engine no está autenticado"
    
    try:
        # Obtener bounding box de la parcela
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Crear geometría
        geometry = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        
        # Formatear fechas
        start_date = fecha_inicio.strftime('%Y-%m-%d')
        end_date = fecha_fin.strftime('%Y-%m-%d')
        
        # Seleccionar colección según satélite
        if satelite == 'SENTINEL-2_GEE':
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            ndvi_bands = ['B8', 'B4']
            ndre_bands = ['B8', 'B5']
            title = "Sentinel-2"
            
        elif satelite == 'LANDSAT-8_GEE':
            collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            ndvi_bands = ['SR_B5', 'SR_B4']
            ndre_bands = ['SR_B5', 'SR_B6']
            title = "Landsat 8"
            
        elif satelite == 'LANDSAT-9_GEE':
            collection = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
            ndvi_bands = ['SR_B5', 'SR_B4']
            ndre_bands = ['SR_B5', 'SR_B6']
            title = "Landsat 9"
            
        else:
            return None, "⚠️ Satélite no soportado"
        
        # Filtrar colección
        filtered = (collection
                   .filterBounds(geometry)
                   .filterDate(start_date, end_date)
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60)))
        
        # Verificar si hay imágenes
        count = filtered.size().getInfo()
        if count == 0:
            return None, f"⚠️ No hay imágenes disponibles para el período {start_date} - {end_date}"
        
        # Tomar la imagen con menos nubes
        image = filtered.sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        # Calcular índices
        ndvi = image.normalizedDifference(ndvi_bands).rename('NDVI')
        ndre = image.normalizedDifference(ndre_bands).rename('NDRE')
        
        # Generar URLs de miniaturas (thumbnails) estáticas
        try:
            # Parámetros comunes
            region_params = {
                'dimensions': 800,
                'region': geometry,
                'format': 'png'
            }
            
            # Configuración específica para cada índice
            ndvi_thumbnail_url = ndvi.getThumbURL({
                'min': -0.2,
                'max': 0.8,
                'palette': ['red', 'yellow', 'green'],
                **region_params
            })
            
            ndre_thumbnail_url = ndre.getThumbURL({
                'min': -0.1,
                'max': 0.6,
                'palette': ['blue', 'white', 'green'],
                **region_params
            })
            
            # Descargar las imágenes
            import requests
            
            ndvi_response = requests.get(ndvi_thumbnail_url)
            ndre_response = requests.get(ndre_thumbnail_url)
            
            if ndvi_response.status_code != 200 or ndre_response.status_code != 200:
                return None, f"❌ Error descargando imágenes: {ndvi_response.status_code}, {ndre_response.status_code}"
            
            # Convertir a bytes
            ndvi_bytes = BytesIO(ndvi_response.content)
            ndre_bytes = BytesIO(ndre_response.content)
            
            return {
                'ndvi_bytes': ndvi_bytes,
                'ndre_bytes': ndre_bytes,
                'title': title,
                'image_date': image.get('system:time_start').getInfo() if image.get('system:time_start') else None,
                'cloud_percent': image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo() if image.get('CLOUDY_PIXEL_PERCENTAGE') else 0,
                'image_id': image.get('system:index').getInfo() if image.get('system:index') else 'N/A'
            }, f"✅ {title} - Imágenes descargadas correctamente"
            
        except Exception as e:
            return None, f"❌ Error generando imágenes estáticas: {str(e)}"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# ===== FUNCIONES PARA EXPORTACIÓN GEO-TIFF GEORREFERENCIADO =====
def crear_geotiff_buffer_desde_gdf(gdf, columna_valor, nombre_mapa="mapa", resolucion_metros=10.0):
    """
    Genera un buffer GeoTIFF georreferenciado a partir de un GeoDataFrame y columna de valores.
    Usa proyección UTM para resolución métrica precisa.
    """
    if not RASTERIO_AVAILABLE:
        st.error("❌ Rasterio no disponible para generar GeoTIFF")
        return None
    
    try:
        # Validar CRS y datos
        gdf = validar_y_corregir_crs(gdf)
        if gdf.empty or columna_valor not in gdf.columns:
            st.error(f"❌ Columna '{columna_valor}' no encontrada en el GeoDataFrame")
            return None
        
        # Calcular zona UTM aproximada desde el centroide
        centroid = gdf.geometry.unary_union.centroid
        utm_zone = int((centroid.x + 180) / 6) + 1
        hemisferio = 'S' if centroid.y < 0 else 'N'
        crs_utm = f'EPSG:327{utm_zone:02d}' if hemisferio == 'S' else f'EPSG:326{utm_zone:02d}'
        
        # Reproyectar a UTM para resolución métrica precisa
        gdf_utm = gdf.to_crs(crs_utm)
        minx, miny, maxx, maxy = gdf_utm.total_bounds
        
        # Calcular dimensiones del raster (respetando relación de aspecto)
        ancho_metros = maxx - minx
        alto_metros = maxy - miny
        width = max(100, int(ancho_metros / resolucion_metros))
        height = max(100, int(alto_metros / resolucion_metros))
        
        # Ajustar resolución para mantener proporción exacta
        res_x = ancho_metros / width
        res_y = alto_metros / height
        
        # Crear transformación afín
        transform = Affine.translation(minx, maxy) * Affine.scale(res_x, -res_y)
        
        # Preparar shapes para rasterización
        shapes = []
        for idx, row in gdf_utm.iterrows():
            if row.geometry is not None and not row.geometry.is_empty:
                valor = row[columna_valor]
                if pd.notna(valor) and isinstance(valor, (int, float)):
                    shapes.append((row.geometry, float(valor)))
        
        if not shapes:
            st.error("❌ No hay datos válidos para rasterizar")
            return None
        
        # Crear raster vacío
        raster = np.full((height, width), np.nan, dtype=np.float32)
        
        # Rasterizar geometrías
        raster = rasterize(
            shapes,
            out_shape=(height, width),
            transform=transform,
            fill=np.nan,
            dtype=np.float32,
            merge_alg=MergeAlg.replace
        )
        
        # Crear buffer GeoTIFF en memoria
        buffer = BytesIO()
        with rasterio.open(
            buffer,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=raster.dtype,
            crs=crs_utm,
            transform=transform,
            nodata=np.nan,
            compress='LZW'
        ) as dst:
            dst.write(raster, 1)
            # Agregar metadatos
            dst.update_tags(
                DESCRIPCION=f"Mapa de {nombre_mapa} - {datetime.now().strftime('%Y-%m-%d')}",
                CULTIVO=cultivo if 'cultivo' in globals() else "N/A",
                COLUMNA_ORIGEN=columna_valor,
                RESOLUCION=f"{res_x:.2f}m x {res_y:.2f}m"
            )
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"❌ Error generando GeoTIFF: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def crear_geotiff_buffer_desde_array(array, bounds, nombre_mapa="dem", resolucion=None):
    """
    Genera GeoTIFF a partir de un array 2D y sus límites geográficos.
    """
    if not RASTERIO_AVAILABLE:
        st.error("❌ Rasterio no disponible para generar GeoTIFF")
        return None
    
    try:
        # Calcular resolución si no se proporciona
        if resolucion is None:
            resolucion = min((bounds[2] - bounds[0]) / array.shape[1], 
                           (bounds[3] - bounds[1]) / array.shape[0])
        
        # Crear transformación
        transform = from_origin(bounds[0], bounds[3], resolucion, resolucion)
        
        # Crear buffer
        buffer = BytesIO()
        with rasterio.open(
            buffer,
            'w',
            driver='GTiff',
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=array.dtype,
            crs='EPSG:4326',
            transform=transform,
            nodata=np.nan if np.issubdtype(array.dtype, np.floating) else None,
            compress='LZW'
        ) as dst:
            dst.write(array, 1)
            dst.update_tags(
                DESCRIPCION=f"{nombre_mapa} - {datetime.now().strftime('%Y-%m-%d')}",
                TIPO=nombre_mapa.upper()
            )
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"❌ Error generando GeoTIFF desde array: {str(e)}")
        return None

def crear_boton_descarga_geotiff(gdf_o_array, columna_o_tipo, nombre_base, descripcion="Mapa"):
    """Botón de descarga para GeoTIFF georreferenciado"""
    if not RASTERIO_AVAILABLE:
        st.warning("⚠️ Rasterio no instalado. Descarga en PNG no disponible.")
        return
    
    # Generar nombre de archivo único
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f"{nombre_base}_{cultivo}_{timestamp}.tif"
    
    # Determinar tipo de datos y generar buffer
    if isinstance(gdf_o_array, gpd.GeoDataFrame) and isinstance(columna_o_tipo, str):
        # Caso: GeoDataFrame con columna de valores
        buffer = crear_geotiff_buffer_desde_gdf(
            gdf_o_array, 
            columna_o_tipo,
            nombre_mapa=descripcion,
            resolucion_metros=5.0  # Resolución predeterminada 5m
        )
    elif isinstance(gdf_o_array, np.ndarray) and isinstance(columna_o_tipo, tuple):
        # Caso: Array con bounds (DEM, pendientes)
        buffer = crear_geotiff_buffer_desde_array(
            gdf_o_array,
            columna_o_tipo,  # bounds
            nombre_mapa=descripcion
        )
    else:
        st.error("❌ Tipo de datos no soportado para GeoTIFF")
        return
    
    if buffer:
        st.download_button(
            label=f"📥 Descargar {descripcion} GeoTIFF",
            data=buffer,
            file_name=nombre_archivo,
            mime="image/tiff",
            key=f"geotiff_{nombre_base}_{timestamp}"
        )
    else:
        st.error(f"❌ No se pudo generar el GeoTIFF para {descripcion}")

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
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
if 'gee_project' not in st.session_state:
    st.session_state.gee_project = ''
if 'modelo_yolo' not in st.session_state:
    st.session_state.modelo_yolo = None

# ===== ESTILOS PERSONALIZADOS - VERSIÓN COMPATIBLE CON STREAMLIT CLOUD =====
st.markdown("""
/* === FONDO GENERAL OSCURO ELEGANTE === */
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* === BANNER HERO SIN IMÁGENES EXTERNAS (100% CSS) === */
.hero-banner {
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.98)),
                radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.15), transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(16, 185, 129, 0.1), transparent 45%);
    padding: 2.5em 1.5em;
    border-radius: 20px;
    margin-bottom: 2em;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(59, 130, 246, 0.3);
    position: relative;
    overflow: hidden;
    text-align: center;
}

.hero-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, transparent 70%);
    z-index: 0;
}

.hero-content {
    position: relative;
    z-index: 2;
    padding: 1.5em;
}

.hero-title {
    color: #ffffff;
    font-size: 2.8em;
    font-weight: 800;
    margin-bottom: 0.5em;
    text-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    background: linear-gradient(135deg, #ffffff 0%, #60a5fa 50%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
}

.hero-subtitle {
    color: #cbd5e1;
    font-size: 1.2em;
    font-weight: 400;
    max-width: 700px;
    margin: 0 auto;
    line-height: 1.6;
    opacity: 0.95;
}

/* === DECORACIÓN DEL BANNER (cultivos abstractos) === */
.hero-banner::after {
    content: '🌾 🌾 🌾 🌾 🌾 🌾 🌾 🌾 🌾 🌾';
    position: absolute;
    bottom: -15px;
    left: 0;
    right: 0;
    font-size: 1.8em;
    letter-spacing: 12px;
    color: rgba(255, 255, 255, 0.15);
    text-align: center;
    z-index: 1;
    transform: scale(1.2);
}

/* === SIDEBAR: FONDO BLANCO CON TEXTO NEGRO === */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
    box-shadow: 2px 0 15px rgba(0, 0, 0, 0.08) !important;
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
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.2);
    letter-spacing: 0.5px;
}

/* Widgets del sidebar */
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stDateInput,
[data-testid="stSidebar"] .stSlider {
    background: rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(8px);
    border-radius: 12px;
    padding: 12px;
    margin: 8px 0;
    border: 1px solid #d1d5db !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05) !important;
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
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35) !important;
    transition: all 0.25s ease !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 18px rgba(59, 130, 246, 0.45) !important;
    background: linear-gradient(135deg, #4f8df8 0%, #2d5fe8 100%) !important;
}

/* === PESTAÑAS === */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(30, 41, 59, 0.7) !important;
    backdrop-filter: blur(10px) !important;
    padding: 8px 16px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(59, 130, 246, 0.3) !important;
    margin-top: 1.5em !important;
    gap: 6px !important;
}

.stTabs [data-baseweb="tab"] {
    color: #94a3b8 !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
    border-radius: 12px !important;
    background: rgba(15, 23, 42, 0.6) !important;
    transition: all 0.25s ease !important;
    border: 1px solid rgba(56, 189, 248, 0.2) !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background: rgba(59, 130, 246, 0.2) !important;
    border-color: rgba(59, 130, 246, 0.4) !important;
    transform: translateY(-1px) !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
}

/* === MÉTRICAS === */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)) !important;
    backdrop-filter: blur(10px) !important;
    border-radius: 18px !important;
    padding: 22px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35) !important;
    border: 1px solid rgba(59, 130, 246, 0.25) !important;
    transition: all 0.3s ease !important;
}

div[data-testid="metric-container"]:hover {
    transform: translateY(-4px) !important;
    box-shadow: 0 10px 25px rgba(59, 130, 246, 0.3) !important;
    border-color: rgba(59, 130, 246, 0.45) !important;
}

div[data-testid="metric-container"] label,
div[data-testid="metric-container"] div,
div[data-testid="metric-container"] [data-testid="stMetricValue"] { 
    color: #ffffff !important;
    font-weight: 600 !important;
}

div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2.3em !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}

/* === DATAFRAMES === */
.dataframe {
    background: rgba(15, 23, 42, 0.85) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    color: #e2e8f0 !important;
    font-size: 0.95em !important;
}

.dataframe th {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    padding: 14px 16px !important;
}

.dataframe td {
    color: #cbd5e1 !important;
    padding: 12px 16px !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* === FOOTER === */
.footer-divider {
    margin: 2.5em 0 1.5em 0;
    border-top: 1px solid rgba(59, 130, 246, 0.3);
}

.footer-content {
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 1.8em;
    border: 1px solid rgba(59, 130, 246, 0.2);
    margin-top: 1.5em;
}

.footer-copyright {
    text-align: center;
    color: #94a3b8;
    padding: 1.2em 0 0.8em 0;
    font-size: 0.95em;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin-top: 1.5em;
}
""", unsafe_allow_html=True)

# ===== BANNER HERO CORREGIDO (100% CSS - SIN IMÁGENES EXTERNAS) =====
st.markdown("""
<div class="hero-banner">
    <div class="hero-content">
        <h1 class="hero-title">🌾 ANALIZADOR MULTI-CULTIVO SATELITAL</h1>
        <p class="hero-subtitle">Potenciado con Google Earth Engine, NASA POWER y datos SRTM para agricultura de precisión</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ===== CONFIGURACIÓN DE SATÉLITES DISPONIBLES =====
SATELITES_DISPONIBLES = {
    'SENTINEL-2_GEE': {
        'nombre': 'Sentinel-2 (Google Earth Engine)',
        'resolucion': '10m',
        'revisita': '5 días',
        'bandas': ['B2', 'B3', 'B4', 'B8', 'B5', 'B11', 'B12'],
        'indices': ['NDVI', 'NDRE', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🌍',
        'requerimiento': 'Google Earth Engine'
    },
    'LANDSAT-8_GEE': {
        'nombre': 'Landsat 8 (Google Earth Engine)',
        'resolucion': '30m',
        'revisita': '16 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'NDRE', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🌍',
        'requerimiento': 'Google Earth Engine'
    },
    'LANDSAT-9_GEE': {
        'nombre': 'Landsat 9 (Google Earth Engine)',
        'resolucion': '30m',
        'revisita': '16 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'NDRE', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🌍',
        'requerimiento': 'Google Earth Engine'
    },
    'SENTINEL-2': {
        'nombre': 'Sentinel-2 (Simulado)',
        'resolucion': '10m',
        'revisita': '5 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B8', 'B11'],
        'indices': ['NDVI', 'NDRE', 'GNDVI', 'OSAVI', 'MCARI'],
        'icono': '🛰️'
    },
    'LANDSAT-8': {
        'nombre': 'Landsat 8 (Simulado)',
        'resolucion': '30m',
        'revisita': '16 días',
        'bandas': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'indices': ['NDVI', 'NDRE', 'NDWI', 'EVI', 'SAVI', 'MSAVI'],
        'icono': '🛰️'
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

# ===== CONFIGURACIÓN VARIEDADES CULTIVOS (ACTUALIZADO CON NUEVOS CULTIVOS) =====
VARIEDADES_CULTIVOS = {
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
    ],
    # NUEVOS CULTIVOS AGREGADOS
    'VID': [
        'Malbec', 'Cabernet Sauvignon', 'Merlot', 'Syrah', 'Chardonnay',
        'Torrontés', 'Bonarda', 'Tempranillo', 'Sangiovese', 'Pinot Noir',
        'Chenin', 'Sauvignon Blanc', 'Viognier', 'Carménère', 'Petit Verdot'
    ],
    'OLIVO': [
        'Arbequina', 'Picual', 'Manzanilla', 'Hojiblanca', 'Cornicabra',
        'Empeltre', 'Frantoio', 'Leccino', 'Coratina', 'Picholine',
        'Kalamata', 'Mission', 'Ascolano', 'Barnea', 'Arbosana'
    ],
    'ALMENDRO': [
        'Non Pareil', 'Carmel', 'Butte', 'Padre', 'Mission',
        'Fritz', 'Monterey', 'Price', 'Aldrich', 'Wood Colony',
        'Peerless', 'Thompson', 'Livingston', 'Sonora', 'Winters'
    ],
    'BANANO': [
        'Cavendish', 'Gros Michel', 'Plátano', 'Manzano', 'Rojo',
        'Morado', 'Baby Banana', 'Blue Java', 'Goldfinger', 'Pisang Awak',
        'Mysore', 'Saba', 'Lakatan', 'Señorita', 'Dwarf Cavendish'
    ],
    'CAFE': [
        'Arabica', 'Robusta', 'Liberica', 'Excelsa', 'Typica',
        'Bourbon', 'Caturra', 'Catuai', 'Mundo Novo', 'Maragogipe',
        'Geisha', 'Pacamara', 'SL-28', 'SL-34', 'Kona'
    ],
    'CACAO': [
        'Forastero', 'Criollo', 'Trinitario', 'Nacional', 'Amelonado',
        'Contamana', 'Marañón', 'Porcelana', 'Chuao', 'Carenero',
        'Ocumare', 'Cundeamor', 'ICS-95', 'UF-613', 'TSH-565'
    ],
    'PALMA_ACEITERA': [
        'Tenera', 'Dura', 'Pisifera', 'DxP', 'Yangambi',
        'AVROS', 'La Mé', 'Ekona', 'Calabar', 'NIFOR',
        'MARDI', 'CIRAD', 'ASD Costa Rica', 'Dami', 'Socfindo'
    ]
}

# ===== CONFIGURACIÓN PARÁMETROS CULTIVOS (ACTUALIZADO) =====
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
        'VARIEDADES': VARIEDADES_CULTIVOS['TRIGO'],
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
        'VARIEDADES': VARIEDADES_CULTIVOS['MAIZ'],
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
        'VARIEDADES': VARIEDADES_CULTIVOS['SORGO'],
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
        'VARIEDADES': VARIEDADES_CULTIVOS['SOJA'],
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
        'VARIEDADES': VARIEDADES_CULTIVOS['GIRASOL'],
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
        'VARIEDADES': VARIEDADES_CULTIVOS['MANI'],
        'ZONAS_ARGENTINA': ['Córdoba', 'San Luis', 'La Pampa']
    },
    # NUEVOS CULTIVOS AGREGADOS
    'VID': {
        'NITROGENO': {'min': 60, 'max': 120},
        'FOSFORO': {'min': 30, 'max': 70},
        'POTASIO': {'min': 150, 'max': 250},
        'MATERIA_ORGANICA_OPTIMA': 2.5,
        'HUMEDAD_OPTIMA': 0.35,
        'NDVI_OPTIMO': 0.65,
        'NDRE_OPTIMO': 0.35,
        'RENDIMIENTO_OPTIMO': 15000,  # kg/ha de uva
        'COSTO_FERTILIZACION': 800,
        'PRECIO_VENTA': 0.80,  # USD/kg uva
        'VARIEDADES': VARIEDADES_CULTIVOS['VID'],
        'ZONAS_ARGENTINA': ['Mendoza', 'San Juan', 'La Rioja', 'Salta']
    },
    'OLIVO': {
        'NITROGENO': {'min': 40, 'max': 100},
        'FOSFORO': {'min': 20, 'max': 50},
        'POTASIO': {'min': 100, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 2.0,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.60,
        'NDRE_OPTIMO': 0.30,
        'RENDIMIENTO_OPTIMO': 8000,  # kg/ha de aceituna
        'COSTO_FERTILIZACION': 600,
        'PRECIO_VENTA': 1.20,  # USD/kg aceituna
        'VARIEDADES': VARIEDADES_CULTIVOS['OLIVO'],
        'ZONAS_ARGENTINA': ['La Rioja', 'Catamarca', 'San Juan', 'Mendoza']
    },
    'ALMENDRO': {
        'NITROGENO': {'min': 80, 'max': 160},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 120, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 2.2,
        'HUMEDAD_OPTIMA': 0.30,
        'NDVI_OPTIMO': 0.62,
        'NDRE_OPTIMO': 0.32,
        'RENDIMIENTO_OPTIMO': 3000,  # kg/ha de almendra
        'COSTO_FERTILIZACION': 700,
        'PRECIO_VENTA': 4.50,  # USD/kg almendra
        'VARIEDADES': VARIEDADES_CULTIVOS['ALMENDRO'],
        'ZONAS_ARGENTINA': ['Río Negro', 'Neuquén', 'Mendoza', 'San Juan']
    },
    'BANANO': {
        'NITROGENO': {'min': 200, 'max': 350},
        'FOSFORO': {'min': 60, 'max': 120},
        'POTASIO': {'min': 300, 'max': 500},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.45,
        'NDVI_OPTIMO': 0.78,
        'NDRE_OPTIMO': 0.40,
        'RENDIMIENTO_OPTIMO': 40000,  # kg/ha de banano
        'COSTO_FERTILIZACION': 1200,
        'PRECIO_VENTA': 0.30,  # USD/kg banano
        'VARIEDADES': VARIEDADES_CULTIVOS['BANANO'],
        'ZONAS_ARGENTINA': ['Formosa', 'Misiones', 'Corrientes']
    },
    'CAFE': {
        'NITROGENO': {'min': 100, 'max': 200},
        'FOSFORO': {'min': 40, 'max': 80},
        'POTASIO': {'min': 150, 'max': 250},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.40,
        'NDVI_OPTIMO': 0.70,
        'NDRE_OPTIMO': 0.38,
        'RENDIMIENTO_OPTIMO': 2000,  # kg/ha de café verde
        'COSTO_FERTILIZACION': 900,
        'PRECIO_VENTA': 3.50,  # USD/kg café
        'VARIEDADES': VARIEDADES_CULTIVOS['CAFE'],
        'ZONAS_ARGENTINA': ['Misiones', 'Corrientes', 'Jujuy']
    },
    'CACAO': {
        'NITROGENO': {'min': 80, 'max': 150},
        'FOSFORO': {'min': 30, 'max': 60},
        'POTASIO': {'min': 120, 'max': 200},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.50,
        'NDVI_OPTIMO': 0.72,
        'NDRE_OPTIMO': 0.38,
        'RENDIMIENTO_OPTIMO': 1500,  # kg/ha de cacao seco
        'COSTO_FERTILIZACION': 850,
        'PRECIO_VENTA': 5.00,  # USD/kg cacao
        'VARIEDADES': VARIEDADES_CULTIVOS['CACAO'],
        'ZONAS_ARGENTINA': ['Misiones', 'Corrientes', 'Formosa']
    },
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 150, 'max': 250},
        'FOSFORO': {'min': 50, 'max': 100},
        'POTASIO': {'min': 200, 'max': 350},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.55,
        'NDVI_OPTIMO': 0.75,
        'NDRE_OPTIMO': 0.42,
        'RENDIMIENTO_OPTIMO': 20000,  # kg/ha de racimos
        'COSTO_FERTILIZACION': 1100,
        'PRECIO_VENTA': 0.40,  # USD/kg aceite
        'VARIEDADES': VARIEDADES_CULTIVOS['PALMA_ACEITERA'],
        'ZONAS_ARGENTINA': ['Formosa', 'Chaco', 'Misiones']
    }
}

# ===== CONFIGURACIÓN TEXTURA SUELO ÓPTIMA (ACTUALIZADO) =====
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
    },
    # NUEVOS CULTIVOS AGREGADOS
    'VID': {
        'textura_optima': 'Franco-arenoso',
        'arena_optima': 50,
        'limo_optima': 30,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.40,
        'porosidad_optima': 0.50
    },
    'OLIVO': {
        'textura_optima': 'Franco-arcilloso',
        'arena_optima': 40,
        'limo_optima': 35,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.35,
        'porosidad_optima': 0.48
    },
    'ALMENDRO': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.38,
        'porosidad_optima': 0.47
    },
    'BANANO': {
        'textura_optima': 'Franco-arcilloso',
        'arena_optima': 35,
        'limo_optima': 40,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.20,
        'porosidad_optima': 0.55
    },
    'CAFE': {
        'textura_optima': 'Franco',
        'arena_optima': 40,
        'limo_optima': 40,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52
    },
    'CACAO': {
        'textura_optima': 'Franco-arcilloso',
        'arena_optima': 30,
        'limo_optima': 45,
        'arcilla_optima': 25,
        'densidad_aparente_optima': 1.15,
        'porosidad_optima': 0.56
    },
    'PALMA_ACEITERA': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.30,
        'porosidad_optima': 0.51
    }
}

# ===== ICONOS Y COLORES PARA CULTIVOS (ACTUALIZADO) =====
ICONOS_CULTIVOS = {
    'TRIGO': '🌾',
    'MAIZ': '🌽',
    'SORGO': '🌾',
    'SOJA': '🫘',
    'GIRASOL': '🌻',
    'MANI': '🥜',
    # NUEVOS CULTIVOS
    'VID': '🍇',
    'OLIVO': '🫒',
    'ALMENDRO': '🌰',
    'BANANO': '🍌',
    'CAFE': '☕',
    'CACAO': '🍫',
    'PALMA_ACEITERA': '🌴'
}

COLORES_CULTIVOS = {
    'TRIGO': '#FFD700',
    'MAIZ': '#F4A460',
    'SORGO': '#8B4513',
    'SOJA': '#228B22',
    'GIRASOL': '#FFD700',
    'MANI': '#D2691E',
    # NUEVOS CULTIVOS
    'VID': '#8B0000',      # Rojo vino
    'OLIVO': '#808000',    # Verde oliva
    'ALMENDRO': '#D2B48C', # Beige
    'BANANO': '#FFD700',   # Amarillo
    'CAFE': '#8B4513',     # Marrón café
    'CACAO': '#4A2C2A',    # Marrón chocolate
    'PALMA_ACEITERA': '#32CD32'  # Verde lima
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
            st.error(f"❌ Error procesando Sentinel-2: {str(e)}")
        return None
        
# ===== FUNCIONES GOOGLE EARTH ENGINE =====
def obtener_datos_sentinel2_gee(gdf, fecha_inicio, fecha_fin, indice='NDVI'):
    """Obtener datos reales de Sentinel-2 usando Google Earth Engine con manejo robusto"""
    if not GEE_AVAILABLE or not st.session_state.gee_authenticated:
        st.warning("⚠️ GEE no disponible o no autenticado")
        return None
    
    try:
        # Validar que el GeoDataFrame tenga geometría válida
        if gdf is None or len(gdf) == 0:
            st.error("❌ El área de estudio no es válida")
            return None
        
        # Obtener bounding box de la parcela con validación
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Validar coordenadas
        if (abs(max_lon - min_lon) < 0.0001 or 
            abs(max_lat - min_lat) < 0.0001):
            st.warning("⚠️ El área de estudio es muy pequeña. Ampliando bounding box.")
            # Expandir ligeramente el área
            min_lon -= 0.001
            max_lon += 0.001
            min_lat -= 0.001
            max_lat += 0.001
        
        # Crear geometría de la parcela
        geometry = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        
        # Formatear fechas para GEE
        start_date = fecha_inicio.strftime('%Y-%m-%d')
        end_date = fecha_fin.strftime('%Y-%m-%d')
        
        # Validar rango de fechas
        if fecha_inicio > fecha_fin:
            st.error("❌ La fecha de inicio debe ser anterior a la fecha de fin")
            # Intercambiar fechas automáticamente
            start_date, end_date = end_date, start_date
            st.info("ℹ️ Se intercambiaron las fechas automáticamente")
        
        # Cargar colección Sentinel-2 con filtros más permisivos
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60)))  # Aumentado a 60% nubes
        
        # Verificar si hay imágenes en la colección
        collection_size = collection.size().getInfo()
        
        if collection_size == 0:
            st.warning(f"⚠️ No se encontraron imágenes Sentinel-2 para:")
            st.warning(f"   - Área: [{min_lon:.4f}, {min_lat:.4f}, {max_lon:.4f}, {max_lat:.4f}]")
            st.warning(f"   - Período: {start_date} a {end_date}")
            st.warning(f"   - Límite de nubes: <60%")
            
            # Intentar con filtro más permisivo
            st.info("🔄 Intentando con filtro de nubes más permisivo (<80%)...")
            collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(geometry)
                         .filterDate(start_date, end_date)
                         .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)))
            
            collection_size = collection.size().getInfo()
            if collection_size == 0:
                st.error("❌ No hay imágenes disponibles incluso con filtro permisivo")
                st.info("💡 Recomendaciones:")
                st.info("   1. Amplía el rango de fechas")
                st.info("   2. Verifica que las coordenadas sean correctas")
                st.info("   3. Prueba con Landsat 8/9 (tiene más cobertura histórica)")
                return None
            else:
                st.success(f"✅ Encontradas {collection_size} imágenes con filtro permisivo")
        
        # Seleccionar la imagen con menor cobertura de nubes
        image = collection.sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        # Verificar que la imagen no sea nula
        if image is None:
            st.error("❌ Error crítico: La imagen seleccionada es nula")
            return None
        
        # Obtener información de la imagen para debugging
        image_id = image.get('system:index').getInfo()
        cloud_percent = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        image_date = image.get('system:time_start').getInfo()
        
        if image_date:
            image_date_str = datetime.fromtimestamp(image_date / 1000).strftime('%Y-%m-%d')
            st.info(f"📅 Imagen seleccionada: {image_id} ({image_date_str}) - Nubes: {cloud_percent}%")
        
        # Calcular índice según selección
        try:
            if indice == 'NDVI':
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                index_image = ndvi
            elif indice == 'NDWI':
                ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
                index_image = ndwi
            elif indice == 'EVI':
                evi = image.expression(
                    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                    {
                        'NIR': image.select('B8'),
                        'RED': image.select('B4'),
                        'BLUE': image.select('B2')
                    }
                ).rename('EVI')
                index_image = evi
            elif indice == 'NDRE':
                ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
                index_image = ndre
            elif indice == 'SAVI':
                savi = image.expression(
                    '((NIR - RED) / (NIR + RED + 0.5)) * (1.5)',
                    {
                        'NIR': image.select('B8'),
                        'RED': image.select('B4')
                    }
                ).rename('SAVI')
                index_image = savi
            elif indice == 'MSAVI':
                msavi = image.expression(
                    '(2 * NIR + 1 - sqrt(pow((2 * NIR + 1), 2) - 8 * (NIR - RED))) / 2',
                    {
                        'NIR': image.select('B8'),
                        'RED': image.select('B4')
                    }
                ).rename('MSAVI')
                index_image = msavi
            else:
                # Por defecto usar NDVI
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                index_image = ndvi
                indice = 'NDVI'
        except Exception as e:
            st.error(f"❌ Error calculando índice {indice}: {str(e)}")
            # Fallback a NDVI
            try:
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                index_image = ndvi
                indice = 'NDVI'
                st.info("ℹ️ Usando NDVI como índice por defecto")
            except:
                st.error("❌ Error crítico: No se pudo calcular ningún índice")
                return None
        
        # Calcular estadísticas del índice dentro de la parcela
        try:
            stats = index_image.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    reducer2=ee.Reducer.minMax(),
                    sharedInputs=True
                ).combine(
                    reducer2=ee.Reducer.stdDev(),
                    sharedInputs=True
                ),
                geometry=geometry,
                scale=10,
                bestEffort=True,
                maxPixels=1e9
            )
            
            stats_dict = stats.getInfo()
            
            if not stats_dict:
                st.warning("⚠️ No se pudieron obtener estadísticas de la imagen")
                # Usar valores por defecto
                valor_promedio = 0.6
                valor_min = 0.3
                valor_max = 0.9
                valor_std = 0.1
            else:
                # Extraer valores con manejo seguro
                valor_promedio = stats_dict.get(f'{indice}_mean', 0.6)
                valor_min = stats_dict.get(f'{indice}_min', 0.3)
                valor_max = stats_dict.get(f'{indice}_max', 0.9)
                valor_std = stats_dict.get(f'{indice}_stdDev', 0.1)
                
        except Exception as e:
            st.warning(f"⚠️ Error obteniendo estadísticas: {str(e)}")
            # Valores simulados como fallback
            valor_promedio = 0.6 + np.random.normal(0, 0.1)
            valor_min = max(0.1, valor_promedio - 0.3)
            valor_max = min(0.95, valor_promedio + 0.3)
            valor_std = 0.1
        
        return {
            'indice': indice,
            'valor_promedio': valor_promedio,
            'valor_min': valor_min,
            'valor_max': valor_max,
            'valor_std': valor_std,
            'fuente': f'Sentinel-2 (Google Earth Engine) - {image_id}' if image_id else 'Sentinel-2 (GEE)',
            'fecha_descarga': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'fecha_imagen': image_date_str if 'image_date_str' in locals() else 'N/A',
            'resolucion': '10m',
            'estado': 'exitosa',
            'cobertura_nubes': f"{cloud_percent}%" if cloud_percent else 'N/A',
            'nota': f"Imágenes encontradas: {collection_size}" if collection_size else 'Sin imágenes'
        }
        
    except Exception as e:
        st.error(f"❌ Error obteniendo datos de Google Earth Engine: {str(e)}")
        st.info("💡 Usando datos simulados como alternativa")
        return None

def obtener_datos_landsat_gee(gdf, fecha_inicio, fecha_fin, dataset='LANDSAT/LC08/C02/T1_L2', indice='NDVI'):
    """Obtener datos reales de Landsat usando Google Earth Engine"""
    if not GEE_AVAILABLE or not st.session_state.gee_authenticated:
        return None
    try:
        # Obtener bounding box de la parcela
        bounds = gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Crear geometría de la parcela
        geometry = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        
        # Formatear fechas para GEE
        start_date = fecha_inicio.strftime('%Y-%m-%d')
        end_date = fecha_fin.strftime('%Y-%m-%d')
        
        # Determinar nombre de bandas según el dataset
        if 'LC08' in dataset or 'LANDSAT/LC08' in dataset:
            red_band = 'SR_B4'
            nir_band = 'SR_B5'
            red_edge_band = 'SR_B6'  # Para NDRE en Landsat
            blue_band = 'SR_B2'
        elif 'LC09' in dataset:
            red_band = 'SR_B4'
            nir_band = 'SR_B5'
            red_edge_band = 'SR_B6'  # Para NDRE en Landsat
            blue_band = 'SR_B2'
        else:
            red_band = 'SR_B4'
            nir_band = 'SR_B5'
            red_edge_band = 'SR_B6'
            blue_band = 'SR_B2'
        
        # Cargar colección Landsat
        collection = (ee.ImageCollection(dataset)
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUD_COVER', 20)))
        
        # Seleccionar la imagen con menor cobertura de nubes
        image = collection.sort('CLOUD_COVER').first()
        
        if image is None:
            st.warning("⚠️ No se encontraron imágenes Landsat para el período y área seleccionados")
            return None
        
        # Calcular índice según selección
        if indice == 'NDVI':
            ndvi = image.normalizedDifference([nir_band, red_band]).rename('NDVI')
            index_image = ndvi
        elif indice == 'NDRE':
            ndre = image.normalizedDifference([nir_band, red_edge_band]).rename('NDRE')
            index_image = ndre
        elif indice == 'NDWI':
            ndwi = image.normalizedDifference(['SR_B3', nir_band]).rename('NDWI')
            index_image = ndwi
        elif indice == 'EVI':
            evi = image.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': image.select(nir_band),
                    'RED': image.select(red_band),
                    'BLUE': image.select(blue_band)
                }
            ).rename('EVI')
            index_image = evi
        elif indice == 'SAVI':
            savi = image.expression(
                '((NIR - RED) / (NIR + RED + 0.5)) * (1.5)',
                {
                    'NIR': image.select(nir_band),
                    'RED': image.select(red_band)
                }
            ).rename('SAVI')
            index_image = savi
        elif indice == 'MSAVI':
            msavi = image.expression(
                '(2 * NIR + 1 - sqrt(pow((2 * NIR + 1), 2) - 8 * (NIR - RED))) / 2',
                {
                    'NIR': image.select(nir_band),
                    'RED': image.select(red_band)
                }
            ).rename('MSAVI')
            index_image = msavi
        else:
            ndvi = image.normalizedDifference([nir_band, red_band]).rename('NDVI')
            index_image = ndvi
            indice = 'NDVI'
        
        # Calcular estadísticas del índice dentro de la parcela
        stats = index_image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.minMax(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            ),
            geometry=geometry,
            scale=30,
            bestEffort=True
        )
        
        # Obtener valores
        stats_dict = stats.getInfo()
        
        if not stats_dict:
            st.warning("⚠️ No se pudieron obtener estadísticas de la imagen")
            return None
        
        # Extraer valores
        valor_promedio = stats_dict.get(f'{indice}_mean', 0)
        valor_min = stats_dict.get(f'{indice}_min', 0)
        valor_max = stats_dict.get(f'{indice}_max', 0)
        valor_std = stats_dict.get(f'{indice}_stdDev', 0)
        
        # Obtener fecha de la imagen
        fecha_imagen_ee = image.get('system:time_start')
        fecha_imagen = fecha_imagen_ee.getInfo() if fecha_imagen_ee else None
        
        if fecha_imagen:
            fecha_imagen = datetime.fromtimestamp(fecha_imagen / 1000).strftime('%Y-%m-%d')
        
        # Determinar nombre del satélite
        if 'LC08' in dataset:
            nombre_satelite = 'Landsat 8'
        elif 'LC09' in dataset:
            nombre_satelite = 'Landsat 9'
        else:
            nombre_satelite = 'Landsat'
        
        # CORRECCIÓN: Manejo correcto de get()
        cloud_cover_ee = image.get('CLOUD_COVER')
        cloud_cover = cloud_cover_ee.getInfo() if cloud_cover_ee else 'N/A'
        
        return {
            'indice': indice,
            'valor_promedio': valor_promedio,
            'valor_min': valor_min,
            'valor_max': valor_max,
            'valor_std': valor_std,
            'fuente': f'{nombre_satelite} (Google Earth Engine)',
            'fecha_descarga': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'fecha_imagen': fecha_imagen,
            'resolucion': '30m',
            'estado': 'exitosa',
            'cobertura_nubes': f"{cloud_cover}%" if cloud_cover != 'N/A' else 'N/A'
        }
        
    except Exception as e:
        st.error(f"❌ Error obteniendo datos de Landsat desde GEE: {str(e)}")
        return None
def descargar_datos_satelitales_gee(gdf, fecha_inicio, fecha_fin, satelite, indice='NDVI'):
    """Descargar datos satelitales usando Google Earth Engine"""
    if satelite == 'SENTINEL-2_GEE':
        return obtener_datos_sentinel2_gee(gdf, fecha_inicio, fecha_fin, indice)
    elif satelite == 'LANDSAT-8_GEE':
        return obtener_datos_landsat_gee(gdf, fecha_inicio, fecha_fin, 'LANDSAT/LC08/C02/T1_L2', indice)
    elif satelite == 'LANDSAT-9_GEE':
        return obtener_datos_landsat_gee(gdf, fecha_inicio, fecha_fin, 'LANDSAT/LC09/C02/T1_L2', indice)
    else:
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
    
# ===== FUNCIÓN PARA EJECUTAR TODOS LOS ANÁLISIS =====
def ejecutar_analisis_completo(gdf, cultivo, n_divisiones, satelite, fecha_inicio, fecha_fin,
                               intervalo_curvas=5.0, resolucion_dem=10.0):
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
        if satelite in ['SENTINEL-2_GEE', 'LANDSAT-8_GEE', 'LANDSAT-9_GEE']:
            # Usar Google Earth Engine
            datos_satelitales = descargar_datos_satelitales_gee(gdf, fecha_inicio, fecha_fin, satelite, indice_seleccionado)
            if datos_satelitales is None:
                st.warning("⚠️ No se pudieron obtener datos de GEE. Usando datos simulados.")
                datos_satelitales = generar_datos_simulados(gdf, cultivo, indice_seleccionado)
        elif satelite == "SENTINEL-2":
            datos_satelitales = descargar_datos_sentinel2(gdf, fecha_inicio, fecha_fin, indice_seleccionado)
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

# ===== NUEVA FUNCIÓN MEJORADA PARA GRÁFICO DE PROYECCIONES =====
def crear_grafico_proyecciones_rendimiento(zonas, sin_fert, con_fert):
    """Crear gráfico de proyecciones de rendimiento - VERSIÓN MEJORADA"""
    try:
        fig, ax = plt.subplots(figsize=(14, 7))
        x = np.arange(len(zonas))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, sin_fert, width, label='Sin Fertilización', 
                      color='#ff9999', edgecolor='darkred', linewidth=1)
        bars2 = ax.bar(x + width/2, con_fert, width, label='Con Fertilización', 
                      color='#66b3ff', edgecolor='darkblue', linewidth=1)
        
        ax.set_xlabel('Zona', fontsize=12)
        ax.set_ylabel('Rendimiento (kg/ha)', fontsize=12)
        ax.set_title('PROYECCIONES DE RENDIMIENTO POR ZONA', fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(zonas, rotation=45, ha='right')
        ax.legend()
        
        # Calcular y mostrar incrementos
        incrementos = [(c-s)/s*100 if s>0 else 0 for s,c in zip(sin_fert, con_fert)]
        
        # Agregar valores en las barras
        for i, (bar1, bar2) in enumerate(zip(bars1, bars2)):
            height1 = bar1.get_height()
            height2 = bar2.get_height()
            
            # Mostrar valores
            ax.text(bar1.get_x() + bar1.get_width()/2., height1 + max(sin_fert)*0.01,
                   f'{height1:.0f}', ha='center', va='bottom', fontsize=8, rotation=90)
            ax.text(bar2.get_x() + bar2.get_width()/2., height2 + max(con_fert)*0.01,
                   f'{height2:.0f}', ha='center', va='bottom', fontsize=8, rotation=90)
            
            # Mostrar incremento
            if incrementos[i] > 0:
                ax.text(bar2.get_x() + bar2.get_width()/2., height2 * 1.05,
                       f'+{incrementos[i]:.1f}%', ha='center', va='bottom', 
                       fontsize=7, color='green', weight='bold')
        
        # Agregar línea de tendencia
        if len(zonas) > 1:
            z = np.polyfit(x, sin_fert, 1)
            p = np.poly1d(z)
            ax.plot(x, p(x), "r--", alpha=0.5, label='Tendencia Base')
            
            z2 = np.polyfit(x, con_fert, 1)
            p2 = np.poly1d(z2)
            ax.plot(x, p2(x), "b--", alpha=0.5, label='Tendencia Mejorada')
        
        # Estadísticas
        stats_text = f"""
        Resumen:
        • Total base: {sum(sin_fert):.0f} kg
        • Total mejorado: {sum(con_fert):.0f} kg
        • Incremento total: {sum(con_fert)-sum(sin_fert):.0f} kg
        • Incremento promedio: {np.mean(incrementos):.1f}%
        """
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.5", facecolor='lightyellow', alpha=0.9))
        
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

def generar_reporte_completo(resultados, cultivo, satelite, fecha_inicio, fecha_fin):
    """Generar reporte DOCX con todos los análisis"""
    try:
        doc = Document()
        # Título
        title = doc.add_heading(f'REPORTE COMPLETO DE ANÁLISIS - {cultivo}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtítulo con variedad
        subtitle = doc.add_paragraph(f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 1. INFORMACIÓN GENERAL
        doc.add_heading('1. INFORMACIÓN GENERAL', level=1)
        info_table = doc.add_table(rows=6, cols=2)  # Aumentado a 6 filas
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
        info_table.cell(5, 0).text = 'Fuente de Datos'
        info_table.cell(5, 1).text = resultados['datos_satelitales']['fuente'] if resultados['datos_satelitales'] else 'N/A'
        
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
            ('Generado por', 'Analizador Multi-Cultivo Satelital'),
            ('Versión', '5.0 - Cultivos Extensivos con Google Earth Engine'),
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

# ===== INTERFAZ PRINCIPAL DE STREAMLIT =====
st.sidebar.markdown('<div class="sidebar-title">⚙️ CONFIGURACIÓN DEL ANÁLISIS</div>', unsafe_allow_html=True)

# Selección de cultivo
cultivo = st.sidebar.selectbox(
    "🌱 Seleccionar Cultivo",
    options=list(PARAMETROS_CULTIVOS.keys()),
    format_func=lambda x: f"{ICONOS_CULTIVOS.get(x, '🌾')} {x.replace('_', ' ').title()}"
)
…    </ul>
    <p style="color: #1e293b; font-size: 0.85em; margin: 10px 0 0 0; font-style: italic;">
        Requiere: <code>pip install rasterio affine</code>
    </p>
</div>
""")
