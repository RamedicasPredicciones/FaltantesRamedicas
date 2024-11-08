import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivos privados de manera segura
@st.cache_data
def load_private_files():
    # Enlace directo para Inventario desde Google Drive
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/export?format=xlsx"
    
    # Cargar archivos de Drive
    inventario_api_df = pd.read_excel(inventario_url)
    maestro_moleculas_df = pd.read_excel('Maestro_Moleculas.xlsx')
    
    return maestro_moleculas_df, inventario_api_df

# Función para extraer el nombre principal antes de "x"
def extraer_nombre_principal(nombre):
    if "x" in nombre.lower():
        return nombre.lower().split("x")[0].strip()
    return nombre.lower().strip()

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales):
    # Normalizar nombres de columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Verificar columnas disponibles
    st.write("Columnas en el archivo de faltantes:", list(faltantes_df.columns))
    
    # Extraer nombres principales de faltantes
    faltantes_df['nombre_principal'] = faltantes_df['nombre'].apply(extraer_nombre_principal)
    nombre_principal_faltantes = faltantes_df['nombre_principal'].unique()

    # Obtener los CUR y codArt únicos de productos con faltantes
    cur_faltantes = faltantes_df['cur'].unique()
    codart_faltantes = faltantes_df['codart'].unique()

    # Filtrar el archivo Maestro_Moleculas para obtener registros con esos CUR
    alternativas_df = maestro_moleculas_df[maestro_moleculas_df['cur'].isin(cur_faltantes)]

    # Agregar búsqueda adicional por nombre principal de producto
    maestro_moleculas_df['nombre_principal'] = maestro_moleculas_df['nombre'].apply(extraer_nombre_principal)
    alternativas_nombre_df = maestro_moleculas_df[maestro_moleculas_df['nombre_principal'].isin(nombre_principal_faltantes)]

    # Combinar ambas alternativas (por CUR y por nombre principal)
    alternativas_combinadas_df = pd.concat([alternativas_df, alternativas_nombre_df]).drop_duplicates()

    # Cruzar estas alternativas con el inventario para verificar disponibilidad
    alternativas_inventario_df = pd.merge(
        alternativas_combinadas_df,
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
        faltantes_df[['cur', 'codart', 'faltante', 'nombre', 'nombre_principal']],
        alternativas_disponibles_df,
        left_on=['cur', 'codart', 'nombre_principal'],
        right_on=['cur', 'codart_faltante', 'nombre_principal'],
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

    # Seleccionar las columnas finales deseadas
    columnas_finales = ['cur', 'codart', 'faltante', 'nombre', 'codart_faltante', 'opcion_alternativa', 'codart_alternativa', 'unidadespresentacionlote', 'bodega']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    
    # Filtrar solo las columnas presentes en el DataFrame
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes Mejorado')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    maestro_moleculas_df, inventario_api_df = load_private_files()

    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir:",
        options=["presentacionArt", "numlote", "fechavencelote"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales)

    st.dataframe(resultado_final_df)

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        return output

    excel_file = to_excel(resultado_final_df)
    st.download_button(label="Descargar Excel", data=excel_file, file_name="resultado_faltantes.xlsx")
