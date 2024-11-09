import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    inventario_api_df = pd.read_excel(inventario_url)
    return inventario_api_df

# Función para obtener una alternativa rápida
def obtener_alternativa_rapida(codart, faltante, inventario_api_df):
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Filtrar alternativas disponibles para el artículo ingresado
    alternativas_df = inventario_api_df[
        (inventario_api_df['codart'] == codart) &
        (inventario_api_df['unidadespresentacionlote'] > 0)
    ]

    if alternativas_df.empty:
        return "No se encontraron alternativas disponibles para este artículo."

    # Ordenar por cantidad de unidades disponibles
    alternativas_df = alternativas_df.sort_values(by='unidadespresentacionlote', ascending=False)

    # Buscar la mejor alternativa
    mejor_opcion = alternativas_df[alternativas_df['unidadespresentacionlote'] >= faltante].head(1)
    if mejor_opcion.empty:
        mejor_opcion = alternativas_df.head(1)

    # Seleccionar columnas para mostrar
    resultado = mejor_opcion[['codart', 'opcion', 'unidadespresentacionlote', 'nomart', 'bodega']]
    resultado.columns = ['CodArt Alternativa', 'Opción Alternativa', 'Unidades Disponibles', 'Nombre Artículo', 'Bodega']
    return resultado

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

# Cargar inventario
inventario_api_df = load_inventory_file()

# Opción rápida para obtener una alternativa de un solo artículo
st.header("Búsqueda rápida de alternativa")
codart_input = st.text_input("Ingresa el código del artículo (CodArt):")
faltante_input = st.number_input("Ingresa la cantidad faltante:", min_value=0)

if st.button("Buscar Alternativa"):
    if codart_input and faltante_input > 0:
        resultado_alternativa = obtener_alternativa_rapida(codart_input, faltante_input, inventario_api_df)
        st.write("Resultado de la búsqueda:")
        if isinstance(resultado_alternativa, str):
            st.warning(resultado_alternativa)
        else:
            st.dataframe(resultado_alternativa)
    else:
        st.warning("Por favor ingresa el código del artículo y la cantidad faltante.")

