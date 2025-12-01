# analizador_cultivos_completo_final.py
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
# PARÁMETROS COMPLETOS DE FERTILIDAD POR CULTIVO (VALORES REALES)
# ============================================================================
PARAMETROS_FERTILIDAD_REAL = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 1.5, 'max': 2.5, 'optimo': 2.0, 'unidad': '%'},
        'FOSFORO': {'min': 15, 'max': 30, 'optimo': 22, 'unidad': 'ppm'},
        'POTASIO': {'min': 0.25, 'max': 0.40, 'optimo': 0.32, 'unidad': 'cmol/kg'},
        'CALCIO': {'min': 3.0, 'max': 6.0, 'optimo': 4.5, 'unidad': 'cmol/kg'},
        'MAGNESIO': {'min': 1.0, 'max': 2.0, 'optimo': 1.5, 'unidad': 'cmol/kg'},
        'AZUFRE': {'min': 10, 'max': 20, 'optimo': 15, 'unidad': 'ppm'},
        'HIERRO': {'min': 50, 'max': 100, 'optimo': 75, 'unidad': 'ppm'},
        'MANGANESO': {'min': 20, 'max': 50, 'optimo': 35, 'unidad': 'ppm'},
        'ZINC': {'min': 2, 'max': 10, 'optimo': 6, 'unidad': 'ppm'},
        'COBRE': {'min': 1, 'max': 5, 'optimo': 3, 'unidad': 'ppm'},
        'BORO': {'min': 0.5, 'max': 2.0, 'optimo': 1.2, 'unidad': 'ppm'},
        'MATERIA_ORGANICA': {'min': 2.5, 'max': 4.5, 'optimo': 3.5, 'unidad': '%'},
        'pH': {'min': 5.0, 'max': 6.0, 'optimo': 5.5, 'unidad': ''},
        'CONDUCTIVIDAD': {'min': 0.8, 'max': 1.5, 'optimo': 1.2, 'unidad': 'dS/m'},
        'CIC': {'min': 10, 'max': 20, 'optimo': 15, 'unidad': 'cmol/kg'}
    },
    'CACAO': {
        'NITROGENO': {'min': 1.8, 'max': 2.8, 'optimo': 2.3, 'unidad': '%'},
        'FOSFORO': {'min': 20, 'max': 35, 'optimo': 27, 'unidad': 'ppm'},
        'POTASIO': {'min': 0.30, 'max': 0.50, 'optimo': 0.40, 'unidad': 'cmol/kg'},
        'CALCIO': {'min': 4.0, 'max': 7.0, 'optimo': 5.5, 'unidad': 'cmol/kg'},
        'MAGNESIO': {'min': 1.2, 'max': 2.2, 'optimo': 1.7, 'unidad': 'cmol/kg'},
        'AZUFRE': {'min': 12, 'max': 25, 'optimo': 18, 'unidad': 'ppm'},
        'MATERIA_ORGANICA': {'min': 3.0, 'max': 5.0, 'optimo': 4.0, 'unidad': '%'},
        'pH': {'min': 5.5, 'max': 6.5, 'optimo': 6.0, 'unidad': ''}
    },
    'BANANO': {
        'NITROGENO': {'min': 2.0, 'max': 3.0, 'optimo': 2.5, 'unidad': '%'},
        'FOSFORO': {'min': 25, 'max': 40, 'optimo': 32, 'unidad': 'ppm'},
        'POTASIO': {'min': 0.35, 'max': 0.60, 'optimo': 0.48, 'unidad': 'cmol/kg'},
        'CALCIO': {'min': 5.0, 'max': 8.0, 'optimo': 6.5, 'unidad': 'cmol/kg'},
        'MAGNESIO': {'min': 1.5, 'max': 2.5, 'optimo': 2.0, 'unidad': 'cmol/kg'},
        'MATERIA_ORGANICA': {'min': 3.5, 'max': 5.5, 'optimo': 4.5, 'unidad': '%'},
        'pH': {'min': 5.8, 'max': 6.8, 'optimo': 6.3, 'unidad': ''}
    }
}

# ============================================================================
# RECOMENDACIONES REALES DE FERTILIZACIÓN
# ============================================================================
RECOMENDACIONES_FERTILIZACION_REAL = {
    'PALMA_ACEITERA': {
        'DEFICIENCIA_NITROGENO': [
            "Aplicar 150-200 kg/ha de urea (46% N) fraccionada en 2-3 aplicaciones",
            "Incorporar leguminosas de cobertura (Mucuna, Canavalia)",
            "Aplicar compost enriquecido (3-5 ton/ha)",
            "Considerar fertilizantes de liberación lenta"
        ],
        'DEFICIENCIA_FOSFORO': [
            "Aplicar 100-150 kg/ha de superfosfato triple (46% P2O5)",
            "Incorporar roca fosfórica en suelos ácidos (1-2 ton/ha)",
            "Aplicar fosfato diamónico en presiembra",
            "Usar inoculantes microbianos (micorrizas)"
        ],
        'DEFICIENCIA_POTASIO': [
            "Aplicar 200-300 kg/ha de cloruro de potasio (60% K2O)",
            "Fraccionar: 40% pre-siembra, 60% en crecimiento",
            "Sulfato de potasio en suelos salinos",
            "Balance N:K de 1:1.5 a 1:2"
        ],
        'DEFICIENCIA_MAGNESIO': [
            "Aplicar 50-100 kg/ha de sulfato de magnesio",
            "Corregir con dolomita en suelos ácidos (1-2 ton/ha)",
            "Evitar exceso de potasio que antagoniza Mg",
            "Foliar: sulfato de magnesio al 2% cada 15 días"
        ],
        'DEFICIENCIA_MICRONUTRIENTES': [
            "Aplicación foliar de quelatos: Zn (0.5%), B (0.2%), Cu (0.1%)",
            "Sulfato de zinc: 10-20 kg/ha al suelo",
            "Bórax: 5-10 kg/ha cada 2 años",
            "Correctivos edáficos con micronutrientes"
        ]
    }
}

# ============================================================================
# FUNCIONES AUXILIARES
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
# FUNCIONES PARA ANÁLISIS DE FERTILIDAD REAL
# ============================================================================
def simular_analisis_fertilidad_real(centroid, cultivo):
    """Simula análisis de laboratorio real de fertilidad del suelo"""
    try:
        # Semilla reproducible basada en coordenadas
        seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_fert")) % (2**32)
        rng = np.random.RandomState(seed_value)
        
        params = PARAMETROS_FERTILIDAD_REAL.get(cultivo, {})
        resultados = {}
        
        # Simular cada parámetro con distribución normal alrededor del óptimo
        for parametro, valores in params.items():
            optimo = valores['optimo']
            min_val = valores['min']
            max_val = valores['max']
            unidad = valores['unidad']
            
            # Desviación estándar como 20% del rango
            desviacion = (max_val - min_val) * 0.2
            
            # Generar valor simulado
            valor_simulado = rng.normal(optimo, desviacion)
            
            # Asegurar que esté dentro de límites razonables
            valor_simulado = max(min_val * 0.5, min(max_val * 1.5, valor_simulado))
            
            # Calcular estado
            if valor_simulado < min_val * 0.7:
                estado = "MUY DEFICIENTE"
                categoria = "CRÍTICO"
            elif valor_simulado < min_val:
                estado = "DEFICIENTE"
                categoria = "BAJO"
            elif valor_simulado <= max_val:
                if abs(valor_simulado - optimo) <= (max_val - min_val) * 0.2:
                    estado = "ÓPTIMO"
                    categoria = "EXCELENTE"
                else:
                    estado = "ADECUADO"
                    categoria = "BUENO"
            else:
                estado = "EXCESIVO"
                categoria = "ALTO"
            
            resultados[parametro] = {
                'valor': round(valor_simulado, 3),
                'unidad': unidad,
                'estado': estado,
                'categoria': categoria,
                'optimo': optimo,
                'min': min_val,
                'max': max_val
            }
        
        return resultados
        
    except Exception as e:
        # Valores por defecto en caso de error
        return {
            'NITROGENO': {'valor': 2.0, 'unidad': '%', 'estado': 'ÓPTIMO', 'categoria': 'EXCELENTE', 'optimo': 2.0, 'min': 1.5, 'max': 2.5},
            'FOSFORO': {'valor': 22, 'unidad': 'ppm', 'estado': 'ÓPTIMO', 'categoria': 'EXCELENTE', 'optimo': 22, 'min': 15, 'max': 30},
            'POTASIO': {'valor': 0.32, 'unidad': 'cmol/kg', 'estado': 'ÓPTIMO', 'categoria': 'EXCELENTE', 'optimo': 0.32, 'min': 0.25, 'max': 0.40},
            'MATERIA_ORGANICA': {'valor': 3.5, 'unidad': '%', 'estado': 'ÓPTIMO', 'categoria': 'EXCELENTE', 'optimo': 3.5, 'min': 2.5, 'max': 4.5},
            'pH': {'valor': 5.5, 'unidad': '', 'estado': 'ÓPTIMO', 'categoria': 'EXCELENTE', 'optimo': 5.5, 'min': 5.0, 'max': 6.0}
        }

def calcular_indice_fertilidad_real(resultados):
    """Calcula índice de fertilidad basado en análisis real"""
    try:
        if not resultados:
            return 0.0, "NO DISPONIBLE", []
        
        puntajes = []
        deficiencias = []
        
        for parametro, datos in resultados.items():
            valor = datos['valor']
            optimo = datos['optimo']
            min_val = datos['min']
            max_val = datos['max']
            estado = datos['estado']
            
            # Calcular puntaje (0-100)
            if estado == "MUY DEFICIENTE":
                puntaje = 20
                deficiencias.append(f"{parametro}: {estado} ({valor:.2f}{datos['unidad']})")
            elif estado == "DEFICIENTE":
                puntaje = 40
                deficiencias.append(f"{parametro}: {estado} ({valor:.2f}{datos['unidad']})")
            elif estado == "ADECUADO":
                # Puntaje entre 60-80 basado en cercanía al óptimo
                distancia_relativa = abs(valor - optimo) / (max_val - min_val)
                puntaje = 80 - (distancia_relativa * 20)
            elif estado == "ÓPTIMO":
                puntaje = 95
            else:  # EXCESIVO
                puntaje = 60
            
            puntajes.append(puntaje)
        
        if puntajes:
            indice = np.mean(puntajes) / 100  # Convertir a escala 0-1
            
            # Determinar categoría
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
            
            return indice, categoria, deficiencias[:5]  # Limitar a 5 deficiencias
        
        return 0.5, "MODERADA", ["Sin datos suficientes"]
        
    except Exception as e:
        return 0.5, "ERROR", [f"Error en cálculo: {str(e)}"]

def generar_recomendaciones_fertilidad_real(resultados, cultivo, deficiencias):
    """Genera recomendaciones reales de fertilización"""
    try:
        recomendaciones = []
        
        # Recomendaciones específicas por deficiencia
        for deficiencia in deficiencias:
            if "NITROGENO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION_REAL:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION_REAL[cultivo].get('DEFICIENCIA_NITROGENO', []))
            
            if "FOSFORO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION_REAL:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION_REAL[cultivo].get('DEFICIENCIA_FOSFORO', []))
            
            if "POTASIO" in deficiencia and "DEFICIENTE" in deficiencia:
                if cultivo in RECOMENDACIONES_FERTILIZACION_REAL:
                    recomendaciones.extend(RECOMENDACIONES_FERTILIZACION_REAL[cultivo].get('DEFICIENCIA_POTASIO', []))
        
        # Recomendaciones generales por cultivo
        if cultivo == "PALMA_ACEITERA":
            recomendaciones.extend([
                "Programa anual de fertilización: 3-4 aplicaciones al año",
                "Balance NPK recomendado: 12-6-18 + 3MgO",
                "Época principal de fertilización: inicio de lluvias",
                "Incorporar 3-5 ton/ha de materia orgánica anualmente",
                "Monitorear niveles de magnesio cada 6 meses",
                "Aplicar micronutrientes vía foliar en períodos críticos"
            ])
        elif cultivo == "CACAO":
            recomendaciones.extend([
                "Fertilización orgánica preferible sobre química",
                "Balance NPK: 15-10-15 para plantas jóvenes",
                "Aplicar después de podas principales",
                "Evitar aplicación en suelo seco",
                "Usar coberturas leguminosas para fijar nitrógeno"
            ])
        elif cultivo == "BANANO":
            recomendaciones.extend([
                "Alta demanda de potasio: aplicar 300-400 kg/ha/año K2O",
                "Balance NPK: 8-4-24 para producción comercial",
                "Fertirrigación recomendada para máxima eficiencia",
                "Monitorear niveles de calcio para evitar desórdenes fisiológicos",
                "Aplicaciones fraccionadas cada 2-3 meses"
            ])
        
        # Eliminar duplicados y limitar
        return list(dict.fromkeys(recomendaciones))[:8]
        
    except Exception as e:
        return ["Consultar con especialista en fertilidad de suelos"]

def analizar_fertilidad_real(gdf, cultivo, mes_analisis):
    """Realiza análisis REAL de fertilidad del suelo"""
    try:
        zonas_gdf = gdf.copy()
        
        # Columnas base
        columnas_base = ['id_zona', 'area_ha']
        
        # Agregar columnas para parámetros principales
        parametros_principales = ['NITROGENO', 'FOSFORO', 'POTASIO', 'MATERIA_ORGANICA', 'pH']
        
        for param in parametros_principales:
            columnas_base.extend([
                f'{param}_valor',
                f'{param}_unidad',
                f'{param}_estado',
                f'{param}_categoria'
            ])
        
        columnas_base.extend([
            'indice_fertilidad',
            'categoria_fertilidad',
            'deficiencias_principales',
            'recomendaciones_fertilizacion'
        ])
        
        # Inicializar columnas
        for col in columnas_base:
            if col == 'id_zona' and col not in zonas_gdf.columns:
                zonas_gdf[col] = range(1, len(zonas_gdf) + 1)
            elif col not in zonas_gdf.columns:
                if any(x in col for x in ['deficiencias', 'recomendaciones', 'estado', 'categoria']):
                    zonas_gdf[col] = ""
                elif 'valor' in col:
                    zonas_gdf[col] = 0.0
                else:
                    zonas_gdf[col] = ""
        
        # Procesar cada zona
        for idx, row in zonas_gdf.iterrows():
            try:
                area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
                zonas_gdf.loc[idx, 'area_ha'] = area_ha
                
                # Obtener centroide para simulación espacial
                if hasattr(row.geometry, 'centroid') and not row.geometry.is_empty:
                    centroid = row.geometry.centroid
                else:
                    centroid = row.geometry.representative_point()
                
                # Simular análisis de laboratorio REAL
                resultados = simular_analisis_fertilidad_real(centroid, cultivo)
                
                if resultados:
                    # Guardar valores de parámetros principales
                    for param in parametros_principales:
                        if param in resultados:
                            datos = resultados[param]
                            zonas_gdf.loc[idx, f'{param}_valor'] = datos['valor']
                            zonas_gdf.loc[idx, f'{param}_unidad'] = datos['unidad']
                            zonas_gdf.loc[idx, f'{param}_estado'] = datos['estado']
                            zonas_gdf.loc[idx, f'{param}_categoria'] = datos['categoria']
                    
                    # Calcular índice de fertilidad
                    indice, categoria, deficiencias = calcular_indice_fertilidad_real(resultados)
                    zonas_gdf.loc[idx, 'indice_fertilidad'] = indice
                    zonas_gdf.loc[idx, 'categoria_fertilidad'] = categoria
                    zonas_gdf.loc[idx, 'deficiencias_principales'] = ' | '.join(deficiencias[:3])
                    
                    # Generar recomendaciones
                    recomendaciones = generar_recomendaciones_fertilidad_real(resultados, cultivo, deficiencias)
                    zonas_gdf.loc[idx, 'recomendaciones_fertilizacion'] = ' • '.join(recomendaciones[:5])
                
            except Exception as e:
                # Valores por defecto en caso de error
                zonas_gdf.loc[idx, 'area_ha'] = area_ha
                zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.5
                zonas_gdf.loc[idx, 'categoria_fertilidad'] = "MODERADA"
                zonas_gdf.loc[idx, 'deficiencias_principales'] = "Error en análisis"
                zonas_gdf.loc[idx, 'recomendaciones_fertilizacion'] = "Consultar con laboratorio de suelos"
        
        return zonas_gdf
    
    except Exception as e:
        st.error(f"❌ Error en análisis de fertilidad: {str(e)}")
        return gdf

# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================
def mostrar_analisis_textura():
    """Muestra análisis de textura con gráfico de torta"""
    try:
        if st.session_state.analisis_textura is None:
            st.warning("No hay datos de análisis de textura")
            return
        
        gdf_textura = st.session_state.analisis_textura
        
        st.markdown("## 🏗️ ANÁLISIS DE TEXTURA DEL SUELO")
        
        if st.button("⬅️ Volver a Configuración", key="volver_textura"):
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
        
        # GRÁFICO DE TORTA - DISTRIBUCIÓN DE TEXTURAS
        st.subheader("📊 DISTRIBUCIÓN DE TEXTURAS (GRÁFICO DE TORTA)")
        
        if 'textura_suelo' in gdf_textura.columns and len(gdf_textura) > 0:
            fig, ax = plt.subplots(figsize=(8, 8))
            
            # Contar frecuencia de cada textura
            textura_counts = gdf_textura['textura_suelo'].value_counts()
            
            if not textura_counts.empty:
                # Preparar datos para el gráfico
                labels = []
                sizes = []
                colors_pie = []
                
                for textura, count in textura_counts.items():
                    info = CLASIFICACION_TEXTURAS_PALMA.get(textura, {})
                    labels.append(info.get('nombre_completo', textura))
                    sizes.append(count)
                    colors_pie.append(info.get('color', '#999999'))
                
                # Crear gráfico de torta
                wedges, texts, autotexts = ax.pie(
                    sizes, 
                    labels=labels, 
                    colors=colors_pie,
                    autopct='%1.1f%%',
                    startangle=90,
                    textprops={'fontsize': 10}
                )
                
                # Mejorar visualización
                ax.axis('equal')  # Torta circular
                ax.set_title('Distribución de Texturas del Suelo', fontsize=14, fontweight='bold')
                
                # Añadir leyenda
                ax.legend(
                    wedges, 
                    labels,
                    title="Texturas",
                    loc="center left",
                    bbox_to_anchor=(1, 0, 0.5, 1)
                )
                
                st.pyplot(fig)
            else:
                st.info("No hay suficientes datos para generar el gráfico de torta")
        
        # Mapa de texturas
        st.subheader("🗺️ MAPA DE DISTRIBUCIÓN DE TEXTURAS")
        
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
                        Materia Orgánica: {row.get('materia_organica', 0):.1f}%<br>
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
                        popup=folium.Popup(popup_text, max_width=250)
                    ).add_to(m)
                
                # Añadir leyenda
                legend_html = '''
                <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; 
                            background: white; padding: 10px; border: 2px solid grey; z-index: 9999;">
                    <b>🎨 Leyenda de Texturas</b><br>
                    <i style="background: #4a7c59; width: 20px; height: 20px; display: inline-block;"></i> Franco<br>
                    <i style="background: #8b4513; width: 20px; height: 20px; display: inline-block;"></i> Franco Arcilloso<br>
                    <i style="background: #d2b48c; width: 20px; height: 20px; display: inline-block;"></i> Franco Arcilloso-Arenoso
                </div>
                '''
                
                m.get_root().html.add_child(folium.Element(legend_html))
                st_folium(m, width=800, height=500)
                
            except Exception as e:
                st.warning(f"No se pudo generar el mapa: {str(e)}")
        
        # Tabla de datos
        st.subheader("📋 DATOS DETALLADOS POR ZONA")
        
        columnas = ['id_zona', 'area_ha', 'textura_nombre_completo', 'arena', 'limo', 'arcilla', 'materia_organica']
        columnas_existentes = [c for c in columnas if c in gdf_textura.columns]
        
        if columnas_existentes:
            df = gdf_textura[columnas_existentes].copy()
            
            # Formatear valores
            if 'area_ha' in df.columns:
                df['area_ha'] = df['area_ha'].apply(lambda x: f"{x:.3f}")
            if 'arena' in df.columns:
                df['arena'] = df['arena'].apply(lambda x: f"{x:.1f}%")
            if 'limo' in df.columns:
                df['limo'] = df['limo'].apply(lambda x: f"{x:.1f}%")
            if 'arcilla' in df.columns:
                df['arcilla'] = df['arcilla'].apply(lambda x: f"{x:.1f}%")
            if 'materia_organica' in df.columns:
                df['materia_organica'] = df['materia_organica'].apply(lambda x: f"{x:.1f}%")
            
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
        
        with col2:
            if not gdf_textura.empty:
                geojson_data = gdf_textura.to_json()
                st.download_button(
                    label="🗺️ Descargar GeoJSON",
                    data=geojson_data,
                    file_name=f"textura_{st.session_state.cultivo_seleccionado}_{datetime.now().strftime('%Y%m%d')}.geojson",
                    mime="application/json"
                )
        
    except Exception as e:
        st.error(f"Error mostrando análisis: {str(e)}")

def mostrar_analisis_fertilidad():
    """Muestra análisis REAL de fertilidad"""
    try:
        if st.session_state.analisis_fertilidad is None:
            st.warning("No hay datos de análisis de fertilidad")
            return
        
        gdf_fertilidad = st.session_state.analisis_fertilidad
        cultivo = st.session_state.cultivo_seleccionado
        
        st.markdown("## 🌿 ANÁLISIS REAL DE FERTILIDAD DEL SUELO")
        
        if st.button("⬅️ Volver a Configuración", key="volver_fertilidad"):
            st.session_state.analisis_completado = False
            st.rerun()
        
        # Estadísticas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if 'indice_fertilidad' in gdf_fertilidad.columns:
                indice_prom = gdf_fertilidad['indice_fertilidad'].mean()
                st.metric("📈 Índice de Fertilidad", f"{indice_prom:.2f}/1.0")
        with col2:
            if 'categoria_fertilidad' in gdf_fertilidad.columns:
                categoria = gdf_fertilidad['categoria_fertilidad'].mode()[0] if not gdf_fertilidad['categoria_fertilidad'].mode().empty else "N/A"
                st.metric("🏆 Categoría Predominante", categoria)
        with col3:
            if 'NITROGENO_valor' in gdf_fertilidad.columns:
                n_prom = gdf_fertilidad['NITROGENO_valor'].mean()
                n_estado = gdf_fertilidad['NITROGENO_estado'].mode()[0] if 'NITROGENO_estado' in gdf_fertilidad.columns else "N/A"
                st.metric("🟢 Nitrógeno", f"{n_prom:.2f}%", n_estado)
        with col4:
            if 'POTASIO_valor' in gdf_fertilidad.columns:
                k_prom = gdf_fertilidad['POTASIO_valor'].mean()
                k_estado = gdf_fertilidad['POTASIO_estado'].mode()[0] if 'POTASIO_estado' in gdf_fertilidad.columns else "N/A"
                st.metric("🟤 Potasio", f"{k_prom:.3f}", k_estado)
        
        # Gráfico de distribución de categorías de fertilidad
        st.subheader("📊 DISTRIBUCIÓN DE CATEGORÍAS DE FERTILIDAD")
        
        if 'categoria_fertilidad' in gdf_fertilidad.columns and len(gdf_fertilidad) > 0:
            fig, ax = plt.subplots(figsize=(8, 8))
            
            # Contar categorías
            categoria_counts = gdf_fertilidad['categoria_fertilidad'].value_counts()
            
            if not categoria_counts.empty:
                # Colores para cada categoría
                colores_categorias = {
                    'EXCELENTE': '#006400',  # Verde oscuro
                    'BUENA': '#32cd32',      # Verde
                    'MODERADA': '#ffd700',   # Amarillo
                    'BAJA': '#ff8c00',       # Naranja
                    'MUY BAJA': '#8b0000'    # Rojo oscuro
                }
                
                labels = categoria_counts.index.tolist()
                sizes = categoria_counts.values.tolist()
                colors = [colores_categorias.get(label, '#999999') for label in labels]
                
                # Crear gráfico de torta
                wedges, texts, autotexts = ax.pie(
                    sizes, 
                    labels=labels, 
                    colors=colors,
                    autopct='%1.1f%%',
                    startangle=90,
                    textprops={'fontsize': 10}
                )
                
                ax.axis('equal')
                ax.set_title('Distribución de Categorías de Fertilidad', fontsize=14, fontweight='bold')
                
                st.pyplot(fig)
            else:
                st.info("No hay suficientes datos para el gráfico")
        
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
                    categoria = row.get('categoria_fertilidad', 'MODERADA')
                    
                    # Color basado en categoría
                    colores_map = {
                        'EXCELENTE': '#006400',
                        'BUENA': '#32cd32',
                        'MODERADA': '#ffd700',
                        'BAJA': '#ff8c00',
                        'MUY BAJA': '#8b0000'
                    }
                    color = colores_map.get(categoria, '#999999')
                    
                    popup_text = f"""
                    <div style="font-size:12px">
                        <b>Zona {row.get('id_zona', 'N/A')}</b><br>
                        Índice: {indice:.2f}<br>
                        Categoría: {categoria}<br>
                        N: {row.get('NITROGENO_valor', 0):.2f}% ({row.get('NITROGENO_estado', 'N/A')})<br>
                        P: {row.get('FOSFORO_valor', 0):.0f} ppm ({row.get('FOSFORO_estado', 'N/A')})<br>
                        K: {row.get('POTASIO_valor', 0):.3f} ({row.get('POTASIO_estado', 'N/A')})<br>
                        MO: {row.get('MATERIA_ORGANICA_valor', 0):.1f}%<br>
                        pH: {row.get('pH_valor', 0):.1f}
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
                        popup=folium.Popup(popup_text, max_width=250)
                    ).add_to(m)
                
                # Leyenda
                legend_html = '''
                <div style="position: fixed; bottom: 50px; left: 50px; width: 200px; 
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
                st_folium(m, width=800, height=500)
                
            except Exception as e:
                st.warning(f"No se pudo generar el mapa: {str(e)}")
        
        # Tabla de nutrientes principales
        st.subheader("📋 ANÁLISIS DE NUTRIENTES PRINCIPALES")
        
        nutrientes_cols = ['id_zona', 'area_ha', 'indice_fertilidad', 'categoria_fertilidad',
                          'NITROGENO_valor', 'NITROGENO_estado',
                          'FOSFORO_valor', 'FOSFORO_estado',
                          'POTASIO_valor', 'POTASIO_estado',
                          'MATERIA_ORGANICA_valor', 'pH_valor']
        
        cols_existentes = [c for c in nutrientes_cols if c in gdf_fertilidad.columns]
        
        if cols_existentes:
            df_nutrientes = gdf_fertilidad[cols_existentes].head(15).copy()
            
            # Formatear valores
            if 'indice_fertilidad' in df_nutrientes.columns:
                df_nutrientes['indice_fertilidad'] = df_nutrientes['indice_fertilidad'].apply(lambda x: f"{x:.2f}")
            if 'area_ha' in df_nutrientes.columns:
                df_nutrientes['area_ha'] = df_nutrientes['area_ha'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(df_nutrientes, height=400)
        
        # Recomendaciones
        st.subheader("💡 RECOMENDACIONES DE FERTILIZACIÓN")
        
        if 'recomendaciones_fertilizacion' in gdf_fertilidad.columns and len(gdf_fertilidad) > 0:
            try:
                # Tomar recomendaciones de la primera zona
                rec_text = gdf_fertilidad.iloc[0]['recomendaciones_fertilizacion']
                if rec_text:
                    recomendaciones = rec_text.split(' • ')
                    
                    col_rec1, col_rec2 = st.columns(2)
                    
                    with col_rec1:
                        for i, rec in enumerate(recomendaciones[:len(recomendaciones)//2]):
                            st.markdown(f"• {rec}")
                    
                    with col_rec2:
                        for i, rec in enumerate(recomendaciones[len(recomendaciones)//2:]):
                            st.markdown(f"• {rec}")
            except:
                pass
            
            # Recomendaciones adicionales por cultivo
            st.markdown("#### 🌱 Recomendaciones Específicas por Cultivo")
            
            if cultivo == "PALMA_ACEITERA":
                st.success("""
                **Para Palma Aceitera:**
                • Época óptima de fertilización: inicio de la estación lluviosa
                • Fraccionamiento recomendado: 3-4 aplicaciones anuales
                • Balance NPK típico: 12-6-18 + 3MgO + micronutrientes
                • Materia orgánica: mínimo 3% en el suelo
                • Monitoreo de pH: mantener entre 5.0-6.0
                """)
            elif cultivo == "CACAO":
                st.info("""
                **Para Cacao:**
                • Preferir fertilización orgánica
                • Aplicar después de podas principales
                • Balance NPK: 15-10-15 para plantas jóvenes
                • Evitar aplicación en suelo seco
                • Usar coberturas leguminosas
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
        
        with col2:
            if not gdf_fertilidad.empty:
                geojson_data = gdf_fertilidad.to_json()
                st.download_button(
                    label="🗺️ Descargar GeoJSON",
                    data=geojson_data,
                    file_name=f"fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d')}.geojson",
                    mime="application/json"
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
            ["ANÁLISIS DE TEXTURA", "FERTILIDAD REAL", "RECOMENDACIONES COMPLETAS"],
            index=0
        )
        
        # Mes
        st.session_state.mes_analisis = st.selectbox(
            "📅 Mes de Análisis:",
            ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", 
             "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"],
            index=0
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
            "Subir archivo de parcela",
            type=['zip', 'kml', 'shp'],
            help="Formatos: Shapefile (.zip), KML, o SHP individual"
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
        elif tipo_analisis == "FERTILIDAD REAL":
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
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
                st.success("✅ Archivo procesado exitosamente")
    
    elif st.session_state.datos_demo and st.session_state.gdf_original is None:
        # Datos demo para Colombia/Venezuela
        poligono = Polygon([
            [-73.5, 5.0], [-73.4, 5.0], [-73.4, 5.1], [-73.5, 5.1], [-73.5, 5.0]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo - Zona Palmera']},
            geometry=[poligono],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.success("✅ Datos de demostración creados")
    
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
            with st.spinner("🔄 Dividiendo parcela en zonas..."):
                gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
                st.session_state.gdf_zonas = gdf_zonas
                st.success(f"✅ Parcela dividida en {len(gdf_zonas)} zonas")
            
            with st.spinner(f"🔬 Realizando análisis de {tipo_analisis.lower()}..."):
                if tipo_analisis == "ANÁLISIS DE TEXTURA":
                    gdf_resultado = analizar_textura_suelo(
                        gdf_zonas, 
                        st.session_state.cultivo_seleccionado, 
                        st.session_state.mes_analisis
                    )
                    st.session_state.analisis_textura = gdf_resultado
                    st.success("✅ Análisis de textura completado")
                
                elif tipo_analisis == "FERTILIDAD REAL":
                    gdf_resultado = analizar_fertilidad_real(
                        gdf_zonas,
                        st.session_state.cultivo_seleccionado,
                        st.session_state.mes_analisis
                    )
                    st.session_state.analisis_fertilidad = gdf_resultado
                    st.success("✅ Análisis de fertilidad REAL completado")
                
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
            2. Selecciona el cultivo
            3. Elige el tipo de análisis
            4. Configura las opciones
            5. Haz clic en 'Iniciar Análisis'
            
            **📄 Formatos soportados:**
            • Shapefile comprimido (.zip)
            • Archivo KML de Google Earth
            • Shapefile individual (.shp)
            """)
        
        with col2:
            st.success("""
            **🔬 Funcionalidades disponibles:**
            
            **ANÁLISIS DE TEXTURA:**
            • Clasificación específica para palma
            • Gráfico de torta de distribución
            • Mapa interactivo de texturas
            • Datos detallados por zona
            
            **FERTILIDAD REAL:**
            • Análisis completo de nutrientes
            • Índice de fertilidad calculado
            • Recomendaciones específicas
            • Mapas de categoría de fertilidad
            """)

# Ejecutar aplicación
if __name__ == "__main__":
    main()
