import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import ee
import geemap
from geemap import foliumap
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import json
from datetime import datetime, timedelta
import io
import base64
from PIL import Image as PILImage
import tempfile
import os
import zipfile
from shapely.geometry import mapping, shape
import fiona
import warnings
warnings.filterwarnings('ignore')

# Configuración de la página
st.set_page_config(page_title="Sistema Agroecológico - Cultivos Tropicales", 
                   page_icon="🌴", 
                   layout="wide",
                   initial_sidebar_state="expanded")

# Inicialización de Earth Engine
def initialize_earth_engine():
    try:
        ee.Initialize()
        return True, "✅ Earth Engine inicializado correctamente"
    except Exception as e:
        try:
            ee.Authenticate()
            ee.Initialize()
            return True, "✅ Earth Engine autenticado e inicializado"
        except:
            return False, f"❌ Earth Engine no disponible: {str(e)}"

# Estado de la aplicación
if 'ee_initialized' not in st.session_state:
    initialized, message = initialize_earth_engine()
    st.session_state.ee_initialized = initialized
    st.session_state.ee_message = message

# Título principal
st.title("🌱 Sistema Agroecológico para Cultivos Tropicales")
st.markdown("---")

# Sidebar con parámetros avanzados
st.sidebar.header("🌿 Parámetros Agroecológicos")

# Gestión de lotes múltiples
st.sidebar.subheader("🗂️ Gestión de Lotes")

# Opción para cargar archivos o crear lotes manualmente
opcion_lotes = st.sidebar.radio(
    "Seleccione opción:",
    ["Cargar archivo KML/Shapefile", "Crear lotes manualmente"]
)

lotes_data = []

if opcion_lotes == "Cargar archivo KML/Shapefile":
    st.sidebar.subheader("📁 Cargar Archivo Geoespacial")
    
    # Subir archivo
    archivo_cargado = st.sidebar.file_uploader(
        "Seleccione archivo KML o ZIP (Shapefile):",
        type=['kml', 'kmz', 'zip'],
        help="Puede cargar: KML, KMZ o ZIP con Shapefile (.shp, .shx, .dbf, .prj)"
    )
    
    if archivo_cargado:
        with st.spinner("Procesando archivo geoespacial..."):
            try:
                # Crear directorio temporal
                with tempfile.TemporaryDirectory() as tmp_dir:
                    archivo_path = os.path.join(tmp_dir, archivo_cargado.name)
                    
                    # Guardar archivo subido
                    with open(archivo_path, 'wb') as f:
                        f.write(archivo_cargado.getvalue())
                    
                    # Procesar según tipo de archivo
                    if archivo_cargado.name.lower().endswith('.zip'):
                        # Es un shapefile comprimido
                        with zipfile.ZipFile(archivo_path, 'r') as zip_ref:
                            zip_ref.extractall(tmp_dir)
                        
                        # Buscar archivo .shp en el zip
                        shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                        if shp_files:
                            shp_path = os.path.join(tmp_dir, shp_files[0])
                            gdf = gpd.read_file(shp_path)
                        else:
                            st.error("No se encontró archivo .shp en el ZIP")
                            gdf = None
                    
                    elif archivo_cargado.name.lower().endswith(('.kml', '.kmz')):
                        # Es un archivo KML/KMZ
                        gdf = gpd.read_file(archivo_path, driver='KML')
                    
                    else:
                        st.error("Formato de archivo no soportado")
                        gdf = None
                    
                    if gdf is not None:
                        # Procesar geometrías
                        gdf = gdf.to_crs('EPSG:4326')  # Convertir a WGS84
                        gdf['area_ha'] = gdf.geometry.area * 10000  # Área en hectáreas
                        
                        # Mostrar información del archivo
                        st.sidebar.success(f"✅ Archivo cargado: {len(gdf)} lotes encontrados")
                        
                        # Configurar lotes desde el archivo
                        for i, row in gdf.iterrows():
                            nombre_lote = row.get('Name', f'Lote_{i+1}')
                            if hasattr(row, 'name') and row.name:
                                nombre_lote = str(row.name)
                            
                            # Buscar nombres en columnas comunes
                            for col in ['nombre', 'name', 'Nombre', 'LOTE', 'lote']:
                                if col in row.index and pd.notna(row[col]):
                                    nombre_lote = str(row[col])
                                    break
                            
                            lote_data = {
                                'nombre': nombre_lote,
                                'cultivo': "Palma Aceitera",  # Default, se puede cambiar
                                'area': max(0.1, row['area_ha']),
                                'nivel_n': 50,
                                'nivel_p': 30,
                                'nivel_k': 100,
                                'ph': 6.0,
                                'materia_organica': 3.0,
                                'geometria': row.geometry,
                                'centroide': row.geometry.centroid
                            }
                            lotes_data.append(lote_data)
                        
                        # Mostrar preview del archivo
                        with st.sidebar.expander("📊 Vista previa del archivo"):
                            st.write(f"**Total de polígonos:** {len(gdf)}")
                            st.write(f"**Área total:** {gdf['area_ha'].sum():.2f} ha")
                            st.write(f"**Columnas disponibles:** {list(gdf.columns)}")
                            
                            # Mostrar tabla de atributos
                            if len(gdf) <= 10:
                                st.dataframe(gdf.drop(columns=['geometry']).head())
                
            except Exception as e:
                st.sidebar.error(f"❌ Error procesando archivo: {str(e)}")
    
    # Si no hay archivo cargado, permitir crear lotes manualmente
    if not archivo_cargado:
        st.sidebar.info("📝 Cargue un archivo KML/Shapefile o cambie a 'Crear lotes manualmente'")

else:  # Crear lotes manualmente
    num_lotes = st.sidebar.number_input("Número de lotes", 1, 50, 1)

    for i in range(num_lotes):
        with st.sidebar.expander(f"Lote {i+1}", expanded=i==0):
            col1, col2 = st.columns(2)
            with col1:
                nombre_lote = st.text_input(f"Nombre Lote {i+1}", f"Lote_{i+1}")
                area_lote = st.number_input(f"Área (ha) {i+1}", 0.1, 1000.0, 5.0)
            with col2:
                cultivo_lote = st.selectbox(f"Cultivo {i+1}", 
                                          ["Palma Aceitera", "Banano", "Cacao", "Café", "Piña", "Mango", "Plátano"])
            
            st.subheader("🧪 Análisis de Suelo")
            col_n, col_p, col_k = st.columns(3)
            with col_n:
                nivel_n = st.slider(f"N (ppm) L{i+1}", 0, 200, 50)
            with col_p:
                nivel_p = st.slider(f"P (ppm) L{i+1}", 0, 150, 30)
            with col_k:
                nivel_k = st.slider(f"K (ppm) L{i+1}", 0, 300, 100)
            
            ph = st.slider(f"pH L{i+1}", 4.0, 8.0, 6.0)
            materia_organica = st.slider(f"M.O. % L{i+1}", 1.0, 10.0, 3.0)
            
            lotes_data.append({
                'nombre': nombre_lote,
                'cultivo': cultivo_lote,
                'area': area_lote,
                'nivel_n': nivel_n,
                'nivel_p': nivel_p,
                'nivel_k': nivel_k,
                'ph': ph,
                'materia_organica': materia_organica,
                'geometria': None,
                'centroide': None
            })

# Parámetros agroecológicos avanzados
st.sidebar.subheader("🌍 Principios Agroecológicos")
rotacion_cultivos = st.sidebar.selectbox("Sistema de rotación", 
                                       ["Monocultivo", "Rotación simple", "Policultivo", "Agroforestería"])
cobertura_suelo = st.sidebar.selectbox("Cobertura del suelo",
                                     ["Suelo desnudo", "Cobertura parcial", "Cobertura completa"])
manejo_organico = st.sidebar.slider("Nivel de manejo orgánico", 0, 100, 50)
biodiversidad = st.sidebar.slider("Índice de biodiversidad", 0, 100, 30)

# Funciones avanzadas de análisis
def analizar_fertilidad_real(lote):
    """Análisis integral de fertilidad basado en principios agroecológicos"""
    
    # Puntaje de fertilidad base (0-100)
    puntaje_ph = max(0, 100 - abs(6.5 - lote['ph']) * 20)  # Óptimo pH 6.5
    puntaje_mo = min(100, lote['materia_organica'] * 10)   # M.O. ideal 5-8%
    
    # Balance NPK
    balance_npk = min(100, (lote['nivel_n'] + lote['nivel_p'] + lote['nivel_k']) / 5)
    
    # Factores agroecológicos
    factor_rotacion = {
        "Monocultivo": 0.7,
        "Rotación simple": 0.8,
        "Policultivo": 0.9,
        "Agroforestería": 1.0
    }[rotacion_cultivos]
    
    factor_cobertura = {
        "Suelo desnudo": 0.6,
        "Cobertura parcial": 0.8,
        "Cobertura completa": 1.0
    }[cobertura_suelo]
    
    factor_organico = manejo_organico / 100
    factor_biodiversidad = biodiversidad / 100
    
    # Cálculo final de fertilidad
    fertilidad_base = (puntaje_ph * 0.3 + puntaje_mo * 0.4 + balance_npk * 0.3)
    fertilidad_ajustada = fertilidad_base * factor_rotacion * factor_cobertura * factor_organico * factor_biodiversidad
    
    return {
        'puntaje_total': round(fertilidad_ajustada, 1),
        'categoria': categorizar_fertilidad(fertilidad_ajustada),
        'puntaje_ph': round(puntaje_ph, 1),
        'puntaje_mo': round(puntaje_mo, 1),
        'puntaje_npk': round(balance_npk, 1),
        'factores_agroecologicos': {
            'rotacion': factor_rotacion,
            'cobertura': factor_cobertura,
            'organico': factor_organico,
            'biodiversidad': factor_biodiversidad
        }
    }

def categorizar_fertilidad(puntaje):
    if puntaje >= 80:
        return "Excelente"
    elif puntaje >= 60:
        return "Buena"
    elif puntaje >= 40:
        return "Regular"
    else:
        return "Baja"

def calcular_recomendaciones_agroecologicas(lote, analisis_fertilidad):
    """Recomendaciones basadas en principios agroecológicos"""
    
    requerimientos = {
        "Palma Aceitera": {"N": 120, "P": 40, "K": 160},
        "Banano": {"N": 150, "P": 35, "K": 200},
        "Cacao": {"N": 100, "P": 30, "K": 120},
        "Café": {"N": 130, "P": 25, "K": 140},
        "Piña": {"N": 180, "P": 45, "K": 220},
        "Mango": {"N": 80, "P": 20, "K": 100},
        "Plátano": {"N": 140, "P": 30, "K": 180}
    }
    
    cultivo = lote['cultivo']
    
    # Cálculo de deficiencias con enfoque agroecológico
    deficiencia_n = max(0, requerimientos[cultivo]["N"] - lote['nivel_n'] * 2) * 0.8
    deficiencia_p = max(0, requerimientos[cultivo]["P"] - lote['nivel_p'] * 1.5) * 0.7
    deficiencia_k = max(0, requerimientos[cultivo]["K"] - lote['nivel_k'] * 1.2) * 0.8
    
    # Ajustar por principios agroecológicos
    factor_agroecologico = analisis_fertilidad['factores_agroecologicos']['organico'] * \
                          analisis_fertilidad['factores_agroecologicos']['biodiversidad']
    
    recomendacion_n = deficiencia_n * factor_agroecologico * lote['area']
    recomendacion_p = deficiencia_p * factor_agroecologico * lote['area']
    recomendacion_k = deficiencia_k * factor_agroecologico * lote['area']
    
    # Recomendaciones de enmiendas orgánicas
    enmiendas_organicas = generar_enmiendas_organicas(lote, deficiencia_n, deficiencia_p, deficiencia_k)
    
    # Prácticas agroecológicas recomendadas
    practicas_recomendadas = generar_practicas_agroecologicas(lote, analisis_fertilidad)
    
    return {
        'quimicos': {
            'N': round(max(0, recomendacion_n), 2),
            'P': round(max(0, recomendacion_p), 2),
            'K': round(max(0, recomendacion_k), 2)
        },
        'organicos': enmiendas_organicas,
        'practicas_agroecologicas': practicas_recomendadas,
        'reduccion_quimicos': round((1 - factor_agroecologico) * 100, 1)
    }

def generar_enmiendas_organicas(lote, def_n, def_p, def_k):
    """Generar recomendaciones de enmiendas orgánicas"""
    enmiendas = []
    
    if def_n > 0:
        enmiendas.append(f"Compost: {def_n * 2:.1f} kg/ha (para N)")
    if def_p > 0:
        enmiendas.append(f"Roca fosfórica: {def_p * 3:.1f} kg/ha (para P)")
    if def_k > 0:
        enmiendas.append(f"Ceniza vegetal: {def_k * 4:.1f} kg/ha (para K)")
    
    # Enmiendas para mejorar pH
    if lote['ph'] < 5.5:
        enmiendas.append(f"Cal agrícola: {(6.5 - lote['ph']) * 500:.1f} kg/ha")
    elif lote['ph'] > 7.5:
        enmiendas.append(f"Azufre: {(lote['ph'] - 6.5) * 200:.1f} kg/ha")
    
    # Mejora de materia orgánica
    if lote['materia_organica'] < 4:
        enmiendas.append(f"Abono verde: 2-3 ton/ha (para mejorar M.O.)")
    
    return enmiendas

def generar_practicas_agroecologicas(lote, analisis_fertilidad):
    """Generar recomendaciones de prácticas agroecológicas"""
    practicas = []
    
    if analisis_fertilidad['puntaje_total'] < 60:
        practicas.append("✅ Implementar abonos verdes (leguminosas)")
        practicas.append("✅ Establecer cobertura vegetal permanente")
        practicas.append("✅ Aplicar compost y biofertilizantes")
    
    if lote['ph'] < 5.5 or lote['ph'] > 7.5:
        practicas.append("✅ Corregir pH con enmiendas naturales")
    
    if lote['materia_organica'] < 3:
        practicas.append("✅ Incorporar materia orgánica regularmente")
        practicas.append("✅ Evitar quema de residuos")
    
    if biodiversidad < 50:
        practicas.append("✅ Establecer bordes diversificados")
        practicas.append("✅ Implementar asociación de cultivos")
    
    if rotacion_cultivos == "Monocultivo":
        practicas.append("✅ Planificar rotación de cultivos")
    
    return practicas

# Funciones para procesar datos geoespaciales
def obtener_centroide_lotes(lotes_data):
    """Obtener centroide promedio de todos los lotes para centrar el mapa"""
    centroides = []
    for lote in lotes_data:
        if lote.get('centroide'):
            centroides.append((lote['centroide'].y, lote['centroide'].x))
        elif lote.get('geometria'):
            centroide = lote['geometria'].centroid
            centroides.append((centroide.y, centroide.x))
    
    if centroides:
        avg_lat = sum(c[0] for c in centroides) / len(centroides)
        avg_lon = sum(c[1] for c in centroides) / len(centroides)
        return [avg_lat, avg_lon]
    else:
        return [9.7489, -83.7534]  # Costa Rica por defecto

def crear_mapa_con_lotes(lotes_data):
    """Crear mapa interactivo con los lotes cargados"""
    
    # Centrar mapa en los lotes
    centro = obtener_centroide_lotes(lotes_data)
    m = folium.Map(location=centro, zoom_start=12)
    
    # Agregar capas base
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Google Satellite'
    ).add_to(m)
    
    # Agregar cada lote al mapa
    for lote in lotes_data:
        if lote.get('geometria'):
            # Calcular color según fertilidad (si existe)
            fert = lote.get('fertilidad_puntaje', 50)  # Default 50 si no hay análisis
            if fert >= 80:
                color = 'green'
                fill_color = 'green'
            elif fert >= 60:
                color = 'lightgreen'
                fill_color = 'lightgreen'
            elif fert >= 40:
                color = 'orange'
                fill_color = 'orange'
            else:
                color = 'red'
                fill_color = 'red'
            
            # Crear popup informativo
            popup_html = f"""
            <b>{lote['nombre']}</b><br>
            Cultivo: {lote['cultivo']}<br>
            Área: {lote['area']:.2f} ha<br>
            Fertilidad: {fert}/100
            """
            
            # Agregar polígono al mapa
            folium.GeoJson(
                lote['geometria'].__geo_interface__,
                style_function=lambda x, color=color, fill_color=fill_color: {
                    'fillColor': fill_color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(m)
            
            # Agregar marcador en el centroide
            centroide = lote['geometria'].centroid
            folium.Marker(
                [centroide.y, centroide.x],
                popup=lote['nombre'],
                tooltip=f"Lote: {lote['nombre']}",
                icon=folium.Icon(color=color, icon='leaf', prefix='fa')
            ).add_to(m)
    
    return m

# Función para generar PDF profesional
def generar_reporte_pdf(lotes, analisis_completo, map_image=None):
    """Generar reporte PDF profesional con todos los análisis"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )
    
    story.append(Paragraph("REPORTE AGROECOLÓGICO - SISTEMA DE CULTIVOS TROPICALES", title_style))
    story.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Resumen ejecutivo
    story.append(Paragraph("RESUMEN EJECUTIVO", styles['Heading2']))
    total_fertilidad = sum(analisis['fertilidad']['puntaje_total'] for analisis in analisis_completo) / len(analisis_completo)
    total_area = sum(lote['area'] for lote in lotes)
    story.append(Paragraph(f"Fertilidad promedio del sistema: {total_fertilidad:.1f}/100", styles['Normal']))
    story.append(Paragraph(f"Área total analizada: {total_area:.2f} hectáreas", styles['Normal']))
    story.append(Paragraph(f"Número de lotes: {len(lotes)}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Análisis por lote
    for i, (lote, analisis) in enumerate(zip(lotes, analisis_completo)):
        story.append(Paragraph(f"LOTE: {lote['nombre']}", styles['Heading3']))
        
        # Tabla de datos del lote
        lote_data = [
            ['Parámetro', 'Valor'],
            ['Cultivo', lote['cultivo']],
            ['Área (ha)', f"{lote['area']:.2f}"],
            ['N (ppm)', f"{lote['nivel_n']}"],
            ['P (ppm)', f"{lote['nivel_p']}"],
            ['K (ppm)', f"{lote['nivel_k']}"],
            ['pH', f"{lote['ph']}"],
            ['M.O. %', f"{lote['materia_organica']}"]
        ]
        
        lote_table = Table(lote_data, colWidths=[2*inch, 2*inch])
        lote_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(lote_table)
        story.append(Spacer(1, 10))
        
        # Análisis de fertilidad
        fert = analisis['fertilidad']
        story.append(Paragraph("ANÁLISIS DE FERTILIDAD", styles['Heading4']))
        fert_data = [
            ['Indicador', 'Puntaje', 'Categoría'],
            ['Fertilidad Total', f"{fert['puntaje_total']}/100", fert['categoria']],
            ['pH', f"{fert['puntaje_ph']}/100", categorizar_fertilidad(fert['puntaje_ph'])],
            ['Materia Orgánica', f"{fert['puntaje_mo']}/100", categorizar_fertilidad(fert['puntaje_mo'])],
            ['Balance NPK', f"{fert['puntaje_npk']}/100", categorizar_fertilidad(fert['puntaje_npk'])]
        ]
        
        fert_table = Table(fert_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        fert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(fert_table)
        story.append(Spacer(1, 10))
        
        # Recomendaciones
        rec = analisis['recomendaciones']
        story.append(Paragraph("RECOMENDACIONES AGROECOLÓGICAS", styles['Heading4']))
        
        # Fertilizantes químicos (minimizados)
        story.append(Paragraph("Fertilizantes Químicos (uso minimizado):", styles['Normal']))
        quim_data = [
            ['Nutriente', 'Cantidad (kg)'],
            ['Nitrógeno (N)', f"{rec['quimicos']['N']}"],
            ['Fósforo (P)', f"{rec['quimicos']['P']}"],
            ['Potasio (K)', f"{rec['quimicos']['K']}"]
        ]
        quim_table = Table(quim_data)
        story.append(quim_table)
        story.append(Paragraph(f"Reducción del uso de químicos: {rec['reduccion_quimicos']}%", styles['Normal']))
        story.append(Spacer(1, 5))
        
        # Enmiendas orgánicas
        story.append(Paragraph("Enmiendas Orgánicas Recomendadas:", styles['Normal']))
        for enmienda in rec['organicos']:
            story.append(Paragraph(f"• {enmienda}", styles['Normal']))
        
        story.append(Spacer(1, 5))
        
        # Prácticas agroecológicas
        story.append(Paragraph("Prácticas Agroecológicas:", styles['Normal']))
        for practica in rec['practicas_agroecologicas']:
            story.append(Paragraph(f"• {practica}", styles['Normal']))
        
        story.append(Spacer(1, 20))
    
    # Principios agroecológicos aplicados
    story.append(Paragraph("PRINCIPIOS AGROECOLÓGICOS APLICADOS", styles['Heading2']))
    principios = [
        "✓ Diversificación productiva",
        "✓ Manejo sostenible del suelo",
        "✓ Minimización de insumos externos",
        "✓ Fortalecimiento de la biodiversidad",
        "✓ Optimización de recursos locales"
    ]
    for principio in principios:
        story.append(Paragraph(principio, styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# Interfaz principal
st.header("📊 Análisis Integral por Lotes")

if lotes_data:
    st.success(f"✅ {len(lotes_data)} lote(s) cargado(s) para análisis")
    
    # Mostrar resumen de lotes
    col1, col2, col3 = st.columns(3)
    with col1:
        total_area = sum(lote['area'] for lote in lotes_data)
        st.metric("Área Total", f"{total_area:.2f} ha")
    with col2:
        cultivos_unicos = len(set(lote['cultivo'] for lote in lotes_data))
        st.metric("Cultivos Diferentes", cultivos_unicos)
    with col3:
        st.metric("Lotes Cargados", len(lotes_data))
    
    # Ejecutar análisis
    if st.button("🌱 Ejecutar Análisis Agroecológico Completo"):
        with st.spinner("Realizando análisis integral..."):
            resultados = []
            
            for i, lote in enumerate(lotes_data):
                # Análisis de fertilidad real
                analisis_fertilidad = analizar_fertilidad_real(lote)
                
                # Recomendaciones agroecológicas
                recomendaciones = calcular_recomendaciones_agroecologicas(lote, analisis_fertilidad)
                
                # Guardar puntaje de fertilidad para el mapa
                lote['fertilidad_puntaje'] = analisis_fertilidad['puntaje_total']
                
                resultados.append({
                    'lote': lote,
                    'fertilidad': analisis_fertilidad,
                    'recomendaciones': recomendaciones
                })
            
            st.session_state.resultados = resultados
            st.success("✅ Análisis completado exitosamente")

# Mostrar resultados y mapa
if 'resultados' in st.session_state and lotes_data:
    resultados = st.session_state.resultados
    
    # Mapa interactivo
    st.subheader("🗺️ Mapa de Lotes")
    mapa = crear_mapa_con_lotes(lotes_data)
    st_folium(mapa, width=800, height=500)
    
    # Resumen general
    st.subheader("📈 Resumen del Análisis")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_fert = sum(r['fertilidad']['puntaje_total'] for r in resultados) / len(resultados)
        st.metric("Fertilidad Promedio", f"{avg_fert:.1f}/100")
    with col2:
        avg_reduction = sum(r['recomendaciones']['reduccion_quimicos'] for r in resultados) / len(resultados)
        st.metric("Reducción Químicos", f"{avg_reduction:.1f}%")
    with col3:
        total_n = sum(r['recomendaciones']['quimicos']['N'] for r in resultados)
        st.metric("N Total Recomendado", f"{total_n:.1f} kg")
    with col4:
        total_area = sum(r['lote']['area'] for r in resultados)
        st.metric("Área Total", f"{total_area:.2f} ha")
    
    # Análisis detallado por lote
    for i, resultado in enumerate(resultados):
        with st.expander(f"📋 {resultado['lote']['nombre']} - {resultado['lote']['cultivo']} - {resultado['fertilidad']['categoria']}", expanded=True):
            col_analisis, col_recomendaciones = st.columns(2)
            
            with col_analisis:
                st.subheader("📊 Análisis de Fertilidad")
                
                # Gráfico de fertilidad
                fig, ax = plt.subplots(figsize=(8, 4))
                categorias = ['Fertilidad Total', 'pH', 'M.O.', 'NPK']
                valores = [
                    resultado['fertilidad']['puntaje_total'],
                    resultado['fertilidad']['puntaje_ph'],
                    resultado['fertilidad']['puntaje_mo'],
                    resultado['fertilidad']['puntaje_npk']
                ]
                
                colors = ['#2ecc71', '#e74c3c', '#f39c12', '#3498db']
                bars = ax.bar(categorias, valores, color=colors)
                ax.set_ylim(0, 100)
                ax.set_ylabel('Puntaje (0-100)')
                ax.set_title('Análisis Integral de Fertilidad')
                
                for bar, valor in zip(bars, valores):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                           f'{valor:.1f}', ha='center', va='bottom')
                
                st.pyplot(fig)
                
            with col_recomendaciones:
                st.subheader("💡 Recomendaciones Agroecológicas")
                
                st.info(f"**Fertilizantes Químicos (reducidos {resultado['recomendaciones']['reduccion_quimicos']}%):**")
                st.write(f"- N: {resultado['recomendaciones']['quimicos']['N']} kg")
                st.write(f"- P: {resultado['recomendaciones']['quimicos']['P']} kg")
                st.write(f"- K: {resultado['recomendaciones']['quimicos']['K']} kg")
                
                st.success("**Enmiendas Orgánicas:**")
                for enmienda in resultado['recomendaciones']['organicos']:
                    st.write(f"- {enmienda}")
                
                st.warning("**Prácticas Agroecológicas:**")
                for practica in resultado['recomendaciones']['practicas_agroecologicas']:
                    st.write(f"- {practica}")

    # Generación de reporte PDF
    st.markdown("---")
    st.subheader("📄 Generar Reporte Final")
    
    if st.button("🖨️ Generar Reporte PDF Completo"):
        with st.spinner("Generando reporte profesional..."):
            pdf_buffer = generar_reporte_pdf(
                [r['lote'] for r in resultados],
                resultados
            )
            
            # Botón de descarga
            st.download_button(
                label="📥 Descargar Reporte PDF",
                data=pdf_buffer,
                file_name=f"reporte_agroecologico_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )
            st.success("✅ Reporte generado exitosamente")

else:
    st.info("👆 Cargue archivos KML/Shapefile o configure lotes manualmente en el sidebar")

# Información técnica
with st.expander("🔧 Instrucciones de Uso"):
    st.write("""
    **Formatos de archivo soportados:**
    
    - **KML/KMZ:** Archivos de Google Earth
    - **Shapefile:** Archivo ZIP que contenga (.shp, .shx, .dbf, .prj)
    
    **Requisitos para Shapefile:**
    - El archivo ZIP debe contener al menos el .shp, .shx y .dbf
    - Sistema de coordenadas preferible: WGS84 (EPSG:4326)
    - Los polígonos representan lotes o parcelas
    
    **Funcionalidades:**
    - Análisis de fertilidad real por lote
    - Recomendaciones de NPK bajo principios agroecológicos
    - Mapas interactivos con visualización de lotes
    - Reportes PDF profesionales
    - Minimización de insumos químicos
    """)

# Footer
st.markdown("---")
st.markdown(
    "🌍 **Sistema Agroecológico para Cultivos Tropicales** • "
    "Soporte para KML y Shapefile • "
    "Desarrollado para agricultura sostenible"
)
