# modules/ia_integration.py - Versión definitiva con manejo robusto de cuota
import os
import time
import pandas as pd
from typing import Dict, Tuple, Optional
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, PermissionDenied, InvalidArgument
import streamlit as st

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def _get_available_model():
    """Obtiene el modelo Gemini disponible, priorizando gemini-1.5-flash."""
    if not GEMINI_API_KEY:
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # Intentar usar gemini-1.5-flash
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Probar con una llamada dummy para verificar disponibilidad
        test_response = model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        if test_response.text is not None:
            return model
    except Exception:
        pass
    
    # Fallback: listar modelos disponibles
    try:
        models = genai.list_models()
        valid_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        if valid_models:
            return genai.GenerativeModel(valid_models[0].name)
    except Exception:
        pass
    return None

def llamar_gemini(prompt: str, system_prompt: str = None, temperature: float = 0.3, max_retries: int = 2) -> Optional[str]:
    """
    Llama a Gemini con reintentos. Retorna None si falla permanentemente.
    """
    if not GEMINI_API_KEY:
        return None
    
    model = _get_available_model()
    if model is None:
        return None
    
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    
    for intento in range(max_retries):
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=1024,  # Reducido aún más
                    top_p=0.95,
                ),
                request_options={'timeout': 30}
            )
            return response.text
        except (ResourceExhausted, PermissionDenied) as e:
            if intento < max_retries - 1:
                wait = 2 ** intento
                time.sleep(wait)
            else:
                # No lanzamos excepción, retornamos None
                return None
        except Exception:
            return None
    return None

# ========== Funciones de análisis (todas retornan string, con fallback) ==========

def preparar_resumen_zonas(gdf_completo, cultivo: str, max_zonas: int = 3) -> Tuple[pd.DataFrame, Dict]:
    """Prepara resumen con máximo 3 zonas representativas para reducir tokens."""
    cols = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre',
            'fert_materia_organica', 'fert_humedad_suelo', 'rec_N', 'rec_P', 'rec_K',
            'costo_costo_total', 'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert',
            'proy_incremento_esperado', 'textura_suelo', 'arena', 'limo', 'arcilla']
    df = gdf_completo[cols].copy()
    df.columns = ['Zona', 'Area_ha', 'NPK', 'NDVI', 'NDRE', 'MO_%', 'Humedad',
                  'N_rec', 'P_rec', 'K_rec', 'Costo_total', 'Rend_sin_fert',
                  'Rend_con_fert', 'Inc_%', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']
    
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
    
    # Seleccionar zonas representativas (baja, media, alta fertilidad)
    df_sorted = df.sort_values('NPK')
    n = max_zonas
    indices = [0, len(df)//2, -1] if len(df) >= 3 else list(range(len(df)))
    df_muestra = df_sorted.iloc[indices].head(n)
    return df_muestra, stats

def generar_analisis_fertilidad(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Retorna análisis o mensaje de error si IA no disponible."""
    system = f"Eres un ingeniero agrónomo experto en {cultivo}. Redacta un análisis técnico de fertilidad."
    prompt = f"""
    Lote de {cultivo} - {stats['num_zonas']} zonas.
    NPK prom: {stats['npk_prom']:.2f} (min {stats['npk_min']:.2f}, max {stats['npk_max']:.2f})
    MO prom: {stats['mo_prom']:.1f}% (min {stats['mo_min']:.1f}%, max {stats['mo_max']:.1f}%)
    Textura dominante: {stats['textura_dominante']}
    Zonas representativas:
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Textura']].to_string(index=False)}
    """
    resultado = llamar_gemini(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ El análisis de fertilidad por IA no está disponible en este momento (cuota agotada). Por favor, use el reporte estándar."
    return resultado

def generar_analisis_ndvi_ndre(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres especialista en teledetección para {cultivo}."
    prompt = f"""
    NDVI prom: {stats['ndvi_prom']:.2f} (min {stats['ndvi_min']:.2f}, max {stats['ndvi_max']:.2f})
    NDRE prom: {stats['ndre_prom']:.2f} (min {stats['ndre_min']:.2f}, max {stats['ndre_max']:.2f})
    Zonas: {df_resumen[['Zona', 'NDVI', 'NDRE']].to_string(index=False)}
    """
    resultado = llamar_gemini(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis NDVI/NDRE no disponible por límite de cuota."
    return resultado

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres hidrólogo de suelos para {cultivo}."
    prompt = f"""
    Humedad prom: {stats['humedad_prom']:.2f}, rango {stats['humedad_min']:.2f}-{stats['humedad_max']:.2f}
    Textura dominante: {stats['textura_dominante']}
    Zonas: {df_resumen[['Zona', 'Humedad', 'Textura']].to_string(index=False)}
    """
    resultado = llamar_gemini(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de riesgo hídrico no disponible."
    return resultado

def generar_analisis_costos(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres asesor económico agrícola."
    prompt = f"""
    Costo total: ${stats['costo_total']:,.2f}
    Rendimiento sin fert: {stats['rend_sin_prom']:.0f} kg/ha, con fert: {stats['rend_con_prom']:.0f} kg/ha
    Incremento: {stats['inc_prom']:.1f}%
    Zonas: {df_resumen[['Zona', 'Costo_total', 'Inc_%']].to_string(index=False)}
    """
    resultado = llamar_gemini(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de costos no disponible."
    return resultado

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres asesor técnico senior en agricultura de precisión."
    prompt = f"""
    NPK prom: {stats['npk_prom']:.2f}, MO prom: {stats['mo_prom']:.1f}%, NDVI prom: {stats['ndvi_prom']:.2f}
    Incremento rendimiento: {stats['inc_prom']:.1f}%
    Textura: {stats['textura_dominante']}
    Genera un plan de manejo integrado (fertilización, agua, prácticas).
    """
    resultado = llamar_gemini(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Recomendaciones integradas no disponibles por límite de cuota."
    return resultado
