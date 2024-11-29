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

    alternativas_disponibles_df = alternativas_disponibles_df[alternativas_disponibles_df['opcion_alternativa'] > 0]

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
        mejor_opcion_bodega = group[group['Existencias codart alternativa'] >= faltante_cantidad]
        mejor_opcion = mejor_opcion_bodega.head(1) if not mejor_opcion_bodega.empty else group.nlargest(1, 'Existencias codart alternativa')
        if not mejor_opcion.empty:
            mejores_alternativas.append(mejor_opcion.iloc[0])

    if not mejores_alternativas:
        st.warning("No se encontraron alternativas para los faltantes.")
        return pd.DataFrame()

    resultado_final_df = pd.DataFrame(mejores_alternativas)
    resultado_final_df['suplido'] = resultado_final_df.apply(
        lambda row: 'SI' if row['Existencias codart alternativa'] >= row['cantidad_necesaria'] else 'NO',
        axis=1
    )

    resultado_final_df['faltante_restante alternativa'] = resultado_final_df.apply(
        lambda row: row['cantidad_necesaria'] - row['Existencias codart alternativa'] if row['suplido'] == 'NO' else 0,
        axis=1
    )

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

# Botones de descarga y actualización
st.markdown(
    f"""
    <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 10px; margin-top: 20px;">
        <a href="{descargar_plantilla()}" download>
            <button style="background-color: #FF5800; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">
                Descargar plantilla de faltantes
            </button>
        </a>
        <button onclick="window.location.reload()" style="background-color: #3A86FF; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">
            Actualizar inventario
        </button>
    </div>
    """,
    unsafe_allow_html=True
)

# Archivo cargado por el usuario
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_file()

    if not inventario_api_df.empty:
        bodegas_disponibles = inventario_api_df['bodega'].unique().tolist()
        bodega_seleccionada = st.multiselect("Seleccione la bodega", options=bodegas_disponibles, default=[])

        columnas_adicionales = st.multiselect(
            "Selecciona columnas adicionales para incluir en el archivo final:",
            options=["presentacionart", "numlote", "fechavencelote"],
            default=[]
        )

        resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada)

        if not resultado_final_df.empty:
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
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("No se pudo cargar el inventario desde la API.")
