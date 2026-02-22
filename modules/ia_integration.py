# modules/ia_integration.py
import requests
import os
import streamlit as st
import pandas as pd
import numpy as np
import json

# ===== FUNCIÓN PRINCIPAL UNIFICADA =====
def llamar_ia(prompt, proveedor="deepseek", temperatura=0.7, max_tokens=3000, modelo=None):
    """
    Función unificada que llama al proveedor de IA seleccionado.
    
    Args:
        prompt (str): El prompt a enviar
        proveedor (str): "deepseek", "qwen", "openai", "ollama", "claude"
        temperatura (float): Control de creatividad (0-1)
        max_tokens (int): Máximo de tokens en la respuesta
        modelo (str): Modelo específico (opcional)
    
    Returns:
        str: Texto generado o mensaje de error
    """
    
    if proveedor == "deepseek":
        return llamar_deepseek(prompt, temperatura, max_tokens, modelo)
    elif proveedor == "qwen":
        return llamar_qwen(prompt, temperatura, max_tokens, modelo)
    elif proveedor == "openai":
        return llamar_openai(prompt, temperatura, max_tokens, modelo)
    elif proveedor == "ollama":
        return llamar_ollama(prompt, modelo, temperatura)
    elif proveedor == "claude":
        return llamar_claude(prompt, temperatura, max_tokens, modelo)
    else:
        return f"❌ Proveedor '{proveedor}' no soportado."

# ===== IMPLEMENTACIONES POR PROVEEDOR =====

def llamar_deepseek(prompt, temperatura=0.7, max_tokens=3000, modelo="deepseek-chat"):
    """Llama a la API de DeepSeek"""
    api_key = st.secrets.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY"))
    if not api_key:
        return "⚠️ No disponible: falta API Key de DeepSeek. Configúrala en Secrets."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": modelo,
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
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'status_code') and e.response.status_code == 402:
            return "❌ Error 402: Créditos insuficientes en DeepSeek. Por favor, recarga en https://platform.deepseek.com"
        return f"❌ Error al consultar DeepSeek: {str(e)}"

def llamar_qwen(prompt, temperatura=0.7, max_tokens=3000, modelo="qwen-max"):
    """
    Llama a la API de Qwen (Alibaba Cloud).
    
    Modelos disponibles:
    - qwen-max: Máxima capacidad (recomendado)
    - qwen-plus: Balance rendimiento/costo
    - qwen-turbo: Más rápido y económico
    """
    api_key = st.secrets.get("QWEN_API_KEY", os.getenv("QWEN_API_KEY"))
    if not api_key:
        return "⚠️ No disponible: falta API Key de Qwen. Configúrala en Secrets."

    # Qwen usa el formato compatible con OpenAI
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": "Eres un asesor agronómico experto con amplia experiencia en agricultura de precisión."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperatura,
        "max_tokens": max_tokens
    }

    try:
        # Endpoint de DashScope (plataforma de Alibaba Cloud para Qwen)
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        
        # El formato de respuesta puede variar, ajusta según documentación
        if 'output' in data and 'choices' in data['output']:
            return data['output']['choices'][0]['message']['content']
        elif 'choices' in data:
            return data['choices'][0]['message']['content']
        else:
            return f"❌ Respuesta inesperada de Qwen: {json.dumps(data)[:200]}"
            
    except requests.exceptions.RequestException as e:
        return f"❌ Error al consultar Qwen: {str(e)}"

def llamar_openai(prompt, temperatura=0.7, max_tokens=3000, modelo="gpt-4"):
    """Llama a la API de OpenAI"""
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    if not api_key:
        return "⚠️ No disponible: falta API Key de OpenAI."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres un asesor agronómico experto con amplia experiencia en agricultura de precisión."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperatura,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error al consultar OpenAI: {str(e)}"

def llamar_ollama(prompt, modelo="llama3", temperatura=0.7):
    """Llama a un modelo local vía Ollama"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": modelo,
                "prompt": f"Eres un asesor agronómico experto. {prompt}",
                "stream": False,
                "options": {"temperature": temperatura}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        return "❌ Error: Ollama no está corriendo en localhost:11434. Asegúrate de tenerlo instalado y ejecutándose."
    except Exception as e:
        return f"❌ Error al consultar Ollama: {str(e)}"

def llamar_claude(prompt, temperatura=0.7, max_tokens=3000, modelo="claude-3-sonnet-20240229"):
    """Llama a la API de Claude (Anthropic)"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY"))
    if not api_key:
        return "⚠️ No disponible: falta API Key de Anthropic."

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            temperature=temperatura,
            system="Eres un asesor agronómico experto con amplia experiencia en agricultura de precisión.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"❌ Error al consultar Claude: {str(e)}"

# ===== FUNCIONES DE PREPARACIÓN DE DATOS (se mantienen igual) =====

def preparar_resumen_zonas(gdf_completo, cultivo):
    """
    Prepara un resumen de las zonas más relevantes para el prompt.
    """
    # Seleccionar columnas clave
    cols = ['id_zona', 'area_ha', 'fert_npk_actual', 'fert_ndvi', 'fert_ndre',
            'fert_materia_organica', 'fert_humedad_suelo', 'rec_N', 'rec_P', 'rec_K',
            'textura_suelo', 'arena', 'limo', 'arcilla',
            'proy_rendimiento_sin_fert', 'proy_rendimiento_con_fert', 'proy_incremento_esperado']

    # Solo las primeras 15 zonas para no exceder tokens
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

# ===== FUNCIONES DE ANÁLISIS (con prompts mejorados) =====

def generar_analisis_fertilidad(df_resumen, stats, cultivo, proveedor="deepseek"):
    """
    Genera un análisis textual de la fertilidad actual usando IA.
    """
    # Detectar textura predominante para recomendaciones específicas
    textura = stats['textura_predominante']
    recomendaciones_textura = ""
    if "arcill" in textura.lower():
        recomendaciones_textura = "Suelos arcillosos: requieren manejo cuidadoso del drenaje y aplicación fraccionada de nutrientes."
    elif "aren" in textura.lower():
        recomendaciones_textura = "Suelos arenosos: alta lixiviación, fertilizar en dosis más frecuentes y considerar materia orgánica."

    prompt = f"""
    Eres un asesor agronómico senior con 20 años de experiencia en agricultura de precisión. 
    Redacta un análisis PROFESIONAL y DETALLADO de fertilidad para un lote de {cultivo}.

    **Contexto:** Este lote se ha dividido en {len(df_resumen)} zonas de manejo con datos satelitales y de suelo.

    **Resumen global del lote:**
    - Área total: {stats['area_total']:.2f} ha
    - Índice NPK promedio: {stats['npk_promedio']:.3f} (escala 0-1, donde 1 es óptimo)
    - NDVI promedio: {stats['ndvi_promedio']:.3f} (vigor vegetativo)
    - Materia orgánica promedio: {stats['mo_promedio']:.2f}%
    - Humedad del suelo promedio: {stats['humedad_promedio']:.3f}
    - Textura predominante: {textura}
    {recomendaciones_textura}

    **Datos detallados por zona (primeras 10 zonas):**
    {df_resumen.head(10).to_string(index=False)}

    **Instrucciones específicas:**
    1. **Interpretación general:** Explica qué significan estos valores para el cultivo de {cultivo}. ¿El lote es homogéneo o heterogéneo? ¿Qué zonas destacan?
    
    2. **Análisis por parámetros:**
       - **Índice NPK:** Identifica las 3 zonas con mayor y menor fertilidad. ¿Por qué? (relación con materia orgánica, NDVI)
       - **NDVI:** ¿Qué indica sobre la biomasa y estado sanitario?
       - **Materia orgánica:** Impacto en estructura del suelo y disponibilidad de nutrientes.
       - **Humedad:** ¿Hay riesgo de estrés hídrico o encharcamiento?
    
    3. **Recomendaciones concretas:**
       - Para zonas con NPK < 0.5: ¿qué dosis de fertilizante (kg/ha) y qué tipo (orgánico/sintético)?
       - Para zonas con MO < 2.5%: ¿qué enmiendas aplicar y en qué momento?
       - Para zonas con humedad > 0.4: ¿qué prácticas de manejo recomiendas?

    **Formato esperado:** 
    - Usa párrafos profesionales, pero incluye viñetas para listas.
    - Menciona siempre los valores numéricos (ej. "la zona 7 tiene NPK 0.44, lo que indica...").
    - Termina con un párrafo de conclusión sobre la fertilidad general del lote.
    """
    
    return llamar_ia(prompt, proveedor=proveedor, temperatura=0.7, max_tokens=3500)

def generar_analisis_riesgo_hidrico(df_resumen, stats, cultivo, proveedor="deepseek"):
    """
    Análisis de riesgo de encharcamiento basado en humedad y textura.
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
    
    2. **Explica la relación textura-humedad:** ¿por qué zonas con similar textura tienen diferente humedad? (topografía, compactación, posición en el lote)
    
    3. **Propone medidas específicas:**
       - Para zonas de alto riesgo: drenaje superficial, surcos en contorno, cultivos de cobertura con raíces profundas.
       - Para zonas de riesgo moderado: monitoreo con sensores, evitar laboreo en exceso.
       - Para zonas arenosas con humedad alta: posible capa freática elevada o posición topográfica baja.
    
    4. **Incluye un párrafo sobre el impacto en el cultivo:** cómo afecta el exceso de agua al rendimiento de {cultivo} y qué síntomas observar.

    **Ejemplo de estilo (como el informe La Pampa):**
    "La zona 24 presenta la humedad más alta (0.433) y una textura franca con 18.6% de arcilla, lo que sugiere una posible acumulación de agua en microdepresiones. Las zonas 23, 15 y 29 combinan alta humedad (>0.40) con contenidos de arcilla superiores al 20%, incrementando el riesgo de saturación y mal drenaje."
    """
    
    return llamar_ia(prompt, proveedor=proveedor, temperatura=0.7, max_tokens=3000)

def generar_recomendaciones_integradas(df_resumen, stats, cultivo, proveedor="deepseek"):
    """
    Recomendaciones finales que combinan fertilidad y riesgo hídrico.
    """
    # Filtrar zonas críticas
    zonas_baja_fertilidad = df_resumen[df_resumen['fert_npk_actual'] < 0.5]
    zonas_alta_humedad = df_resumen[df_resumen['fert_humedad_suelo'] > 0.38]
    
    baja_fert_str = zonas_baja_fertilidad[['id_zona', 'fert_npk_actual', 'fert_materia_organica']].to_string(index=False) if not zonas_baja_fertilidad.empty else "No hay zonas con NPK < 0.5"
    alta_hum_str = zonas_alta_humedad[['id_zona', 'fert_humedad_suelo', 'textura_suelo']].to_string(index=False) if not zonas_alta_humedad.empty else "No hay zonas con humedad > 0.38"

    prompt = f"""
    Basado en TODOS los datos disponibles, genera un plan de manejo integrado para el lote de {cultivo}.

    **Resumen ejecutivo:**
    - Área total: {stats['area_total']:.2f} ha
    - Fertilidad promedio (NPK): {stats['npk_promedio']:.3f}
    - Humedad promedio: {stats['humedad_promedio']:.3f}
    - Incremento potencial con fertilización: {stats['incremento_promedio']:.1f}%
    - Inversión total estimada: ${stats['costo_total']:,.2f} USD

    **Zonas críticas:**
    
    **A) Baja fertilidad (NPK < 0.5):**
    {baja_fert_str}
    
    **B) Alta humedad (>0.38):**
    {alta_hum_str}

    **Instrucciones: genera un plan en 5 secciones:**

    1. **PRIORIDADES DE INTERVENCIÓN** (tabla conceptual con: zona, problema principal, urgencia, acción prioritaria)
    
    2. **MANEJO DIFERENCIADO POR GRUPOS:**
       - **Grupo Fertilidad:** dosis específicas de N-P-K (kg/ha), tipo de fertilizante, momento de aplicación.
       - **Grupo Drenaje:** obras recomendadas (zanjas, camellones), cultivos de cobertura específicos, ajustes en labranza.
       - **Grupo Mixto** (si existe): combinación de ambas estrategias.
    
    3. **PRÁCTICAS AGROECOLÓGICAS SUGERIDAS:**
       - Rotaciones recomendadas para {cultivo}
       - Abonos verdes / cultivos de cobertura
       - Control biológico si aplica
    
    4. **VALIDACIÓN EN CAMPO:**
       - Puntos georreferenciados a muestrear
       - Parámetros a analizar en laboratorio
       - Época recomendada para muestreo
    
    5. **CRONOGRAMA SUGERIDO (próximos 6 meses):**
       Actividades mes a mes (ej. Mes 1: muestreo, Mes 2: aplicación de enmiendas...)

    **Estilo:** profesional, concreto, con datos específicos. Usa viñetas y tablas conceptuales cuando sea útil.
    """
    
    return llamar_ia(prompt, proveedor=proveedor, temperatura=0.7, max_tokens=4000)
