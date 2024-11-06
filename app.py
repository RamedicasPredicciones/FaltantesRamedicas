import streamlit as st
import pandas as pd

# Cargar archivos privados de manera segura
@st.cache_data
def load_private_files():
    # Enlace directo para Inventario desde Google Drive
    inventario_url = "https://drive.google.com/uc?export=download&id=1oym_KRpUduqS7LoIy361RYEXA_fe-U6l"
    
    # Cargar ambos archivos, uno desde Drive y el otro localmente
    maestro_moleculas_df = pd.read_excel('Maestro_Moleculas.xlsx')
    inventario_api_df = pd.read_excel(inventario_url)
    
    return maestro_moleculas_df, inventario_api_df

# Función para procesar el archivo de faltantes y generar el resultado
def procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df):
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    maestro_moleculas_df.columns = maestro_moleculas_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

    cur_faltantes = faltantes_df['cur'].unique()
    codart_faltantes = faltantes_df['codart'].unique()

    alternativas_df = maestro_moleculas_df[maestro_moleculas_df['cur'].isin(cur_faltantes)]

    alternativas_inventario_df = pd.merge(
        alternativas_df,
        inventario_api_df,
        on='cur',
        how='inner',
        suffixes=('_alternativas', '_inventario')
    )

    alternativas_disponibles_df = alternativas_inventario_df[
        (alternativas_inventario_df['cantidad'] > 0) &
        (alternativas_inventario_df['codart_alternativas'].isin(codart_faltantes))
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

    # Ordenar por 'codart_faltante' y 'opcion_alternativa' para priorizar las mejores opciones
    alternativas_disponibles_df.sort_values(by=['codart_faltante', 'opcion_alternativa'], inplace=True)

    # Seleccionar la mejor alternativa para cada faltante
    mejores_alternativas = []
    for codart_faltante, group in alternativas_disponibles_df.groupby('codart_faltante'):
        faltante_cantidad = group['faltante'].iloc[0]

        # Filtrar opciones que tienen cantidad mayor o igual al faltante y obtener la mejor
        mejor_opcion = group[group['cantidad'] >= faltante_cantidad].head(1)

        if mejor_opcion.empty:
            # Si no hay opción suficiente, tomar la mayor cantidad disponible
            mejor_opcion = group.nlargest(1, 'cantidad')

        mejores_alternativas.append(mejor_opcion.iloc[0])

    resultado_final_df = pd.DataFrame(mejores_alternativas)

    # Seleccionar las columnas finales deseadas
    columnas_finales = ['cur', 'codart', 'faltante', 'codart_faltante', 'opcion_alternativa', 'codart_alternativa', 'cantidad', 'bodega']
    resultado_final_df = resultado_final_df[columnas_finales]

    return resultado_final_df

# Streamlit UI
st.title('Generador de Alternativas de Faltantes')

uploaded_file = st.file_uploader("Sube tu archivo de faltantes", type="xlsx")

if uploaded_file:
    faltantes_df = pd.read_excel(uploaded_file)
    maestro_moleculas_df, inventario_api_df = load_private_files()

    resultado_final_df = procesar_faltantes(faltantes_df, maestro_moleculas_df, inventario_api_df)

    st.write("Archivo procesado correctamente.")
    st.dataframe(resultado_final_df)

    # Botón para descargar el archivo generado
    st.download_button(
        label="Descargar archivo de alternativas",
        data=resultado_final_df.to_excel(index=False, engine='openpyxl'),
        file_name='alternativas_disponibles.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
