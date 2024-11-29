import streamlit as st
import pandas as pd
import math
import requests
from io import BytesIO

# URL del archivo Excel para enriquecer la API
EXCEL_URL = "https://docs.google.com/spreadsheets/d/19myWtMrvsor2P_XHiifPgn8YKdTWE39O/export?format=xlsx"

# URL de la API que quieres leer
API_URL = "https://apkit.ramedicas.com/api/items/ws-batchsunits?token=3f8857af327d7f1adb005b81a12743bc17fef5c48f228103198100d4b032f556"

# Función para cargar los datos de la API
def load_api_data():
    response = requests.get(API_URL, verify=False)
    if response.status_code == 200:
        api_data = response.json()
        api_df = pd.DataFrame(api_data)
        return api_df
    else:
        st.error(f"Error al obtener datos de la API: {response.status_code}")
        return pd.DataFrame()

# Función para cargar el archivo Excel con las columnas adicionales
def load_excel_file():
    excel_df = pd.read_excel(EXCEL_URL)
    return excel_df

# Función para enriquecer el inventario API con datos del Excel
def enriquecer_inventario(api_df, excel_df):
    # Normalizar nombres de columnas (eliminar espacios y uniformar)
    api_df.columns = api_df.columns.str.lower().str.strip()
    excel_df.columns = excel_df.columns.str.lower().str.strip()

    # Renombrar columnas de la API según el formato necesario
    api_df.rename(columns={'codart': 'codart_api'}, inplace=True)

    # Realizar un merge por cada columna del Excel para enriquecer la API
    columnas_a_enriquecer = ['embalaje', 'cur', 'carta']
    for columna in columnas_a_enriquecer:
        if columna in excel_df.columns:
            api_df = pd.merge(
                api_df,
                excel_df[['codart', columna]].rename(columns={'codart': 'codart_excel'}),
                left_on='codart_api',  # Clave en la API
                right_on='codart_excel',  # Clave en el Excel
                how='left'
            )
            # Renombrar la columna agregada para mantener claridad
            api_df.rename(columns={columna: f'{columna}_excel'}, inplace=True)
        else:
            st.warning(f"La columna '{columna}' no se encontró en el archivo Excel.")

    # Limpiar la columna auxiliar 'codart_excel'
    api_df.drop(columns=['codart_excel'], inplace=True, errors='ignore')

    # Verificar si faltan valores en las columnas enriquecidas
    for columna in columnas_a_enriquecer:
        if api_df[f'{columna}_excel'].isnull().any():
            st.warning(f"Algunos códigos de artículo no tienen coincidencia para la columna '{columna}' en el Excel.")

    return api_df

# Función para procesar faltantes
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    # Verificar que el archivo de faltantes tiene las columnas necesarias
    columnas_necesarias = {'cur', 'codart', 'faltante', 'embalaje'}
    if not columnas_necesarias.issubset(faltantes_df.columns):
        st.error(f"El archivo de faltantes debe contener las columnas: {', '.join(columnas_necesarias)}")
        return pd.DataFrame()  # Devuelve un DataFrame vacío si faltan columnas

    cur_faltantes = faltantes_df['cur'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur_excel'].isin(cur_faltantes)]

    if bodega_seleccionada:
        alternativas_inventario_df = alternativas_inventario_df[alternativas_inventario_df['bodega'].isin(bodega_seleccionada)]

    alternativas_disponibles_df = alternativas_inventario_df[alternativas_inventario_df['unidadespresentacionlote'] > 0]

    alternativas_disponibles_df.rename(columns={
        'codart_api': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'embalaje_excel': 'embalaje_alternativa',
        'unidadespresentacionlote': 'Existencias codart alternativa'
    }, inplace=True)

    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante', 'embalaje']],
        alternativas_disponibles_df,
        left_on='cur',
        right_on='cur_excel',
        how='inner'
    )

    # Filtrar registros donde opcion_alternativa sea mayor a 0
    alternativas_disponibles_df = alternativas_disponibles_df[alternativas_disponibles_df['opcion_alternativa'] > 0]

    # Agregar columna de cantidad necesaria ajustada por embalaje
    alternativas_disponibles_df['cantidad_necesaria'] = alternativas_disponibles_df.apply(
        lambda row: math.ceil(row['faltante'] * row['embalaje'] / row['embalaje_alternativa'])
        if pd.notnull(row['embalaje']) and pd.notnull(row['embalaje_alternativa']) and row['embalaje_alternativa'] > 0
        else None,
        axis=1
    )

    alternativas_disponibles_df.sort_values(by=['codart', 'Existencias codart alternativa'], inplace=True)

    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Buscar en la bodega seleccionada
        mejor_opcion_bodega = group[group['Existencias codart alternativa'] >= faltante_cantidad]
        mejor_opcion = mejor_opcion_bodega.head(1) if not mejor_opcion_bodega.empty else group.nlargest(1, 'Existencias codart alternativa')
        
        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Nuevas columnas para verificar si el faltante fue suplido y el faltante restante
    resultado_final_df['suplido'] = resultado_final_df.apply(
        lambda row: 'SI' if row['Existencias codart alternativa'] >= row['cantidad_necesaria'] else 'NO',
        axis=1
    )

    # Renombrar la columna faltante_restante a faltante_restante alternativa
    resultado_final_df['faltante_restante alternativa'] = resultado_final_df.apply(
        lambda row: row['cantidad_necesaria'] - row['Existencias codart alternativa'] if row['suplido'] == 'NO' else 0,
        axis=1
    )

    # Selección de las columnas finales a mostrar
    columnas_finales = ['cur', 'codart', 'faltante', 'embalaje', 'codart_alternativa', 'opcion_alternativa', 
                        'embalaje_alternativa', 'cantidad_necesaria', 'Existencias codart alternativa', 'bodega', 'suplido', 
                        'faltante_restante alternativa']
    columnas_finales.extend([col.lower() for col in columnas_adicionales])
    columnas_presentes = [col for col in columnas_finales if col in resultado_final_df.columns]
    resultado_final_df = resultado_final_df[columnas_presentes]

    return resultado_final_df

# Interfaz de Streamlit
st.markdown(
    """
    <h1 style="text-align: center; color: #FF5800; font-family: Arial, sans-serif;">
        RAMEDICAS S.A.S.
    </h1>
    <h3 style="text-align: center; font-family: Arial, sans-serif; color: #3A86FF;">
        Generador de Alternativas para Faltantes
    </h3>
    <p style="text-align: center; font-family: Arial, sans-serif; color: #6B6B6B;">
        Esta herramienta te permite buscar el código alternativa para cada faltante de los pedidos en Ramédicas con su respectivo inventario actual.
    </p>
    """, unsafe_allow_html=True
)

# Función para devolver la URL de la plantilla
def descargar_plantilla():
    return EXCEL_URL

# Sección de botones alineados a la izquierda
st.markdown(
    f"""
    <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 10px; margin-top: 20px;">
        <a href="{descargar_plantilla()}" download>
            <button style="background-color: #FF5800; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">
                Descargar plantilla
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True
)
