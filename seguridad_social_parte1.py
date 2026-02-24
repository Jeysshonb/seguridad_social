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

Posiciones fijas confirmadas (0-indexed) para registros tipo 02:
  [0:2]    tipo_registro
  [2:7]    secuencia
  [7:9]    tipo_doc
  [9:25]   num_doc
  [25:29]  tipo_cotizante
  [29:31]  subtipo_cotizante
  [31:36]  cod_municipio (DIVIPOLA)
  [36:56]  primer_apellido (20 chars)
  [56:86]  segundo_apellido (30 chars)
  [86:106] primer_nombre (20 chars)
  [106:142] segundo_nombre (36 chars, excluye zona de indicadores)
  [142]    ING  (X = Ingreso)
  [144]    VST  (X = Variacion Salarial / activo)
  [145]    RET  (X = Retiro)
  [148]    LIC  (L = Licencia/incapacidad)
  [151:159] cod_admin_afp (8 chars, ej. '00230301')
  [165:171] cod_eps (6 chars, ej. 'EPS002')
  [177:182] cod_ccf (5 chars, ej. 'CCF22')
  [183:191] dias bloque (8 digitos = pension|eps|arl|ccf, 2 cada uno)
  [191:200] IBC (9 digitos)
  [200]    forma_salario (F=Fijo, V=Variable)
  [201:237] 4 x 9 digitos IBC por subsistema (pension, eps, arl, ccf)
  [237:]   seccion de tarifas/aportes
  EOL      (d{9})(d{3})+s+(d{7}) = monto|horas_laboradas|cod_entidad
"""

import math
import re
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Tabla de codigos administradoras
# ---------------------------------------------------------------------------
CODIGOS_ADMIN = {
    # AFP / Fondos de Pensiones
    '230101': 'AFP ISS (COLPENSIONES)',
    '230201': 'AFP COLFONDOS',
    '230301': 'AFP PORVENIR',
    '230401': 'AFP OLD MUTUAL',
    '230501': 'AFP PROTECCION',
    '230601': 'AFP ING (PROTECCION)',
    '230701': 'AFP SANTANDER',
    '230801': 'AFP DAVIVIR',
    '230901': 'AFP HORIZONTE (PORVENIR)',
    '231001': 'AFP COLFONDOS',
    '231101': 'AFP SKANDIA',
    # EPS / Entidades Promotoras de Salud
    'EPS001': 'COLSEGUROS (SURA)',
    'EPS002': 'SALUD TOTAL',
    'EPS003': 'CAFESALUD',
    'EPS005': 'FAMISANAR',
    'EPS008': 'COMPENSAR',
    'EPS010': 'MEDIMAS EPS',
    'EPS012': 'COOSALUD',
    'EPS016': 'SERVICIO OCCIDENTAL DE SALUD',
    'EPS017': 'SURA EPS',
    'EPS018': 'ALIANSALUD',
    'EPS037': 'NUEVA EPS',
    'EPS040': 'SANITAS EPS',
    'EPS041': 'COOMEVA EPS',
    'EPS044': 'AMBUQ (SALUD BOLIVAR)',
    'EPS046': 'FERROCARRILES (COLPENSIONES)',
    'EPS048': 'ECOOPSOS',
    'CCFC20': 'COMPENSAR SALUD',
    'CCFC33': 'COMFENALCO ANTIOQUIA SALUD',
    'CCFC50': 'COLSUBSIDIO SALUD',
    'CCFC55': 'CAFAM SALUD',
    'EPSC25': 'EPS CONVIDA',
    'EPSC34': 'EPS SOS',
    'EPSIC1': 'EPS MAGISTERIO 1',
    'EPSIC3': 'EPS MAGISTERIO 3',
    'EPSIC4': 'EPS MAGISTERIO 4',
    'EPSIC5': 'EPS MAGISTERIO 5',
    'EPSIC6': 'EPS MAGISTERIO 6',
    'ESSC07': 'MEDIAS (SUBSIDIADO)',
    'ESSC18': 'CONVIDA (SUBSIDIADO)',
    'ESSC24': 'COOSALUD SUBSIDIADA',
    'ESSC62': 'CAJACOPI SALUD',
    'MIN001': 'MINISTERIO SALUD',
    # CCF / Cajas de Compensacion Familiar
    'CCF04': 'COMFENALCO ANTIOQUIA',
    'CCF07': 'COMFACOR',
    'CCF08': 'COMFABOY',
    'CCF10': 'COFREM',
    'CCF11': 'COMFAMILIAR RISARALDA',
    'CCF13': 'COMFAMILIAR HUILA',
    'CCF14': 'COMFACUNDI',
    'CCF15': 'COMFATOL',
    'CCF16': 'COMFAORIENTE',
    'CCF22': 'COLSUBSIDIO',
    'CCF29': 'COMFANAR',
    'CCF30': 'COMCAJA',
    'CCF32': 'COMFAMILIAR CARTAGENA',
    'CCF33': 'CAJAMAG',
    'CCF34': 'COMFACESAR',
    'CCF35': 'COMFAPUTUMAYO',
    'CCF37': 'COMFASURORIENTE',
    'CCF40': 'COMFAUCA',
    'CCF41': 'COMFACAUCA',
    'CCF43': 'COMFACHOCO',
    'CCF44': 'CAFAM',
    'CCF48': 'COMFAMILIAR ATLANTICO',
    'CCF56': 'COMFENALCO SANTANDER',
    'CCF63': 'COMFAMILIAR NARINO',
    'CCF65': 'COMCAUCA',
    'CCF67': 'COMFABOL',
    'CCF69': 'COMFACOR (CORDOBA)',
}


def _lookup(codigo: str) -> str:
    """Busca el nombre de una administradora dado su codigo."""
    codigo = codigo.strip()
    if codigo in CODIGOS_ADMIN:
        return CODIGOS_ADMIN[codigo]
    # AFP: intentar con los ultimos 6 digitos del campo de 8 chars
    if len(codigo) >= 6:
        tail6 = codigo[-6:]
        if tail6.isdigit() and tail6 in CODIGOS_ADMIN:
            return CODIGOS_ADMIN[tail6]
    return ''


def _afp_code_clean(raw_8char: str) -> str:
    """Extrae el codigo limpio de AFP del campo de 8 chars."""
    raw = raw_8char.strip()
    if len(raw) >= 6:
        tail6 = raw[-6:]
        if tail6.isdigit():
            return tail6
    return raw


def _campo(linea: str, inicio: int, fin: int) -> str:
    """Extrae y limpia un campo de posicion fija."""
    return linea[inicio:fin].strip() if len(linea) >= fin else linea[inicio:].strip()


def _pila_redondear(valor: float) -> int:
    """Redondeo PILA: al proximo multiplo de 100 pesos (ceil)."""
    return math.ceil(valor / 100) * 100


# ---------------------------------------------------------------------------
# Parsers de registros
# ---------------------------------------------------------------------------
def _parsear_tipo01(linea: str) -> dict:
    nit_m = re.search(r'NI(\d{9})', linea)
    nit = nit_m.group(1) if nit_m else ''
    razon_social = linea[7:].strip()[:100]
    return {'tipo_registro': '01', 'nit': nit, 'razon_social': razon_social}


def _parsear_tipo06(linea: str) -> dict:
    numeros = re.findall(r'\d+', linea[2:])
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

    # ── Identidad ──────────────────────────────────────────────────────────
    rec['No']               = _campo(linea, 2, 7)
    rec['Tipo_ID']          = _campo(linea, 7, 9)
    rec['No_ID']            = _campo(linea, 9, 25)
    rec['Primer_Apellido']  = _campo(linea, 36, 56)
    rec['Segundo_Apellido'] = _campo(linea, 56, 86)
    rec['Primer_Nombre']    = _campo(linea, 86, 106)
    # Segundo nombre: hasta pos 142 (antes de zona de indicadores)
    rec['Segundo_Nombre']   = linea[106:142].strip() if len(linea) > 142 else linea[106:].strip()
    rec['Nombre_Completo']  = ' '.join(filter(None, [
        rec['Primer_Apellido'], rec['Segundo_Apellido'],
        rec['Primer_Nombre'],   rec['Segundo_Nombre'],
    ]))

    rec['Cod_Municipio']     = _campo(linea, 31, 36)
    rec['Tipo_Cotizante']    = _campo(linea, 25, 29)
    rec['Subtipo_Cotizante'] = _campo(linea, 29, 31)

    # ── Indicadores de novedad ──────────────────────────────────────────────
    def _char(pos: int) -> str:
        return linea[pos] if len(linea) > pos else ' '

    rec['ING'] = 'X' if _char(142) == 'X' else ''
    rec['VST'] = 'X' if _char(144) == 'X' else ''
    rec['RET'] = 'X' if _char(145) == 'X' else ''
    rec['SLN'] = 'X' if _char(148) == 'L' else ''
    rec['IGE'] = ''
    rec['LMA'] = ''

    # Fechas de novedad en el orden en que aparecen en la linea
    fechas = re.findall(r'\d{4}-\d{2}-\d{2}', linea)
    rec['Fecha_ING']   = fechas[0] if rec['ING'] == 'X' and fechas else ''
    rec['Fecha_RET']   = fechas[0] if rec['RET'] == 'X' and fechas else ''
    rec['Inicio_SLN']  = fechas[0] if rec['SLN'] == 'X' and len(fechas) > 0 else ''
    rec['Fin_SLN']     = fechas[1] if rec['SLN'] == 'X' and len(fechas) > 1 else ''

    # Periodo de planilla (ej. S14-28 -> '14-28')
    per_m = re.search(r'S(\d{2}-\d{2})', linea)
    rec['Periodo_Planilla'] = per_m.group(1) if per_m else ''

    rec['Forma_Salario'] = _char(200)  # F=Fijo, V=Variable

    # ── AFP / Pension ───────────────────────────────────────────────────────
    cod_admin_raw        = _campo(linea, 151, 159)
    rec['Cod_Admin_AFP'] = _afp_code_clean(cod_admin_raw)
    rec['Admin_AFP']     = _lookup(cod_admin_raw)

    rec['Dias_AFP'] = int(linea[183:185]) if len(linea) > 185 and linea[183:185].isdigit() else None
    rec['IBC_AFP']  = int(linea[201:210]) if len(linea) > 210 and linea[201:210].isdigit() else None

    # ── EPS / Salud ─────────────────────────────────────────────────────────
    rec['Cod_EPS']   = _campo(linea, 165, 171)
    rec['Admin_EPS'] = _lookup(rec['Cod_EPS'])

    rec['Dias_EPS'] = int(linea[185:187]) if len(linea) > 187 and linea[185:187].isdigit() else None
    rec['IBC_EPS']  = int(linea[210:219]) if len(linea) > 219 and linea[210:219].isdigit() else None

    # ── ARL ─────────────────────────────────────────────────────────────────
    rec['Dias_ARL'] = int(linea[187:189]) if len(linea) > 189 and linea[187:189].isdigit() else None
    rec['IBC_ARL']  = int(linea[219:228]) if len(linea) > 228 and linea[219:228].isdigit() else None

    # ── CCF ─────────────────────────────────────────────────────────────────
    rec['Cod_CCF']   = _campo(linea, 177, 182)
    rec['Admin_CCF'] = _lookup(rec['Cod_CCF'])

    rec['Dias_CCF'] = int(linea[189:191]) if len(linea) > 191 and linea[189:191].isdigit() else None
    rec['IBC_CCF']  = int(linea[228:237]) if len(linea) > 237 and linea[228:237].isdigit() else None

    # IBC global (posicion 191:200)
    rec['IBC'] = int(linea[191:200]) if len(linea) > 200 and linea[191:200].isdigit() else None

    # ── Tarifas (secuencia fija desde pos 237: AFP, EPS, ARL, CCF, ...) ────
    if len(linea) > 237:
        tail    = linea[237:]
        tarifas = re.findall(r'0\.(\d{6})', tail)

        def _tar(idx: int) -> float:
            return float(f"0.{tarifas[idx]}") if idx < len(tarifas) else 0.0

        t_afp  = _tar(0)
        t_eps  = _tar(1)
        t_arl  = _tar(2)
        t_ccf  = _tar(3)
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

    # ── Fin de linea: horas laboradas y codigo entidad ───────────────────────
    eol_m = re.search(r'(\d{9})(\d{3})\s+(\d{7})\s*$', linea)
    if eol_m:
        rec['Horas_Laboradas'] = int(eol_m.group(2))
        rec['Cod_Entidad']     = eol_m.group(3)
    else:
        rec['Horas_Laboradas'] = None
        rec['Cod_Entidad']     = ''

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

    lineas       = contenido.splitlines()
    info_empresa = {}
    info_totales = {}
    registros    = []

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
        except Exception as e:
            registros.append({
                'tipo_registro': tipo,
                'Num_Linea': i,
                'error_parseo': str(e),
                'raw': linea[:80],
            })

    df = pd.DataFrame(registros)

    cols_orden = [
        'Num_Linea', 'No', 'Tipo_ID', 'No_ID',
        'Primer_Apellido', 'Segundo_Apellido',
        'Primer_Nombre', 'Segundo_Nombre', 'Nombre_Completo',
        'Cod_Municipio', 'Tipo_Cotizante', 'Subtipo_Cotizante',
        'Horas_Laboradas', 'Forma_Salario',
        'ING', 'Fecha_ING',
        'RET', 'Fecha_RET',
        'VST', 'SLN', 'Inicio_SLN', 'Fin_SLN',
        'IGE', 'LMA',
        'Periodo_Planilla',
        'Cod_Admin_AFP', 'Admin_AFP', 'Dias_AFP', 'IBC_AFP', 'Tarifa_AFP', 'Valor_AFP',
        'Cod_EPS',       'Admin_EPS', 'Dias_EPS', 'IBC_EPS', 'Tarifa_EPS', 'Valor_EPS',
        'Dias_ARL',                   'IBC_ARL',  'Tarifa_ARL', 'Valor_ARL', 'Cod_Entidad',
        'Cod_CCF',       'Admin_CCF', 'Dias_CCF', 'IBC_CCF', 'Tarifa_CCF', 'Valor_CCF',
        'IBC', 'Exonerado',
    ]
    cols_presentes = [c for c in cols_orden if c in df.columns]
    cols_extra     = [c for c in df.columns  if c not in cols_orden]
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
    total_registros  = len(df)
    empleados_unicos = df['No_ID'].nunique()   if 'No_ID'    in df.columns else 0
    total_ibc        = df['IBC'].sum()          if 'IBC'      in df.columns else 0
    total_pension    = df['Valor_AFP'].sum()    if 'Valor_AFP' in df.columns else 0
    total_eps        = df['Valor_EPS'].sum()    if 'Valor_EPS' in df.columns else 0
    total_arl        = df['Valor_ARL'].sum()    if 'Valor_ARL' in df.columns else 0
    total_ccf        = df['Valor_CCF'].sum()    if 'Valor_CCF' in df.columns else 0

    def _si(v):
        return int(v) if pd.notna(v) else 0

    return {
        'empresa':          info_empresa.get('razon_social', '')[:60],
        'nit':              info_empresa.get('nit', ''),
        'total_registros':  total_registros,
        'empleados_unicos': empleados_unicos,
        'total_ibc':        _si(total_ibc),
        'total_pension':    _si(total_pension),
        'total_eps':        _si(total_eps),
        'total_arl':        _si(total_arl),
        'total_ccf':        _si(total_ccf),
    }


# ---------------------------------------------------------------------------
# CLI rapido
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
