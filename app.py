# -*- coding: utf-8 -*-
"""
app.py — Visor PILA Seguridad Social
"""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from seguridad_social_parte1 import (
    adaptar_admin_con_referencias,
    parse_pila_txt,
    resumen_planilla,
)

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PILA — Seguridad Social",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR  = Path(__file__).parent
SALIDA_DIR = BASE_DIR / "Salida"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)
RUTA_REF_DEFAULT  = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "pila_modificada.txt"
RUTA_COMP_DEFAULT = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "comparacion.csv"
SEP = ";"

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #F0F2F6;
    font-family: "Inter", system-ui, sans-serif;
    color: #1C1C1E;
}
[data-testid="stSidebar"] { display: none; }
[data-testid="stHeader"]  { background: transparent; }

/* Header principal */
.top-bar {
    background: #1C1C1E;
    border-radius: 16px;
    padding: 20px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.top-bar h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.3px;
}
.top-bar p {
    margin: 4px 0 0 0;
    font-size: 12px;
    color: #8E8E93;
}
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 6px;
}
.badge-ok  { background:#D1FAE5; color:#065F46; }
.badge-no  { background:#FEE2E2; color:#991B1B; }

/* Cards */
.card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.card-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: #6B7280;
    margin-bottom: 12px;
}

/* KPI strip */
.kpi-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.kpi {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 12px 16px;
    flex: 1;
    min-width: 150px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.kpi .k-label { font-size: 11px; color: #9CA3AF; margin-bottom: 4px; }
.kpi .k-value { font-size: 20px; font-weight: 700; color: #111827; }
.kpi .k-sub   { font-size: 11px; color: #6B7280; margin-top: 2px; }

/* Tabla */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* Botones descarga */
.stDownloadButton > button {
    background: #111827 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 20px !important;
    width: 100% !important;
    cursor: pointer !important;
}
.stDownloadButton > button:hover {
    background: #374151 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    border-radius: 12px;
}

/* Inputs */
.stMultiSelect [data-baseweb="select"] { border-radius: 10px; }
.stTextInput input { border-radius: 10px; }

/* Expander */
[data-testid="stExpander"] { border-radius: 12px !important; border: 1px solid #E5E7EB !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F3F4F6; }
::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
ref_ok  = RUTA_REF_DEFAULT.exists()
comp_ok = RUTA_COMP_DEFAULT.exists()

badge_ref  = '<span class="badge badge-ok">REF OK</span>'  if ref_ok  else '<span class="badge badge-no">SIN REF</span>'
badge_comp = '<span class="badge badge-ok">COMP OK</span>' if comp_ok else '<span class="badge badge-no">SIN COMP</span>'

st.markdown(f"""
<div class="top-bar">
  <div>
    <h1>PILA — Seguridad Social</h1>
    <p>Parseo y validacion de planillas PILA en formato TXT</p>
  </div>
  <div>{badge_ref}{badge_comp}</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-title">Archivo de entrada</div>', unsafe_allow_html=True)
archivo = st.file_uploader(
    "Sube el archivo PILA (.TxT / .txt)",
    type=["txt", "TxT", "TXT"],
    label_visibility="collapsed",
)
st.markdown("</div>", unsafe_allow_html=True)

if archivo is None:
    st.markdown("""
    <div style="text-align:center; padding:40px; color:#9CA3AF; font-size:14px;">
        Sube un archivo PILA TXT para comenzar.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------
with st.spinner("Procesando..."):
    contenido_bytes = archivo.read()
    df, info_empresa, info_totales = parse_pila_txt(contenido_bytes)
    ruta_ref  = RUTA_REF_DEFAULT  if ref_ok  else None
    ruta_comp = RUTA_COMP_DEFAULT if comp_ok else None
    df = adaptar_admin_con_referencias(df, ruta_ref, ruta_comp)

resumen = resumen_planilla(df, info_empresa)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="kpi-row">
  <div class="kpi">
    <div class="k-label">Empleados</div>
    <div class="k-value">{resumen['empleados_unicos']:,}</div>
    <div class="k-sub">{len(df):,} registros</div>
  </div>
  <div class="kpi">
    <div class="k-label">IBC Total</div>
    <div class="k-value">${resumen['total_ibc']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-label">Pension</div>
    <div class="k-value">${resumen['total_pension']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-label">Salud (EPS)</div>
    <div class="k-value">${resumen['total_eps']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-label">ARL</div>
    <div class="k-value">${resumen['total_arl']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-label">CCF</div>
    <div class="k-value">${resumen['total_ccf']:,.0f}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
with st.expander("Filtros", expanded=False):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        ops_eps  = sorted(df['admin_eps'].dropna().unique()) if 'admin_eps' in df.columns else []
        f_eps    = st.multiselect("EPS", ops_eps)
    with c2:
        ops_ccf  = sorted(df['admin_ccf'].dropna().unique()) if 'admin_ccf' in df.columns else []
        f_ccf    = st.multiselect("CCF", ops_ccf)
    with c3:
        ops_afp  = sorted(df['admin_afp'].dropna().unique()) if 'admin_afp' in df.columns else []
        f_afp    = st.multiselect("AFP", ops_afp)
    with c4:
        ops_tipo = sorted(df['tipo_de_cotizante'].dropna().unique()) if 'tipo_de_cotizante' in df.columns else []
        f_tipo   = st.multiselect("Tipo cotizante", ops_tipo)
    with c5:
        buscar   = st.text_input("Buscar nombre / documento")

df_f = df.copy()
if f_eps:   df_f = df_f[df_f['admin_eps'].isin(f_eps)]
if f_ccf:   df_f = df_f[df_f['admin_ccf'].isin(f_ccf)]
if f_afp:   df_f = df_f[df_f['admin_afp'].isin(f_afp)]
if f_tipo:  df_f = df_f[df_f['tipo_de_cotizante'].isin(f_tipo)]
if buscar:
    mask = (
        df_f.get('nombre_completo', pd.Series(dtype=str)).str.contains(buscar.upper(), case=False, na=False)
        | df_f.get('no_id', pd.Series(dtype=str)).str.contains(buscar, case=False, na=False)
    )
    df_f = df_f[mask]

# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-title">Datos</div>', unsafe_allow_html=True)

COLS_DEFAULT = [
    'no', 'tipo_id', 'no_id', 'primer_apellido', 'segundo_apellido',
    'primer_nombre', 'segundo_nombre',
    'ciudad', 'departamento',
    'tipo_de_cotizante', 'subtipo_de_cotizante', 'horas_laboradas',
    'ing', 'fecha_ing', 'ret', 'fecha_ret', 'vst', 'sln',
    'admin_afp', 'dias_afp', 'ibc_afp', 'tarifa_afp', 'valor_afp',
    'admin_eps', 'dias_eps', 'ibc_eps', 'tarifa_eps', 'valor_eps',
    'admin_arl', 'clase_arl', 'dias_arl', 'ibc_arl', 'tarifa_arl', 'valor_arl',
    'admin_ccf', 'dias_ccf', 'ibc_ccf', 'tarifa_ccf', 'valor_ccf',
    'ibc', 'exonerado', 'cod_entidad',
]
cols_disp = [c for c in COLS_DEFAULT if c in df_f.columns]

with st.expander("Seleccionar columnas", expanded=False):
    todas = cols_disp + [c for c in df_f.columns if c not in cols_disp]
    cols_sel = st.multiselect("Columnas visibles", todas, default=cols_disp)

st.caption(f"{len(df_f):,} de {len(df):,} registros")
st.dataframe(df_f[cols_sel] if cols_sel else df_f[cols_disp], use_container_width=True, height=500)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Exportar — solo 1 CSV
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-title">Exportar</div>', unsafe_allow_html=True)

csv_buf = io.StringIO()
df_f.to_csv(csv_buf, index=False, encoding="utf-8-sig", sep=SEP)
csv_bytes = csv_buf.getvalue().encode("utf-8-sig")
nombre_csv = Path(archivo.name).stem + ".csv"

col_dl, col_save = st.columns([1, 2])
with col_dl:
    st.download_button(
        label="Descargar CSV",
        data=csv_bytes,
        file_name=nombre_csv,
        mime="text/csv",
    )
with col_save:
    if st.checkbox("Guardar en carpeta Salida", value=True):
        (SALIDA_DIR / nombre_csv).write_bytes(csv_bytes)
        st.caption(f"Guardado en {SALIDA_DIR / nombre_csv}")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------
with st.expander("Analisis por administradora", expanded=False):
    tc1, tc2 = st.columns(2)
    with tc1:
        st.markdown("**Valor AFP por administradora**")
        if 'admin_afp' in df_f.columns and 'valor_afp' in df_f.columns:
            grp = df_f.groupby('admin_afp')['valor_afp'].sum().sort_values(ascending=False)
            st.bar_chart(grp)
    with tc2:
        st.markdown("**Valor EPS por administradora**")
        if 'admin_eps' in df_f.columns and 'valor_eps' in df_f.columns:
            grp = df_f.groupby('admin_eps')['valor_eps'].sum().sort_values(ascending=False)
            st.bar_chart(grp)

with st.expander("Empresa / Totales", expanded=False):
    st.json(info_empresa)
    if info_totales:
        st.text(info_totales.get('raw', ''))
