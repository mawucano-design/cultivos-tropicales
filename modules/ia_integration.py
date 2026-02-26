# modules/ia_integration.py (Gemini con selección automática y prompts técnicos)
import os
import pandas as pd
from typing import Dict
import google.generativeai as genai
import streamlit as st

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def _get_available_model():
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        models = genai.list_models()
        valid_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        if not valid_models:
            raise RuntimeError("No hay modelos Gemini que soporten generateContent.")
        model_names = [m.name for m in valid_models]
        print(f"Modelos Gemini disponibles: {model_names}")
        chosen_model = valid_models[0].name
        print(f"Usando modelo: {chosen_model}")
        return genai.GenerativeModel(chosen_model)
    except Exception as e:
        st.error(f"Error al listar modelos Gemini: {str(e)}")
        raise

def llamar_gemini(prompt: str, system_prompt: str = None, temperature: float = 0.3) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno")
    model = _get_available_model()
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=4096  # Aumentado para respuestas más largas
            )
        )
        return response.text
    except Exception as e:
        print(f"Error en llamada a Gemini: {str(e)}")
        raise

# ========== Funciones específicas con prompts técnicos ==========

def preparar_resumen_zonas(gdf_completo, cultivo: str) -> tuple:
    """Prepara un DataFrame resumen y estadísticas para alimentar a la IA."""
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
    return df, stats

def generar_analisis_fertilidad(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis técnico de fertilidad (NPK, MO, pH implícito, textura)"""
    system = f"Eres un ingeniero agrónomo con especialización en edafología y nutrición vegetal, experto en {cultivo}. Redacta un análisis técnico detallado basado en los datos."
    prompt = f"""
    Se ha realizado un análisis de fertilidad en un lote de {cultivo} dividido en {stats['num_zonas']} zonas de manejo.
    **Datos generales:**
    - Área total: {stats['total_area']:.2f} ha
    - Índice NPK (compuesto) promedio: {stats['npk_prom']:.3f} (rango {stats['npk_min']:.3f} - {stats['npk_max']:.3f})
    - Materia orgánica (MO): promedio {stats['mo_prom']:.2f}% (mínimo {stats['mo_min']:.2f}%, máximo {stats['mo_max']:.2f}%)
    - Humedad del suelo: promedio {stats['humedad_prom']:.2f} (rango {stats['humedad_min']:.2f} - {stats['humedad_max']:.2f})
    - Textura dominante: {stats['textura_dominante']}

    **Datos por zona (primeras 10 filas):**
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Humedad', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']].head(10).to_string()}

    **Instrucciones para el análisis:**
    1. **Interpretación del índice NPK**: Explica qué significa el valor (0-1) en términos de disponibilidad de nutrientes. Relación con el cultivo.
    2. **Materia orgánica**: Analiza su nivel (bajo/medio/alto) y su impacto en la fertilidad física, química y biológica (capacidad de intercambio catiónico, estructura, retención de agua).
    3. **Textura del suelo**: Describe las ventajas y limitantes de la textura predominante (y las variaciones por zona) para el cultivo de {cultivo}. Menciona permeabilidad, capacidad de retención de agua, riesgo de compactación o erosión.
    4. **Humedad**: Relación con la textura y disponibilidad hídrica.
    5. **Recomendaciones generales**: Basado en los datos, propón prácticas de manejo para mejorar la fertilidad (enmiendas, corrección de pH si es necesario, etc.). Incluye la necesidad de medir pH si no se dispone del dato.
    Utiliza un vocabulario técnico preciso y evita generalidades.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_ndvi_ndre(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis detallado de índices de vegetación (estado del cultivo)"""
    system = f"Eres un especialista en teledetección aplicada a la agricultura y fisiología vegetal, experto en {cultivo}. Redacta un análisis técnico de los índices espectrales."
    prompt = f"""
    Se han obtenido imágenes satelitales que permiten calcular NDVI y NDRE para el lote de {cultivo}.
    **Resumen estadístico:**
    - NDVI: promedio {stats['ndvi_prom']:.3f}, mínimo {stats['ndvi_min']:.3f}, máximo {stats['ndvi_max']:.3f}
    - NDRE: promedio {stats['ndre_prom']:.3f}, mínimo {stats['ndre_min']:.3f}, máximo {stats['ndre_max']:.3f}

    **Datos por zona (primeras 10 filas):**
    {df_resumen[['Zona', 'NDVI', 'NDRE']].head(10).to_string()}

    **Instrucciones:**
    1. **Interpretación del NDVI**: Relaciona los valores con la biomasa verde, área foliar y estado sanitario. Identifica zonas con posible estrés (valores bajos) y zonas con vigor óptimo.
    2. **Interpretación del NDRE**: Explica su sensibilidad al contenido de clorofila y nitrógeno. Compara con NDVI para detectar deficiencias nutricionales incipientes o estrés en etapas tempranas.
    3. **Correlación con fertilidad**: Relaciona los valores de NDVI/NDRE con los datos de NPK y MO de las zonas. ¿Hay coherencia? ¿Zonas con bajo NDRE y buen NDVI podrían indicar deficiencia de N?
    4. **Estado general del cultivo**: Concluye sobre la heterogeneidad del lote y posibles causas (suelo, manejo, topografía).
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis de riesgo hídrico (encharcamiento/sequía) basado en textura y humedad"""
    system = f"Eres un hidrólogo de suelos especializado en drenaje y riego para {cultivo}."
    prompt = f"""
    Basado en la humedad del suelo y la textura, analiza el riesgo de encharcamiento o estrés hídrico.
    **Datos relevantes:**
    - Humedad promedio: {stats['humedad_prom']:.2f}, rango {stats['humedad_min']:.2f} - {stats['humedad_max']:.2f}
    - Textura dominante: {stats['textura_dominante']}
    - Datos por zona (primeras 10):
    {df_resumen[['Zona', 'Humedad', 'Textura', 'Arena_%', 'Limo_%', 'Arcilla_%']].head(10).to_string()}

    **Instrucciones:**
    1. **Zonas con alto riesgo de encharcamiento**: Identifica zonas con humedad > umbral crítico (ej. >0.35) y alto contenido de arcilla. Explica por qué.
    2. **Zonas con riesgo de sequía**: Zonas con baja humedad y textura arenosa, que drenan rápido.
    3. **Recomendaciones**: Propón prácticas de drenaje (superficial/subterráneo) para zonas encharcables, y estrategias de riego o cobertura para zonas secas.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_analisis_costos(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Análisis económico con priorización de inversión"""
    system = f"Eres un asesor en gestión agrícola y economía, especializado en optimización de insumos para {cultivo}."
    prompt = f"""
    Se ha estimado el costo de fertilización por zona y la proyección de rendimiento.
    **Datos económicos:**
    - Costo total de fertilización: ${stats['costo_total']:,.2f} USD
    - Rendimiento promedio sin fertilización: {stats['rend_sin_prom']:.0f} kg/ha
    - Rendimiento promedio con fertilización: {stats['rend_con_prom']:.0f} kg/ha
    - Incremento promedio esperado: {stats['inc_prom']:.1f}%

    **Detalle por zona (primeras 10):**
    {df_resumen[['Zona', 'Costo_total', 'Rend_sin_fert', 'Rend_con_fert', 'Inc_%', 'N_rec', 'P_rec', 'K_rec']].head(10).to_string()}

    **Instrucciones:**
    1. **Análisis de retorno por zona**: Calcula la relación beneficio/costo (ingreso adicional / costo fertilización) para cada zona. Identifica las 3 zonas con mayor y menor retorno.
    2. **Priorización de inversión**: ¿En qué zonas conviene aplicar la dosis completa? ¿Dónde se podría reducir?
    3. **Recomendación de dosis óptima**: Basado en el incremento porcentual y el costo, sugiere si es rentable fertilizar en todas las zonas o concentrar recursos en las de mayor respuesta.
    Usa un enfoque técnico-económico.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    """Recomendaciones finales de manejo integrado (síntesis)"""
    system = f"Eres un asesor técnico senior en agricultura de precisión, experto en {cultivo}. Integra todos los análisis previos en un plan de manejo coherente y técnico."
    prompt = f"""
    Con todos los datos disponibles (fertilidad, NDVI/NDRE, textura, humedad, costos) para el lote de {cultivo}, genera un plan de manejo integrado que incluya:

    1. **Estrategia de fertilización** (dosis por zona, momentos, tipo de fertilizante recomendado según textura).
    2. **Manejo de agua** (drenaje/riego) considerando zonas de riesgo.
    3. **Prácticas complementarias**: cultivos de cobertura, labranza, enmiendas orgánicas, corrección de pH si aplica.
    4. **Priorización de zonas para intervención** (cuáles atender primero).
    5. **Conclusión técnica** sobre el potencial productivo del lote y las limitantes principales.

    Sé específico y basado en los datos. Utiliza terminología profesional.
    """
    return llamar_gemini(prompt, system_prompt=system, temperature=0.3)
