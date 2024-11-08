import streamlit as st
import pandas as pd
from io import BytesIO
import gdown

# Cargar archivos privados desde Google Drive
@st.cache_data
def load_private_files():
    # URL del archivo en Google Drive (asegúrate de obtener la URL de descarga directa)
    inventario_url = "https://drive.google.com/uc?id=1WV4la88gTl6OUgqQ5UM0IztNBn_k4VrC"

    # Descargar el archivo de inventario desde Google Drive
    output = 'inventario_api.xlsx'
    gdown.download(inventario_url, output, quiet=False)
    
    # Cargar archivos
    maestro_moleculas_df = pd.read_excel('Maestro_Moleculas.xlsx')
    inventario_api_df = pd.read_excel(output)
    
    return maestro_moleculas_df, inventario_api_df

# Función para extraer el nombre principal (sin la cantidad)
def extraer_nombre_principal(nombre):
    if isinstance(nombre, str):
        return nombre.split(' x')[0].strip()  # Cortar el nombre antes de 'x' y quitar espacios
    return nombre

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    faltantes_df['nombre_principal'] = faltantes_df['nombre'].apply(extraer_nombre_principal)

    alternativas_df = pd.merge(
        faltantes_df[['cur', 'nombre_principal', 'codart', 'faltante']],
        maestro_moleculas_df[['cur', 'nombre', 'codart']],
        left_on='nombre_principal',
        right_on='nombre',
        how='left',
        suffixes=('_faltante', '_alternativa')
    )

    alternativas_inventario_df = pd.merge(
        alternativas_df,
        inventario_api_df[['cur', 'nomart', 'codart', 'unidadespresentacionlote', 'bodega']],
        left_on='cur',
        right_on='cur',
        how='inner',
        suffixes=('_alternativas', '_inventario')
    )

    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['unidadespresentacionlote'] > 0) & 
        (alternativas_inventario_df['codart_alternativa'].isin(faltantes_df['codart']))
    ]

    alternativas_disponibles_df.rename(columns={
        'codart_alternativa': 'codart_faltante',
        'nomart': 'opcion_alternativa',
        'codart_inventario': 'codart_alternativa'
    }, inplace=True)

    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart_faltante'):
        faltante_cantidad = group['faltante'].iloc[0]
        mejor_opcion = group[group['unidadespresentacionlote'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            mejor_opcion = group.nlargest(1, 'unidadespresentacionlote')

        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    columnas_finales = ['cur', 'codart', 'faltante', 'codart_faltante', 'opcion_alternativa', 'codart_alternativa', 'unidadespresentacionlote', 'bodega']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    maestro_moleculas_df, inventario_api_df = load_private_files()

    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionArt", "numlote", "fechavencelote"],
        default=[]
    )

    resultado_final_df = procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df, columnas_adicionales)

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
