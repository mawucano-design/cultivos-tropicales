# app.py - Simple entry point
import subprocess
import sys
import os

# Check if we're in Streamlit Cloud
if os.path.exists("/mount/src/cultivos-tropicales"):
    sys.path.insert(0, "/mount/src/cultivos-tropicales")

try:
    # Try to import the main app
    from cultivostropicalescorregir_final import main
    
    # Run the app
    if __name__ == "__main__":
        main()
        
except Exception as e:
    # Create a simple error page if import fails
    import streamlit as st
    st.error(f"Error al cargar la aplicación: {str(e)}")
    st.info("Verificando dependencias...")
    
    # Try to install missing packages
    with st.spinner("Instalando dependencias..."):
        try:
            # Try to install geopandas and fiona
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "geopandas==1.1.1", "fiona==1.10.1", 
                "--no-cache-dir"
            ])
            st.success("Dependencias instaladas. Recargando...")
            st.rerun()
        except:
            st.error("No se pudieron instalar las dependencias automáticamente.")
