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
    generar_reporte_inconsistencias,
    parse_pila_txt,
    resumen_planilla,
)

# ---------------------------------------------------------------------------
# Configuracion de pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PILA - Seguridad Social",
    page_icon="📋",
    layout="wide",
)

st.title("📋 PILA – Seguridad Social")
st.markdown(
    "Carga un archivo PILA en formato **TXT** (ancho fijo) para convertirlo a CSV "
    "y visualizar los aportes de seguridad social."
)

# ---------------------------------------------------------------------------
# Carpeta de salida por defecto
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).parent
SALIDA_DIR = BASE_DIR / "Salida"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuracion")
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
    ref_archivo = st.file_uploader(
        "Referencia (pila_modificada.txt)",
        type=["txt"],
        accept_multiple_files=False,
        help="Opcional: genera un reporte de diferencias vs la referencia.",
    )
    st.markdown("---")
    st.caption("seguridad_social_parte1.py v2.0")

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
col1.metric("Empleados unicos",  f"{resumen['empleados_unicos']:,}")
col2.metric("Total IBC",         f"${resumen['total_ibc']:,.0f}")
col3.metric("Total Pension",     f"${resumen['total_pension']:,.0f}")
col4.metric("Total EPS",         f"${resumen['total_eps']:,.0f}")
col5.metric("Total ARL",         f"${resumen['total_arl']:,.0f}")

with st.expander("ℹ️ Informacion empresa / encabezado"):
    st.json(info_empresa)

# ---------------------------------------------------------------------------
# Reporte de inconsistencias (opcional)
# ---------------------------------------------------------------------------
if ref_archivo is not None:
    with st.spinner("Generando reporte de inconsistencias..."):
        ruta_ref = SALIDA_DIR / f"_ref_{ref_archivo.name}"
        ruta_ref.write_bytes(ref_archivo.getvalue())
        ruta_reporte = SALIDA_DIR / f"{Path(archivo.name).stem}_reporte.txt"
        generar_reporte_inconsistencias(df, ruta_ref, ruta_reporte)
        reporte_bytes = ruta_reporte.read_bytes()
    st.success(f"Reporte generado: `{ruta_reporte}`")
    st.download_button(
        label="Descargar reporte de inconsistencias",
        data=reporte_bytes,
        file_name=ruta_reporte.name,
        mime='text/plain',
    )

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.subheader("🔍 Filtros")
fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)

with fcol1:
    ops_eps = sorted(df['cod_eps'].dropna().unique().tolist()) if 'cod_eps' in df.columns else []
    filtro_eps = st.multiselect("EPS", ops_eps, default=[])

with fcol2:
    ops_ccf = sorted(df['cod_ccf'].dropna().unique().tolist()) if 'cod_ccf' in df.columns else []
    filtro_ccf = st.multiselect("CCF", ops_ccf, default=[])

with fcol3:
    ops_afp = sorted(df['admin_afp'].dropna().unique().tolist()) if 'admin_afp' in df.columns else []
    filtro_afp = st.multiselect("AFP", ops_afp, default=[])

with fcol4:
    ops_tipo = sorted(df['tipo_cotizante'].dropna().unique().tolist()) if 'tipo_cotizante' in df.columns else []
    filtro_tipo = st.multiselect("Tipo cotizante", ops_tipo, default=[])

with fcol5:
    buscar = st.text_input("Buscar nombre / documento", "")

# Aplicar filtros
df_filtrado = df.copy()

if filtro_eps:
    df_filtrado = df_filtrado[df_filtrado['cod_eps'].isin(filtro_eps)]
if filtro_ccf:
    df_filtrado = df_filtrado[df_filtrado['cod_ccf'].isin(filtro_ccf)]
if filtro_afp:
    df_filtrado = df_filtrado[df_filtrado['admin_afp'].isin(filtro_afp)]
if filtro_tipo:
    df_filtrado = df_filtrado[df_filtrado['tipo_cotizante'].isin(filtro_tipo)]
if buscar:
    mask = (
        df_filtrado.get('nombre_completo', pd.Series(dtype=str))
        .str.contains(buscar.upper(), case=False, na=False)
        |
        df_filtrado.get('no_id', pd.Series(dtype=str))
        .str.contains(buscar, case=False, na=False)
    )
    df_filtrado = df_filtrado[mask]

st.caption(f"Mostrando {len(df_filtrado):,} de {len(df):,} registros")

# ---------------------------------------------------------------------------
# Tabla de datos
# ---------------------------------------------------------------------------
st.subheader("📊 Datos de empleados")

cols_default = [
    'no', 'tipo_id', 'no_id', 'nombre_completo',
    'tipo_cotizante', 'cod_municipio',
    'ing', 'fecha_ing', 'ret', 'fecha_ret', 'vst', 'sln',
    'cod_admin_afp', 'admin_afp', 'dias_afp', 'ibc_afp', 'tarifa_afp', 'valor_afp',
    'cod_eps',       'admin_eps', 'dias_eps', 'ibc_eps', 'tarifa_eps', 'valor_eps',
    'dias_arl',                  'ibc_arl',  'tarifa_arl', 'valor_arl',
    'cod_ccf',       'admin_ccf', 'dias_ccf', 'ibc_ccf', 'tarifa_ccf', 'valor_ccf',
    'ibc', 'horas_laboradas', 'exonerado',
]
cols_disp  = [c for c in cols_default if c in df_filtrado.columns]
cols_extra = [c for c in df_filtrado.columns if c not in cols_default]

with st.expander("Seleccionar columnas a mostrar", expanded=False):
    todas_cols = cols_disp + cols_extra
    cols_sel = st.multiselect("Columnas", todas_cols, default=cols_disp)

df_mostrar = df_filtrado[cols_sel] if cols_sel else df_filtrado[cols_disp]
st.dataframe(df_mostrar, use_container_width=True, height=500)

# ---------------------------------------------------------------------------
# Exportar CSV
# ---------------------------------------------------------------------------
st.subheader("⬇️ Exportar")

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

if guardar_en_disco:
    ruta_guardada = SALIDA_DIR / nombre_salida
    ruta_guardada.write_bytes(csv_bytes)
    st.success(f"CSV guardado en: `{ruta_guardada}`")

# ---------------------------------------------------------------------------
# Graficas rapidas
# ---------------------------------------------------------------------------
st.subheader("📈 Analisis rapido")

tab1, tab2, tab3, tab4 = st.tabs(["Por EPS", "Por AFP", "Por CCF", "Dias cotizados"])

with tab1:
    if 'cod_eps' in df_filtrado.columns and 'ibc_eps' in df_filtrado.columns:
        grp = (
            df_filtrado.groupby('cod_eps', dropna=False)['ibc_eps']
            .sum().sort_values(ascending=False).reset_index()
        )
        grp.columns = ['EPS', 'IBC EPS Total']
        st.bar_chart(grp.set_index('EPS'))
    else:
        st.info("No hay datos de EPS.")

with tab2:
    if 'admin_afp' in df_filtrado.columns and 'valor_afp' in df_filtrado.columns:
        grp = (
            df_filtrado.groupby('admin_afp', dropna=False)['valor_afp']
            .sum().sort_values(ascending=False).reset_index()
        )
        grp.columns = ['AFP', 'Valor AFP Total']
        st.bar_chart(grp.set_index('AFP'))
    else:
        st.info("No hay datos de AFP.")

with tab3:
    if 'cod_ccf' in df_filtrado.columns and 'valor_ccf' in df_filtrado.columns:
        grp = (
            df_filtrado.groupby('cod_ccf', dropna=False)['valor_ccf']
            .sum().sort_values(ascending=False).reset_index()
        )
        grp.columns = ['CCF', 'Valor CCF Total']
        st.bar_chart(grp.set_index('CCF'))
    else:
        st.info("No hay datos de CCF.")

with tab4:
    if 'dias_afp' in df_filtrado.columns:
        dist = df_filtrado['dias_afp'].value_counts().sort_index().reset_index()
        dist.columns = ['Dias cotizados', 'Cantidad']
        st.bar_chart(dist.set_index('Dias cotizados'))
    else:
        st.info("No hay datos de dias.")

# ---------------------------------------------------------------------------
# Totales del registro 06
# ---------------------------------------------------------------------------
if info_totales:
    with st.expander("📑 Registro de totales (tipo 06)"):
        st.text(info_totales.get('raw', ''))
