import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    inventario_api_df = pd.read_excel(inventario_url)
    return inventario_api_df

# Cargar archivo Maestro Moleculas
@st.cache_data
def load_maestro_moleculas():
    maestro_moleculas_df = pd.read_excel('/content/Maestro_Moleculas.xlsx')  # Ruta local del archivo
    return maestro_moleculas_df

# Procesar faltantes con datos del archivo subido
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    cur_faltantes = faltantes_df['cur'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0)
    ]
    alternativas_disponibles_df.rename(columns={'codart': 'codart_alternativa'}, inplace=True)
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_disponibles_df,
        on='cur',
        how='inner'
    )
    alternativas_disponibles_df.sort_values(by=['codart', 'unidadespresentacionlote'], inplace=True)
    resultado_final_df = alternativas_disponibles_df.head(1)
    return resultado_final_df

# Función para búsqueda rápida
def busqueda_rapida(articulo, cantidad, inventario_api_df, maestro_moleculas_df):
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    
    # Obtener el CUR del artículo ingresado
    cur_info = maestro_moleculas_df[maestro_moleculas_df['articulo'] == articulo]
    if cur_info.empty:
        st.error("Artículo no encontrado en el maestro.")
        return pd.DataFrame()
    
    cur = cur_info['cur'].iloc[0]
    
    # Filtrar en inventario por el CUR
    alternativas_df = inventario_api_df[
        (inventario_api_df['cur'] == cur) &
        (inventario_api_df['unidadespresentacionlote'] > cantidad)
    ]
    
    if alternativas_df.empty:
        st.warning("No hay alternativas disponibles.")
        return pd.DataFrame()

    alternativas_df.sort_values(by='unidadespresentacionlote', ascending=False, inplace=True)
    return alternativas_df.head(1)

# UI de Streamlit
st.title('Generador de Alternativas de Faltantes')

option = st.selectbox("Selecciona una opción", ["Subir archivo de faltantes", "Búsqueda rápida"])

inventario_api_df = load_inventory_file()
maestro_moleculas_df = load_maestro_moleculas()

# Primera opción: subir archivo de faltantes
if option == "Subir archivo de faltantes":
    uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")
    if uploaded_file:
        faltantes_df = pd.read_excel(uploaded_file)
        resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, [])
        st.dataframe(resultado_final_df)
        st.download_button(
            label="Descargar archivo de alternativas",
            data=resultado_final_df.to_csv().encode('utf-8'),
            file_name='alternativas.csv'
        )

# Segunda opción: Búsqueda rápida
if option == "Búsqueda rápida":
    articulo = st.text_input("Ingresa el artículo:")
    cantidad = st.number_input("Cantidad faltante:", min_value=1, step=1)
    
    if st.button("Buscar Alternativa"):
        resultado_df = busqueda_rapida(articulo, cantidad, inventario_api_df, maestro_moleculas_df)
        if not resultado_df.empty:
            st.dataframe(resultado_df)
