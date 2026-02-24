# -*- coding: utf-8 -*-
"""
app.py
------
Frontend Streamlit para cargar un archivo PILA TXT,
parsearlo con seguridad_social_parte1.py y descargarlo como CSV.
"""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from seguridad_social_parte1 import (
    exportar_csv,
    parse_pila_txt,
    resumen_planilla,
)

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PILA – Seguridad Social",
    page_icon="📋",
    layout="wide",
)

st.title("📋 PILA – Seguridad Social")
st.markdown(
    "Carga un archivo PILA en formato **TXT** (ancho fijo) para convertirlo a CSV "
    "y visualizar los aportes de seguridad social."
)

# ---------------------------------------------------------------------------
# Carpeta de salida por defecto (relativa al script)
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).parent
SALIDA_DIR  = BASE_DIR / "Salida"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Sidebar – configuración
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    sep_csv = st.radio(
        "Separador CSV",
        options=[";", ",", "|"],
        index=0,
        help="Separador para el archivo CSV de salida.",
    )
    guardar_en_disco = st.checkbox(
        "Guardar CSV en carpeta Salida",
        value=True,
        help=f"Guarda el archivo en:\n{SALIDA_DIR}",
    )
    st.markdown("---")
    st.caption("seguridad_social_parte1.py v1.0")

# ---------------------------------------------------------------------------
# Carga del archivo
# ---------------------------------------------------------------------------
archivo = st.file_uploader(
    "Selecciona el archivo PILA (.TxT / .txt)",
    type=["txt", "TxT", "TXT"],
    accept_multiple_files=False,
)

if archivo is None:
    st.info("👆 Sube un archivo PILA TXT para comenzar.")
    st.stop()

# ---------------------------------------------------------------------------
# Parseo
# ---------------------------------------------------------------------------
with st.spinner("Procesando archivo..."):
    contenido_bytes = archivo.read()
    df, info_empresa, info_totales = parse_pila_txt(contenido_bytes)

# ---------------------------------------------------------------------------
# Resumen general
# ---------------------------------------------------------------------------
resumen = resumen_planilla(df, info_empresa)

st.success(f"Archivo procesado: **{archivo.name}**  |  {len(df):,} registros tipo 02")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Empleados únicos",   f"{resumen['empleados_unicos']:,}")
col2.metric("Total IBC",          f"${resumen['total_ibc']:,.0f}")
col3.metric("Total Pensión",      f"${resumen['total_pension']:,.0f}")
col4.metric("Total EPS",          f"${resumen['total_eps']:,.0f}")
col5.metric("Total ARL",          f"${resumen['total_arl']:,.0f}")

with st.expander("ℹ️ Información empresa / encabezado"):
    st.json(info_empresa)

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.subheader("🔍 Filtros")
fcol1, fcol2, fcol3, fcol4 = st.columns(4)

with fcol1:
    opciones_eps = sorted(df['cod_eps'].dropna().unique().tolist()) if 'cod_eps' in df.columns else []
    filtro_eps = st.multiselect("EPS", opciones_eps, default=[])

with fcol2:
    opciones_ccf = sorted(df['cod_ccf'].dropna().unique().tolist()) if 'cod_ccf' in df.columns else []
    filtro_ccf = st.multiselect("CCF", opciones_ccf, default=[])

with fcol3:
    opciones_tipo_cot = sorted(df['tipo_cotizante'].dropna().unique().tolist()) if 'tipo_cotizante' in df.columns else []
    filtro_tipo_cot = st.multiselect("Tipo cotizante", opciones_tipo_cot, default=[])

with fcol4:
    buscar_nombre = st.text_input("Buscar nombre / documento", "")

# Aplicar filtros
df_filtrado = df.copy()

if filtro_eps:
    df_filtrado = df_filtrado[df_filtrado['cod_eps'].isin(filtro_eps)]

if filtro_ccf:
    df_filtrado = df_filtrado[df_filtrado['cod_ccf'].isin(filtro_ccf)]

if filtro_tipo_cot:
    df_filtrado = df_filtrado[df_filtrado['tipo_cotizante'].isin(filtro_tipo_cot)]

if buscar_nombre:
    mask = (
        df_filtrado.get('nombre_completo', pd.Series(dtype=str))
        .str.contains(buscar_nombre.upper(), case=False, na=False)
        |
        df_filtrado.get('num_doc', pd.Series(dtype=str))
        .str.contains(buscar_nombre, case=False, na=False)
    )
    df_filtrado = df_filtrado[mask]

st.caption(f"Mostrando {len(df_filtrado):,} de {len(df):,} registros")

# ---------------------------------------------------------------------------
# Tabla de datos
# ---------------------------------------------------------------------------
st.subheader("📊 Datos de empleados")

# Columnas más relevantes para mostrar por defecto
cols_mostrar_default = [
    'secuencia', 'tipo_doc', 'num_doc', 'nombre_completo',
    'tipo_cotizante', 'cod_municipio',
    'cod_eps', 'cod_ccf',
    'dias_eps', 'dias_pension',
    'ibc', 'aporte_pension', 'aporte_eps', 'aporte_arl', 'aporte_ccf',
    'ind_ingreso', 'ind_retiro', 'ind_licencia',
    'fecha_inicio_novedad', 'fecha_fin_novedad',
]
cols_disponibles = [c for c in cols_mostrar_default if c in df_filtrado.columns]
cols_extra_disp  = [c for c in df_filtrado.columns if c not in cols_mostrar_default]

with st.expander("Seleccionar columnas a mostrar", expanded=False):
    todas_cols = cols_disponibles + cols_extra_disp
    cols_sel = st.multiselect(
        "Columnas",
        todas_cols,
        default=cols_disponibles,
    )

if cols_sel:
    df_mostrar = df_filtrado[cols_sel]
else:
    df_mostrar = df_filtrado[cols_disponibles]

st.dataframe(df_mostrar, use_container_width=True, height=500)

# ---------------------------------------------------------------------------
# Descargar CSV
# ---------------------------------------------------------------------------
st.subheader("⬇️ Exportar")

# Generar CSV en memoria
csv_buffer = io.StringIO()
df_filtrado.to_csv(csv_buffer, index=False, encoding='utf-8-sig', sep=sep_csv)
csv_bytes = csv_buffer.getvalue().encode('utf-8-sig')

nombre_salida = Path(archivo.name).stem + '.csv'

st.download_button(
    label="📥 Descargar CSV (datos filtrados)",
    data=csv_bytes,
    file_name=nombre_salida,
    mime='text/csv',
)

# Guardar en disco si está marcado
if guardar_en_disco:
    ruta_guardada = SALIDA_DIR / nombre_salida
    ruta_guardada.write_bytes(csv_bytes)
    st.success(f"CSV guardado en: `{ruta_guardada}`")

# ---------------------------------------------------------------------------
# Gráficas rápidas
# ---------------------------------------------------------------------------
st.subheader("📈 Análisis rápido")

tab1, tab2, tab3 = st.tabs(["Por EPS", "Por CCF", "Días cotizados"])

with tab1:
    if 'cod_eps' in df_filtrado.columns and 'ibc' in df_filtrado.columns:
        eps_group = (
            df_filtrado.groupby('cod_eps', dropna=False)['ibc']
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        eps_group.columns = ['EPS', 'IBC Total']
        st.bar_chart(eps_group.set_index('EPS'))
    else:
        st.info("No hay datos de EPS disponibles.")

with tab2:
    if 'cod_ccf' in df_filtrado.columns and 'ibc' in df_filtrado.columns:
        ccf_group = (
            df_filtrado.groupby('cod_ccf', dropna=False)['ibc']
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        ccf_group.columns = ['CCF', 'IBC Total']
        st.bar_chart(ccf_group.set_index('CCF'))
    else:
        st.info("No hay datos de CCF disponibles.")

with tab3:
    if 'dias_eps' in df_filtrado.columns:
        dias_dist = df_filtrado['dias_eps'].value_counts().sort_index().reset_index()
        dias_dist.columns = ['Días cotizados', 'Cantidad']
        st.bar_chart(dias_dist.set_index('Días cotizados'))
    else:
        st.info("No hay datos de días disponibles.")

# ---------------------------------------------------------------------------
# Totales del registro 06
# ---------------------------------------------------------------------------
if info_totales:
    with st.expander("📑 Registro de totales (tipo 06)"):
        st.text(info_totales.get('raw', ''))
