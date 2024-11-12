import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    inventario_api_df = pd.read_excel(inventario_url)
    return inventario_api_df

# Cargar archivo Maestro Moleculas desde Google Drive
@st.cache_data
def load_maestro_moleculas():
    maestro_url = "https://docs.google.com/spreadsheets/d/1t9x5zUoEKj-export?format=xlsx"
    maestro_df = pd.read_excel(maestro_url)
    return maestro_df

# Función para obtener CUR desde Maestro Moleculas
def obtener_cur(codart, maestro_df):
    maestro_df.columns = maestro_df.columns.str.lower().str.strip()
    cur = maestro_df.loc[maestro_df['codart'] == codart, 'cur']
    if not cur.empty:
        return cur.iloc[0]
    return None

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    cur_faltantes = faltantes_df['cur'].unique()
    codart_faltantes = faltantes_df['codart'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) &
        (alternativas_inventario_df['codart'].isin(codart_faltantes))
    ]

    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'nomart': 'nomart_alternativa'
    }, inplace=True)

    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_disponibles_df,
        on='cur',
        how='inner'
    )

    alternativas_disponibles_df.sort_values(by=['codart', 'unidadespresentacionlote'], inplace=True)
    mejores_alternativas = []

    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)
        if mejor_opcion.empty:
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')
        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)
    columnas_finales = ['cur', 'codart', 'faltante', 'codart_alternativa', 'opcion_alternativa', 'unidadespresentacionlote', 'bodega', 'nomart_alternativa']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

inventario_api_df = load_inventory_file()
maestro_df = load_maestro_moleculas()

# Opción de cargar archivo de faltantes
st.header("Opción 1: Procesar archivo de faltantes")
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    columnas_adicionales = st.multiselect("Selecciona columnas adicionales:", ["presentacionart", "numlote", "fechavencelote", "nomart"], default=[])
    resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales)
    st.dataframe(resultado_final_df)

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Alternativas')
        return output.getvalue()

    st.download_button(label="Descargar archivo", data=to_excel(resultado_final_df), file_name='alternativas.xlsx')

# Opción de búsqueda rápida
st.header("Opción 2: Búsqueda rápida de una alternativa")
codart_input = st.text_input("Ingresa el código de artículo:")
faltante_input = st.number_input("Cantidad faltante:", min_value=1)

if st.button("Buscar Alternativa"):
    cur = obtener_cur(codart_input, maestro_df)
    if cur:
        faltante_df = pd.DataFrame({'cur': [cur], 'codart': [codart_input], 'faltante': [faltante_input]})
        resultado_df = procesar_faltantes(faltante_df, inventario_api_df, [])
        if resultado_df.empty:
            st.warning("No se encontraron alternativas disponibles.")
        else:
            st.dataframe(resultado_df)
    else:
        st.error("No se encontró el CUR para el código de artículo ingresado.")
