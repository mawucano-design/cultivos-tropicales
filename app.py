import streamlit as st
import cv2
import numpy as np
from PIL import Image
import torch
from ultralytics import YOLO
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sklearn.cluster import DBSCAN
from scipy import ndimage
import io
import base64
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Diagnóstico de Plagas en Cultivo de Banano",
    page_icon="🍌",
    layout="wide"
)

# Título principal
st.title("🍌 Diagnóstico de Plagas en Cultivo de Banano")
st.markdown("---")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Selección de modelo
    model_option = st.selectbox(
        "Seleccionar modelo",
        ["YOLOv8n", "YOLOv8s", "YOLOv8m"],
        index=0
    )
    
    # Umbral de confianza
    conf_threshold = st.slider(
        "Umbral de confianza",
        min_value=0.1,
        max_value=0.9,
        value=0.5,
        step=0.05
    )
    
    # Parámetros de segmentación
    st.subheader("Segmentación de Plantas")
    min_plant_size = st.slider(
        "Tamaño mínimo de planta (px)",
        min_value=500,
        max_value=5000,
        value=1500,
        step=500
    )
    
    max_distance = st.slider(
        "Distancia máxima entre hojas (px)",
        min_value=50,
        max_value=300,
        value=150,
        step=10
    )
    
    # Botón para análisis avanzado
    advanced_analysis = st.checkbox("Análisis avanzado por planta", value=True)
    
    st.markdown("---")
    st.info("""
    ### Clases detectadas:
    - 🍃 **Hoja sana**: Color verde intenso
    - ⚪ **Hoja blanca**: Deficiencias nutricionales
    - ✂️ **Hoja corta**: Posible estrés hídrico
    - 🌿 **Maleza**: Competencia por recursos
    - 🌱 **Tallo**: Base de la planta
    """)

# Inicialización del modelo
@st.cache_resource
def load_model(model_name="YOLOv8n"):
    """Carga el modelo YOLO preentrenado"""
    model_map = {
        "YOLOv8n": "yolov8n.pt",
        "YOLOv8s": "yolov8s.pt", 
        "YOLOv8m": "yolov8m.pt"
    }
    
    try:
        # En producción, usarías tu modelo entrenado
        # model = YOLO("models/best.pt")
        model = YOLO(model_map[model_name])
        return model
    except Exception as e:
        st.error(f"Error cargando modelo: {e}")
        return None

# Funciones de procesamiento de imágenes
def segmentar_plantas_individuales(detecciones, imagen_shape, max_distance=150):
    """
    Segmenta las detecciones en plantas individuales usando clustering
    basado en la proximidad espacial
    """
    if len(detecciones) == 0:
        return []
    
    # Extraer centros de las detecciones
    centros = []
    for det in detecciones:
        x1, y1, x2, y2 = det['bbox']
        centro_x = (x1 + x2) / 2
        centro_y = (y1 + y2) / 2
        centros.append([centro_x, centro_y])
    
    centros = np.array(centros)
    
    # Usar DBSCAN para clustering espacial
    clustering = DBSCAN(eps=max_distance, min_samples=2).fit(centros)
    labels = clustering.labels_
    
    # Agrupar detecciones por planta
    plantas = {}
    for i, (det, label) in enumerate(zip(detecciones, labels)):
        if label not in plantas:
            plantas[label] = {
                'detections': [],
                'bbox_global': [float('inf'), float('inf'), 0, 0]  # x1, y1, x2, y2
            }
        
        plantas[label]['detections'].append(det)
        
        # Actualizar bbox global de la planta
        x1, y1, x2, y2 = det['bbox']
        bbox_global = plantas[label]['bbox_global']
        bbox_global[0] = min(bbox_global[0], x1)
        bbox_global[1] = min(bbox_global[1], y1)
        bbox_global[2] = max(bbox_global[2], x2)
        bbox_global[3] = max(bbox_global[3], y2)
    
    # Filtrar plantas muy pequeñas y convertir a lista
    plantas_filtradas = []
    for label, planta_data in plantas.items():
        if label == -1:  # Puntos no asignados (ruido)
            continue
            
        bbox = planta_data['bbox_global']
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        
        if area >= 1000:  # Área mínima
            plantas_filtradas.append({
                'id': label,
                'detections': planta_data['detections'],
                'bbox': bbox,
                'area': area,
                'center': [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
            })
    
    return plantas_filtradas

def analizar_planta(detecciones_planta):
    """Analiza una planta individual y calcula métricas"""
    conteos = {
        'hoja_sana': 0,
        'hoja_blanca': 0,
        'hoja_corta': 0,
        'tallo': 0,
        'maleza': 0
    }
    
    for det in detecciones_planta:
        clase = det['class']
        if clase in conteos:
            conteos[clase] += 1
    
    total_hojas = conteos['hoja_sana'] + conteos['hoja_blanca'] + conteos['hoja_corta']
    
    # Calcular índices de salud
    if total_hojas > 0:
        indice_salud = (conteos['hoja_sana'] / total_hojas) * 100
        indice_deficiencia = (conteos['hoja_blanca'] / total_hojas) * 100
    else:
        indice_salud = 0
        indice_deficiencia = 0
    
    # Determinar estado general
    if indice_salud >= 80:
        estado = "Excelente"
        color_estado = "🟢"
    elif indice_salud >= 60:
        estado = "Bueno"
        color_estado = "🟡"
    elif indice_salud >= 40:
        estado = "Regular"
        color_estado = "🟠"
    else:
        estado = "Crítico"
        color_estado = "🔴"
    
    # Calcular densidad foliar aproximada
    densidad_foliar = total_hojas / len(detecciones_planta) if len(detecciones_planta) > 0 else 0
    
    return {
        'conteos': conteos,
        'total_hojas': total_hojas,
        'indice_salud': indice_salud,
        'indice_deficiencia': indice_deficiencia,
        'estado': estado,
        'color_estado': color_estado,
        'densidad_foliar': densidad_foliar,
        'presencia_maleza': conteos['maleza'] > 0,
        'tallo_detectado': conteos['tallo'] > 0
    }

def procesar_imagen_completa(model, imagen, conf_threshold=0.5):
    """Procesa la imagen completa con el modelo YOLO"""
    resultados = model(imagen, conf=conf_threshold)
    
    detecciones = []
    for result in resultados:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                
                # Mapear clases según tu dataset
                clases = ['hoja_sana', 'hoja_blanca', 'hoja_corta', 'maleza', 'tallo']
                if cls < len(clases):
                    clase_nombre = clases[cls]
                    
                    detecciones.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'confidence': float(conf),
                        'class': clase_nombre,
                        'class_id': cls
                    })
    
    return detecciones, resultados

def visualizar_analisis_por_planta(imagen, plantas, detecciones_totales):
    """Crea una visualización con colores por planta"""
    # Convertir a numpy array si es PIL Image
    if isinstance(imagen, Image.Image):
        img_np = np.array(imagen)
        if len(img_np.shape) == 3 and img_np.shape[2] == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
    else:
        img_np = imagen.copy()
    
    # Paleta de colores para plantas
    colores = [
        (255, 0, 0),    # Rojo
        (0, 255, 0),    # Verde
        (0, 0, 255),    # Azul
        (255, 255, 0),  # Amarillo
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cian
        (128, 0, 0),    # Rojo oscuro
        (0, 128, 0),    # Verde oscuro
        (0, 0, 128),    # Azul oscuro
        (128, 128, 0)   # Oliva
    ]
    
    # Dibujar bounding boxes por planta
    for i, planta in enumerate(plantas):
        color = colores[i % len(colores)]
        
        # Dibujar bbox de la planta
        x1, y1, x2, y2 = map(int, planta['bbox'])
        cv2.rectangle(img_np, (x1, y1), (x2, y2), color, 3)
        
        # Etiqueta de la planta
        label = f"Planta {i+1}"
        cv2.putText(img_np, label, (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Dibujar centro de la planta
        centro_x, centro_y = map(int, planta['center'])
        cv2.circle(img_np, (centro_x, centro_y), 8, color, -1)
    
    # Dibujar detecciones individuales
    for det in detecciones_totales:
        x1, y1, x2, y2 = map(int, det['bbox'])
        
        # Color por clase
        colores_clase = {
            'hoja_sana': (0, 255, 0),
            'hoja_blanca': (255, 255, 255),
            'hoja_corta': (0, 165, 255),
            'maleza': (0, 0, 255),
            'tallo': (139, 69, 19)
        }
        
        color = colores_clase.get(det['class'], (255, 255, 255))
        cv2.rectangle(img_np, (x1, y1), (x2, y2), color, 2)
        
        # Etiqueta de clase
        label = f"{det['class']}: {det['confidence']:.2f}"
        cv2.putText(img_np, label, (x1, y1-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    return img_np

def generar_reporte_planta(planta_id, analisis):
    """Genera un reporte detallado por planta"""
    reporte = f"""
    ## 📊 Planta #{planta_id + 1}
    
    ### 📈 Métricas:
    - **Índice de Salud:** {analisis['indice_salud']:.1f}%
    - **Estado:** {analisis['estado']} {analisis['color_estado']}
    - **Deficiencias:** {analisis['indice_deficiencia']:.1f}%
    
    ### 🍃 Conteo de Hojas:
    - Hojas sanas: {analisis['conteos']['hoja_sana']}
    - Hojas blancas: {analisis['conteos']['hoja_blanca']}
    - Hojas cortas: {analisis['conteos']['hoja_corta']}
    - Total de hojas: {analisis['total_hojas']}
    
    ### 🌱 Información Adicional:
    - Tallo detectado: {'✅ Sí' if analisis['tallo_detectado'] else '❌ No'}
    - Maleza cercana: {'⚠️ Sí' if analisis['presencia_maleza'] else '✅ No'}
    - Densidad foliar: {analisis['densidad_foliar']:.2f}
    
    ---
    """
    return reporte

def crear_graficos_analisis(plantas_analizadas):
    """Crea gráficos de análisis de las plantas"""
    
    # Preparar datos para gráficos
    ids_plantas = [f"Planta {i+1}" for i in range(len(plantas_analizadas))]
    indices_salud = [p['indice_salud'] for p in plantas_analizadas]
    conteos_sanas = [p['conteos']['hoja_sana'] for p in plantas_analizadas]
    conteos_blancas = [p['conteos']['hoja_blanca'] for p in plantas_analizadas]
    conteos_cortas = [p['conteos']['hoja_corta'] for p in plantas_analizadas]
    estados = [p['estado'] for p in plantas_analizadas]
    
    # Gráfico 1: Índice de salud por planta
    fig_salud = go.Figure(data=[
        go.Bar(
            x=ids_plantas,
            y=indices_salud,
            marker_color=['green' if s >= 60 else 'orange' if s >= 40 else 'red' 
                         for s in indices_salud],
            text=[f"{s:.1f}%" for s in indices_salud],
            textposition='auto',
        )
    ])
    
    fig_salud.update_layout(
        title="Índice de Salud por Planta",
        xaxis_title="Plantas",
        yaxis_title="Índice de Salud (%)",
        yaxis_range=[0, 100]
    )
    
    # Gráfico 2: Distribución de tipos de hojas
    fig_distribucion = go.Figure(data=[
        go.Bar(name='Hojas Sanas', x=ids_plantas, y=conteos_sanas, marker_color='green'),
        go.Bar(name='Hojas Blancas', x=ids_plantas, y=conteos_blancas, marker_color='white'),
        go.Bar(name='Hojas Cortas', x=ids_plantas, y=conteos_cortas, marker_color='orange')
    ])
    
    fig_distribucion.update_layout(
        title="Distribución de Tipos de Hojas por Planta",
        xaxis_title="Plantas",
        yaxis_title="Cantidad de Hojas",
        barmode='stack'
    )
    
    # Gráfico 3: Mapa de calor de estados
    estados_map = {'Excelente': 4, 'Bueno': 3, 'Regular': 2, 'Crítico': 1}
    valores_estado = [estados_map[e] for e in estados]
    
    fig_estado = go.Figure(data=go.Heatmap(
        z=[valores_estado],
        x=ids_plantas,
        y=['Estado'],
        colorscale=[[0, 'red'], [0.5, 'orange'], [0.75, 'yellow'], [1, 'green']],
        showscale=False
    ))
    
    fig_estado.update_layout(
        title="Mapa de Estado de las Plantas",
        xaxis_title="Plantas",
        height=200
    )
    
    return fig_salud, fig_distribucion, fig_estado

# Interfaz principal de la aplicación
def main():
    # Cargar modelo
    model = load_model(model_option)
    
    # Subida de imágenes
    uploaded_file = st.file_uploader(
        "📤 Sube una imagen del cultivo de banano",
        type=['jpg', 'jpeg', 'png', 'bmp'],
        help="Sube una imagen que muestre varias plantas de banano"
    )
    
    if uploaded_file is not None:
        # Leer y mostrar imagen
        imagen = Image.open(uploaded_file)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌄 Imagen Original")
            st.image(imagen, caption="Imagen del cultivo", use_container_width=True)
        
        # Procesar imagen
        with st.spinner("🔍 Analizando imagen..."):
            # Procesar con YOLO
            detecciones, resultados = procesar_imagen_completa(
                model, imagen, conf_threshold
            )
            
            if advanced_analysis and len(detecciones) > 0:
                # Segmentar en plantas individuales
                plantas = segmentar_plantas_individuales(
                    detecciones, 
                    imagen.size,
                    max_distance
                )
                
                # Analizar cada planta
                plantas_analizadas = []
                for i, planta in enumerate(plantas):
                    analisis = analizar_planta(planta['detections'])
                    analisis['id'] = i
                    analisis['bbox'] = planta['bbox']
                    analisis['area'] = planta['area']
                    plantas_analizadas.append(analisis)
                
                # Visualizar resultados
                img_procesada = visualizar_analisis_por_planta(
                    imagen, plantas, detecciones
                )
                
                with col2:
                    st.subheader("🎯 Análisis por Planta")
                    st.image(img_procesada, caption="Plantas identificadas", use_container_width=True)
                
                # Mostrar métricas generales
                st.markdown("---")
                st.subheader("📊 Métricas Generales del Cultivo")
                
                col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4)
                
                with col_metrics1:
                    st.metric(
                        "Total de Plantas",
                        len(plantas),
                        delta=f"{len(plantas)} identificadas"
                    )
                
                with col_metrics2:
                    avg_health = np.mean([p['indice_salud'] for p in plantas_analizadas])
                    st.metric(
                        "Salud Promedio",
                        f"{avg_health:.1f}%",
                        delta="Buena" if avg_health >= 70 else "Regular" if avg_health >= 50 else "Baja"
                    )
                
                with col_metrics3:
                    total_maleza = sum(1 for p in plantas_analizadas if p['presencia_maleza'])
                    st.metric(
                        "Plantas con Maleza",
                        total_maleza,
                        delta=f"{total_maleza/len(plantas)*100:.1f}%"
                    )
                
                with col_metrics4:
                    plantas_criticas = sum(1 for p in plantas_analizadas if p['estado'] == "Crítico")
                    st.metric(
                        "Plantas Críticas",
                        plantas_criticas,
                        delta=f"⚠️ {plantas_criticas} requieren atención"
                    )
                
                # Reportes detallados por planta
                st.markdown("---")
                st.subheader("📋 Reportes Individuales por Planta")
                
                # Crear pestañas para cada planta
                tabs = st.tabs([f"Planta {i+1}" for i in range(len(plantas_analizadas))])
                
                for idx, tab in enumerate(tabs):
                    with tab:
                        analisis = plantas_analizadas[idx]
                        reporte = generar_reporte_planta(idx, analisis)
                        st.markdown(reporte)
                        
                        # Mostrar área específica de la planta
                        x1, y1, x2, y2 = map(int, analisis['bbox'])
                        planta_img = np.array(imagen)[y1:y2, x1:x2]
                        if len(planta_img) > 0:
                            st.image(planta_img, caption=f"Vista detallada Planta {idx+1}", width=300)
                
                # Gráficos de análisis
                st.markdown("---")
                st.subheader("📈 Análisis Visual")
                
                fig_salud, fig_distribucion, fig_estado = crear_graficos_analisis(plantas_analizadas)
                
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    st.plotly_chart(fig_salud, use_container_width=True)
                
                with col_chart2:
                    st.plotly_chart(fig_distribucion, use_container_width=True)
                
                st.plotly_chart(fig_estado, use_container_width=True)
                
                # Exportar resultados
                st.markdown("---")
                st.subheader("📤 Exportar Resultados")
                
                # Crear DataFrame para exportación
                datos_exportar = []
                for i, analisis in enumerate(plantas_analizadas):
                    datos_exportar.append({
                        'Planta': i+1,
                        'Indice_Salud': analisis['indice_salud'],
                        'Estado': analisis['estado'],
                        'Hojas_Sanas': analisis['conteos']['hoja_sana'],
                        'Hojas_Blancas': analisis['conteos']['hoja_blanca'],
                        'Hojas_Cortas': analisis['conteos']['hoja_corta'],
                        'Total_Hojas': analisis['total_hojas'],
                        'Maleza_Cercana': 'Sí' if analisis['presencia_maleza'] else 'No',
                        'Area_px': analisis['area'],
                        'Densidad_Foliar': analisis['densidad_foliar']
                    })
                
                df_resultados = pd.DataFrame(datos_exportar)
                
                col_export1, col_export2, col_export3 = st.columns(3)
                
                with col_export1:
                    # Exportar a CSV
                    csv = df_resultados.to_csv(index=False)
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"analisis_banano_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                with col_export2:
                    # Exportar a Excel
                    excel_buffer = io.BytesIO()
                    df_resultados.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    st.download_button(
                        label="📊 Descargar Excel",
                        data=excel_buffer,
                        file_name=f"analisis_banano_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                with col_export3:
                    # Exportar imagen procesada
                    img_buffer = io.BytesIO()
                    img_pil = Image.fromarray(img_procesada)
                    img_pil.save(img_buffer, format="PNG")
                    img_buffer.seek(0)
                    st.download_button(
                        label="🖼️ Descargar Imagen",
                        data=img_buffer,
                        file_name=f"analisis_banano_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                        mime="image/png"
                    )
                
                # Mostrar tabla resumen
                st.markdown("### 📋 Tabla Resumen de Resultados")
                st.dataframe(df_resultados, use_container_width=True)
                
            else:
                # Análisis básico (sin segmentación por planta)
                with col2:
                    st.subheader("🔍 Detecciones Generales")
                    img_array = np.array(imagen)
                    
                    # Dibujar detecciones
                    for det in detecciones:
                        x1, y1, x2, y2 = map(int, det['bbox'])
                        
                        colores_clase = {
                            'hoja_sana': (0, 255, 0),
                            'hoja_blanca': (255, 255, 255),
                            'hoja_corta': (0, 165, 255),
                            'maleza': (0, 0, 255),
                            'tallo': (139, 69, 19)
                        }
                        
                        color = colores_clase.get(det['class'], (255, 255, 255))
                        cv2.rectangle(img_array, (x1, y1), (x2, y2), color, 2)
                        
                        label = f"{det['class']}: {det['confidence']:.2f}"
                        cv2.putText(img_array, label, (x1, y1-5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    
                    st.image(img_array, caption="Detecciones generales", use_container_width=True)
                
                # Mostrar estadísticas generales
                st.markdown("---")
                st.subheader("📊 Estadísticas Generales")
                
                conteos_generales = {}
                for det in detecciones:
                    clase = det['class']
                    conteos_generales[clase] = conteos_generales.get(clase, 0) + 1
                
                col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
                
                with col_stat1:
                    st.metric("Hojas Sanas", conteos_generales.get('hoja_sana', 0))
                
                with col_stat2:
                    st.metric("Hojas Blancas", conteos_generales.get('hoja_blanca', 0))
                
                with col_stat3:
                    st.metric("Hojas Cortas", conteos_generales.get('hoja_corta', 0))
                
                with col_stat4:
                    st.metric("Maleza", conteos_generales.get('maleza', 0))
                
                with col_stat5:
                    st.metric("Tallos", conteos_generales.get('tallo', 0))
        
        # Recomendaciones basadas en análisis
        st.markdown("---")
        st.subheader("💡 Recomendaciones")
        
        if advanced_analysis and len(detecciones) > 0:
            # Recomendaciones basadas en análisis por planta
            plantas_criticas = [p for p in plantas_analizadas if p['estado'] == "Crítico"]
            
            if len(plantas_criticas) > 0:
                st.warning(f"⚠️ **Atención requerida:** {len(plantas_criticas)} plantas se encuentran en estado crítico.")
                st.info("""
                **Acciones recomendadas:**
                1. Realizar aplicación de fertilizantes foliares
                2. Aumentar frecuencia de riego
                3. Aplicar fungicidas preventivos
                4. Eliminar maleza manualmente
                5. Monitorear diariamente estas plantas
                """)
            
            plantas_con_maleza = [p for p in plantas_analizadas if p['presencia_maleza']]
            if len(plantas_con_maleza) > 0:
                st.warning(f"🌿 **Control de maleza:** {len(plantas_con_maleza)} plantas tienen maleza cercana.")
                st.info("""
                **Recomendaciones para control de maleza:**
                1. Realizar deshierbe manual alrededor de las plantas
                2. Aplicar herbicidas selectivos
                3. Implementar cobertura vegetal (mulch)
                4. Mantener limpieza regular del cultivo
                """)
            
            # Recomendaciones generales
            avg_health = np.mean([p['indice_salud'] for p in plantas_analizadas])
            if avg_health < 60:
                st.info("""
                **Mejora general del cultivo:**
                - Realizar análisis de suelo
                - Ajustar programa de fertilización
                - Implementar riego por goteo
                - Considerar sombreado temporal
                """)
        
        else:
            # Recomendaciones generales
            st.info("""
            **Recomendaciones generales para el cultivo de banano:**
            
            1. **Control de plagas:** Monitorear regularmente signos de plagas
            2. **Fertilización:** Aplicar fertilizantes balanceados cada 3 meses
            3. **Riego:** Mantener humedad constante sin encharcamientos
            4. **Poda:** Eliminar hojas enfermas y mantener 8-10 hojas por planta
            5. **Sombra:** Proporcionar sombra parcial en horas de mayor calor
            """)
    
    else:
        # Mensaje cuando no hay imagen cargada
        st.info("👈 **Sube una imagen** para comenzar el análisis")
        
        # Mostrar ejemplo
        col_ex1, col_ex2, col_ex3 = st.columns(3)
        
        with col_ex1:
            st.markdown("### 📸 Ejemplo 1")
            st.image("https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400", 
                    caption="Cultivo saludable")
        
        with col_ex2:
            st.markdown("### 🌿 Ejemplo 2")
            st.image("https://images.unsplash.com/photo-1608032912326-3f3b71614395?w=400", 
                    caption="Plantas con deficiencias")
        
        with col_ex3:
            st.markdown("### 🍌 Ejemplo 3")
            st.image("https://images.unsplash.com/photo-1629666451138-2c8e7e5e99b2?w-400", 
                    caption="Cultivo con maleza")

# Pie de página
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>🍌 <strong>Sistema de Diagnóstico de Cultivos de Banano</strong></p>
        <p>Desarrollado para monitoreo y análisis de salud vegetal | v2.0</p>
    </div>
    """,
    unsafe_allow_html=True
)

if __name__ == "__main__":
    main()
