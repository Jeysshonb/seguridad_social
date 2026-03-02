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
    construir_df_formato_comparacion,
    parse_pila_txt,
    resumen_planilla,
)
from pila.comparacion import (
    generar_reporte_inconsistencias,
)
from pila.validacion import generar_reporte_validaciones, validar_planilla

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
RUTA_COMP_DEFAULT = BASE_DIR / "seguridad_archivos" / "NOMINA REGULAR" / "comparacion.csv"
SEP = ";"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _cached_parse(contenido_bytes: bytes):
    return parse_pila_txt(contenido_bytes)


@st.cache_data(show_spinner=False)
def _cached_adapt(df: pd.DataFrame, ruta_comp: str, ruta_comp_mtime: float | None):
    ruta = Path(ruta_comp) if ruta_comp else None
    return adaptar_admin_con_referencias(df, None, ruta)


@st.cache_data(show_spinner=False)
def _cached_build_csv(df: pd.DataFrame, ruta_comp: str, ruta_comp_mtime: float | None, encabezado: str):
    ruta = Path(ruta_comp) if ruta_comp else None
    df_cmp = construir_df_formato_comparacion(df, ruta, encabezado=encabezado)
    csv_buf = io.StringIO()
    df_cmp.to_csv(csv_buf, index=False, encoding="utf-8-sig", sep=SEP)
    return csv_buf.getvalue().encode("utf-8-sig")


@st.cache_data(show_spinner=False)
def _cached_validaciones(df: pd.DataFrame, info_empresa: dict, info_totales: dict):
    return validar_planilla(df, info_empresa, info_totales)


@st.cache_data(show_spinner=False)
def _cached_reporte_validaciones(df: pd.DataFrame, info_empresa: dict, info_totales: dict):
    return generar_reporte_validaciones(df, info_empresa, info_totales)

# ---------------------------------------------------------------------------
# Estilos — responde automáticamente al tema claro/oscuro del sistema
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

/* ── Design tokens ──────────────────────────────────────── */
:root {
    --bg:         #F0F2F8;
    --surface:    #FFFFFF;
    --surface-2:  #F8F9FC;
    --border:     #E2E8F0;
    --txt:        #0F172A;
    --txt-soft:   #64748B;
    --txt-xs:     #94A3B8;

    --indigo:     #4F46E5;
    --indigo-lt:  #EEF2FF;
    --purple:     #7C3AED;
    --purple-lt:  #F5F3FF;
    --teal:       #0D9488;
    --teal-lt:    #F0FDFA;
    --emerald:    #059669;
    --emerald-lt: #ECFDF5;
    --amber:      #D97706;
    --amber-lt:   #FFFBEB;
    --cyan:       #0891B2;
    --cyan-lt:    #ECFEFF;

    --green:      #059669;
    --green-bg:   #ECFDF5;
    --red:        #E11D48;
    --red-bg:     #FFF1F2;

    --shadow:     0 1px 3px rgba(15,23,42,.06), 0 1px 2px rgba(15,23,42,.04);
    --shadow-md:  0 4px 8px rgba(15,23,42,.08), 0 2px 4px rgba(15,23,42,.04);
    --shadow-lg:  0 12px 28px rgba(15,23,42,.12), 0 4px 10px rgba(15,23,42,.06);
    --radius:     16px;
    --radius-sm:  10px;
}

@media (prefers-color-scheme: dark) {
    :root {
        --bg:         #080D18;
        --surface:    #0F172A;
        --surface-2:  #141E33;
        --border:     #1E293B;
        --txt:        #E2E8F0;
        --txt-soft:   #94A3B8;
        --txt-xs:     #475569;

        --indigo:     #818CF8;
        --indigo-lt:  #1E1B4B;
        --purple:     #A78BFA;
        --purple-lt:  #2E1065;
        --teal:       #2DD4BF;
        --teal-lt:    #042F2E;
        --emerald:    #34D399;
        --emerald-lt: #022C22;
        --amber:      #FCD34D;
        --amber-lt:   #2A1800;
        --cyan:       #22D3EE;
        --cyan-lt:    #082F49;

        --green:      #34D399;
        --green-bg:   #022C22;
        --red:        #FB7185;
        --red-bg:     #4C0519;

        --shadow:     0 1px 3px rgba(0,0,0,.3),  0 1px 2px rgba(0,0,0,.2);
        --shadow-md:  0 4px 8px rgba(0,0,0,.35), 0 2px 4px rgba(0,0,0,.2);
        --shadow-lg:  0 12px 28px rgba(0,0,0,.55), 0 4px 10px rgba(0,0,0,.3);
    }
}

/* ── Base ───────────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
.stApp {
    background: var(--bg) !important;
    font-family: "Plus Jakarta Sans", system-ui, sans-serif !important;
    color: var(--txt) !important;
}

[data-testid="stSidebar"]    { display: none !important; }
[data-testid="stHeader"]     { background: transparent !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }

/* ── Header ─────────────────────────────────────────────── */
.ssnl-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 55%, #312e81 100%);
    border-radius: var(--radius);
    padding: 32px 36px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}
.ssnl-header::before {
    content: '';
    position: absolute;
    width: 340px; height: 340px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(124,58,237,.4) 0%, transparent 65%);
    top: -110px; right: -70px;
    pointer-events: none;
}
.ssnl-header::after {
    content: '';
    position: absolute;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(79,70,229,.3) 0%, transparent 70%);
    bottom: -80px; left: 25%;
    pointer-events: none;
}
.ssnl-icon {
    font-size: 42px;
    margin-right: 16px;
    flex-shrink: 0;
    filter: drop-shadow(0 2px 10px rgba(124,58,237,.6));
    position: relative; z-index: 1;
}
.ssnl-title { line-height: 1; flex: 1; position: relative; z-index: 1; }
.ssnl-title h1 {
    margin: 0 0 6px 0;
    font-size: 26px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.5px;
}
.ssnl-title p {
    margin: 0;
    font-size: 13px;
    color: rgba(255,255,255,.5);
    font-weight: 400;
}
.ssnl-badges { display:flex; gap:8px; align-items:center; flex-wrap:wrap; flex-shrink:0; position:relative; z-index:1; }

/* ── Badges ─────────────────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 13px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
.badge-ok { background: rgba(52,211,153,.15); color: #34D399; border: 1px solid rgba(52,211,153,.35); }
.badge-no { background: rgba(251,113,133,.15); color: #FB7185; border: 1px solid rgba(251,113,133,.35); }
.badge-dot-ok { width:6px; height:6px; border-radius:50%; background:#34D399; }
.badge-dot-no { width:6px; height:6px; border-radius:50%; background:#FB7185; }

/* ── Cards ──────────────────────────────────────────────── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px 24px;
    margin-bottom: 18px;
    box-shadow: var(--shadow-md);
}
.card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--txt-xs);
    margin-bottom: 16px;
}

/* ── KPI strip ──────────────────────────────────────────── */
.kpi-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
    gap: 14px;
    margin-bottom: 22px;
}
.kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    box-shadow: var(--shadow-md);
    position: relative;
    overflow: hidden;
    transition: transform .15s ease, box-shadow .15s ease;
    cursor: default;
}
.kpi:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }

.kpi-indigo::before  { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#4F46E5,#818CF8); border-radius:var(--radius) var(--radius) 0 0; }
.kpi-purple::before  { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#7C3AED,#A78BFA); border-radius:var(--radius) var(--radius) 0 0; }
.kpi-teal::before    { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#0D9488,#2DD4BF); border-radius:var(--radius) var(--radius) 0 0; }
.kpi-emerald::before { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#059669,#34D399); border-radius:var(--radius) var(--radius) 0 0; }
.kpi-amber::before   { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#D97706,#FCD34D); border-radius:var(--radius) var(--radius) 0 0; }
.kpi-cyan::before    { content:''; position:absolute; top:0;left:0;right:0;height:4px; background:linear-gradient(90deg,#0891B2,#22D3EE); border-radius:var(--radius) var(--radius) 0 0; }

.kpi .k-icon { font-size: 20px; margin-bottom: 10px; display: block; }
.kpi .k-lbl  { font-size: 11px; color: var(--txt-soft); font-weight: 600; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi .k-val  { font-size: 20px; font-weight: 800; color: var(--txt); letter-spacing: -0.5px; }
.kpi .k-sub  { font-size: 11px; color: var(--txt-xs); margin-top: 4px; }

/* ── Upload zone ────────────────────────────────────────── */
[data-testid="stFileUploader"] > div {
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--surface-2) !important;
    transition: border-color .2s, background .2s;
}
[data-testid="stFileUploader"] > div:hover {
    border-color: var(--indigo) !important;
    background: var(--indigo-lt) !important;
}

/* ── Buttons ────────────────────────────────────────────── */
.stDownloadButton > button {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: "Plus Jakarta Sans", sans-serif !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 11px 22px !important;
    letter-spacing: 0.2px !important;
    width: 100% !important;
    box-shadow: 0 4px 14px rgba(79,70,229,.4) !important;
    transition: opacity .15s, transform .1s !important;
}
.stDownloadButton > button:hover { opacity: .88 !important; transform: translateY(-1px) !important; }

.stButton > button {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: "Plus Jakarta Sans", sans-serif !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 10px 22px !important;
    box-shadow: 0 4px 14px rgba(79,70,229,.4) !important;
    transition: opacity .15s, transform .1s !important;
}
.stButton > button:hover { opacity: .88 !important; transform: translateY(-1px) !important; }

/* ── Expanders ──────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--surface) !important;
    box-shadow: var(--shadow) !important;
}

/* ── Selects & inputs ───────────────────────────────────── */
[data-baseweb="select"] > div { border-radius: var(--radius-sm) !important; }
input[type="text"]            { border-radius: var(--radius-sm) !important; }

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--indigo); }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
comp_ok = RUTA_COMP_DEFAULT.exists()

dot_comp = '<span class="badge-dot-ok"></span>' if comp_ok else '<span class="badge-dot-no"></span>'
lbl_comp = f'<span class="badge badge-ok">{dot_comp} Comparación</span>' if comp_ok else f'<span class="badge badge-no">{dot_comp} Sin comparación</span>'

st.markdown(f"""
<div class="ssnl-header">
  <span class="ssnl-icon">📋</span>
  <div class="ssnl-title">
    <h1>Seguridad Social Nómina</h1>
    <p>Procesamiento y validación de planillas PILA en formato TXT</p>
  </div>
  <div class="ssnl-badges">
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
    df_raw, info_empresa, info_totales = _cached_parse(contenido_bytes)
    ruta_comp = RUTA_COMP_DEFAULT if comp_ok else None
    ruta_comp_mtime = ruta_comp.stat().st_mtime if ruta_comp else None
    df = _cached_adapt(df_raw, str(ruta_comp) if ruta_comp else '', ruta_comp_mtime)

df_ok = df
if 'error_parseo' in df_ok.columns:
    df_ok = df_ok[df_ok['error_parseo'].isna()]

resumen = resumen_planilla(df_ok, info_empresa)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
empresa = str(resumen.get('empresa', '')).strip()
nit     = str(resumen.get('nit', '')).strip()

st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi kpi-indigo">
    <span class="k-icon">👥</span>
    <div class="k-lbl">Empleados únicos</div>
    <div class="k-val">{resumen['empleados_unicos']:,}</div>
    <div class="k-sub">{len(df_ok):,} registros</div>
  </div>
  <div class="kpi kpi-purple">
    <span class="k-icon">💼</span>
    <div class="k-lbl">IBC Total</div>
    <div class="k-val">${resumen['total_ibc']:,.0f}</div>
  </div>
  <div class="kpi kpi-teal">
    <span class="k-icon">🏦</span>
    <div class="k-lbl">Pensión</div>
    <div class="k-val">${resumen['total_pension']:,.0f}</div>
  </div>
  <div class="kpi kpi-emerald">
    <span class="k-icon">🏥</span>
    <div class="k-lbl">Salud (EPS)</div>
    <div class="k-val">${resumen['total_eps']:,.0f}</div>
  </div>
  <div class="kpi kpi-amber">
    <span class="k-icon">⚠️</span>
    <div class="k-lbl">ARL</div>
    <div class="k-val">${resumen['total_arl']:,.0f}</div>
  </div>
  <div class="kpi kpi-cyan">
    <span class="k-icon">🏢</span>
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
        ops_eps  = sorted(df_ok['admin_eps'].dropna().unique()) if 'admin_eps' in df_ok.columns else []
        f_eps    = st.multiselect("EPS", ops_eps)
    with c2:
        ops_ccf  = sorted(df_ok['admin_ccf'].dropna().unique()) if 'admin_ccf' in df_ok.columns else []
        f_ccf    = st.multiselect("CCF", ops_ccf)
    with c3:
        ops_afp  = sorted(df_ok['admin_afp'].dropna().unique()) if 'admin_afp' in df_ok.columns else []
        f_afp    = st.multiselect("AFP", ops_afp)
    with c4:
        ops_tipo = sorted(df_ok['tipo_de_cotizante'].dropna().unique()) if 'tipo_de_cotizante' in df_ok.columns else []
        f_tipo   = st.multiselect("Tipo cotizante", ops_tipo)
    with c5:
        buscar = st.text_input("Buscar nombre / documento")

df_f = df_ok.copy()
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
    'ibc', 'exonerado', 'actividad_economica',
]
cols_disp = [c for c in COLS_DEFAULT if c in df_f.columns]

st.markdown('<div class="card"><div class="card-label">Datos</div>', unsafe_allow_html=True)
with st.expander("Seleccionar columnas", expanded=False):
    todas = cols_disp + [c for c in df_f.columns if c not in cols_disp]
    cols_sel = st.multiselect("Columnas visibles", todas, default=cols_disp)

st.caption(f"{len(df_f):,} de {len(df_ok):,} registros")
st.dataframe(df_f[cols_sel] if cols_sel else df_f[cols_disp], use_container_width=True, height=500)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-label">Exportar</div>', unsafe_allow_html=True)

col_enc, col_btn = st.columns([2, 1])
with col_enc:
    encabezado = st.selectbox(
        "Encabezado",
        options=["snake", "oficial"],
        index=0,
        help="Snake_case por defecto. Usa oficial si necesitas compatibilidad con comparacion.csv.",
        label_visibility="collapsed",
    )
with col_btn:
    nombre_csv = Path(archivo.name).stem + ".csv"
    csv_bytes = _cached_build_csv(
        df_f,
        str(ruta_comp) if ruta_comp else '',
        ruta_comp_mtime,
        encabezado,
    )
    st.download_button(
        label="Descargar CSV",
        data=csv_bytes,
        file_name=nombre_csv,
        mime="text/csv",
        use_container_width=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------
with st.expander("Validaciones", expanded=False):
    datos_val = _cached_validaciones(df, info_empresa, info_totales)
    kpi = datos_val["kpis"]

    kc1, kc2, kc3, kc4, kc5, kc6 = st.columns(6)
    kc1.metric("Errores parseo", kpi["errores_parseo"])
    kc2.metric("Tipo desconocido", kpi["registros_desconocidos"])
    kc3.metric("Campos vacios", kpi["campos_criticos_vacios"])
    kc4.metric("Codigos desconocidos", kpi["codigos_desconocidos"])
    kc5.metric("Municipios desconocidos", kpi["municipios_desconocidos"])
    kc6.metric("Inconsistencias admin", kpi["inconsistencias_admin"])

    reporte_txt = _cached_reporte_validaciones(df, info_empresa, info_totales)
    st.download_button(
        label="Descargar reporte validaciones",
        data=reporte_txt.encode("utf-8"),
        file_name="reporte_validaciones.txt",
        mime="text/plain",
    )

    st.markdown("**Errores de parseo**")
    if datos_val["errores_parseo"].empty:
        st.caption("Sin errores.")
    else:
        st.dataframe(datos_val["errores_parseo"], use_container_width=True, height=200)

    st.markdown("**Campos criticos vacios**")
    if datos_val["campos_criticos_vacios"].empty:
        st.caption("Sin faltantes.")
    else:
        st.dataframe(datos_val["campos_criticos_vacios"], use_container_width=True, height=200)

    st.markdown("**Codigos desconocidos**")
    st.text(
        "AFP: "
        + (", ".join(datos_val["codigos_desconocidos"]["afp"]) or "(sin codigos)")
    )
    st.text(
        "EPS: "
        + (", ".join(datos_val["codigos_desconocidos"]["eps"]) or "(sin codigos)")
    )
    st.text(
        "CCF: "
        + (", ".join(datos_val["codigos_desconocidos"]["ccf"]) or "(sin codigos)")
    )

    st.markdown("**Municipios desconocidos**")
    if datos_val["municipios_desconocidos"]:
        st.text(", ".join(datos_val["municipios_desconocidos"]))
    else:
        st.caption("Sin municipios.")

    st.markdown("**Inconsistencias admin**")
    if datos_val["inconsistencias_admin"].empty:
        st.caption("Sin inconsistencias.")
    else:
        st.dataframe(datos_val["inconsistencias_admin"], use_container_width=True, height=200)

    st.markdown("**Reporte inconsistencias vs referencia (opcional)**")
    ref_archivo = st.file_uploader(
        "Sube referencia (txt/csv) para comparar",
        type=["txt", "csv", "tsv"],
        key="ref_cmp",
    )
    if ref_archivo is not None:
        ref_bytes = ref_archivo.getvalue()
        ref_nombre = Path(ref_archivo.name).name
        if st.button("Generar reporte inconsistencias"):
            ruta_ref = SALIDA_DIR / ref_nombre
            ruta_ref.write_bytes(ref_bytes)
            ruta_rep = SALIDA_DIR / (Path(ref_nombre).stem + "_reporte.txt")
            generar_reporte_inconsistencias(df, ruta_ref, ruta_rep, ruta_comp)
            st.download_button(
                label="Descargar reporte inconsistencias",
                data=ruta_rep.read_bytes(),
                file_name=ruta_rep.name,
                mime="text/plain",
            )

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
