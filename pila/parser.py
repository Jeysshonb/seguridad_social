# -*- coding: utf-8 -*-
"""
Parser PILA para archivos de ancho fijo.
"""

import math
import re
from pathlib import Path

import pandas as pd

from .catalogos import (
    ARL_CLASE_POR_TARIFA,
    ARL_POR_PREFIJO,
    DANE_MUNICIPIOS,
    TIPO_COTIZANTE_LABEL,
    lookup_admin,
)
from .normalizacion import _normalizar_columnas


RE_NIT = re.compile(r'NI(\d{9})')
RE_NUM = re.compile(r'\d+')
RE_PERIODO = re.compile(r'[SN](\d{2}-\d{2})')
RE_TARIFAS = re.compile(r'0\.(\d{6})')
RE_EOL = re.compile(r'(\d{9})(\d{3})\s+(\d{7})\s*$')
RE_FECHA = re.compile(r'(\d{4})-(\d{2})-(\d{2})')


def _afp_code_clean(raw_8char: str) -> str:
    """Extrae el codigo limpio de AFP del campo de 8 chars."""
    raw = raw_8char.strip()
    if len(raw) >= 6:
        tail6 = raw[-6:]
        if tail6.isdigit():
            return tail6
    return raw if raw.isdigit() else ''


def _campo(linea: str, inicio: int, fin: int, linea_len: int = None) -> str:
    """Extrae y limpia un campo de posicion fija."""
    if linea_len is None:
        linea_len = len(linea)
    return linea[inicio:fin].strip() if linea_len >= fin else linea[inicio:].strip()


def _pila_redondear(valor: float) -> int:
    """Redondeo PILA: al proximo multiplo de 100 pesos (ceil)."""
    return math.ceil(valor / 100) * 100


# ---------------------------------------------------------------------------
# Parsers de registros
# ---------------------------------------------------------------------------

def _parsear_tipo01(linea: str) -> dict:
    nit_m = RE_NIT.search(linea)
    nit = nit_m.group(1) if nit_m else ''
    razon_social = linea[7:].strip()[:100]
    return {'tipo_registro': '01', 'nit': nit, 'razon_social': razon_social}


def _parsear_tipo06(linea: str) -> dict:
    numeros = RE_NUM.findall(linea[2:])
    return {
        'tipo_registro': '06',
        'raw': linea.strip(),
        'numeros_extraidos': ' | '.join(numeros),
    }


def _parsear_tipo02(linea: str) -> dict:
    """
    Parsea un registro de empleado (tipo 02).
    Usa posiciones fijas confirmadas por analisis del archivo real.
    """
    rec = {}
    linea_len = len(linea)

    # Identidad
    rec['No']               = _campo(linea, 2, 7, linea_len)
    rec['Tipo_ID']          = _campo(linea, 7, 9, linea_len)
    rec['No_ID']            = _campo(linea, 9, 25, linea_len)
    rec['Primer_Apellido']  = _campo(linea, 36, 56, linea_len)
    rec['Segundo_Apellido'] = _campo(linea, 56, 86, linea_len)
    rec['Primer_Nombre']    = _campo(linea, 86, 106, linea_len)
    # Segundo nombre: [106:136] (30 chars), indicadores arrancan en 136
    rec['Segundo_Nombre']   = linea[106:136].strip() if linea_len > 136 else linea[106:].strip()
    rec['Nombre_Completo']  = ' '.join(filter(None, [
        rec['Primer_Apellido'], rec['Segundo_Apellido'],
        rec['Primer_Nombre'],   rec['Segundo_Nombre'],
    ]))

    cod_muni = _campo(linea, 31, 36, linea_len)
    rec['Cod_Municipio'] = cod_muni
    ciudad_info = DANE_MUNICIPIOS.get(cod_muni, ('', ''))
    rec['Ciudad'] = ciudad_info[0]
    rec['Departamento'] = ciudad_info[1]

    tipo_cot_raw = _campo(linea, 25, 29, linea_len)
    subtipo_raw = _campo(linea, 29, 31, linea_len)
    rec['Tipo_Cotizante'] = tipo_cot_raw
    rec['Subtipo_Cotizante'] = subtipo_raw
    rec['Tipo_De_Cotizante'] = TIPO_COTIZANTE_LABEL.get(tipo_cot_raw, tipo_cot_raw)
    rec['Subtipo_De_Cotizante'] = 'NINGUNO' if subtipo_raw.strip() in ('', 'X') else subtipo_raw

    # Indicadores de novedad
    # Posiciones confirmadas empiricamente:
    # 136=ING, 137=RET, 142=VSP, 144=VST, 148=SLN(L)
    def _char(pos: int) -> str:
        return linea[pos] if linea_len > pos else ' '

    _SISTEMAS = 'Todos los sistemas (ARL, AFP, CCF, EPS)'
    has_ing = _char(136) == 'X'
    has_ret = _char(137) == 'X'
    has_vsp = _char(142) == 'X'
    has_vst = _char(144) == 'X'
    has_col = _char(145) == 'X'   # Colombiano Temporalmente en el Exterior
    has_sln = _char(148) == 'L'

    rec['ING']  = _SISTEMAS if has_ing else 'NO'
    rec['RET']  = _SISTEMAS if has_ret else 'NO'
    rec['VSP']  = 'SI' if has_vsp else 'NO'
    rec['VST']  = 'SI' if has_vst else 'NO'
    rec['Colombiano_Temporalmente_En_El_Exterior'] = 'SI' if has_col else 'NO'
    # SLN: label oficial PILA (COL implica licencia no remunerada)
    rec['SLN']  = 'LICENCIA NO REMUNERADA' if (has_sln or has_col) else 'NO'
    rec['IGE']  = 'NO'
    rec['LMA']  = 'NO'
    rec['TDE']  = 'NO'
    rec['TAE']  = 'NO'
    rec['TDP']  = 'NO'
    rec['TAP']  = 'NO'
    rec['AVP']  = 'NO'
    rec['VCT']  = 'NO'
    rec['IRL']  = 'NO'

    # Fechas novedades: ING=514 | RET=524 | VSP=534
    # COL: inicio 544 / fin 554   SLN directo: inicio 604 / fin 614
    def _fecha_pos(pos: int) -> str:
        if linea_len <= pos + 10:
            return ''
        chunk = linea[pos:pos + 10]
        m = RE_FECHA.match(chunk)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        return ''

    rec['Fecha_ING']   = _fecha_pos(514) if has_ing else ''
    rec['Fecha_RET']   = _fecha_pos(524) if has_ret else ''
    rec['Fecha_VSP']   = _fecha_pos(534) if has_vsp else ''
    # Inicio/Fin SLN: COL usa 544/554; SLN directo usa 604/614
    if has_col:
        rec['Inicio_SLN'] = _fecha_pos(544)
        rec['Fin_SLN']    = _fecha_pos(554)
    elif has_sln:
        rec['Inicio_SLN'] = _fecha_pos(604)
        rec['Fin_SLN']    = _fecha_pos(614)
    else:
        rec['Inicio_SLN'] = ''
        rec['Fin_SLN']    = ''
    rec['Inicio_IGE']  = ''
    rec['Fin_IGE']     = ''
    rec['Inicio_LMA']  = ''
    rec['Fin_LMA']     = ''
    rec['Inicio_VAC_LR'] = ''
    rec['Fin_VAC_LR']    = ''
    rec['Inicio_VCT']  = ''
    rec['Fin_VCT']     = ''
    rec['Inicio_IRL']  = ''
    rec['Fin_IRL']     = ''

    # Periodo de planilla (ej. S14-28 -> '14-28')
    per_m = RE_PERIODO.search(linea[490:540])
    rec['Periodo_Planilla'] = per_m.group(1) if per_m else ''

    rec['Forma_Salario'] = _char(200)  # F=Fijo, V=Variable

    # AFP / Pension
    cod_admin_raw = _campo(linea, 151, 159, linea_len)
    rec['Cod_Admin_AFP'] = _afp_code_clean(cod_admin_raw)
    rec['Admin_AFP'] = lookup_admin(cod_admin_raw) or lookup_admin(rec['Cod_Admin_AFP'])

    rec['Dias_AFP'] = int(linea[183:185]) if linea_len > 185 and linea[183:185].isdigit() else None
    rec['IBC_AFP']  = int(linea[201:210]) if linea_len > 210 and linea[201:210].isdigit() else None

    # EPS / Salud
    rec['Cod_EPS'] = _campo(linea, 165, 171, linea_len)
    rec['Admin_EPS'] = lookup_admin(rec['Cod_EPS'])

    rec['Dias_EPS'] = int(linea[185:187]) if linea_len > 187 and linea[185:187].isdigit() else None
    rec['IBC_EPS']  = int(linea[210:219]) if linea_len > 219 and linea[210:219].isdigit() else None

    # ARL
    rec['Dias_ARL'] = int(linea[187:189]) if linea_len > 189 and linea[187:189].isdigit() else None
    rec['IBC_ARL']  = int(linea[219:228]) if linea_len > 228 and linea[219:228].isdigit() else None

    # CCF
    rec['Cod_CCF'] = _campo(linea, 177, 182, linea_len)
    rec['Admin_CCF'] = lookup_admin(rec['Cod_CCF'])

    rec['Dias_CCF'] = int(linea[189:191]) if linea_len > 191 and linea[189:191].isdigit() else None
    rec['IBC_CCF']  = int(linea[228:237]) if linea_len > 237 and linea[228:237].isdigit() else None

    # IBC global (posicion 191:200)
    rec['IBC'] = int(linea[191:200]) if linea_len > 200 and linea[191:200].isdigit() else None

    # Tarifas (secuencia fija desde pos 237: AFP, EPS, ARL, CCF, ...)
    if linea_len > 237:
        tail = linea[237:]
        tarifas = RE_TARIFAS.findall(tail)

        def _tar(idx: int) -> float:
            return float(f"0.{tarifas[idx]}") if idx < len(tarifas) else 0.0

        t_afp = _tar(0)
        t_eps = _tar(1)
        t_arl = _tar(2)
        t_ccf = _tar(3)
        t_sena = _tar(4)
        t_icbf = _tar(5)

        rec['Tarifa_AFP'] = t_afp
        rec['Tarifa_EPS'] = t_eps
        rec['Tarifa_ARL'] = t_arl
        rec['Tarifa_CCF'] = t_ccf
        rec['Exonerado']  = 'SI' if (t_sena == 0.0 and t_icbf == 0.0) else 'NO'

        ibc_afp = rec['IBC_AFP']
        ibc_eps = rec['IBC_EPS']
        ibc_arl = rec['IBC_ARL']
        ibc_ccf = rec['IBC_CCF']

        rec['Valor_AFP'] = _pila_redondear(ibc_afp * t_afp) if ibc_afp and t_afp else 0
        rec['Valor_EPS'] = _pila_redondear(ibc_eps * t_eps) if ibc_eps and t_eps else 0
        rec['Valor_ARL'] = _pila_redondear(ibc_arl * t_arl) if ibc_arl and t_arl else 0
        rec['Valor_CCF'] = _pila_redondear(ibc_ccf * t_ccf) if ibc_ccf and t_ccf else 0
    else:
        for k in ['Tarifa_AFP', 'Tarifa_EPS', 'Tarifa_ARL', 'Tarifa_CCF',
                  'Valor_AFP', 'Valor_EPS', 'Valor_ARL', 'Valor_CCF']:
            rec[k] = None
        rec['Exonerado'] = ''

    # Tarifas: clase ARL
    _t_arl_for_clase = rec.get('Tarifa_ARL', 0.0) or 0.0
    _clase_arl = ''
    for _tref, _cls in ARL_CLASE_POR_TARIFA.items():
        if abs(_t_arl_for_clase - _tref) < 0.00001:
            _clase_arl = _cls
            break
    rec['Clase_ARL'] = _clase_arl

    # Fin de linea: horas laboradas y codigo entidad
    eol_m = RE_EOL.search(linea)
    if eol_m:
        rec['Horas_Laboradas'] = int(eol_m.group(2))
        cod_entidad = eol_m.group(3)
        rec['Cod_Entidad'] = cod_entidad
        # ARL: prefijo 4 digitos del cod_entidad
        rec['Admin_ARL'] = ARL_POR_PREFIJO.get(cod_entidad[:4], '')
    else:
        rec['Horas_Laboradas'] = None
        rec['Cod_Entidad'] = ''
        rec['Admin_ARL'] = ''

    return rec


# ---------------------------------------------------------------------------
# Funcion principal de parseo
# ---------------------------------------------------------------------------

def parse_pila_txt(contenido) -> tuple:
    """
    Parsea el contenido de un archivo PILA TXT.

    Parametros
    ----------
    contenido : str | bytes
        Contenido del archivo. Si es bytes se decodifica con latin-1.

    Retorna
    -------
    df_empleados : pd.DataFrame
    info_empresa : dict
    info_totales : dict
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
                rec['Num_Linea'] = i
                registros.append(rec)
            elif tipo == '06':
                info_totales = _parsear_tipo06(linea)
            else:
                registros.append({
                    'tipo_registro': tipo,
                    'Num_Linea': i,
                    'error_parseo': 'tipo_registro_desconocido',
                    'raw': linea[:80],
                })
        except Exception as e:
            registros.append({
                'tipo_registro': tipo,
                'Num_Linea': i,
                'error_parseo': str(e),
                'raw': linea[:80],
            })

    df = pd.DataFrame(registros)
    df = _normalizar_columnas(df)
    if 'cod_entidad' in df.columns:
        df = df.rename(columns={'cod_entidad': 'actividad_economica'})

    cols_orden = [
        'num_linea', 'no', 'tipo_id', 'no_id',
        'primer_apellido', 'segundo_apellido',
        'primer_nombre', 'segundo_nombre', 'nombre_completo',
        'cod_municipio', 'tipo_cotizante', 'subtipo_cotizante',
        'horas_laboradas', 'forma_salario',
        'ing', 'fecha_ing',
        'ret', 'fecha_ret',
        'vst', 'sln', 'inicio_sln', 'fin_sln',
        'ige', 'lma',
        'periodo_planilla',
        'cod_admin_afp', 'admin_afp', 'dias_afp', 'ibc_afp', 'tarifa_afp', 'valor_afp',
        'cod_eps',       'admin_eps', 'dias_eps', 'ibc_eps', 'tarifa_eps', 'valor_eps',
        'dias_arl',                 'ibc_arl',  'tarifa_arl', 'valor_arl', 'actividad_economica',
        'cod_ccf',       'admin_ccf', 'dias_ccf', 'ibc_ccf', 'tarifa_ccf', 'valor_ccf',
        'ibc', 'exonerado',
    ]
    cols_presentes = [c for c in cols_orden if c in df.columns]
    cols_extra = [c for c in df.columns if c not in cols_orden]
    df = df[cols_presentes + cols_extra]

    return df, info_empresa, info_totales


# ---------------------------------------------------------------------------
# Exportar a CSV
# ---------------------------------------------------------------------------

def exportar_csv(df: pd.DataFrame, ruta_salida) -> Path:
    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding='utf-8-sig', sep=';')
    return ruta


# ---------------------------------------------------------------------------
# Resumen estadistico
# ---------------------------------------------------------------------------

def resumen_planilla(df: pd.DataFrame, info_empresa: dict) -> dict:
    df_base = df
    if 'error_parseo' in df_base.columns:
        df_base = df_base[df_base['error_parseo'].isna()]

    total_registros = len(df_base)
    empleados_unicos = df_base['no_id'].nunique() if 'no_id' in df_base.columns else 0
    total_ibc = df_base['ibc'].sum() if 'ibc' in df_base.columns else 0
    total_pension = df_base['valor_afp'].sum() if 'valor_afp' in df_base.columns else 0
    total_eps = df_base['valor_eps'].sum() if 'valor_eps' in df_base.columns else 0
    total_arl = df_base['valor_arl'].sum() if 'valor_arl' in df_base.columns else 0
    total_ccf = df_base['valor_ccf'].sum() if 'valor_ccf' in df_base.columns else 0

    def _si(v):
        return int(v) if pd.notna(v) else 0

    return {
        'empresa': info_empresa.get('razon_social', '')[:60],
        'nit': info_empresa.get('nit', ''),
        'total_registros': total_registros,
        'empleados_unicos': empleados_unicos,
        'total_ibc': _si(total_ibc),
        'total_pension': _si(total_pension),
        'total_eps': _si(total_eps),
        'total_arl': _si(total_arl),
        'total_ccf': _si(total_ccf),
    }
