import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivo de inventario desde Google Drive
@st.cache_data
def load_inventory_file():
    inventario_url = "https://drive.google.com/uc?export=download&id=1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC"
    inventario_api_df = pd.read_excel(inventario_url)
    return inventario_api_df

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales):
    # Normalizar nombres de columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Mostrar columnas y primeros registros para depuración
    st.write("Columnas en faltantes_df:", faltantes_df.columns)
    st.write("Primeras filas de faltantes_df:", faltantes_df.head())

    st.write("Columnas en inventario_api_df:", inventario_api_df.columns)
    st.write("Primeras filas de inventario_api_df:", inventario_api_df.head())

    # Obtener los CUR únicos de productos con faltantes
    cur_faltantes = faltantes_df['cur'].unique()

    # Filtrar el inventario para obtener registros con esos CUR y disponibilidad mayor a cero
    alternativas_inventario_df = inventario_api_df[
        (inventario_api_df['cur'].isin(cur_faltantes)) &
        (inventario_api_df['unidadespresentacionlote'] > 0)
    ]

    # Verificar si existen registros después del filtrado
    st.write("Columnas en alternativas_inventario_df después del filtrado:", alternativas_inventario_df.columns)
    st.write("Primeras filas de alternativas_inventario_df:", alternativas_inventario_df.head())

    # Agregar la columna faltante al hacer merge
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_inventario_df,
        on='cur',
        how='inner'
    )

    # Verificar si existen registros después del merge
    st.write("Columnas en alternativas_disponibles_df después del merge:", alternativas_disponibles_df.columns)
    st.write("Primeras filas de alternativas_disponibles_df:", alternativas_disponibles_df.head())

    # Ordenar por 'codart' y cantidad para priorizar las mejores opciones
    if 'codart' in alternativas_disponibles_df.columns and 'unidadespresentacionlote' in alternativas_disponibles_df.columns:
        alternativas_disponibles_df.sort_values(by=['codart', 'unidadespresentacionlote'], ascending=[True, False], inplace=True)
    else:
        st.error("Error: Columnas 'codart' o 'unidadespresentacionlote' no están presentes en alternativas_disponibles_df.")

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

    # Seleccionar las columnas finales deseadas, incluyendo las columnas adicionales seleccionadas
    columnas_finales = ['cur', 'codart', 'faltante', 'unidadespresentacionlote', 'bodega']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    
    # Filtrar solo las columnas que existen en el DataFrame
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

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
        file_name='alternativas_disponibles.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
