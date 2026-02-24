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
# Styles
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --ink: #0b0f19;
        --slate: #1f2937;
        --muted: #6b7280;
        --accent: #00c389;
        --accent-2: #f6b73c;
        --paper: #f7f6f2;
        --card: rgba(255,255,255,0.92);
        --line: rgba(15, 23, 42, 0.10);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(1000px 520px at 15% -10%, #e6fbf3 0%, rgba(230,251,243,0) 55%),
            radial-gradient(900px 480px at 110% 0%, #fff2d8 0%, rgba(255,242,216,0) 55%),
            linear-gradient(180deg, #fbfaf6 0%, #f2efe7 100%);
        color: var(--ink);
        font-family: "Manrope", system-ui, -apple-system, sans-serif;
    }

    [data-testid="stSidebar"] { display: none; }
    header, [data-testid="stHeader"] { background: transparent; }

    .shell {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px;
        background: rgba(255,255,255,0.35);
        backdrop-filter: blur(8px);
    }

    .hero {
        background: linear-gradient(135deg, #0b1220 0%, #102a37 55%, #0f3b2e 100%);
        color: #f5f7fb;
        padding: 28px 32px;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(10, 12, 20, 0.25);
        margin-bottom: 16px;
    }
    .hero h1 {
        font-size: 36px;
        margin: 0 0 6px 0;
        letter-spacing: -0.6px;
    }
    .hero p {
        margin: 0;
        color: rgba(245,247,251,0.85);
        font-size: 14px;
    }
    .chips { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    .chip {
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.18);
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 11px;
        letter-spacing: 0.2px;
    }

    .section-title {
        font-weight: 700;
        font-size: 15px;
        color: var(--slate);
        margin: 10px 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    .panel {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px 16px;
        box-shadow: 0 12px 30px rgba(15, 18, 26, 0.08);
    }

    .stat-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(140px, 1fr));
        gap: 12px;
        margin-top: 8px;
    }
    .stat-card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px 14px;
        box-shadow: 0 8px 24px rgba(15, 18, 26, 0.06);
    }
    .stat-card .label { font-size: 11px; color: var(--muted); margin-bottom: 6px; }
    .stat-card .value { font-size: 20px; font-weight: 700; color: var(--ink); }

    .tiny { font-size: 12px; color: var(--muted); }

    .stDownloadButton button, .stButton button {
        border-radius: 12px !important;
        border: 1px solid rgba(11, 15, 25, 0.14) !important;
        padding: 8px 16px !important;
        font-weight: 700 !important;
        background: #0f172a !important;
        color: #f8fafc !important;
    }
    .stDownloadButton button:hover {
        background: #0b1220 !important;
    }

    .stTextInput input, .stSelectbox div, .stMultiSelect div {
        border-radius: 12px !important;
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

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
        <h1>PILA - Seguridad Social</h1>
        <p>Control center para convertir TXT PILA a CSV, validar y exportar.</p>
        <div class="chips">
            <span class="chip">CSV normalizado</span>
            <span class="chip">CSV comparacion</span>
            <span class="chip">Reporte TXT</span>
            <span class="chip">Codigos inferidos</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Entrada</div>', unsafe_allow_html=True)
col_up, col_ref, col_opt = st.columns([2, 1, 1])

with col_up:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    archivo = st.file_uploader(
        "Archivo PILA (TXT)",
        type=["txt", "TxT", "TXT"],
        accept_multiple_files=False,
    )
    st.caption("TXT en ancho fijo. Procesamiento PILA estandar.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_ref:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    ref_archivo = st.file_uploader(
        "Referencia (pila_modificada.txt)",
        type=["txt"],
        accept_multiple_files=False,
    )
    comp_archivo = st.file_uploader(
        "Comparacion (comparacion.csv)",
        type=["csv"],
        accept_multiple_files=False,
    )
    st.caption("Si no subes referencias se usan las del repositorio.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_opt:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    guardar_en_disco = st.checkbox(
        "Guardar archivos en Salida",
        value=True,
        help=f"Ruta: {SALIDA_DIR}",
    )
    st.caption("Se exporta CSV normalizado, CSV comparacion y reporte.")
    st.markdown('</div>', unsafe_allow_html=True)

if archivo is None:
    st.markdown(
        """
        <div class="panel">
            <div class="section-title">Listo para procesar</div>
            <div class="tiny">Sube un TXT PILA para iniciar el parseo, la validacion y las exportaciones.</div>
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
# References
# ---------------------------------------------------------------------------
ruta_ref = None
ruta_comp = None
if ref_archivo is not None:
    ruta_ref = SALIDA_DIR / f"_ref_{ref_archivo.name}"
    ruta_ref.write_bytes(ref_archivo.getvalue())
if comp_archivo is not None:
    ruta_comp = SALIDA_DIR / f"_comp_{comp_archivo.name}"
    ruta_comp.write_bytes(comp_archivo.getvalue())

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
ruta_ref_eff = ruta_ref
if ruta_ref_eff is None:
    ruta_def = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "pila_modificada.txt"
    if ruta_def.exists():
        ruta_ref_eff = ruta_def
if ruta_ref_eff is None and ruta_comp is not None:
    ruta_ref_eff = ruta_comp

reporte_bytes = None
ruta_reporte = None
if ruta_ref_eff is not None:
    with st.spinner("Generando reporte de inconsistencias..."):
        ruta_reporte = SALIDA_DIR / f"{Path(archivo.name).stem}_reporte.txt"
        generar_reporte_inconsistencias(df, ruta_ref_eff, ruta_reporte, ruta_comp)
        reporte_bytes = ruta_reporte.read_bytes()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)
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

if filtro_eps:
    _df = _df[_df['cod_eps'].isin(filtro_eps)]
if filtro_ccf:
    _df = _df[_df['cod_ccf'].isin(filtro_ccf)]
if filtro_afp:
    _df = _df[_df['admin_afp'].isin(filtro_afp)]
if filtro_tipo:
    _df = _df[_df['tipo_cotizante'].isin(filtro_tipo)]
if buscar:
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
# Tabs
# ---------------------------------------------------------------------------
main_tabs = st.tabs(["Datos", "Exportar", "Analisis", "Totales"])

with main_tabs[0]:
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

    with st.expander("Seleccionar columnas"):
        todas_cols = cols_disp + cols_extra
        cols_sel = st.multiselect("Columnas", todas_cols, default=cols_disp)

    df_mostrar = df_filtrado[cols_sel] if cols_sel else df_filtrado[cols_disp]
    st.dataframe(df_mostrar, use_container_width=True, height=520)

with main_tabs[1]:
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
    if ruta_comp_eff is None:
        ruta_def = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "comparacion.csv"
        if ruta_def.exists():
            ruta_comp_eff = ruta_def

    df_cmp = construir_df_formato_comparacion(df_filtrado, ruta_comp_eff)
    csv_cmp_buffer = io.StringIO()
    df_cmp.to_csv(csv_cmp_buffer, index=False, encoding='utf-8-sig', sep=';')
    csv_cmp_bytes = csv_cmp_buffer.getvalue().encode('utf-8-sig')
    nombre_salida_cmp = Path(archivo.name).stem + '_comparacion.csv'

    st.download_button(
        label="Descargar CSV formato comparacion",
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

    if guardar_en_disco:
        ruta_guardada = SALIDA_DIR / nombre_salida
        ruta_guardada.write_bytes(csv_bytes)
        ruta_cmp_guardada = SALIDA_DIR / nombre_salida_cmp
        ruta_cmp_guardada.write_bytes(csv_cmp_bytes)
        if reporte_bytes is not None and ruta_reporte is not None:
            ruta_reporte.write_bytes(reporte_bytes)
        st.caption(f"Guardado en: {SALIDA_DIR}")

with main_tabs[2]:
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

with main_tabs[3]:
    if info_totales:
        st.text(info_totales.get('raw', ''))
    else:
        st.info("No hay registro de totales.")
