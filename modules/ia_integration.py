# modules/ia_integration.py
import requests
import os
import streamlit as st
import pandas as pd
import numpy as np

def llamar_deepseek(prompt, temperatura=0.7, max_tokens=3000):
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
        "model": "deepseek-chat",  # o "deepseek-reasoner" para razonamiento más profundo
        "messages": [
            {"role": "system", "content": "Eres un asesor agronómico senior con 20 años de experiencia en agricultura de precisión. Tus informes son detallados, profesionales y se basan estrictamente en los datos proporcionados."},
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
    Genera un análisis textual detallado de la fertilidad actual usando IA.
    """
    prompt = f"""
    Eres un asesor agronómico senior con 20 años de experiencia en agricultura de precisión. 
    Redacta un análisis PROFESIONAL y DETALLADO de fertilidad para un lote de {cultivo}.

    **Contexto:** Este lote se ha dividido en {len(df_resumen)} zonas de manejo con datos satelitales y de suelo.

    **Resumen global:**
    - Área total: {stats['area_total']:.2f} ha
    - Índice NPK promedio: {stats['npk_promedio']:.3f} (escala 0-1, donde 1 es óptimo)
    - NDVI promedio: {stats['ndvi_promedio']:.3f} (vigor vegetativo)
    - Materia orgánica promedio: {stats['mo_promedio']:.2f}%
    - Humedad del suelo promedio: {stats['humedad_promedio']:.3f}
    - Textura predominante: {stats['textura_predominante']}

    **Datos detallados por zona (primeras 10 zonas):**
    {df_resumen.head(10).to_string(index=False)}

    **Instrucciones específicas:**
    1. **Interpretación general:** Explica qué significan estos valores para el cultivo de {cultivo}. ¿El lote es homogéneo o heterogéneo? ¿Qué zonas destacan?
    2. **Análisis por parámetros:**
       - **Índice NPK:** Identifica las 3 zonas con mayor y menor fertilidad. ¿Por qué?
       - **NDVI:** Relación con la biomasa y estado sanitario.
       - **Materia orgánica:** Impacto en la estructura del suelo y disponibilidad de nutrientes.
       - **Humedad:** ¿Hay riesgo de estrés hídrico o encharcamiento?
    3. **Recomendaciones concretas:**
       - Para zonas con NPK < 0.5: ¿qué dosis de fertilizante y qué tipo (orgánico/sintético)?
       - Para zonas con MO < 2.5%: ¿qué enmiendas aplicar y en qué momento?
       - Para zonas con humedad > 0.4: ¿qué cultivos de cobertura o prácticas de drenaje?

    **Formato esperado:** 
    - Usa párrafos profesionales, pero incluye viñetas para listas.
    - Menciona siempre los valores numéricos (ej. "la zona 7 tiene NPK 0.44, lo que indica...").
    - Termina con un párrafo de conclusión sobre la fertilidad general del lote.
    """
    return llamar_deepseek(prompt, temperatura=0.7, max_tokens=3000)

def generar_analisis_riesgo_hidrico(df_resumen, stats, cultivo):
    """
    Análisis detallado de riesgo de encharcamiento basado en humedad y textura.
    """
    prompt = f"""
    Como especialista en manejo de agua y suelos, analiza en detalle el riesgo de encharcamiento para {cultivo}.

    **Datos críticos (humedad y textura por zona):**
    {df_resumen[['id_zona', 'fert_humedad_suelo', 'textura_suelo', 'arena', 'limo', 'arcilla']].head(15).to_string(index=False)}

    **Criterios de análisis:**
    - Humedad > 0.38 = riesgo alto (encharcamiento probable)
    - Humedad 0.30-0.38 = riesgo moderado (monitorear)
    - Textura arcillosa (>25% arcilla) = drenaje lento
    - Textura arenosa (>60% arena) = drenaje rápido pero poca retención

    **Instrucciones:**
    1. **Identifica las zonas con mayor riesgo** (lista ordenada de mayor a menor humedad).
    2. **Explica la relación textura-humedad:** ¿por qué zonas con similar textura tienen diferente humedad? (topografía, compactación, etc.)
    3. **Propone medidas específicas:**
       - Para zonas de alto riesgo: drenaje superficial, surcos en contorno, cultivos de cobertura con raíces profundas.
       - Para zonas de riesgo moderado: monitoreo con sensores, evitar laboreo en exceso.
       - Para zonas arenosas con humedad alta: posible capa freática elevada o posición topográfica baja.
    4. **Incluye un párrafo sobre el impacto en el cultivo:** cómo afecta el exceso de agua al rendimiento de {cultivo} y qué síntomas observar.

    **Ejemplo de estilo (como el informe La Pampa):**
    "La zona 24 presenta la humedad más alta (0.433) y una textura franca con 18.6% de arcilla, lo que sugiere una posible acumulación de agua en microdepresiones. Las zonas 23, 15 y 29 combinan alta humedad (>0.40) con contenidos de arcilla superiores al 20%, incrementando el riesgo de saturación y mal drenaje."
    """
    return llamar_deepseek(prompt, temperatura=0.7, max_tokens=2800)

def generar_recomendaciones_integradas(df_resumen, stats, cultivo):
    """
    Recomendaciones finales que combinan fertilidad y riesgo hídrico de forma integrada.
    """
    prompt = f"""
    Basado en TODOS los datos, genera un plan de manejo integrado para el lote de {cultivo}.

    **Resumen ejecutivo:**
    - Área: {stats['area_total']:.2f} ha
    - Fertilidad (NPK): {stats['npk_promedio']:.3f}
    - Humedad: {stats['humedad_promedio']:.3f}
    - Incremento potencial con fertilización: {stats['incremento_promedio']:.1f}%
    - Inversión total estimada: ${stats['costo_total']:,.2f} USD

    **Zonas críticas:**
    - Baja fertilidad (NPK < 0.5): 
      {df_resumen[df_resumen['fert_npk_actual'] < 0.5][['id_zona', 'fert_npk_actual', 'fert_materia_organica']].to_string(index=False)}
    - Alta humedad (>0.38): 
      {df_resumen[df_resumen['fert_humedad_suelo'] > 0.38][['id_zona', 'fert_humedad_suelo', 'textura_suelo']].to_string(index=False)}

    **Instrucciones: genera un plan en 5 secciones:**

    1. **PRIORIDADES DE INTERVENCIÓN** (tabla conceptual con: zona, problema, urgencia, acción principal)
    2. **MANEJO DIFERENCIADO POR GRUPOS:**
       - Grupo A (baja fertilidad): dosis específicas, tipo de fertilizante, momento de aplicación.
       - Grupo B (alta humedad): obras de drenaje, cultivos de cobertura, ajustes en labranza.
       - Grupo C (mixto): combinación de ambas estrategias.
    3. **PRÁCTICAS AGROECOLÓGICAS:** rotaciones, abonos verdes, control biológico, etc.
    4. **VALIDACIÓN EN CAMPO:** qué puntos georreferenciados muestrear y qué analizar.
    5. **CRONOGRAMA SUGERIDO:** actividades mes a mes para los próximos 6 meses.

    **Estilo:** profesional, concreto, con datos específicos. Usa viñetas y tablas conceptuales cuando sea útil.
    """
    return llamar_deepseek(prompt, temperatura=0.7, max_tokens=3500)
