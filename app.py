import streamlit as st
import pandas as pd
import math
from io import BytesIO
import requests

# Enlace del inventario API y del archivo de Excel con codArt y demás detalles
API_URL = "https://apkit.ramedicas.com/api/items/ws-batchsunits?token=3f8857af327d7f1adb005b81a12743bc17fef5c48f228103198100d4b032f556"
EXCEL_URL = "https://docs.google.com/spreadsheets/d/19myWtMrvsor2P_XHiifPgn8YKdTWE39O/export?format=xlsx"

# Función para cargar los datos de la API
def load_inventory_api():
    response = requests.get(API_URL)
    if response.status_code == 200:
        # Suponiendo que la respuesta de la API es en formato JSON
        inventario_api_df = pd.DataFrame(response.json())  
        return inventario_api_df
    else:
        st.error("Error al cargar los datos desde la API.")
        return pd.DataFrame()

# Función para cargar el archivo de Excel que contiene las columnas 'cur', 'codart', 'embalaje'
def load_excel_inventory():
    excel_inventory_df = pd.read_excel(EXCEL_URL)
    return excel_inventory_df

# Función para procesar los faltantes y agregar las columnas necesarias del inventario
def procesar_faltantes(faltantes_df, inventario_api_df, excel_inventory_df, columnas_adicionales, bodega_seleccionada):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()
    excel_inventory_df.columns = excel_inventory_df.columns.str.lower().str.strip()

    # Verificar que el archivo de faltantes tiene las columnas necesarias
    columnas_necesarias = {'cur', 'codart', 'faltante', 'embalaje'}
    if not columnas_necesarias.issubset(faltantes_df.columns):
        st.error(f"El archivo de faltantes debe contener las columnas: {', '.join(columnas_necesarias)}")
        return pd.DataFrame()  # Devuelve un DataFrame vacío si faltan columnas

    cur_faltantes = faltantes_df['cur'].unique()
    alternativas_inventario_df = inventario_api_df[inventario_api_df['cur'].isin(cur_faltantes)]

    if bodega_seleccionada:
        alternativas_inventario_df = alternativas_inventario_df[alternativas_inventario_df['bodega'].isin(bodega_seleccionada)]

    alternativas_disponibles_df = alternativas_inventario_df[alternativas_inventario_df['unidadespresentacionlote'] > 0]

    # Agregar las columnas de alternativas desde el archivo de Excel basado en 'codart'
    alternativas_disponibles_df = pd.merge(
        alternativas_disponibles_df, 
        excel_inventory_df[['codart', 'cur', 'embalaje']], 
        on='codart', 
        how='left'
    )

    # Renombrar columnas para mayor claridad
    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'embalaje': 'embalaje_alternativa',
        'unidadespresentacionlote': 'Existencias codart alternativa'
    }, inplace=True)

    # Unir con el archivo de faltantes
    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante', 'embalaje']],
        alternativas_disponibles_df,
        on='cur',
        how='inner'
    )

    # Filtrar registros donde la opción alternativa sea mayor a 0
    alternativas_disponibles_df = alternativas_disponibles_df[alternativas_disponibles_df['opcion_alternativa'] > 0]

    # Agregar columna de cantidad necesaria ajustada por embalaje
    alternativas_disponibles_df['cantidad_necesaria'] = alternativas_disponibles_df.apply(
        lambda row: math.ceil(row['faltante'] * row['embalaje'] / row['embalaje_alternativa'])
        if pd.notnull(row['embalaje']) and pd.notnull(row['embalaje_alternativa']) and row['embalaje_alternativa'] > 0
        else None,
        axis=1
    )

    # Ordenar los resultados
    alternativas_disponibles_df.sort_values(by=['codart', 'Existencias codart alternativa'], inplace=True)

    # Buscar la mejor opción de alternativa
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Buscar en la bodega seleccionada
        mejor_opcion_bodega = group[group['Existencias codart alternativa'] >= faltante_cantidad]
        mejor_opcion = mejor_opcion_bodega.head(1) if not mejor_opcion_bodega.empty else group.nlargest(1, 'Existencias codart alternativa')
        
        mejores_alternativas.append(mejor_opcion.iloc[0])

    # Resultado final
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
    return "https://docs.google.com/spreadsheets/d/1CPMBfCiuXq2_l8KY68HgexD-kyNVJ2Ml/export?format=xlsx"

# Sección de botones alineados a la izquierda
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

# Cargar los archivos cargados por el usuario
uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    inventario_api_df = load_inventory_api()
    excel_inventory_df = load_excel_inventory()

    bodegas_disponibles = inventario_api_df['bodega'].unique().tolist()
    bodega_seleccionada = st.multiselect("Seleccione la bodega", options=bodegas_disponibles, default=[])

    columnas_adicionales = st.multiselect(
        "Selecciona columnas adicionales para incluir en el archivo final:",
        options=["presentacionart", "numlote", "disponibilidadlote", "fechaimportacion"]
    )

    if st.button("Generar archivo de alternativas"):
        if not faltantes_df.empty and not inventario_api_df.empty and not excel_inventory_df.empty:
            resultado_final_df = procesar_faltantes(faltantes_df, inventario_api_df, excel_inventory_df, columnas_adicionales, bodega_seleccionada)
            if not resultado_final_df.empty:
                st.write("Archivo generado exitosamente!")
                st.dataframe(resultado_final_df)

                # Crear archivo Excel con el DataFrame de resultados
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    resultado_final_df.to_excel(writer, index=False, sheet_name="Alternativas")
                st.download_button(
                    label="Descargar archivo de alternativas",
                    data=output.getvalue(),
                    file_name="alternativas_faltantes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.error("Por favor, asegúrate de haber cargado los archivos correctamente.")
