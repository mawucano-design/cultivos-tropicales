# 🌾 Analizador Multi-Cultivo Satelital - Versión 3.0

Aplicación web para agricultura de precisión con Google Earth Engine - **SIN INSTALACIÓN REQUERIDA**

## 🚀 Características Principales

### ✅ **Sin instalación local**
- Acceso vía navegador web
- No requiere Python en la computadora
- Funciona en cualquier dispositivo

### ✅ **Autenticación flexible**
- Cuenta de servicio Google Cloud
- Token de acceso temporal
- Modo público (limitado)
- Secrets de Streamlit Cloud

### ✅ **Datos satelitales reales**
- Google Earth Engine integrado
- Sentinel-2 (10m resolución)
- Landsat 8/9 (30m resolución)
- MODIS (250m resolución)

### ✅ **Cultivos soportados**
- Trigo 🌾
- Maíz 🌽
- Sorgo 🌾
- Soja 🫘
- Girasol 🌻
- Maní 🥜

## 🌐 Cómo usar online

### Opción 1: Usar versión alojada (recomendado)
1. Visita: `https://agriculturadeprecision.streamlit.app/`
2. Autentica con tu cuenta GEE
3. Sube tu parcela
4. Obtén análisis inmediato

### Opción 2: Desplegar en tu cuenta
1. Fork este repositorio en GitHub
2. Conecta a Streamlit Cloud
3. Configura Secrets con credenciales GEE
4. Tu app estará en: `https://tunombre-analizador.streamlit.app/`

## 🔧 Configuración para desarrolladores

### Despliegue en Streamlit Cloud
1. **Crea cuenta en [Streamlit Cloud](https://streamlit.io/cloud)**
2. **Conecta tu repositorio de GitHub**
3. **Configura Secrets:**

```toml
# En Streamlit Cloud > Settings > Secrets
EE_ACCOUNT ="gee-service-account@ee-mawucano25.iam.gserviceaccount.com"
EE_PRIVATE_KEY = '''
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
-----END PRIVATE KEY-----
'''
