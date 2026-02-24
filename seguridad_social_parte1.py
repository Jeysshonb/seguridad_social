# -*- coding: utf-8 -*-
"""
seguridad_social_parte1.py
--------------------------
Parseo del archivo PILA (Planilla Integrada de Liquidación de Aportes)
en formato TXT de ancho fijo, y exportación a CSV.

Tipos de registro:
  01 -> Encabezado (aportante/empresa)
  02 -> Registros de empleados (cotizantes)
  06 -> Totales / pie de planilla
"""

import re
import io
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Constantes de posición (0-indexed) para registros tipo 02
# ---------------------------------------------------------------------------
POS_TIPO_REG       = (0,  2)
POS_SECUENCIA      = (2,  7)
POS_TIPO_DOC       = (7,  9)
POS_NUM_DOC        = (9,  25)
POS_TIPO_COTIZANTE = (25, 29)
POS_SUBTIPO_COT    = (29, 31)
POS_COD_MUNICIPIO  = (31, 36)
POS_PRIMER_APELL   = (36, 56)
POS_SEGUNDO_APELL  = (56, 86)
POS_PRIMER_NOMBRE  = (86, 106)
POS_SEGUNDO_NOMBRE = (106, 146)
# A partir de 146 viene la sección de indicadores y valores monetarios


def _campo(linea: str, inicio: int, fin: int) -> str:
    """Extrae y limpia un campo de posición fija."""
    return linea[inicio:fin].strip() if len(linea) >= fin else linea[inicio:].strip()


def _parsear_tipo01(linea: str) -> dict:
    """Parsea el registro de encabezado (tipo 01)."""
    # Buscar NIT (empieza con NI seguido de 9 dígitos)
    nit_match = re.search(r'NI(\d{9})', linea)
    nit = nit_match.group(1) if nit_match else ''
    razon_social = linea[7:].strip()[:100]
    return {
        'tipo_registro': '01',
        'nit': nit,
        'razon_social': razon_social,
    }


def _parsear_tipo06(linea: str) -> dict:
    """Parsea el registro de totales (tipo 06)."""
    # Extraer todos los bloques numéricos del registro de totales
    numeros = re.findall(r'\d+', linea[2:])
    return {
        'tipo_registro': '06',
        'raw': linea.strip(),
        'numeros_extraidos': ' | '.join(numeros),
    }


def _limpiar_segundo_nombre(raw: str) -> str:
    """
    El campo de 40 chars para segundo_nombre incluye al final los indicadores
    de novedad (X, L) seguidos de espacios.  Este helper elimina esa cola.
    Ejemplo: 'MARIA                                 X ' → 'MARIA'
    Nota: nombres que terminan en X (ej. ALEX) están protegidos porque
    los indicadores siempre van precedidos de al menos 5 espacios.
    """
    limpio = re.sub(r'\s{3,}([XL]\s*)+$', '', raw)
    return limpio.strip()


def _parsear_tipo02(linea: str) -> dict:
    """
    Parsea un registro de empleado (tipo 02).
    Retorna un diccionario con todos los campos identificados.
    """
    rec = {}

    # --- Campos de posición fija ---
    rec['tipo_registro']    = _campo(linea, *POS_TIPO_REG)
    rec['secuencia']        = _campo(linea, *POS_SECUENCIA)
    rec['tipo_doc']         = _campo(linea, *POS_TIPO_DOC)
    rec['num_doc']          = _campo(linea, *POS_NUM_DOC)
    rec['tipo_cotizante']   = _campo(linea, *POS_TIPO_COTIZANTE)
    rec['subtipo_cotizante']= _campo(linea, *POS_SUBTIPO_COT)
    rec['cod_municipio']    = _campo(linea, *POS_COD_MUNICIPIO)
    rec['primer_apellido']  = _campo(linea, *POS_PRIMER_APELL)
    rec['segundo_apellido'] = _campo(linea, *POS_SEGUNDO_APELL)
    rec['primer_nombre']    = _campo(linea, *POS_PRIMER_NOMBRE)
    # segundo_nombre: campo de 40 chars que incluye indicadores al final → limpiar
    rec['segundo_nombre']   = _limpiar_segundo_nombre(
        linea[POS_SEGUNDO_NOMBRE[0]:POS_SEGUNDO_NOMBRE[1]]
        if len(linea) >= POS_SEGUNDO_NOMBRE[1]
        else linea[POS_SEGUNDO_NOMBRE[0]:]
    )

    # Nombre completo para facilitar lectura
    apellidos = ' '.join(filter(None, [rec['primer_apellido'], rec['segundo_apellido']]))
    nombres   = ' '.join(filter(None, [rec['primer_nombre'],  rec['segundo_nombre']]))
    rec['nombre_completo'] = f"{apellidos} {nombres}".strip()

    # --- Sección posterior a los nombres (indicadores + montos) ---
    resto = linea[146:] if len(linea) > 146 else ''

    # Indicadores de novedades (ingreso, retiro, licencia, etc.)
    # Se buscan los primeros ~20 chars para detectar flags X / L
    indicadores_raw = linea[146:166] if len(linea) > 166 else linea[146:]
    rec['ind_ingreso']   = 'X' if indicadores_raw.startswith('X') or \
                            (len(indicadores_raw) > 0 and indicadores_raw[0] == 'X') else ''
    rec['ind_retiro']    = 'X' if len(indicadores_raw) > 1 and indicadores_raw[1] == 'X' else ''
    rec['ind_licencia']  = 'L' if 'L' in indicadores_raw[:15] else ''
    rec['indicadores_raw'] = indicadores_raw

    # --- Código EPS (EPS###, ESSC##, CCFC##) ---
    eps_match = re.search(r'(EPS\w{2,3}|ESSC\w{2}|CCFC\w{2})', resto)
    rec['cod_eps'] = eps_match.group(0) if eps_match else ''

    # --- Código CCF (CCF## o CCF#) ---
    ccf_match = re.search(r'CCF\w{1,2}', resto)
    rec['cod_ccf'] = ccf_match.group(0) if ccf_match else ''

    # --- Días (8 dígitos) + IBC (9 dígitos) + Forma (F/V) ---
    # Patrón: DDPPAACC + IBC9 + F/V  (después del código CCF)
    din_match = re.search(r'CCF\w{1,2}\s+(\d{8})(\d{9})([FV])', linea)
    if din_match:
        dias_raw = din_match.group(1)
        rec['dias_eps']        = int(dias_raw[0:2])
        rec['dias_pension']    = int(dias_raw[2:4])
        rec['dias_arl']        = int(dias_raw[4:6])
        rec['dias_ccf']        = int(dias_raw[6:8])
        rec['ibc']             = int(din_match.group(2))
        rec['forma_salario']   = din_match.group(3)

        # Texto que viene después del indicador de forma (F/V)
        after_form_pos = din_match.end()
        after_form = linea[after_form_pos:]

        # Cuatro bloques de IBC desglosado (9 chars c/u)
        ibcs_match = re.match(r'(\d{9})(\d{9})(\d{9})(\d{9})', after_form)
        if ibcs_match:
            rec['ibc_pension_campo'] = int(ibcs_match.group(1))
            rec['ibc_eps_campo']     = int(ibcs_match.group(2))
            rec['ibc_arl_campo']     = int(ibcs_match.group(3))
            rec['ibc_ccf_campo']     = int(ibcs_match.group(4))
            tail = after_form[36:]
        else:
            tail = after_form

        # Tarifas y aportes (formato .TT########## repetido)
        # Pensión (tarifa ~0.16)
        pension_m = re.search(r'\.(\d{2})(\d{6})(\d{9})', tail)
        if pension_m:
            rec['tarifa_pension']  = float(f"0.{pension_m.group(1)}")
            rec['aporte_pension']  = int(pension_m.group(3))
            tail2 = tail[pension_m.end():]
        else:
            tail2 = tail

        # EPS (tarifa ~0.125)
        eps_m = re.search(r'\.(\d{2,3})(\d{6})(\d{9})', tail2)
        if eps_m:
            rec['tarifa_eps']  = float(f"0.{eps_m.group(1)}")
            rec['aporte_eps']  = int(eps_m.group(3))
            tail3 = tail2[eps_m.end():]
        else:
            tail3 = tail2

        # ARL (tarifa variable, ej. 0.00522)
        arl_m = re.search(r'\.(00\d{3})(\d{6})(\d{9})', tail3)
        if arl_m:
            rec['tarifa_arl']  = float(f"0.{arl_m.group(1)}")
            rec['aporte_arl']  = int(arl_m.group(3))
            tail4 = tail3[arl_m.end():]
        else:
            tail4 = tail3

        # CCF (tarifa ~0.04)
        ccf_m = re.search(r'\.(\d{2})(\d{6})(\d{9})', tail4)
        if ccf_m:
            rec['tarifa_ccf']  = float(f"0.{ccf_m.group(1)}")
            rec['aporte_ccf']  = int(ccf_m.group(3))
    else:
        # Si no hay patrón de días+IBC, dejar en blanco
        for col in ['dias_eps', 'dias_pension', 'dias_arl', 'dias_ccf',
                    'ibc', 'forma_salario']:
            rec[col] = None

    # --- Fecha inicio / fin de novedad (formato YYYY-MM-DD) ---
    fechas = re.findall(r'\d{4}-\d{2}-\d{2}', linea)
    rec['fecha_inicio_novedad'] = fechas[0] if len(fechas) > 0 else ''
    rec['fecha_fin_novedad']    = fechas[1] if len(fechas) > 1 else ''

    # --- Período de planilla (S14-28 o similar) ---
    periodo_m = re.search(r'S(\d{2}-\d{2})', linea)
    rec['periodo_planilla'] = periodo_m.group(1) if periodo_m else ''

    return rec


# ---------------------------------------------------------------------------
# Función principal de parseo
# ---------------------------------------------------------------------------
def parse_pila_txt(contenido) -> tuple[pd.DataFrame, dict, dict]:
    """
    Parsea el contenido de un archivo PILA TXT.

    Parámetros
    ----------
    contenido : str | bytes
        Contenido del archivo. Si es bytes se decodifica con latin-1.

    Retorna
    -------
    df_empleados : pd.DataFrame
        DataFrame con todos los registros tipo 02.
    info_empresa : dict
        Información del registro tipo 01 (encabezado).
    info_totales : dict
        Información del registro tipo 06 (totales).
    """
    if isinstance(contenido, bytes):
        contenido = contenido.decode('latin-1')

    lineas = contenido.splitlines()

    info_empresa = {}
    info_totales = {}
    registros = []

    for i, linea in enumerate(lineas, start=1):
        if len(linea) < 2:
            continue
        tipo = linea[0:2]
        try:
            if tipo == '01':
                info_empresa = _parsear_tipo01(linea)
            elif tipo == '02':
                rec = _parsear_tipo02(linea)
                rec['num_linea'] = i
                registros.append(rec)
            elif tipo == '06':
                info_totales = _parsear_tipo06(linea)
        except Exception as e:
            registros.append({
                'tipo_registro': tipo,
                'num_linea': i,
                'error_parseo': str(e),
                'raw': linea[:80],
            })

    df = pd.DataFrame(registros)

    # Ordenar columnas de forma lógica si existen
    cols_orden = [
        'num_linea', 'tipo_registro', 'secuencia',
        'tipo_doc', 'num_doc',
        'primer_apellido', 'segundo_apellido',
        'primer_nombre', 'segundo_nombre', 'nombre_completo',
        'tipo_cotizante', 'subtipo_cotizante',
        'cod_municipio',
        'cod_eps', 'cod_ccf',
        'dias_eps', 'dias_pension', 'dias_arl', 'dias_ccf',
        'ibc', 'forma_salario',
        'ibc_pension_campo', 'ibc_eps_campo', 'ibc_arl_campo', 'ibc_ccf_campo',
        'tarifa_pension', 'aporte_pension',
        'tarifa_eps', 'aporte_eps',
        'tarifa_arl', 'aporte_arl',
        'tarifa_ccf', 'aporte_ccf',
        'ind_ingreso', 'ind_retiro', 'ind_licencia',
        'fecha_inicio_novedad', 'fecha_fin_novedad',
        'periodo_planilla',
        'indicadores_raw',
    ]
    cols_presentes = [c for c in cols_orden if c in df.columns]
    cols_extra     = [c for c in df.columns if c not in cols_orden]
    df = df[cols_presentes + cols_extra]

    return df, info_empresa, info_totales


# ---------------------------------------------------------------------------
# Exportar a CSV
# ---------------------------------------------------------------------------
def exportar_csv(df: pd.DataFrame, ruta_salida: str | Path) -> Path:
    """
    Guarda el DataFrame como CSV en la ruta indicada.

    Retorna la ruta del archivo generado.
    """
    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding='utf-8-sig', sep=';')
    return ruta


# ---------------------------------------------------------------------------
# Resumen estadístico
# ---------------------------------------------------------------------------
def resumen_planilla(df: pd.DataFrame, info_empresa: dict) -> dict:
    """
    Genera un resumen rápido de la planilla.
    """
    total_registros = len(df)
    if 'num_doc' in df.columns:
        empleados_unicos = df['num_doc'].nunique()
    else:
        empleados_unicos = 0

    total_ibc = df['ibc'].sum() if 'ibc' in df.columns else 0
    total_pension = df['aporte_pension'].sum() if 'aporte_pension' in df.columns else 0
    total_eps     = df['aporte_eps'].sum()     if 'aporte_eps'     in df.columns else 0
    total_arl     = df['aporte_arl'].sum()     if 'aporte_arl'     in df.columns else 0
    total_ccf     = df['aporte_ccf'].sum()     if 'aporte_ccf'     in df.columns else 0

    return {
        'empresa': info_empresa.get('razon_social', '')[:60],
        'nit': info_empresa.get('nit', ''),
        'total_registros': total_registros,
        'empleados_unicos': empleados_unicos,
        'total_ibc': int(total_ibc) if pd.notna(total_ibc) else 0,
        'total_pension': int(total_pension) if pd.notna(total_pension) else 0,
        'total_eps':     int(total_eps)     if pd.notna(total_eps)     else 0,
        'total_arl':     int(total_arl)     if pd.notna(total_arl)     else 0,
        'total_ccf':     int(total_ccf)     if pd.notna(total_ccf)     else 0,
    }


# ---------------------------------------------------------------------------
# CLI rápido (ejecución directa)
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Uso: python seguridad_social_parte1.py <archivo.TxT> [carpeta_salida]")
        sys.exit(1)

    archivo_entrada = Path(sys.argv[1])
    carpeta_salida  = Path(sys.argv[2]) if len(sys.argv) > 2 else archivo_entrada.parent

    print(f"Leyendo: {archivo_entrada}")
    with open(archivo_entrada, 'r', encoding='latin-1') as f:
        contenido = f.read()

    df, empresa, totales = parse_pila_txt(contenido)

    nombre_csv = archivo_entrada.stem + '.csv'
    ruta_csv   = carpeta_salida / nombre_csv
    exportar_csv(df, ruta_csv)

    resumen = resumen_planilla(df, empresa)
    print("\n=== RESUMEN ===")
    for k, v in resumen.items():
        print(f"  {k}: {v:,}" if isinstance(v, int) and v > 999 else f"  {k}: {v}")
    print(f"\nCSV generado: {ruta_csv}")
    print(f"Filas exportadas: {len(df):,}")
