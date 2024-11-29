import streamlit as st
import pandas as pd
import math
import requests
from io import BytesIO

# URL de la API
API_URL = "https://apkit.ramedicas.com/api/items/ws-batchsunits?token=3f8857af327d7f1adb005b81a12743bc17fef5c48f228103198100d4b032f556"

# URL del archivo de Excel adicional
EXCEL_URL = "https://docs.google.com/spreadsheets/d/19myWtMrvsor2P_XHiifPgn8YKdTWE39O/export?format=xlsx"

# URL de la plantilla en Google Sheets
PLANTILLA_URL = "https://docs.google.com/spreadsheets/d/1CPMBfCiuXq2_l8KY68HgexD-kyNVJ2Ml/export?format=xlsx"

# Función para devolver la URL de la plantilla
def descargar_plantilla():
    return PLANTILLA_URL

# Función para cargar el inventario desde la API y combinarlo con el archivo Excel adicional
def load_inventory_file():
    try:
        # Cargar inventario desde la API
        response = requests.get(API_URL, verify=False)
        response.raise_for_status()
        api_data = response.json()
        inventario_api_df = pd.DataFrame(api_data)

        st.write("Columnas originales del inventario de la API:", inventario_api_df.columns.tolist())
        
        # Renombrar la columna "unidadesPresentacionLote" a "Existencias codart alternativa", si existe
        if "unidadesPresentacionLote" in inventario_api_df.columns:
            inventario_api_df.rename(columns={"unidadesPresentacionLote": "Existencias codart alternativa"}, inplace=True)
        else:
            st.warning("La columna 'unidadesPresentacionLote' no está presente en el inventario de la API. Verifique los datos.")

        # Cargar datos adicionales desde el Excel
        datos_adicionales_df = pd.read_excel(EXCEL_URL)
        datos_adicionales_df.columns = datos_adicionales_df.columns.str.lower().str.strip()
        
        st.write("Columnas del archivo Excel adicional:", datos_adicionales_df.columns.tolist())

        # Verificar que las columnas necesarias estén presentes
        columnas_requeridas = ['codart', 'cur', 'carta', 'embalaje']
        columnas_disponibles = [col for col in columnas_requeridas if col in datos_adicionales_df.columns]
        
        if not columnas_disponibles:
            st.warning("El archivo de Excel adicional no contiene las columnas requeridas.")
            return inventario_api_df

        # Realizar el merge entre los dos datasets usando "codArt" y "codart"
        inventario_api_df = inventario_api_df.merge(
            datos_adicionales_df[columnas_disponibles], 
            left_on="codArt", 
            right_on="codart", 
            how="left"
        )
        
        st.write("Columnas combinadas después del merge:", inventario_api_df.columns.tolist())
        
        inventario_api_df.drop_duplicates(inplace=True)
        return inventario_api_df
    
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

# Función para procesar el archivo de faltantes
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    columnas_necesarias = {'cur', 'codart', 'faltante', 'embalaje'}
    if not columnas_necesarias.issubset(faltantes_df.columns):
        st.error(f"El archivo de faltantes debe contener las columnas: {', '.join(columnas_necesarias)}")
        return pd.DataFrame()

    st.write("Columnas actuales del inventario:", inventario_api_df.columns.tolist())

    if "existencias codart alternativa" not in inventario_api_df.columns:
        st.error("El inventario no contiene la columna 'Existencias codart alternativa'.")
        return pd.DataFrame()

    if "opcion" in inventario_api_df.columns:
        inventario_api_df.rename(columns={"opcion": "opcion_alternativa"}, inplace=True)

    if "opcion_alternativa" not in inventario_api_df.columns:
        st.warning("El inventario no contiene la columna 'opcion_alternativa'. Verifique los datos.")
        return pd.DataFrame()

    # Convertir 'opcion_alternativa' a numérico y limpiar datos no válidos
    inventario_api_df['opcion_alternativa'] = pd.to_numeric(inventario_api_df['opcion_alternativa'], errors='coerce')
    inventario_api_df = inventario_api_df.dropna(subset=['opcion_alternativa'])

    cur_faltantes = faltantes_df['cur'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]

    if bodega_seleccionada:
        alternativas_inventario_df = alternativas_inventario_df[alternativas_inventario_df['bodega'].isin(bodega_seleccionada)]

    alternativas_disponibles_df = alternativas_inventario_df[alternativas_inventario_df['existencias codart alternativa'] > 0]

    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'embalaje': 'embalaje_alternativa',
        'existencias codart alternativa': 'Existencias codart alternativa'
    }, inplace=True)

    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante', 'embalaje']],
        alternativas_disponibles_df,
        on='cur',
        how='inner'
    )

    alternativas_disponibles_df['opcion_alternativa'] = pd.to_numeric(
        alternativas_disponibles_df['opcion_alternativa'], errors='coerce'
    ).fillna(0)

    alternativas_disponibles_df['cantidad_necesaria'] = alternativas_disponibles_df.apply(
        lambda row: math.ceil(row['faltante'] * row['embalaje'] / row['embalaje_alternativa'])
        if pd.notnull(row['embalaje']) and pd.notnull(row['embalaje_alternativa']) and row['embalaje_alternativa'] > 0
        else None,
        axis=1
    )

    alternativas_disponibles_df = alternativas_disponibles_df[
        alternativas_disponibles_df['cantidad_necesaria'].notnull()
    ]

    columnas_resultado = ['cur', 'codart', 'faltante', 'embalaje', 'codart_alternativa', 
                          'embalaje_alternativa', 'Existencias codart alternativa', 'cantidad_necesaria']

    # Incluir columnas adicionales si están en el inventario
    for columna in columnas_adicionales:
        if columna in inventario_api_df.columns:
            columnas_resultado.append(columna)

    return alternativas_disponibles_df[columnas_resultado]

# Lógica principal de la aplicación
st.title("Gestión de Inventario y Faltantes")

# Botón para descargar la plantilla
if st.button("Descargar plantilla"):
    st.markdown(f"[Descargar plantilla]({descargar_plantilla()})", unsafe_allow_html=True)

# Cargar archivo de faltantes
archivo_faltantes = st.file_uploader("Sube el archivo de faltantes (Excel)", type=["xlsx"])

# Selección de bodegas
bodegas_disponibles = ["Bodega 1", "Bodega 2", "Bodega 3"]  # Reemplaza con tus bodegas reales
bodega_seleccionada = st.multiselect("Selecciona las bodegas para filtrar:", bodegas_disponibles)

# Cargar y combinar inventario
st.subheader("Cargando inventario desde la API...")
inventario_api_df = load_inventory_file()

if archivo_faltantes:
    faltantes_df = pd.read_excel(archivo_faltantes)
    columnas_adicionales = ['columna_extra_1', 'columna_extra_2']  # Reemplaza con columnas adicionales necesarias

    st.subheader("Procesando archivo de faltantes...")
    resultado_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada)

    if not resultado_df.empty:
        st.success("Archivo procesado exitosamente. A continuación, los resultados:")
        st.dataframe(resultado_df)

        # Botón para descargar el archivo procesado
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            resultado_df.to_excel(writer, index=False, sheet_name="Resultado")
            writer.save()
            buffer.seek(0)
        
        st.download_button(
            label="Descargar archivo procesado",
            data=buffer,
            file_name="resultado_faltantes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No se encontraron alternativas disponibles en el inventario.")
