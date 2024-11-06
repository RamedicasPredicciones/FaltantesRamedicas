import streamlit as st
import pandas as pd
from io import BytesIO

# Agregar fondo personalizado con CSS
st.markdown(
    """
    <style>
    body {
        background-color: #f2f2f2;  # Color de fondo de la página
        color: #333;  # Color del texto
    }
    .stButton>button {
        background-color: #4CAF50;  # Botón con color verde
        color: white;  # Color del texto del botón
        border: none;
        border-radius: 5px;
        padding: 10px 20px;
        font-size: 16px;
    }
    .stButton>button:hover {
        background-color: #45a049;  # Hover color más oscuro
    }
    .stTitle {
        color: #2a6a6a;  # Color del título
    }
    .stDataFrame {
        background-color: #ffffff;  # Fondo blanco para las tablas
        border-radius: 10px;  # Bordes redondeados
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_seleccionadas):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    cur_faltantes = faltantes_df['cur'].unique()
    codArt_faltantes = faltantes_df['codart'].unique()

    alternativas_df = maestro_moleculas_df[maestro_moleculas_df['cur'].isin(cur_faltantes)]

    alternativas_inventario_df = pd.merge(
        alternativas_df,
        inventario_api_df,
        on='cur',
        how='inner',
        suffixes=('_alternativas', '_inventario')
    )

    # Cambié 'unidadeslote' por 'unidadespresentacionlote'
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) &
        (alternativas_inventario_df['codart_alternativas'].isin(codArt_faltantes))
    ]

    alternativas_disponibles_df.rename(columns={ 
        'codart_alternativas': 'codart_faltante',
        'opcion_inventario': 'opcion_alternativa',
        'codart_inventario': 'codart_alternativa'
    }, inplace=True)

    # Agregar la columna `faltante` al hacer merge
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante']],
        alternativas_disponibles_df,
        left_on=['cur', 'codart'],
        right_on=['cur', 'codart_faltante'],
        how='inner'
    )

    # Seleccionar columnas adicionales basadas en la selección del usuario
    for columna in columnas_seleccionadas:
        if columna in inventario_api_df.columns:
            alternativas_disponibles_df[columna] = alternativas_disponibles_df[f'{columna}_inventario']
    
    # Ordenar por 'codart_faltante' y 'opcion_alternativa' para priorizar las mejores opciones
    alternativas_disponibles_df.sort_values(by=['codart_faltante', 'opcion_alternativa'], inplace=True)

    # Seleccionar la mejor alternativa para cada faltante
    mejores_alternativas = []
    for codArt_faltante, group in alternativas_disponibles_df.groupby('codart_faltante'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Filtrar opciones que tienen cantidad mayor o igual al faltante y obtener la mejor
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            # Si no hay opción suficiente, tomar la mayor cantidad disponible
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')

        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Seleccionar las columnas finales deseadas, asegurándonos de que todas existan
    columnas_finales = ['cur', 'codart', 'faltante', 'codart_faltante', 'opcion_alternativa', 'codart_alternativa', 'unidadespresentacionlote', 'bodega']
    for columna in columnas_seleccionadas:
        if columna in resultado_final_df.columns:
            columnas_finales.append(columna)

    resultado_final_df = resultado_final_df[columnas_finales]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    maestro_moleculas_df, inventario_api_df = load_private_files()

    # Opciones para agregar columnas del inventario
    columnas_disponibles = ['nomart', 'presentacionart', 'descontinuado', 'numlote', 'fechavencelote', 'unidadeslote', 'bodega']
    columnas_seleccionadas = st.multiselect("Selecciona las columnas que deseas agregar", columnas_disponibles)

    resultado_final_df = procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_seleccionadas)

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
