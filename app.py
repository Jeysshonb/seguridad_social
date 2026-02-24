# -*- coding: utf-8 -*-
"""
app.py
------
Streamlit UI for PILA TXT parsing, validation, and export.
"""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from seguridad_social_parte1 import (
    adaptar_admin_con_referencias,
    construir_df_formato_comparacion,
    generar_reporte_inconsistencias,
    parse_pila_txt,
    resumen_planilla,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PILA - Seguridad Social",
    page_icon="PILA",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Simple, neutral styles
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background: #f5f5f2;
        color: #0b0f19;
        font-family: "Manrope", system-ui, -apple-system, sans-serif;
    }

    [data-testid="stSidebar"] { display: none; }

    .header {
        background: #ffffff;
        border: 1px solid #e6e6e1;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }
    .header h1 {
        margin: 0 0 6px 0;
        font-size: 26px;
    }
    .header p { margin: 0; color: #6b7280; font-size: 13px; }

    .section-title {
        font-weight: 700;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: #374151;
        margin: 12px 0 8px 0;
    }

    .panel {
        background: #ffffff;
        border: 1px solid #e6e6e1;
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 12px;
    }

    .stat-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(140px, 1fr));
        gap: 10px;
        margin-top: 8px;
    }
    .stat-card {
        background: #ffffff;
        border: 1px solid #e6e6e1;
        border-radius: 12px;
        padding: 10px 12px;
    }
    .stat-card .label { font-size: 11px; color: #6b7280; margin-bottom: 6px; }
    .stat-card .value { font-size: 18px; font-weight: 700; color: #0b0f19; }

    .tiny { font-size: 12px; color: #6b7280; }

    .stDownloadButton button {
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        font-weight: 600 !important;
        background: #111827 !important;
        color: #f9fafb !important;
    }

    @media (max-width: 1200px) {
        .stat-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
SALIDA_DIR = BASE_DIR / "Salida"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)

SEP_CSV = ';'
RUTA_REF_DEFAULT = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "pila_modificada.txt"
RUTA_COMP_DEFAULT = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "comparacion.csv"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="header">
        <h1>PILA - Seguridad Social</h1>
        <p>Sube un TXT PILA. El sistema valida referencias automaticamente y genera exportaciones.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Reference status
# ---------------------------------------------------------------------------
ref_ok = RUTA_REF_DEFAULT.exists()
comp_ok = RUTA_COMP_DEFAULT.exists()

st.markdown('<div class="section-title">Referencias</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.caption(f"pila_modificada.txt: {'OK' if ref_ok else 'NO ENCONTRADO'}")
    st.caption(f"comparacion.csv: {'OK' if comp_ok else 'NO ENCONTRADO'}")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Entrada</div>', unsafe_allow_html=True)
archivo = st.file_uploader(
    "Archivo PILA (TXT)",
    type=["txt", "TxT", "TXT"],
    accept_multiple_files=False,
)

if archivo is None:
    st.markdown(
        """
        <div class="panel">
            <div class="tiny">Sube un TXT PILA para iniciar el proceso.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------
with st.spinner("Procesando archivo..."):
    contenido_bytes = archivo.read()
    df, info_empresa, info_totales = parse_pila_txt(contenido_bytes)

# ---------------------------------------------------------------------------
# References are always auto-loaded
# ---------------------------------------------------------------------------
ruta_ref = RUTA_REF_DEFAULT if ref_ok else None
ruta_comp = RUTA_COMP_DEFAULT if comp_ok else None

df = adaptar_admin_con_referencias(df, ruta_ref, ruta_comp)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
resumen = resumen_planilla(df, info_empresa)

st.markdown(
    f"""
    <div class="panel">
        <div class="section-title">Resumen</div>
        <div class="tiny">{archivo.name} | {len(df):,} registros tipo 02</div>
        <div class="stat-grid">
            <div class="stat-card"><div class="label">Empleados unicos</div><div class="value">{resumen['empleados_unicos']:,}</div></div>
            <div class="stat-card"><div class="label">Total IBC</div><div class="value">${resumen['total_ibc']:,.0f}</div></div>
            <div class="stat-card"><div class="label">Total Pension</div><div class="value">${resumen['total_pension']:,.0f}</div></div>
            <div class="stat-card"><div class="label">Total EPS</div><div class="value">${resumen['total_eps']:,.0f}</div></div>
            <div class="stat-card"><div class="label">Total ARL</div><div class="value">${resumen['total_arl']:,.0f}</div></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Informacion empresa / encabezado"):
    st.json(info_empresa)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
reporte_bytes = None
ruta_reporte = None
if ruta_ref is not None:
    with st.spinner("Generando reporte de inconsistencias..."):
        ruta_reporte = SALIDA_DIR / f"{Path(archivo.name).stem}_reporte.txt"
        generar_reporte_inconsistencias(df, ruta_ref, ruta_reporte, ruta_comp)
        reporte_bytes = ruta_reporte.read_bytes()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)
with st.expander("Mostrar filtros", expanded=False):
    row1 = st.columns(3)
    row2 = st.columns(2)

    with row1[0]:
        ops_eps = sorted(df['cod_eps'].dropna().unique().tolist()) if 'cod_eps' in df.columns else []
        filtro_eps = st.multiselect("EPS", ops_eps, default=[])

    with row1[1]:
        ops_ccf = sorted(df['cod_ccf'].dropna().unique().tolist()) if 'cod_ccf' in df.columns else []
        filtro_ccf = st.multiselect("CCF", ops_ccf, default=[])

    with row1[2]:
        ops_afp = sorted(df['admin_afp'].dropna().unique().tolist()) if 'admin_afp' in df.columns else []
        filtro_afp = st.multiselect("AFP", ops_afp, default=[])

    with row2[0]:
        ops_tipo = sorted(df['tipo_cotizante'].dropna().unique().tolist()) if 'tipo_cotizante' in df.columns else []
        filtro_tipo = st.multiselect("Tipo cotizante", ops_tipo, default=[])

    with row2[1]:
        buscar = st.text_input("Buscar nombre / documento", "")

_df = df.copy()

if 'filtro_eps' in locals() and filtro_eps:
    _df = _df[_df['cod_eps'].isin(filtro_eps)]
if 'filtro_ccf' in locals() and filtro_ccf:
    _df = _df[_df['cod_ccf'].isin(filtro_ccf)]
if 'filtro_afp' in locals() and filtro_afp:
    _df = _df[_df['admin_afp'].isin(filtro_afp)]
if 'filtro_tipo' in locals() and filtro_tipo:
    _df = _df[_df['tipo_cotizante'].isin(filtro_tipo)]
if 'buscar' in locals() and buscar:
    mask = (
        _df.get('nombre_completo', pd.Series(dtype=str))
        .str.contains(buscar.upper(), case=False, na=False)
        |
        _df.get('no_id', pd.Series(dtype=str))
        .str.contains(buscar, case=False, na=False)
    )
    _df = _df[mask]

df_filtrado = _df
st.caption(f"Mostrando {len(df_filtrado):,} de {len(df):,} registros")

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Datos</div>', unsafe_allow_html=True)
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
cols_disp = [c for c in cols_default if c in df_filtrado.columns]
cols_extra = [c for c in df_filtrado.columns if c not in cols_default]

with st.expander("Seleccionar columnas", expanded=False):
    todas_cols = cols_disp + cols_extra
    cols_sel = st.multiselect("Columnas", todas_cols, default=cols_disp)

df_mostrar = df_filtrado[cols_sel] if cols_sel else df_filtrado[cols_disp]
st.dataframe(df_mostrar, use_container_width=True, height=520)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Exportar</div>', unsafe_allow_html=True)

csv_buffer = io.StringIO()
df_filtrado.to_csv(csv_buffer, index=False, encoding='utf-8-sig', sep=SEP_CSV)
csv_bytes = csv_buffer.getvalue().encode('utf-8-sig')

nombre_salida = Path(archivo.name).stem + '.csv'

st.download_button(
    label="Descargar CSV normalizado",
    data=csv_bytes,
    file_name=nombre_salida,
    mime='text/csv',
)

ruta_comp_eff = ruta_comp
if ruta_comp_eff is None and RUTA_COMP_DEFAULT.exists():
    ruta_comp_eff = RUTA_COMP_DEFAULT

df_cmp = construir_df_formato_comparacion(df_filtrado, ruta_comp_eff)
csv_cmp_buffer = io.StringIO()
df_cmp.to_csv(csv_cmp_buffer, index=False, encoding='utf-8-sig', sep=';')
csv_cmp_bytes = csv_cmp_buffer.getvalue().encode('utf-8-sig')

nombre_salida_cmp = Path(archivo.name).stem + '_comparacion.csv'

st.download_button(
    label="Descargar CSV formato oficial",
    data=csv_cmp_bytes,
    file_name=nombre_salida_cmp,
    mime='text/csv',
)

if reporte_bytes is not None and ruta_reporte is not None:
    st.download_button(
        label="Descargar reporte de inconsistencias",
        data=reporte_bytes,
        file_name=ruta_reporte.name,
        mime='text/plain',
    )

guardar_en_disco = st.checkbox(
    "Guardar archivos en carpeta Salida",
    value=True,
    help=f"Ruta: {SALIDA_DIR}",
)

if guardar_en_disco:
    ruta_guardada = SALIDA_DIR / nombre_salida
    ruta_guardada.write_bytes(csv_bytes)
    ruta_cmp_guardada = SALIDA_DIR / nombre_salida_cmp
    ruta_cmp_guardada.write_bytes(csv_cmp_bytes)
    if reporte_bytes is not None and ruta_reporte is not None:
        ruta_reporte.write_bytes(reporte_bytes)
    st.caption(f"Guardado en: {SALIDA_DIR}")

# ---------------------------------------------------------------------------
# Quick analysis (optional)
# ---------------------------------------------------------------------------
with st.expander("Analisis rapido", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        if 'cod_eps' in df_filtrado.columns and 'ibc_eps' in df_filtrado.columns:
            grp = (
                df_filtrado.groupby('cod_eps', dropna=False)['ibc_eps']
                .sum().sort_values(ascending=False).reset_index()
            )
            grp.columns = ['EPS', 'IBC EPS Total']
            st.bar_chart(grp.set_index('EPS'))
        else:
            st.info("No hay datos de EPS.")
    with c2:
        if 'admin_afp' in df_filtrado.columns and 'valor_afp' in df_filtrado.columns:
            grp = (
                df_filtrado.groupby('admin_afp', dropna=False)['valor_afp']
                .sum().sort_values(ascending=False).reset_index()
            )
            grp.columns = ['AFP', 'Valor AFP Total']
            st.bar_chart(grp.set_index('AFP'))
        else:
            st.info("No hay datos de AFP.")

with st.expander("Registro 06", expanded=False):
    if info_totales:
        st.text(info_totales.get('raw', ''))
    else:
        st.info("No hay registro de totales.")
