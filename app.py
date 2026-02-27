# -*- coding: utf-8 -*-
"""
app.py — Seguridad Social Nómina
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
    page_title="Seguridad Social — Nómina",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR   = Path(__file__).parent
SALIDA_DIR = BASE_DIR / "Salida"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)
RUTA_REF_DEFAULT  = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "pila_modificada.txt"
RUTA_COMP_DEFAULT = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "comparacion.csv"
SEP = ";"

# ---------------------------------------------------------------------------
# Estilos — responde automáticamente al tema claro/oscuro del sistema
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

/* ── Variables de tema ─────────────────────────────────── */
:root {
    --bg:        #F2F4F8;
    --surface:   #FFFFFF;
    --border:    #E4E7EF;
    --txt:       #0D1117;
    --txt-soft:  #5A6478;
    --accent:    #1A56DB;
    --accent-bg: #EEF4FF;
    --green:     #0E6D42;
    --green-bg:  #D1FAE5;
    --red:       #9A1616;
    --red-bg:    #FEE2E2;
    --shadow:    0 1px 4px rgba(0,0,0,.07);
    --shadow-lg: 0 4px 20px rgba(0,0,0,.09);
    --radius:    14px;
    --header-bg: linear-gradient(135deg, #0D1117 0%, #1A2338 100%);
    --header-txt:#FFFFFF;
    --header-sub:#8B97AD;
    --kpi-accent:#1A56DB;
}

@media (prefers-color-scheme: dark) {
    :root {
        --bg:        #0D1117;
        --surface:   #161B26;
        --border:    #21293A;
        --txt:       #E6EDF3;
        --txt-soft:  #7D8EA4;
        --accent:    #4F8EF7;
        --accent-bg: #1A2338;
        --green:     #3DD68C;
        --green-bg:  #0A2E1A;
        --red:       #F87171;
        --red-bg:    #2A0D0D;
        --shadow:    0 1px 4px rgba(0,0,0,.35);
        --shadow-lg: 0 4px 20px rgba(0,0,0,.45);
        --header-bg: linear-gradient(135deg, #0A0E18 0%, #111929 100%);
        --header-txt:#E6EDF3;
        --header-sub:#5A6E8A;
        --kpi-accent:#4F8EF7;
    }
}

/* ── Fondo base ─────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
.stApp {
    background: var(--bg) !important;
    font-family: "Plus Jakarta Sans", system-ui, sans-serif !important;
    color: var(--txt) !important;
}

[data-testid="stSidebar"]      { display: none !important; }
[data-testid="stHeader"]       { background: transparent !important; }
[data-testid="stDecoration"]   { display: none !important; }
[data-testid="stToolbar"]      { display: none !important; }

/* ── Header ─────────────────────────────────────────────── */
.ssnl-header {
    background: var(--header-bg);
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 22px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    box-shadow: var(--shadow-lg);
}
.ssnl-title  { line-height: 1; }
.ssnl-title h1 {
    margin: 0 0 6px 0;
    font-size: 28px;
    font-weight: 800;
    color: var(--header-txt);
    letter-spacing: -0.5px;
}
.ssnl-title p {
    margin: 0;
    font-size: 13px;
    color: var(--header-sub);
    font-weight: 400;
}
.ssnl-badges { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* ── Badges ─────────────────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
.badge-ok  { background: var(--green-bg);  color: var(--green); }
.badge-no  { background: var(--red-bg);    color: var(--red);   }
.badge-dot-ok  { width:6px; height:6px; border-radius:50%; background: var(--green); }
.badge-dot-no  { width:6px; height:6px; border-radius:50%; background: var(--red);   }

/* ── Cards ──────────────────────────────────────────────── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
}
.card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--txt-soft);
    margin-bottom: 14px;
}

/* ── KPI strip ──────────────────────────────────────────── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 18px;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
}
.kpi::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent);
    border-radius: var(--radius) var(--radius) 0 0;
}
.kpi .k-lbl  { font-size: 11px; color: var(--txt-soft); font-weight: 500; margin-bottom: 6px; }
.kpi .k-val  { font-size: 22px; font-weight: 800; color: var(--txt); letter-spacing: -0.5px; }
.kpi .k-sub  { font-size: 11px; color: var(--txt-soft); margin-top: 3px; }

/* ── Upload zone ────────────────────────────────────────── */
[data-testid="stFileUploader"] > div {
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--surface) !important;
    transition: border-color .2s;
}
[data-testid="stFileUploader"] > div:hover {
    border-color: var(--accent) !important;
}

/* ── Download button ────────────────────────────────────── */
.stDownloadButton > button {
    background: var(--accent) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: "Plus Jakarta Sans", sans-serif !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 11px 22px !important;
    letter-spacing: 0.2px !important;
    transition: opacity .15s !important;
    width: 100% !important;
}
.stDownloadButton > button:hover { opacity: .87 !important; }

/* ── Streamlit widgets override ─────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--surface) !important;
}
[data-baseweb="select"] > div { border-radius: 10px !important; }
input[type="text"]            { border-radius: 10px !important; }

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
ref_ok  = RUTA_REF_DEFAULT.exists()
comp_ok = RUTA_COMP_DEFAULT.exists()

dot_ref  = '<span class="badge-dot-ok"></span>' if ref_ok  else '<span class="badge-dot-no"></span>'
dot_comp = '<span class="badge-dot-ok"></span>' if comp_ok else '<span class="badge-dot-no"></span>'
lbl_ref  = f'<span class="badge badge-ok">{dot_ref} Referencia</span>'  if ref_ok  else f'<span class="badge badge-no">{dot_ref} Sin referencia</span>'
lbl_comp = f'<span class="badge badge-ok">{dot_comp} Comparación</span>' if comp_ok else f'<span class="badge badge-no">{dot_comp} Sin comparación</span>'

st.markdown(f"""
<div class="ssnl-header">
  <div class="ssnl-title">
    <h1>Seguridad Social Nómina</h1>
    <p>Procesamiento y validación de planillas PILA en formato TXT</p>
  </div>
  <div class="ssnl-badges">
    {lbl_ref}
    {lbl_comp}
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-label">Archivo de entrada</div>', unsafe_allow_html=True)
archivo = st.file_uploader(
    "Sube el archivo PILA (.TxT / .txt)",
    type=["txt", "TxT", "TXT"],
    label_visibility="collapsed",
)
st.markdown("</div>", unsafe_allow_html=True)

if archivo is None:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;color:var(--txt-soft);font-size:14px;font-weight:500;">
        Sube un archivo TXT PILA para comenzar el análisis.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------
with st.spinner("Procesando archivo..."):
    contenido_bytes = archivo.read()
    df, info_empresa, info_totales = parse_pila_txt(contenido_bytes)
    ruta_ref  = RUTA_REF_DEFAULT  if ref_ok  else None
    ruta_comp = RUTA_COMP_DEFAULT if comp_ok else None
    df = adaptar_admin_con_referencias(df, ruta_ref, ruta_comp)

resumen = resumen_planilla(df, info_empresa)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
empresa = str(resumen.get('empresa', '')).strip()
nit     = str(resumen.get('nit', '')).strip()

st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi">
    <div class="k-lbl">Empleados únicos</div>
    <div class="k-val">{resumen['empleados_unicos']:,}</div>
    <div class="k-sub">{len(df):,} registros en planilla</div>
  </div>
  <div class="kpi">
    <div class="k-lbl">IBC Total</div>
    <div class="k-val">${resumen['total_ibc']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-lbl">Pensión</div>
    <div class="k-val">${resumen['total_pension']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-lbl">Salud (EPS)</div>
    <div class="k-val">${resumen['total_eps']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-lbl">ARL</div>
    <div class="k-val">${resumen['total_arl']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="k-lbl">CCF</div>
    <div class="k-val">${resumen['total_ccf']:,.0f}</div>
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
        buscar = st.text_input("Buscar nombre / documento")

df_f = df.copy()
if f_eps:  df_f = df_f[df_f['admin_eps'].isin(f_eps)]
if f_ccf:  df_f = df_f[df_f['admin_ccf'].isin(f_ccf)]
if f_afp:  df_f = df_f[df_f['admin_afp'].isin(f_afp)]
if f_tipo: df_f = df_f[df_f['tipo_de_cotizante'].isin(f_tipo)]
if buscar:
    mask = (
        df_f.get('nombre_completo', pd.Series(dtype=str)).str.contains(buscar.upper(), case=False, na=False)
        | df_f.get('no_id', pd.Series(dtype=str)).str.contains(buscar, case=False, na=False)
    )
    df_f = df_f[mask]

# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------
COLS_DEFAULT = [
    'no', 'tipo_id', 'no_id',
    'primer_apellido', 'segundo_apellido', 'primer_nombre', 'segundo_nombre',
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

st.markdown('<div class="card"><div class="card-label">Datos</div>', unsafe_allow_html=True)
with st.expander("Seleccionar columnas", expanded=False):
    todas = cols_disp + [c for c in df_f.columns if c not in cols_disp]
    cols_sel = st.multiselect("Columnas visibles", todas, default=cols_disp)

st.caption(f"{len(df_f):,} de {len(df):,} registros")
st.dataframe(df_f[cols_sel] if cols_sel else df_f[cols_disp], use_container_width=True, height=500)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Exportar — 1 solo CSV
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-label">Exportar</div>', unsafe_allow_html=True)

csv_buf = io.StringIO()
df_f.to_csv(csv_buf, index=False, encoding="utf-8-sig", sep=SEP)
csv_bytes = csv_buf.getvalue().encode("utf-8-sig")
nombre_csv = Path(archivo.name).stem + ".csv"

col_dl, col_sv = st.columns([1, 2])
with col_dl:
    st.download_button(
        label="Descargar CSV",
        data=csv_bytes,
        file_name=nombre_csv,
        mime="text/csv",
    )
with col_sv:
    if st.checkbox("Guardar en carpeta Salida", value=True):
        (SALIDA_DIR / nombre_csv).write_bytes(csv_bytes)
        st.caption(f"Guardado en {SALIDA_DIR / nombre_csv}")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------
with st.expander("Análisis por administradora", expanded=False):
    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown("**Valor AFP por fondo**")
        if 'admin_afp' in df_f.columns and 'valor_afp' in df_f.columns:
            grp = df_f.groupby('admin_afp')['valor_afp'].sum().sort_values(ascending=False)
            st.bar_chart(grp)
    with ac2:
        st.markdown("**Valor EPS por entidad**")
        if 'admin_eps' in df_f.columns and 'valor_eps' in df_f.columns:
            grp = df_f.groupby('admin_eps')['valor_eps'].sum().sort_values(ascending=False)
            st.bar_chart(grp)

with st.expander("Empresa / Encabezado planilla", expanded=False):
    if empresa:
        st.markdown(f"**{empresa}** — NIT `{nit}`")
    st.json(info_empresa)
    if info_totales:
        st.text(info_totales.get('raw', ''))
