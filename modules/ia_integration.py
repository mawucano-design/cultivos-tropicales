# modules/ia_integration.py - Versión para DeepSeek API (compatible OpenAI)
import os
import time
import pandas as pd
from typing import Dict, Tuple, Optional
from openai import OpenAI
import streamlit as st

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Inicializar cliente DeepSeek (usa base_url oficial)
def _get_deepseek_client():
    if not DEEPSEEK_API_KEY:
        return None
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

def llamar_deepseek(prompt: str, system_prompt: str = None, temperature: float = 0.3, max_retries: int = 2) -> Optional[str]:
    """
    Llama a DeepSeek API con reintentos. Retorna None si falla permanentemente.
    """
    client = _get_deepseek_client()
    if client is None:
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for intento in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",  # modelo gratuito con 1M contexto
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
                timeout=30
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() or "quota" in str(e).lower():
                if intento < max_retries - 1:
                    wait = 2 ** intento
                    time.sleep(wait)
                else:
                    return None
            else:
                # Otros errores (red, autenticación, etc.)
                return None
    return None

# ========== Funciones de análisis (misma interfaz que antes) ==========

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
    system = f"Eres un ingeniero agrónomo con especialización en edafología y nutrición vegetal, experto en {cultivo}. Redacta un análisis técnico detallado basado en los datos."
    prompt = f"""
    Lote de {cultivo} - {stats['num_zonas']} zonas.
    NPK prom: {stats['npk_prom']:.2f} (min {stats['npk_min']:.2f}, max {stats['npk_max']:.2f})
    MO prom: {stats['mo_prom']:.1f}% (min {stats['mo_min']:.1f}%, max {stats['mo_max']:.1f}%)
    Textura dominante: {stats['textura_dominante']}
    Zonas representativas:
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Textura']].to_string(index=False)}
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ El análisis de fertilidad por IA no está disponible en este momento (error de API o cuota). Por favor, use el reporte estándar."
    return resultado

def generar_analisis_ndvi_ndre(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres un especialista en teledetección aplicada a la agricultura y fisiología vegetal, experto en {cultivo}."
    prompt = f"""
    NDVI prom: {stats['ndvi_prom']:.2f} (min {stats['ndvi_min']:.2f}, max {stats['ndvi_max']:.2f})
    NDRE prom: {stats['ndre_prom']:.2f} (min {stats['ndre_min']:.2f}, max {stats['ndre_max']:.2f})
    Zonas: {df_resumen[['Zona', 'NDVI', 'NDRE']].to_string(index=False)}
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis NDVI/NDRE no disponible por error de API."
    return resultado

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres un hidrólogo de suelos especializado en drenaje y riego para {cultivo}."
    prompt = f"""
    Humedad prom: {stats['humedad_prom']:.2f}, rango {stats['humedad_min']:.2f}-{stats['humedad_max']:.2f}
    Textura dominante: {stats['textura_dominante']}
    Zonas: {df_resumen[['Zona', 'Humedad', 'Textura']].to_string(index=False)}
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de riesgo hídrico no disponible."
    return resultado

def generar_analisis_costos(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres un asesor en gestión agrícola y economía, especializado en optimización de insumos para {cultivo}."
    prompt = f"""
    Costo total: ${stats['costo_total']:,.2f}
    Rendimiento sin fert: {stats['rend_sin_prom']:.0f} kg/ha, con fert: {stats['rend_con_prom']:.0f} kg/ha
    Incremento: {stats['inc_prom']:.1f}%
    Zonas: {df_resumen[['Zona', 'Costo_total', 'Inc_%']].to_string(index=False)}
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de costos no disponible."
    return resultado

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"Eres un asesor técnico senior en agricultura de precisión, experto en {cultivo}."
    prompt = f"""
    NPK prom: {stats['npk_prom']:.2f}, MO prom: {stats['mo_prom']:.1f}%, NDVI prom: {stats['ndvi_prom']:.2f}
    Incremento rendimiento: {stats['inc_prom']:.1f}%
    Textura: {stats['textura_dominante']}
    Genera un plan de manejo integrado (fertilización, agua, prácticas).
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Recomendaciones integradas no disponibles por error de API."
    return resultado
