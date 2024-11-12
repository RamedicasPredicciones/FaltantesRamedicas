import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de Inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    inventario_api_df = pd.read_excel(inventario_url)
    return inventario_api_df

# Función para obtener el CUR de un artículo
def obtener_cur(codart, inventario_api_df):
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    cur_resultado = inventario_api_df[inventario_api_df['codart'] == codart]['cur'].unique()
    return cur_resultado[0] if len(cur_resultado) > 0 else None

# Función para obtener una alternativa rápida utilizando el CUR
def obtener_alternativa_rapida(codart, faltante, inventario_api_df):
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    
    # Obtener el CUR del artículo ingresado
    cur = obtener_cur(codart, inventario_api_df)
    
    if cur is None:
        return "No se encontró CUR para este artículo."
    
    # Filtrar alternativas disponibles utilizando el CUR
    alternativas_df = inventario_api_df[
        (inventario_api_df['cur'] == cur) &
        (inventario_api_df['unidadespresentacionlote'] > 0)
    ]

    if alternativas_df.empty:
        return "No se encontraron alternativas disponibles para este CUR."

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

# Cargar inventario
inventario_api_df = load_inventory_file()

# Opción rápida para obtener una alternativa de un solo artículo
st.header("Búsqueda rápida de alternativa")
codart_input = st.text_input("Ingresa el código del artículo (CodArt):")
faltante_input = st.number_input("Ingresa la cantidad faltante:", min_value=0)

if st.button("Buscar Alternativa"):
    if codart_input and faltante_input > 0:
        resultado_alternativa = obtener_alternativa_rapida(codart_input, faltante_input, inventario_api_df)
        st.write("Resultado de la búsqueda rápida:")
        if isinstance(resultado_alternativa, str):
            st.warning(resultado_alternativa)
        else:
            st.dataframe(resultado_alternativa)
    else:
        st.warning("Por favor ingresa el código del artículo y la cantidad faltante.")

# Opción para procesar un archivo de faltantes completo
st.header("Cargar archivo de faltantes para procesar")
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)

    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
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
