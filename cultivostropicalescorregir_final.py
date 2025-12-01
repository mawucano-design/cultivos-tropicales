# Add at the very top of the file, after imports
import sys
import traceback

# Try to handle GDAL environment setup
try:
    from osgeo import gdal
    gdal.UseExceptions()
except ImportError:
    # If GDAL is not available, continue without it
    pass

# Modify the main function to catch all exceptions
def main():
    """Función principal de la aplicación - VERSIÓN CORREGIDA"""
    try:
        # Mostrar siempre el título principal
        st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA GEE COMPLETA CON AGROECOLOGÍA")
        st.markdown("---")
        
        # ... rest of your existing main function code ...
        
    except Exception as e:
        st.error(f"❌ Error crítico en la aplicación: {str(e)}")
        st.error("Por favor, recarga la página o contacta al administrador.")
        st.code(traceback.format_exc())
        
        # Provide debugging info
        with st.expander("Información de depuración"):
            st.write("**Versiones de Python y paquetes:**")
            st.write(f"Python: {sys.version}")
            st.write(f"Streamlit: {st.__version__}")
