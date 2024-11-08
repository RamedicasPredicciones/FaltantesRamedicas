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

    # Obtener los CUR, nombres y codArt únicos de productos con faltantes
    cur_faltantes = faltantes_df['cur'].unique()
    nombre_faltantes = faltantes_df['nombre'].unique()
    codart_faltantes = faltantes_df['codart'].unique()

    # Filtrar el inventario para obtener registros con esos CUR
    alternativas_cur_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]

    # Buscar alternativas adicionales por nombre, que pueden tener diferente composición pero nombre similar
    alternativas_nombre_df = inventario_api_df[inventario_api_df['nombre'].isin(nombre_faltantes)]

    # Concatenar ambos conjuntos de alternativas
    alternativas_disponibles_df = pd.concat([alternativas_cur_df, alternativas_nombre_df]).drop_duplicates()

    # Filtrar filas donde la cantidad en inventario sea mayor a cero
    alternativas_disponibles_df = alternativas_disponibles_df[
        alternativas_disponibles_df['unidadespresentacionlote'] > 0
    ]

    # Renombrar columnas para incluir `codart_alternativa` y `nombre_alternativa`
    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'nombre': 'nombre_alternativa',
        'opcion': 'opcion_alternativa'
    }, inplace=True)

    # Agregar la columna faltante al hacer merge
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'nombre', 'faltante']],
        alternativas_disponibles_df,
        left_on=['cur'],
        right_on=['cur'],
        how='inner'
    )

    # Ordenar para priorizar las mejores opciones (por nombre y cantidad en inventario)
    alternativas_disponibles_df.sort_values(by=['nombre', 'unidadespresentacionlote'], ascending=[True, False], inplace=True)

    # Seleccionar la mejor alternativa para cada faltante
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Filtrar opciones que tienen cantidad mayor o igual al faltante y obtener la mejor
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            # Si no hay opción suficiente, tomar la mayor cantidad disponible
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')

        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Seleccionar columnas finales deseadas
    columnas_finales = ['cur', 'codart', 'nombre', 'faltante', 'codart_alternativa', 'nombre_alternativa', 'opcion_alternativa', 'unidadespresentacionlote', 'bodega']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes con Búsqueda Avanzada')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_file()

    # Seleccionar columnas adicionales para el archivo final
    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionart", "numlote", "fechavencelote"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales)

    st.write("Archivo procesado correctamente.")
    st.dataframe(resultado_final_df)

    # Crear archivo Excel en memoria para la descarga
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Alternativas')
        return output.getvalue()

    # Botón para descargar el archivo generado
    st.download_button(
        label="Descargar archivo de alternativas",
        data=to_excel(resultado_final_df),
        file_name='alternativas_disponibles_avanzadas.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
