import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    # Enlace directo para Inventario desde Google Drive
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"

    # Cargar el archivo de inventario directamente desde el enlace
    inventario_api_df = pd.read_excel(inventario_url)
    
    return inventario_api_df

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales):
    # Normalizar nombres de columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Obtener los CUR y codArt únicos de productos con faltantes
    cur_faltantes = faltantes_df['cur'].unique()
    codart_faltantes = faltantes_df['codart'].unique()

    # Filtrar el inventario para obtener registros con esos CUR
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]

    # Filtrar filas donde la cantidad en inventario sea mayor a cero y el codart esté en la lista de faltantes
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) &
        (alternativas_inventario_df['codart'].isin(codart_faltantes))
    ]

    # Renombrar columnas para incluir 'codart_alternativa'
    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'nomart': 'nomart_alternativa'
    }, inplace=True)

    # Agregar la columna faltante al hacer merge
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_disponibles_df,
        left_on=['cur'],
        right_on=['cur'],
        how='inner'
    )

    # Ordenar por 'codart' y 'unidadespresentacionlote' para priorizar las mejores opciones
    alternativas_disponibles_df.sort_values(by=['codart', 'unidadespresentacionlote'], inplace=True)

    # Seleccionar la mejor alternativa para cada faltante
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)
        if mejor_opcion.empty:
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')
        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Seleccionar columnas finales deseadas
    columnas_finales = ['cur', 'codart', 'faltante', 'codart_alternativa', 'opcion_alternativa', 'unidadespresentacionlote', 'bodega', 'nomart_alternativa']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Nueva función para buscar una alternativa rápida
def obtener_alternativa_rapida(codart, faltante, inventario_api_df):
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    
    # Filtrar alternativas disponibles para el artículo ingresado
    alternativas_df = inventario_api_df[
        (inventario_api_df['codart'] == codart) &
        (inventario_api_df['unidadespresentacionlote'] > 0)
    ]
    
    if alternativas_df.empty:
        return "No se encontraron alternativas disponibles para este artículo."
    
    # Ordenar por cantidad de unidades
    alternativas_df = alternativas_df.sort_values(by='unidadespresentacionlote', ascending=False)
    
    # Buscar la mejor alternativa
    mejor_opcion = alternativas_df[alternativas_df['unidadespresentacionlote'] >= faltante].head(1)
    
    if mejor_opcion.empty:
        mejor_opcion = alternativas_df.head(1)
    
    # Formatear el resultado
    resultado = mejor_opcion[['codart', 'opcion', 'unidadespresentacionlote', 'nomart', 'bodega']]
    resultado.rename(columns={
        'codart': 'CodArt Alternativa',
        'opcion': 'Opción Alternativa',
        'unidadespresentacionlote': 'Unidades Disponibles',
        'nomart': 'Nombre Artículo',
        'bodega': 'Bodega'
    }, inplace=True)
    
    return resultado

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_file()

    # Opción para procesamiento de archivo completo
    st.header("Procesamiento Completo")
    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionart", "numlote", "fechavencelote", "nomart"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales)
    st.dataframe(resultado_final_df)

    st.download_button(
        label="Descargar archivo de alternativas",
        data=BytesIO(pd.ExcelWriter(BytesIO(), engine='openpyxl').save()),
        file_name='alternativas_disponibles.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    # Opción rápida de búsqueda
    st.header("Búsqueda Rápida de Alternativa para un Artículo")
    codart_input = st.text_input("Ingrese el código del artículo (CodArt):")
    faltante_input = st.number_input("Ingrese la cantidad faltante:", min_value=1, step=1)
    
    if st.button("Buscar Alternativa"):
        resultado_alternativa = obtener_alternativa_rapida(codart_input, faltante_input, inventario_api_df)
        st.write("Resultado:")
        st.dataframe(resultado_alternativa)
