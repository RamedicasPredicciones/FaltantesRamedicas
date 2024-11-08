import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivos privados de manera segura
@st.cache_data
def load_private_files():
    # Enlace directo para Inventario desde Google Drive
    inventario_url = "https://drive.google.com/uc?export=download&id=1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC"
    
    # Cargar ambos archivos, uno desde Drive y el otro localmente
    maestro_moleculas_df = pd.read_excel('Maestro_Moleculas.xlsx')
    inventario_api_df = pd.read_excel(inventario_url)
    
    return maestro_moleculas_df, inventario_api_df

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales):
    # Normalizar nombres de columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Obtener los CUR y codArt únicos de productos con faltantes
    cur_faltantes = faltantes_df['cur'].unique()
    codart_faltantes = faltantes_df['codart'].unique()

    # Filtrar el archivo Maestro_Moleculas para obtener registros con esos CUR
    alternativas_df = maestro_moleculas_df[maestro_moleculas_df['cur'].isin(cur_faltantes)]

    # Cruzar estas alternativas con el inventario para verificar disponibilidad
    alternativas_inventario_df = pd.merge(
        alternativas_df,
        inventario_api_df,
        on='cur',
        how='inner',
        suffixes=('_alternativas', '_inventario')
    )

    # Filtrar filas donde la cantidad en inventario sea mayor a cero y el codart esté en la lista de faltantes
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) &
        (alternativas_inventario_df['codart_alternativas'].isin(codart_faltantes))
    ]

    # Renombrar columnas para el archivo final
    alternativas_disponibles_df.rename(columns={
        'codart_alternativas': 'codart_faltante',
        'opcion_inventario': 'opcion_alternativa',
        'codart_inventario': 'codart_alternativa'
    }, inplace=True)

    # Agregar la columna faltante al hacer merge
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_disponibles_df,
        left_on=['cur', 'codart'],
        right_on=['cur', 'codart_faltante'],
        how='inner'
    )

    # Ordenar por 'codart_faltante' y 'opcion_alternativa' para priorizar las mejores opciones
    alternativas_disponibles_df.sort_values(by=['codart_faltante', 'opcion_alternativa'], inplace=True)

    # Seleccionar la mejor alternativa para cada faltante
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart_faltante'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Filtrar opciones que tienen cantidad mayor o igual al faltante y obtener la mejor
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            # Si no hay opción suficiente, tomar la mayor cantidad disponible
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')

        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Seleccionar las columnas finales deseadas, incluyendo las columnas adicionales seleccionadas
    columnas_finales = ['cur', 'codart', 'faltante', 'codart_faltante', 'opcion_alternativa', 'codart_alternativa', 'unidadespresentacionlote', 'bodega']
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
    maestro_moleculas_df, inventario_api_df = load_private_files()

    # Seleccionar columnas adicionales para el archivo final
    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionArt", "numlote", "fechavencelote"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales)

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
    
