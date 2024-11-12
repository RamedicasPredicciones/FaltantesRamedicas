import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    return pd.read_excel(inventario_url)

# Cargar archivo Maestro de Moléculas desde Google Drive
@st.cache_data
def load_maestro_file():
    maestro_url = "https://docs.google.com/spreadsheets/d/19myWtMrvsor2P_XHiifPgn8YKdTWE39O/export?format=xlsx"
    return pd.read_excel(maestro_url)

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
    return resultado_final_df[columnas_presentes]

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

# Opción 1: Subir archivo de faltantes
st.subheader("Opción 1: Subir archivo de faltantes")
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")
if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_file()

    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final (Opción 1):",
        options=["presentacionart", "numlote", "fechavencelote", "nomart"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales)
    st.write("Archivo procesado correctamente.")
    st.dataframe(resultado_final_df)

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Alternativas')
        return output.getvalue()

    st.download_button(
        label="Descargar archivo de alternativas",
        data=to_excel(resultado_final_df),
        file_name='alternativas_disponibles.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# Opción 2: Búsqueda rápida de alternativa para un artículo específico
st.subheader("Opción 2: Búsqueda rápida de alternativa")

codigo_articulo = st.text_input("Ingrese el código del artículo con faltante:")
cantidad_faltante = st.number_input("Ingrese la cantidad de faltante:", min_value=1, step=1)

# Selección de columnas adicionales para la segunda opción
columnas_adicionales_rapida = st.multiselect(
    "Selecciona columnas adicionales para incluir en el archivo final (Opción 2):",
    options=["presentacionart", "numlote", "fechavencelote", "nomart"],
    default=[]
)

if st.button("Buscar alternativa"):
    if codigo_articulo and cantidad_faltante:
        maestro_df = load_maestro_file()
        inventario_api_df = load_inventory_file()

        cur_articulo = maestro_df.loc[maestro_df['codart'] == codigo_articulo, 'cur'].values
        if cur_articulo.size > 0:
            cur_articulo = cur_articulo[0]
            faltante_df = pd.DataFrame({'cur': [cur_articulo], 'codart': [codigo_articulo], 'faltante': [cantidad_faltante]})
            resultado_individual_df = procesar_faltantes(faltante_df, inventario_api_df, columnas_adicionales_rapida)

            st.write("Alternativa encontrada:")
            st.dataframe(resultado_individual_df)
        else:
            st.error("Código de artículo no encontrado en el archivo Maestro.")
    else:
        st.warning("Por favor, ingrese tanto el código del artículo como la cantidad faltante.")

