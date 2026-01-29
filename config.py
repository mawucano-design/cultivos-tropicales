import os
import streamlit as st
from datetime import datetime, timedelta

def get_sentinelhub_config():
    """Obtener configuración de Sentinel Hub desde secrets.toml"""
    try:
        # Intentar obtener desde secrets.toml
        secrets = st.secrets
        
        config = {
            'instance_id': secrets.get('SENTINELHUB_INSTANCE_ID', ''),
            'client_id': secrets.get('SENTINELHUB_CLIENT_ID', ''),
            'client_secret': secrets.get('SENTINELHUB_CLIENT_SECRET', '')
        }
        
        # Verificar que todas las credenciales estén presentes
        missing_creds = []
        if not config['instance_id']:
            missing_creds.append('SENTINELHUB_INSTANCE_ID')
        if not config['client_id']:
            missing_creds.append('SENTINELHUB_CLIENT_ID') 
        if not config['client_secret']:
            missing_creds.append('SENTINELHUB_CLIENT_SECRET')
            
        if missing_creds:
            st.warning(f"⚠️ Credenciales faltantes en secrets.toml: {', '.join(missing_creds)}")
            return None
            
        st.success("✅ Credenciales de Sentinel Hub cargadas correctamente")
        return config
        
    except Exception as e:
        st.error(f"❌ Error cargando configuración: {str(e)}")
        return None

# Configuración de Sentinel Hub
SENTINELHUB_CONFIG = get_sentinelhub_config()

# Configuración USGS EarthExplorer (Landsat) - Opcional
USGS_CONFIG = {
    'username': st.secrets.get('USGS_USERNAME', ''),
    'password': st.secrets.get('USGS_PASSWORD', '')
}

# Parámetros de imágenes por cultivo (mantener igual)
IMAGE_PARAMETERS = {
    'VID': {
        'optimal_moths': [5, 6, 7],
        'cloud_cover_max': 10,
        'resolution': 10
    },
    'OLIVO': {
        'optimal_months': [6, 7, 8],
        'cloud_cover_max': 10,
        'resolution': 10
    },
     'HORTALIZAS': {
        'optimal_months': [6, 7, 8],
        'cloud_cover_max': 10,
        'resolution': 10
    },# ... (mantener el resto igual)
}
