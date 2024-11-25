import streamlit as st
import pandas as pd
import math
from io import BytesIO
# Enlace de la plantilla en Google Sheets
PLANTILLA_URL = "https://docs.google.com/spreadsheets/d/1CPMBfCiuXq2_l8KY68HgexD-kyNVJ2Ml/export?format=xlsx"
# Función para cargar archivo de inventario desde Google Drive
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx&sheet=Hoja3"
    inventario_api_df = pd.read_excel(inventario_url, sheet_name="Hoja3")
    return inventario_api_df
# Función para procesar el archivo de faltantes
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    return resultado_final_df

# Interfaz de Streamlit
st.markdown(
    """
    <h1 style="text-align: center; color: #FF5800; font-family: Arial, sans-serif;">
        RAMEDICAS S.A.S.
    </h1>
    <h3 style="text-align: center; font-family: Arial, sans-serif; color: #3A86FF;">
        Generador de Alternativas para Faltantes
    </h3>
    <p style="text-align: center; font-family: Arial, sans-serif; color: #6B6B6B;">
        Esta herramienta te permite buscar el código alternativa para cada faltante de los pedidos en Ramédicas con su respectivo inventario actual.
    </p>
    """, unsafe_allow_html=True
)

# Función para exportar a Excel
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Alternativas')
    return output.getvalue()
st.download_button(
    label="Descargar archivo de alternativas",
    data=to_excel(resultado_final_df),
    file_name='alternativas_disponibles.xlsx',
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Función para devolver la URL de la plantilla
def descargar_plantilla():
    return PLANTILLA_URL  # Asegúrate de que PLANTILLA_URL esté definida con el enlace correcto
# Sección de botones alineados a la izquierda
st.markdown(
    f"""
    <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 10px; margin-top: 20px;">
        <a href="{descargar_plantilla()}" download>
            <button style="background-color: #FF5800; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">
                Descargar plantilla de faltantes
            </button>
        </a>
        <button onclick="window.location.reload()" style="background-color: #3A86FF; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">
            Actualizar inventario
        </button>
    </div>
    """,
    unsafe_allow_html=True
)

# Archivo cargado por el usuario
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")
if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_file()
    bodegas_disponibles = inventario_api_df['bodega'].unique().tolist()
    bodega_seleccionada = st.multiselect("Seleccione la bodega", options=bodegas_disponibles, default=[])
    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionart", "numlote", "fechavencelote"],
        default=[]
    )
    resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada)
    if not resultado_final_df.empty:
        st.write("Archivo procesado correctamente.")
        st.dataframe(resultado_final_df)
        # Función para exportar a Excel
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Alternativas')
            return output.getvalue()
        st.download_button(
            label="Descargar archivo de alternativas",
            data=to_excel(resultado_final_df),
            file_name='alternativas_disponibles.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
