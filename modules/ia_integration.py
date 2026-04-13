# modules/ia_integration.py - Versión corregida con reintentos, modelo flash y reducción de datos
import os
import time
import pandas as pd
from typing import Dict, Tuple
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import streamlit as st

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def _get_available_model():
    """Obtiene el modelo Gemini disponible, priorizando gemini-1.5-flash por su mayor cuota."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no está configurada")
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # Intentar usar gemini-1.5-flash (más económico y con mayor límite)
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Probar con una llamada dummy para verificar disponibilidad
            test_response = model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
            if test_response.text:
                print("✅ Usando modelo gemini-1.5-flash")
                return model
        except Exception:
            pass
        
        # Fallback: listar modelos disponibles
        models = genai.list_models()
        valid_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        if not valid_models:
            raise RuntimeError("No hay modelos Gemini que soporten generateContent.")
        chosen_model = valid_models[0].name
        print(f"⚠️ Usando modelo alternativo: {chosen_model}")
        return genai.GenerativeModel(chosen_model)
    except Exception as e:
        st.error(f"Error al inicializar Gemini: {str(e)}")
        raise

def llamar_gemini(prompt: str, system_prompt: str = None, temperature: float = 0.3, max_retries: int = 3) -> str:
    """
    Llama a Gemini con reintentos automáticos en caso de ResourceExhausted.
    Devuelve el texto de la respuesta o un mensaje de error fallback.
    """
    if not GEMINI_API_KEY:
        return "⚠️ No se pudo generar el análisis porque falta la API Key de Gemini."

    model = _get_available_model()
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    for intento in range(max_retries):
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=2048,          # Respuesta más corta para evitar saturación
                    top_p=0.95,
                ),
                request_options={'timeout': 30}      # Timeout de 30 segundos
            )
            return response.text
        except ResourceExhausted as e:
            if intento < max_retries - 1:
                wait = 2 ** intento  # 1, 2, 4 segundos
                print(f"⚠️ Cuota agotada, reintentando en {wait} segundos (intento {intento+1}/{max_retries})...")
                time.sleep(wait)
            else:
                return (f"⚠️ El análisis con IA no pudo completarse por límites de cuota de Gemini (ResourceExhausted). "
                        f"Por favor, intente más tarde o use el reporte estándar. Detalle: {e}")
        except Exception as e:
            # Otros errores (token demasiado largo, red, etc.)
            return f"⚠️ Error inesperado con la IA: {str(e)}"
    return "⚠️ No se pudo generar el análisis después de varios reintentos."

# ========== Funciones con reducción de datos ==========

def preparar_resumen_zonas(gdf_completo, cultivo: str, max_zonas: int = 5) -> Tuple[pd.DataFrame, Dict]:
    """
    Prepara un resumen conciso para la IA:
    - Estadísticas globales (media, min, max)
    - Solo las zonas más representativas (baja y alta fertilidad) hasta `max_zonas`
    """
    cols = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre',
            'fert_materia_organica', 'fert_humedad_suelo', 'rec_N', 'rec_P', 'rec_K',
            'costo_costo_total', 'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert',
            'proy_incremento_esperado', 'textura_suelo', 'arena', 'limo', 'arcilla']
    df = gdf_completo[cols].copy()
    df.columns = ['Zona', 'Area_ha', 'NPK', 'NDVI', 'NDRE', 'MO_%', 'Humedad',
                  'N_rec', 'P_rec', 'K_rec', 'Costo_total', 'Rend_sin_fert',
                  'Rend_con_fert', 'Inc_%', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']
    
    # Estadísticas globales
    stats = {
        'total_area': df['Area_ha'].sum(),
        'num_zonas': len(df),
        'npk_prom': df['NPK'].mean(),
        'npk_min': df['NPK'].min(),
        'npk_max': df['NPK'].max(),
        'mo_prom': df['MO_%'].mean(),
        'mo_min': df['MO_%'].min(),
        'mo_max': df['MO_%'].max(),
        'humedad_prom': df['Humedad'].mean(),
        'humedad_min': df['Humedad'].min(),
        'humedad_max': df['Humedad'].max(),
        'ndvi_prom': df['NDVI'].mean(),
        'ndvi_min': df['NDVI'].min(),
        'ndvi_max': df['NDVI'].max(),
        'ndre_prom': df['NDRE'].mean(),
        'ndre_min': df['NDRE'].min(),
        'ndre_max': df['NDRE'].max(),
        'rend_sin_prom': df['Rend_sin_fert'].mean(),
        'rend_con_prom': df['Rend_con_fert'].mean(),
        'inc_prom': df['Inc_%'].mean(),
        'costo_total': df['Costo_total'].sum(),
        'textura_dominante': df['Textura'].mode()[0] if not df['Textura'].empty else 'No determinada'
    }
    
    # Seleccionar zonas representativas: las de menor y mayor NPK (hasta max_zonas/2 cada una)
    df_sorted = df.sort_values('NPK')
    n_low = max(1, max_zonas // 2)
    n_high = max_zonas - n_low
    zonas_bajas = df_sorted.head(n_low)
    zonas_altas = df_sorted.tail(n_high)
    df_muestra = pd.concat([zonas_bajas, zonas_altas]).drop_duplicates()
    # Limitar a max_zonas (por si hay duplicados)
    df_muestra = df_muestra.head(max_zonas)
    
    return df_muestra, stats

def generar_analisis_fertilidad(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis técnico de fertilidad (NPK, MO, textura) con resumen reducido."""
    system = f"Eres un ingeniero agrónomo con especialización en edafología y nutrición vegetal, experto en {cultivo}. Redacta un análisis técnico detallado basado en los datos."
    prompt = f"""
    Se ha realizado un análisis de fertilidad en un lote de {cultivo} dividido en {stats['num_zonas']} zonas de manejo.
    **Datos generales:**
    - Área total: {stats['total_area']:.2f} ha
    - Índice NPK (compuesto) promedio: {stats['npk_prom']:.3f} (rango {stats['npk_min']:.3f} - {stats['npk_max']:.3f})
    - Materia orgánica (MO): promedio {stats['mo_prom']:.2f}% (mínimo {stats['mo_min']:.2f}%, máximo {stats['mo_max']:.2f}%)
    - Humedad del suelo: promedio {stats['humedad_prom']:.2f} (rango {stats['humedad_min']:.2f} - {stats['humedad_max']:.2f})
    - Textura dominante: {stats['textura_dominante']}

    **Zonas representativas (baja y alta fertilidad):**
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Humedad', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']].to_string(index=False)}

    **Instrucciones para el análisis:**
    1. **Interpretación del índice NPK**: Explica qué significa el valor (0-1) en términos de disponibilidad de nutrientes. Relación con el cultivo.
    2. **Materia orgánica**: Analiza su nivel (bajo/medio/alto) y su impacto en la fertilidad física, química y biológica.
    3. **Textura del suelo**: Describe ventajas y limitantes para {cultivo}.
    4. **Humedad**: Relación con la textura y disponibilidad hídrica.
    5. **Recomendaciones generales**: Propón prácticas de manejo (enmiendas, corrección de pH si es necesario).
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_ndvi_ndre(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis detallado de índices de vegetación (estado del cultivo)."""
    system = f"Eres un especialista en teledetección aplicada a la agricultura y fisiología vegetal, experto en {cultivo}."
    prompt = f"""
    Se han obtenido imágenes satelitales para el lote de {cultivo}.
    **Resumen estadístico:**
    - NDVI: promedio {stats['ndvi_prom']:.3f}, mínimo {stats['ndvi_min']:.3f}, máximo {stats['ndvi_max']:.3f}
    - NDRE: promedio {stats['ndre_prom']:.3f}, mínimo {stats['ndre_min']:.3f}, máximo {stats['ndre_max']:.3f}

    **Zonas representativas:**
    {df_resumen[['Zona', 'NDVI', 'NDRE']].to_string(index=False)}

    **Instrucciones:**
    1. Interpretación del NDVI (biomasa, estrés).
    2. Interpretación del NDRE (clorofila, nitrógeno). Comparación con NDVI.
    3. Correlación con fertilidad (NPK, MO).
    4. Estado general del cultivo y heterogeneidad del lote.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis de riesgo hídrico (encharcamiento/sequía)."""
    system = f"Eres un hidrólogo de suelos especializado en drenaje y riego para {cultivo}."
    prompt = f"""
    Basado en humedad y textura:
    - Humedad promedio: {stats['humedad_prom']:.2f}, rango {stats['humedad_min']:.2f} - {stats['humedad_max']:.2f}
    - Textura dominante: {stats['textura_dominante']}
    **Zonas representativas:**
    {df_resumen[['Zona', 'Humedad', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']].to_string(index=False)}

    **Instrucciones:**
    1. Identificar zonas con riesgo de encharcamiento (humedad >0.35 y alto contenido de arcilla).
    2. Zonas con riesgo de sequía (baja humedad y textura arenosa).
    3. Recomendaciones de drenaje o riego.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_costos(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis económico con priorización de inversión."""
    system = f"Eres un asesor en gestión agrícola y economía, especializado en optimización de insumos para {cultivo}."
    prompt = f"""
    Datos económicos:
    - Costo total de fertilización: ${stats['costo_total']:,.2f} USD
    - Rendimiento promedio sin fertilización: {stats['rend_sin_prom']:.0f} kg/ha
    - Rendimiento promedio con fertilización: {stats['rend_con_prom']:.0f} kg/ha
    - Incremento promedio esperado: {stats['inc_prom']:.1f}%

    **Zonas representativas:**
    {df_resumen[['Zona', 'Costo_total', 'Rend_sin_fert', 'Rend_con_fert', 'Inc_%', 'N_rec', 'P_rec', 'K_rec']].to_string(index=False)}

    **Instrucciones:**
    1. Calcular relación beneficio/costo para cada zona representativa.
    2. Priorizar inversión (zonas de mayor retorno).
    3. Recomendar dosis óptima y ajustes.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Recomendaciones finales de manejo integrado."""
    system = f"Eres un asesor técnico senior en agricultura de precisión, experto en {cultivo}."
    prompt = f"""
    Con los datos disponibles para el lote de {cultivo}, genera un plan de manejo integrado:

    1. **Estrategia de fertilización** (dosis por zona, momento, tipo de fertilizante).
    2. **Manejo de agua** (drenaje/riego según riesgos).
    3. **Prácticas complementarias**: coberturas, labranza, enmiendas.
    4. **Priorización de zonas para intervención**.
    5. **Conclusión técnica** sobre el potencial productivo y limitantes principales.

    Datos clave:
    - NPK prom: {stats['npk_prom']:.2f}
    - MO prom: {stats['mo_prom']:.1f}%
    - Textura dominante: {stats['textura_dominante']}
    - NDVI prom: {stats['ndvi_prom']:.2f}
    - Incremento rendimiento prom: {stats['inc_prom']:.1f}%
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)
