# ========== FUNCIONES DE ANÁLISIS CON PROMPTS MEJORADOS ==========

def generar_analisis_fertilidad(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"""Eres un ingeniero agrónomo con especialización en edafología, nutrición vegetal y transición agroecológica, experto en {cultivo}.
    Redacta un análisis técnico detallado y orientado a la sostenibilidad. Incluye:
    - Evaluación de la fertilidad química (NPK, MO, pH si disponible) y su interpretación fisiológica para el cultivo.
    - Relación con la textura del suelo y su impacto en la disponibilidad de nutrientes.
    - Recomendaciones específicas para mejorar la fertilidad desde un enfoque agroecológico: uso de abonos verdes, compost, biofertilizantes, micorrizas, rotaciones con leguminosas, etc.
    - Indicadores de salud del suelo a monitorear (respiración, agregados, carbono orgánico).
    - Evita recomendaciones genéricas; sé concreto y basado en los datos proporcionados."""
    
    prompt = f"""
    Lote de **{cultivo}** - {stats['num_zonas']} zonas de manejo diferenciado.
    
    **Parámetros promedio del suelo:**
    - NPK (índice de fertilidad química): {stats['npk_prom']:.2f} (rango: {stats['npk_min']:.2f} - {stats['npk_max']:.2f})
    - Materia orgánica: {stats['mo_prom']:.1f}% (rango: {stats['mo_min']:.1f}% - {stats['mo_max']:.1f}%)
    - Textura dominante: {stats['textura_dominante']}
    
    **Detalle por zonas representativas:**
    {df_resumen[['Zona', 'NPK', 'MO_%', 'Textura']].to_string(index=False)}
    
    **Instrucciones para el análisis:**
    1. Interpretar el nivel de NPK y MO en el contexto del cultivo y la región.
    2. Explicar cómo la textura influye en la retención de nutrientes y agua.
    3. Proponer **al menos 3 prácticas agroecológicas concretas** para elevar la fertilidad natural (ej. incorporación de leguminosas, elaboración de compost con residuos de cosecha, aplicación de harina de rocas, etc.).
    4. Sugerir un plan de monitoreo participativo de indicadores de salud del suelo.
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ El análisis de fertilidad por IA no está disponible en este momento. Por favor, use el reporte estándar."
    return resultado

def generar_analisis_ndvi_ndre(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"""Eres un especialista en teledetección aplicada a la agricultura de precisión y fisiología vegetal, con enfoque en transición agroecológica.
    Analiza los índices espectrales NDVI y NDRE de forma técnica, relacionándolos con:
    - Estado nutricional del cultivo (especialmente nitrógeno).
    - Estrés hídrico o biótico.
    - Heterogeneidad espacial y su relación con prácticas de manejo previas.
    - Recomendaciones para la agricultura regenerativa: manejo de coberturas, siembra directa, policultivos, etc."""
    
    prompt = f"""
    **Cultivo:** {cultivo}
    **NDVI promedio:** {stats['ndvi_prom']:.2f} (rango: {stats['ndvi_min']:.2f} - {stats['ndvi_max']:.2f})
    **NDRE promedio:** {stats['ndre_prom']:.2f} (rango: {stats['ndre_min']:.2f} - {stats['ndre_max']:.2f})
    
    **Zonas representativas:**
    {df_resumen[['Zona', 'NDVI', 'NDRE']].to_string(index=False)}
    
    **Análisis requerido:**
    1. Interpretar los valores de NDVI y NDRE: ¿Qué indican sobre biomasa, vigor y nivel de nitrógeno?
    2. Identificar zonas de baja productividad potencial y sus posibles causas (compactación, deficiencias, excesos).
    3. Recomendar prácticas agroecológicas específicas para homogeneizar el cultivo: aplicación diferenciada de bioinsumos, establecimiento de franjas de biodiversidad funcional, ajuste de densidades de siembra, etc.
    4. Sugerir umbrales de alerta temprana basados en estos índices.
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis NDVI/NDRE no disponible por error de API."
    return resultado

def generar_analisis_riesgo_hidrico(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"""Eres un hidrólogo de suelos y especialista en manejo del agua en agroecosistemas.
    Evalúa el riesgo hídrico y propone estrategias de adaptación basadas en principios agroecológicos:
    - Captación y almacenamiento de agua de lluvia.
    - Mejora de la infiltración y retención (materia orgánica, coberturas, curvas de nivel).
    - Selección de cultivos y variedades tolerantes a sequía o anegamiento.
    - Integración de sistemas silvopastoriles o agroforestales para regular el ciclo hidrológico."""
    
    prompt = f"""
    **Cultivo:** {cultivo}
    **Humedad del suelo (índice o contenido):** promedio {stats['humedad_prom']:.2f}, rango {stats['humedad_min']:.2f} - {stats['humedad_max']:.2f}
    **Textura dominante:** {stats['textura_dominante']}
    
    **Zonas representativas:**
    {df_resumen[['Zona', 'Humedad', 'Textura']].to_string(index=False)}
    
    **Análisis requerido:**
    1. Evaluar el riesgo de estrés hídrico (déficit o exceso) según la textura y la variabilidad espacial.
    2. Estimar la capacidad de retención de agua disponible para el cultivo.
    3. Proponer un plan de manejo agroecológico del agua que incluya al menos:
       - Prácticas para aumentar la infiltración (coberturas muertas/vivas, hoyos de siembra, etc.).
       - Sistemas de captación o microalmacenamiento (barreras, jagüeyes, aljibes).
       - Estrategias de riego complementario de bajo costo (riego por goteo con energía solar, etc.).
    4. Indicadores de monitoreo de la eficiencia del uso del agua.
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de riesgo hídrico no disponible."
    return resultado

def generar_analisis_costos(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"""Eres un economista ecológico y asesor en gestión de fincas agroecológicas.
    Analiza la viabilidad económica de la transición, considerando:
    - Reducción de insumos externos (fertilizantes sintéticos, plaguicidas).
    - Inversiones en prácticas regenerativas (compost, biofábricas, cercas vivas).
    - Incrementos de rendimiento y resiliencia a largo plazo.
    - Beneficios no monetarios (salud del suelo, biodiversidad, servicios ecosistémicos)."""
    
    prompt = f"""
    **Cultivo:** {cultivo}
    **Costo total actual (fertilizantes sintéticos + aplicaciones):** ${stats['costo_total']:,.2f}
    **Rendimiento promedio sin fertilización sintética:** {stats['rend_sin_prom']:.0f} kg/ha
    **Rendimiento con fertilización convencional:** {stats['rend_con_prom']:.0f} kg/ha
    **Incremento porcentual por fertilización:** {stats['inc_prom']:.1f}%
    
    **Zonas representativas (costo e incremento):**
    {df_resumen[['Zona', 'Costo_total', 'Inc_%']].to_string(index=False)}
    
    **Análisis requerido:**
    1. Evaluar la rentabilidad actual y la dependencia de insumos externos.
    2. Calcular el ahorro potencial al reemplazar parcialmente fertilizantes sintéticos por bioinsumos y prácticas agroecológicas.
    3. Proponer un escenario de transición a 3 años con inversiones progresivas (compost, abonos verdes, etc.) y estimar el impacto en el margen neto.
    4. Identificar incentivos o fuentes de financiamiento para la transición (créditos verdes, pagos por servicios ambientales, etc.).
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Análisis de costos no disponible."
    return resultado

def generar_recomendaciones_integradas(df_resumen: pd.DataFrame, stats: Dict, cultivo: str) -> str:
    system = f"""Eres un asesor técnico senior en agricultura de precisión y agroecología, con amplia experiencia en transición de sistemas convencionales a regenerativos.
    Genera un plan de manejo integrado, priorizando acciones de bajo costo y alto impacto ecológico.
    Incluye:
    - Calendario agroecológico (coberturas, rotaciones, bioinsumos).
    - Diseño de la biodiversidad funcional (bordes, franjas, árboles dispersos).
    - Estrategias de manejo de suelo sin labranza.
    - Integración de animales si es pertinente.
    - Indicadores de éxito y puntos de control."""
    
    prompt = f"""
    **Síntesis del diagnóstico:**
    - Cultivo: {cultivo}
    - NPK promedio: {stats['npk_prom']:.2f}
    - Materia orgánica: {stats['mo_prom']:.1f}%
    - NDVI promedio: {stats['ndvi_prom']:.2f}
    - Incremento de rendimiento con fertilización convencional: {stats['inc_prom']:.1f}%
    - Textura dominante: {stats['textura_dominante']}
    
    **Plan de transición agroecológica requerido:**
    1. **Fase 1 (primer año):** Acciones inmediatas de bajo costo (incorporación de rastrojos, aplicación de micorrizas, establecimiento de franjas de flores).
    2. **Fase 2 (segundo año):** Rotación de cultivos, abonos verdes, reducción del 30-50% de fertilizantes sintéticos.
    3. **Fase 3 (tercer año):** Consolidación de sistemas agroforestales, biofábrica en finca, certificación participativa.
    
    Incluye indicadores de monitoreo por fase y recomendaciones para manejar la resistencia al cambio.
    """
    resultado = llamar_deepseek(prompt, system_prompt=system, temperature=0.3)
    if resultado is None:
        return "⚠️ Recomendaciones integradas no disponibles por error de API."
    return resultado
