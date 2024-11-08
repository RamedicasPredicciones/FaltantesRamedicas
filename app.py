import streamlit as st
import pandas as pd
from io import BytesIO

# Cargar archivos privados de manera segura
@st.cache_data
def load_private_files():
    # Enlace directo para Inventario desde Google Drive
    inventario_url = "https://docs.google.com/spreadsheets/d/1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC/edit?usp=sharing&ouid=103276733743472138817&rtpof=true&sd=true"
    
    # Cargar ambos archivos, uno desde Drive y el otro localmente
    maestro_moleculas_df = pd.read_excel('Maestro_Moleculas.xlsx')
    inventario_api_df = pd.read_excel(inventario_url)
    
    return maestro_moleculas_df, inventario_api_df

# Función para extraer el nombre principal (sin la cantidad)
def extraer_nombre_principal(nombre):
    # Supongamos que el nombre principal termina antes de la 'x' que indica la cantidad
    if isinstance(nombre, str):
        return nombre.split(' x')[0].strip()  # Cortar el nombre antes de 'x' y quitar espacios
    return nombre

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales):
    # Normalizar nombres de columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Extraer el nombre principal de los faltantes para la comparación
    faltantes_df['nombre_principal'] = faltantes_df['nombre'].apply(extraer_nombre_principal)

    # Buscar las alternativas basadas en el nombre y cur
    alternativas_df = pd.merge(
        faltantes_df[['cur', 'nombre_principal', 'codart', 'faltante']],
        maestro_moleculas_df[['cur', 'nombre', 'codart']],
        left_on='nombre_principal',
        right_on='nombre',
        how='left',
        suffixes=('_faltante', '_alternativa')
    )

    # Buscar las alternativas en el inventario
    alternativas_inventario_df = pd.merge(
        alternativas_df,
        inventario_api_df[['cur', 'nomart', 'codart', 'unidadespresentacionlote', 'bodega']],
        left_on='cur',
        right_on='cur',
        how='inner',
        suffixes=('_alternativas', '_inventario')
    )

    # Filtrar por unidades en inventario y codart
    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) & 
        (alternativas_inventario_df['codart_alternativa'].isin(faltantes_df['codart']))
    ]

    # Renombrar las columnas para el resultado final
    alternativas_disponibles_df.rename(columns={
        'codart_alternativa': 'codart_faltante',
        'nomart': 'opcion_alternativa',
        'codart_inventario': 'codart_alternativa'
    }, inplace=True)

    # Crear una columna con las mejores alternativas
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart_faltante'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Filtrar opciones con cantidad suficiente
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            # Si no hay suficiente cantidad, tomar la opción con la mayor cantidad disponible
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
