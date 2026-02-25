import os
import json
import pandas as pd
from typing import Dict, Any, Optional
import requests

# Configuración
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # deepseek-chat o deepseek-coder

def llamar_deepseek(prompt: str, system_prompt: str = None, temperature: float = 0.3) -> str:
    """
    Llama a DeepSeek API usando el endpoint oficial.
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY no está configurada en las variables de entorno")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error en llamada a DeepSeek: {str(e)}")
        raise

# ========== Funciones específicas para el análisis agronómico ==========

def preparar_resumen_zonas(gdf_completo, cultivo: str) -> tuple:
    """
    Prepara un DataFrame resumen y estadísticas para alimentar a la IA.
    Similar a la versión original pero simplificada.
    """
    # Seleccionar columnas de interés
    cols = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre',
            'fert_materia_organica', 'fert_humedad_suelo', 'rec_N', 'rec_P', 'rec_K',
            'costo_costo_total', 'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert',
            'proy_incremento_esperado', 'textura_suelo', 'arena', 'limo', 'arcilla']
    df = gdf_completo[cols].copy()
    df.columns = ['Zona', 'Area_ha', 'NPK', 'NDVI', 'NDRE', 'MO_%', 'Humedad',
                  'N_rec', 'P_rec', 'K_rec', 'Costo_total', 'Rend_sin_fert',
                  'Rend_con_fert', 'Inc_%', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']
    # Estadísticas generales
    stats = {
        'total_area': df['Area_ha'].sum(),
        'num_zonas': len(df),
        'npk_prom': df['NPK'].mean(),
        'npk_min': df['NPK'].min(),
        'npk_max': df['NPK'].max(),
        'mo_prom': df['MO_%'].mean(),
        'humedad_prom': df['Humedad'].mean(),
        'rend_sin_prom': df['Rend_sin_fert'].mean(),
        'rend_con_prom': df['Rend_con_fert'].mean(),
        'inc_prom': df['Inc_%'].mean(),
        'costo_total': df['Costo_total'].sum(),
    }
    return df, stats

def generar_analisis_fertilidad(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Genera análisis interpretativo de fertilidad usando DeepSeek"""
    system = f"Eres un ingeniero agrónomo experto en {cultivo}. Analiza los datos de fertilidad por zonas y proporciona un diagnóstico claro y recomendaciones prácticas."
    prompt = f"""
    Se ha realizado un análisis de fertilidad en un lote de {cultivo} dividido en {stats['num_zonas']} zonas.
    Datos generales:
    - Área total: {stats['total_area']:.2f} ha
    - Índice NPK promedio: {stats['npk_prom']:.3f} (rango {stats['npk_min']:.3f} - {stats['npk_max']:.3f})
    - Materia orgánica promedio: {stats['mo_prom']:.2f}%
    - Humedad del suelo promedio: {stats['humedad_prom']:.2f}

    A continuación los datos por zona (primeras 10 filas):
    {df_resumen.head(10).to_string()}

    Por favor, genera un análisis que incluya:
    1. Identificación de zonas críticas (baja fertilidad, problemas de humedad, etc.)
    2. Posibles causas de la variabilidad
    3. Recomendaciones de manejo específicas
    """
    return llamar_deepseek(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis de riesgo de encharcamiento / estrés hídrico"""
    system = f"Eres un especialista en hidrología de suelos y manejo de agua en cultivos de {cultivo}."
    prompt = f"""
    Basado en los siguientes datos de humedad del suelo y textura, analiza el riesgo de encharcamiento o estrés hídrico en el lote.
    Datos por zona (primeras 10):
    {df_resumen[['Zona', 'Humedad', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']].head(10).to_string()}

    Humedad promedio: {stats['humedad_prom']:.2f}
    Cultivo: {cultivo}

    Proporciona:
    - Zonas con mayor probabilidad de encharcamiento
    - Zonas con riesgo de sequía
    - Recomendaciones de drenaje o riego
    """
    return llamar_deepseek(prompt, system_prompt=system, temperature=0.3)

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Recomendaciones finales de manejo integrado"""
    system = f"Eres un asesor técnico en agricultura de precisión, especialista en {cultivo}."
    prompt = f"""
    Con todos los datos disponibles del lote de {cultivo}:
    - Fertilidad NPK (promedio {stats['npk_prom']:.2f})
    - Rendimiento potencial sin fertilización: {stats['rend_sin_prom']:.0f} kg/ha, con fertilización: {stats['rend_con_prom']:.0f} kg/ha (incremento {stats['inc_prom']:.1f}%)
    - Costo total de fertilización estimado: ${stats['costo_total']:,.2f} USD

    Datos detallados por zona:
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Humedad', 'N_rec', 'P_rec', 'K_rec', 'Rend_sin_fert', 'Rend_con_fert', 'Inc_%']].head(10).to_string()}

    Genera un plan de manejo integrado que incluya:
    - Estrategia de fertilización (dosis, momentos, productos)
    - Manejo de agua (drenaje/riego)
    - Otras prácticas agronómicas (cultivos de cobertura, labranza, etc.)
    - Priorización de zonas para intervención
    """
    return llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
