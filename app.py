import requests
import pandas as pd
from io import BytesIO

# 1. Descargar inventario desde la API (formato JSON -> Excel)
url_inventario = "https://apkit.ramedicas.com/api/items/ws-batchsunits?token=3f8857af327d7f1adb005b81a12743bc17fef5c48f228103198100d4b032f556"
response = requests.get(url_inventario, verify=False)

if response.status_code == 200:
    # Convertir la respuesta en formato JSON a un DataFrame
    data_inventario = response.json()
    inventario_df = pd.DataFrame(data_inventario)

    # Normalizar las columnas para evitar discrepancias en mayúsculas/minúsculas
    inventario_df.columns = inventario_df.columns.str.lower().str.strip()

    # Guardar el DataFrame como un archivo Excel
    inventario_df.to_excel("productos_completos.xlsx", index=False)

    # Mostrar el DataFrame (opcional)
    print(inventario_df.head())
else:
    print(f"Error al obtener datos de la API: {response.status_code}")


# 2. Cargar el archivo de Google Sheets con las columnas "cur" y "embalaje"
url_plantilla = "https://docs.google.com/spreadsheets/d/19myWtMrvsor2P_XHiifPgn8YKdTWE39O/edit?usp=sharing&ouid=109532697276677589725&rtpof=true&sd=true"
url_plantilla = url_plantilla.replace('/edit?usp=sharing', '/export?format=xlsx')

# Cargar el archivo Excel desde Google Sheets
plantilla_df = pd.read_excel(url_plantilla)

# Normalizar las columnas para evitar discrepancias en mayúsculas/minúsculas
plantilla_df.columns = plantilla_df.columns.str.lower().str.strip()

# Mostrar las primeras filas del archivo de la plantilla (opcional)
print(plantilla_df.head())

# 3. Hacer el "merge" para agregar las columnas 'cur' y 'embalaje' al inventario
inventario_completo_df = pd.merge(
    inventario_df,
    plantilla_df[['codart', 'cur', 'embalaje']],  # Seleccionamos solo las columnas relevantes
    on='codart',  # Nos aseguramos de hacer la fusión por la columna 'codart' en minúsculas
    how='left'  # 'left' para mantener todos los registros del inventario original
)

# Mostrar el DataFrame final (opcional)
print(inventario_completo_df.head())

# Guardar el inventario combinado en un archivo Excel
inventario_completo_df.to_excel("inventario_completo.xlsx", index=False)

# Función para procesar el archivo de faltantes
def procesar_faltantes(faltantes_df, inventario_api_df, columnas_adicionales, bodega_seleccionada):
    # Normalizar las columnas
    faltantes_df.columns = faltantes_df.columns.str.lower().str.strip()
    inventario_api_df.columns = inventario_api_df.columns.str.lower().str.strip()

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

    alternativas_disponibles_df.rename(columns={
        'codart': 'codart_alternativa',
        'opcion': 'opcion_alternativa',
        'embalaje': 'embalaje_alternativa',
        'unidadespresentacionlote': 'Existencias codart alternativa'
    }, inplace=True)

    alternativas_disponibles_df = pd.merge(
        faltantes_df[['cur', 'codart', 'faltante', 'embalaje']],
        alternativas_disponibles_df,
        on='cur',
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

