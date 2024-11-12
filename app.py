import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    return pd.read_excel(inventario_url)

# Cargar archivo Maestro de Moléculas
@st.cache_data
def load_maestro_moleculas_file():
    maestro_url = "/content/Maestro_Moleculas.xlsx"  # Ruta del archivo Maestro de Moléculas
    return pd.read_excel(maestro_url)

# Función para obtener el CUR de un artículo desde el archivo maestro
def obtener_cur_desde_maestro(codart, maestro_moleculas_df):
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    cur_resultado = maestro_moleculas_df[maestro_moleculas_df['codart'] == codart]['cur'].unique()
    return cur_resultado[0] if len(cur_resultado) > 0 else None

# Función para obtener una alternativa rápida utilizando el CUR desde el archivo de inventario
def obtener_alternativa_rapida(codart, faltante, inventario_api_df, maestro_moleculas_df):
    # Buscar el CUR en el archivo Maestro de Moléculas
    cur = obtener_cur_desde_maestro(codart, maestro_moleculas_df)
    
    if cur is None:
        return "No se encontró CUR para este artículo en el archivo maestro."

    # Filtrar alternativas disponibles en el inventario usando el CUR
    alternativas_df = inventario_api_df[
        (inventario_api_df['cur'] == cur) & (inventario_api_df['unidadespresentacionlote'] > 0)
    ]

    if alternativas_df.empty:
        return "No se encontraron alternativas disponibles para este CUR en el inventario."

    # Ordenar por cantidad de unidades disponibles
    alternativas_df = alternativas_df.sort_values(by='unidadespresentacionlote', ascending=False)

    # Buscar la mejor alternativa
    mejor_opcion = alternativas_df[alternativas_df['unidadespresentacionlote'] >= faltante].head(1)
    if mejor_opcion.empty:
        mejor_opcion = alternativas_df.head(1)

    # Seleccionar columnas para mostrar
    resultado = mejor_opcion[['cur', 'codart', 'opcion', 'unidadespresentacionlote', 'nomart', 'bodega']]
    resultado.columns = ['CUR', 'CodArt Alternativa', 'Opción Alternativa', 'Unidades Disponibles', 'Nombre Artículo', 'Bodega']
    return resultado

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

# Cargar archivos de inventario y maestro de moléculas
inventario_api_df = load_inventory_file()
maestro_moleculas_df = load_maestro_moleculas_file()

# Opción rápida para obtener una alternativa de un solo artículo
st.header("Búsqueda rápida de alternativa")
codart_input = st.text_input("Ingresa el código del artículo (CodArt):")
faltante_input = st.number_input("Ingresa la cantidad faltante:", min_value=0)

if st.button("Buscar Alternativa"):
    if codart_input and faltante_input > 0:
        resultado_alternativa = obtener_alternativa_rapida(codart_input, faltante_input, inventario_api_df, maestro_moleculas_df)
        st.write("Resultado de la búsqueda rápida:")
        if isinstance(resultado_alternativa, str):
            st.warning(resultado_alternativa)
        else:
            st.dataframe(resultado_alternativa)
    else:
        st.warning("Por favor ingresa el código del artículo y la cantidad faltante.")
