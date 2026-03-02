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
    construir_codigos_autogen_text,
    exportar_codigos_autogen,
    generar_reporte_inconsistencias,
    obtener_overrides_admin,
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
def _cached_overrides(df: pd.DataFrame, ruta_comp: str, ruta_comp_mtime: float | None):
    ruta = Path(ruta_comp) if ruta_comp else None
    return obtener_overrides_admin(df, None, ruta)


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
comp_ok = RUTA_COMP_DEFAULT.exists()

dot_comp = '<span class="badge-dot-ok"></span>' if comp_ok else '<span class="badge-dot-no"></span>'
lbl_comp = f'<span class="badge badge-ok">{dot_comp} Comparación</span>' if comp_ok else f'<span class="badge badge-no">{dot_comp} Sin comparación</span>'

st.markdown(f"""
<div class="ssnl-header">
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
  <div class="kpi">
    <div class="k-lbl">Empleados únicos</div>
    <div class="k-val">{resumen['empleados_unicos']:,}</div>
    <div class="k-sub">{len(df_ok):,} registros en planilla</div>
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
# Exportar — 1 solo CSV
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-label">Exportar</div>', unsafe_allow_html=True)

encabezado = st.selectbox(
    "Encabezado exportacion",
    options=["snake", "oficial"],
    index=0,
    help="Snake_case por defecto. Usa oficial si necesitas compatibilidad con comparacion.csv.",
)

filtro_sig = (tuple(f_eps), tuple(f_ccf), tuple(f_afp), tuple(f_tipo), buscar, encabezado)
if st.session_state.get("csv_sig") != filtro_sig:
    st.session_state["csv_sig"] = filtro_sig
    st.session_state["csv_ready"] = False

if st.button("Generar CSV"):
    st.session_state["csv_ready"] = True

nombre_csv = Path(archivo.name).stem + ".csv"
csv_bytes = None
if st.session_state.get("csv_ready"):
    csv_bytes = _cached_build_csv(
        df_f,
        str(ruta_comp) if ruta_comp else '',
        ruta_comp_mtime,
        encabezado,
    )
else:
    st.caption("Haz clic en Generar CSV para preparar la descarga.")

overrides = _cached_overrides(df, str(ruta_comp) if ruta_comp else '', ruta_comp_mtime)
autogen_text = construir_codigos_autogen_text(overrides)
autogen_bytes = autogen_text.encode("utf-8") if autogen_text else None

col_dl, col_sv = st.columns([1, 2])
with col_dl:
    if csv_bytes:
        st.download_button(
            label="Descargar CSV",
            data=csv_bytes,
            file_name=nombre_csv,
            mime="text/csv",
        )
    else:
        st.caption("CSV no generado aun.")
with col_sv:
    if autogen_bytes:
        st.download_button(
            label="Descargar codigos autogen",
            data=autogen_bytes,
            file_name="codigos_admin_autogen.txt",
            mime="text/plain",
        )
    if st.checkbox("Guardar en carpeta Salida", value=False):
        if csv_bytes:
            (SALIDA_DIR / nombre_csv).write_bytes(csv_bytes)
            st.caption(f"Guardado en {SALIDA_DIR / nombre_csv}")
        else:
            st.caption("Genera el CSV antes de guardar.")
        if autogen_bytes:
            exportar_codigos_autogen(overrides, SALIDA_DIR / "codigos_admin_autogen.txt")
            st.caption(f"Guardado en {SALIDA_DIR / 'codigos_admin_autogen.txt'}")

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
