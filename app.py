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

    # Verificar que el archivo de faltantes tiene las columnas necesarias
    columnas_necesarias = {'cur', 'codart', 'faltante', 'embalaje'}
    if not columnas_necesarias.issubset(faltantes_df.columns):
        st.error(f"El archivo de faltantes debe contener las columnas: {', '.join(columnas_necesarias)}")
        return pd.DataFrame()  # Devuelve un DataFrame vacío si faltan columnas

    cur_faltantes = faltantes_df['cur'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]

    if bodega_seleccionada:
        alternativas_inventario_df = alternativas_inventario_df[alternativas_inventario_df['bodega'].isin(bodega_seleccionada)]

    alternativas_disponibles_df = alternativas_inventario_df[alternativas_inventario_df['unidadespresentacionlote'] > 0]

    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'embalaje': 'embalaje_alternativa'
    }, inplace=True)

    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante', 'embalaje']],
        alternativas_disponibles_df,
        on='cur',
        how='inner'
    )

    # Filtrar registros donde opcion_alternativa sea mayor a 0
    alternativas_disponibles_df = alternativas_disponibles_df[alternativas_disponibles_df['opcion_alternativa'] > 0]

    # Agregar columna de cantidad necesaria ajustada por embalaje
    alternativas_disponibles_df['cantidad_necesaria'] = alternativas_disponibles_df.apply(
        lambda row: math.ceil(row['faltante'] * row['embalaje'] / row['embalaje_alternativa'])
        if pd.notnull(row['embalaje']) and pd.notnull(row['embalaje_alternativa']) and row['embalaje_alternativa'] > 0
        else None,
        axis=1
    )

    alternativas_disponibles_df.sort_values(by=['codart', 'unidadespresentacionlote'], inplace=True)

    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Buscar en la bodega seleccionada
        mejor_opcion_bodega = group[group['unidadespresentacionlote'] >= faltante_cantidad]
        mejor_opcion = mejor_opcion_bodega.head(1) if not mejor_opcion_bodega.empty else group.nlargest(1, 'unidadespresentacionlote')
        
        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    columnas_finales = ['cur', 'codart', 'faltante', 'embalaje', 'codart_alternativa', 'opcion_alternativa', 
                        'embalaje_alternativa', 'cantidad_necesaria', 'unidadespresentacionlote', 'bodega', 'carta']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

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
    columnas_adicionales = []  # Aquí puedes agregar las columnas adicionales si las tienes
    bodega_seleccionada = []  # Puedes personalizar la selección de bodegas
    resultado_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada)

    # Mostrar el resultado final
    if not resultado_df.empty:
        st.write("Resultados de alternativas encontradas:", resultado_df)
    else:
        st.warning("No se encontraron alternativas para los faltantes.")
