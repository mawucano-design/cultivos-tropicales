# modules/ia_integration.py
import requests
import json
import streamlit as st
import pandas as pd
import numpy as np

def llamar_deepseek(prompt, temperatura=0.7, max_tokens=2000):
    """
    Llama a la API de DeepSeek y devuelve el texto generado.
    """
    api_key = st.secrets.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY"))
    if not api_key:
        return "⚠️ No disponible: falta API Key de DeepSeek."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",  # o "deepseek-reasoner" si prefieres
        "messages": [
            {"role": "system", "content": "Eres un asesor agronómico experto con amplia experiencia en agricultura de precisión."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperatura,
        "max_tokens": max_tokens
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"❌ Error al consultar DeepSeek: {str(e)}"

def preparar_resumen_zonas(gdf_completo, cultivo):
    """
    Prepara un resumen de las zonas más relevantes para el prompt.
    """
    # Seleccionar columnas clave
    cols = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre',
            'fert_materia_organica', 'fert_humedad_suelo', 'rec_N', 'rec_P', 'rec_K',
            'textura_suelo', 'arena', 'limo', 'arcilla',
            'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert', 'proy_incremento_esperado']
    
    # Solo las primeras 15 zonas para no exceder tokens (puedes ajustar)
    df_resumen = gdf_completo[cols].head(15).copy()
    
    # Agregar estadísticas globales
    stats = {
        'area_total': gdf_completo['area_ha'].sum(),
        'npk_promedio': gdf_completo['fert_npk_actual'].mean(),
        'ndvi_promedio': gdf_completo['fert_ndvi'].mean(),
        'mo_promedio': gdf_completo['fert_materia_organica'].mean(),
        'humedad_promedio': gdf_completo['fert_humedad_suelo'].mean(),
        'incremento_promedio': gdf_completo['proy_incremento_esperado'].mean(),
        'costo_total': gdf_completo['costo_costo_total'].sum(),
        'textura_predominante': gdf_completo['textura_suelo'].mode()[0] if len(gdf_completo) > 0 else 'N/A'
    }
    
    return df_resumen, stats

def generar_analisis_fertilidad(df_resumen, stats, cultivo):
    """
    Genera un análisis textual de la fertilidad actual usando IA.
    """
    prompt = f"""
    Como asesor agronómico experto, analiza los siguientes datos de fertilidad para un cultivo de {cultivo}.

    **Resumen global del lote:**
    - Área total: {stats['area_total']:.2f} ha
    - Índice NPK promedio: {stats['npk_promedio']:.3f}
    - NDVI promedio: {stats['ndvi_promedio']:.3f}
    - Materia orgánica promedio: {stats['mo_promedio']:.2f}%
    - Humedad del suelo promedio: {stats['humedad_promedio']:.3f}
    - Textura predominante: {stats['textura_predominante']}

    **Datos por zona (solo las más representativas):**
    {df_resumen.to_string(index=False)}

    Por favor, redacta un análisis profesional que incluya:
    1. Interpretación del nivel general de fertilidad (índice NPK) y su relación con el cultivo.
    2. Identificación de las zonas con mejor y peor fertilidad, explicando por qué (basado en NDVI, materia orgánica, etc.).
    3. Recomendaciones específicas para mejorar la fertilidad en las zonas críticas.
    4. Relación entre la textura del suelo y la retención de nutrientes/humedad.

    Usa un tono técnico pero accesible para un productor. Evita listas genéricas; sé específico con los valores.
    """
    return llamar_deepseek(prompt, temperatura=0.7)

def generar_analisis_riesgo_hidrico(df_resumen, stats, cultivo):
    """
    Análisis de riesgo de encharcamiento basado en humedad y textura.
    """
    prompt = f"""
    Como asesor agronómico, analiza el riesgo de encharcamiento/exceso hídrico para el cultivo de {cultivo} en este lote.

    **Datos de humedad y textura por zona:**
    {df_resumen[['id_zona', 'fert_humedad_suelo', 'textura_suelo', 'arena', 'limo', 'arcilla']].to_string(index=False)}

    **Considera:**
    - La humedad óptima para {cultivo} es alrededor de {PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA']}.
    - Texturas con más arcilla retienen más agua y pueden encharcarse.
    - Las zonas con humedad > 0.38 se consideran de atención prioritaria (según el ejemplo de La Pampa).

    Redacta un análisis que:
    - Identifique las zonas con mayor probabilidad de encharcamiento.
    - Explique la relación entre textura y drenaje.
    - Proponga medidas de manejo (drenajes, cultivos de cobertura, etc.) para las zonas críticas.
    """
    return llamar_deepseek(prompt)

def generar_recomendaciones_integradas(df_resumen, stats, cultivo):
    """
    Recomendaciones finales que combinan fertilidad y riesgo hídrico.
    """
    prompt = f"""
    Basado en todos los datos disponibles para el cultivo de {cultivo}, genera un conjunto de recomendaciones agronómicas integradas.

    **Resumen global:**
    - Área: {stats['area_total']:.2f} ha
    - Fertilidad (NPK): {stats['npk_promedio']:.3f}
    - Humedad promedio: {stats['humedad_promedio']:.3f}
    - Incremento esperado con fertilización: {stats['incremento_promedio']:.1f}%
    - Costo total estimado: ${stats['costo_total']:.2f} USD

    **Datos de zonas críticas (bajo NPK o alta humedad):**
    {df_resumen[df_resumen['fert_npk_actual'] < 0.5].to_string(index=False)}
    {df_resumen[df_resumen['fert_humedad_suelo'] > 0.38].to_string(index=False)}

    Proporciona:
    1. **Prioridades de intervención:** ¿qué zonas requieren atención inmediata y por qué?
    2. **Manejo diferenciado:** recomendaciones específicas para grupos de zonas (ej. fertilización en zonas de baja fertilidad, drenaje en zonas húmedas).
    3. **Prácticas agroecológicas** sugeridas (cultivos de cobertura, rotaciones, etc.).
    4. **Validación en campo:** qué puntos verificar antes de implementar.

    El formato debe ser claro, con párrafos cortos y viñetas si es necesario.
    """
    return llamar_deepseek(prompt, max_tokens=2500)
