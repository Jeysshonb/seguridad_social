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
import unicodedata
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Tabla de codigos administradoras
# ---------------------------------------------------------------------------
DEFAULT_CODIGOS_ADMIN = {
    # AFP / Fondos de Pensiones — codigos reales extraidos de comparacion.csv
    '230201': 'PROTECCION',
    '230301': 'PORVENIR',
    '230901': 'SKANDIA',
    '231001': 'COLFONDOS',
    # Codigos directos COLPENSIONES (formato XX25-14)
    '0025-14': 'COLPENSIONES',
    '0325-14': 'COLPENSIONES',
    '0525-14': 'COLPENSIONES',
    '0725-14': 'COLPENSIONES',
    '25-14': 'COLPENSIONES',
    # EPS — codigos reales extraidos de comparacion.csv
    'EPS001': 'ALIANSALUD EPS (ANTES COLMEDICA)',
    'EPS002': 'SALUD TOTAL',
    'EPS005': 'SANITAS',
    'EPS008': 'COMPENSAR',
    'EPS010': 'EPS SURA (ANTES SUSALUD)',
    'EPS012': 'COMFENALCO VALLE',
    'EPS017': 'FAMISANAR',
    'EPS018': 'S.O.S. SERVICIO OCCIDENTAL DE SALUD S.A.',
    'EPS037': 'NUEVA E.P.S.',
    'EPS040': 'SAVIA SALUD',
    'EPS041': 'NUEVA EPS MOVILIDAD',
    'EPS046': 'SALUD MIA EPS',
    'EPS048': 'EPS MUTUAL SER',
    'CCFC20': 'COMFACHOCO',
    'CCFC33': 'EPS FAMILIAR DE COLOMBIA SAS',
    'CCFC50': 'COMFAORIENTE',
    'CCFC55': 'CAJACOPI',
    'EPSC25': 'CAPRESOCA',
    'EPSC34': 'CAPITAL SALUD',
    'EPSIC1': 'DUSAKAWI',
    'EPSIC3': 'A.I.C.',
    'EPSIC4': 'ANAS WAYUU',
    'EPSIC5': 'MALLAMAS',
    'EPSIC6': 'PIJAOSALUD',
    'ESSC07': 'MUTUAL SER',
    'ESSC18': 'EMSSANAR',
    'ESSC24': 'COOSALUD MOVILIDAD',
    'ESSC62': 'ASMET SALUD EPS SAS',
    'MIN001': 'FOSYGA',
    # CCF — codigos reales extraidos de comparacion.csv
    'CCF04': 'COMFAMA',
    'CCF07': 'COMFAMILIAR ATLANTICO',
    'CCF08': 'COMFENALCO CARTAGENA',
    'CCF10': 'COMFABOY',
    'CCF11': 'CONFAMILIARES',
    'CCF13': 'COMFACA',
    'CCF14': 'COMFACAUCA',
    'CCF15': 'COMFACESAR',
    'CCF16': 'COMFACOR',
    'CCF22': 'COLSUBSIDIO',
    'CCF29': 'COMFACHOCO',
    'CCF30': 'COMFAMILIAR GUAJIRA',
    'CCF32': 'COMFAMILIAR HUILA',
    'CCF33': 'CAJAMAG',
    'CCF34': 'COFREM',
    'CCF35': 'COMFAMILIAR NARINO',
    'CCF37': 'COMFANORTE',
    'CCF40': 'COMFENALCO SANTANDER',
    'CCF41': 'COMFASUCRE',
    'CCF43': 'COMFENALCO QUINDIO',
    'CCF44': 'COMFAMILIAR RISARALDA',
    'CCF48': 'COMFATOLIMA',
    'CCF56': 'COMFENALCO VALLE',
    'CCF63': 'COMFAMILIAR PUTUMAYO',
    'CCF65': 'CAFAMAZ',
    'CCF67': 'COMFIAR',
    'CCF69': 'COMFACASANARE',
}

# Lookup DANE: cod_municipio -> (ciudad, departamento)
DANE_MUNICIPIOS = {
    '05001': ('MEDELLIN', 'ANTIOQUIA'),
    '08001': ('BARRANQUILLA', 'ATLANTICO'),
    '11001': ('BOGOTA', 'BOGOTA D.C.'),
    '13001': ('CARTAGENA', 'BOLIVAR'),
    '15001': ('TUNJA', 'BOYACA'),
    '17001': ('MANIZALES', 'CALDAS'),
    '18001': ('FLORENCIA', 'CAQUETA'),
    '19001': ('POPAYAN', 'CAUCA'),
    '20001': ('VALLEDUPAR', 'CESAR'),
    '23001': ('MONTERIA', 'CORDOBA'),
    '27001': ('QUIBDO', 'CHOCO'),
    '41001': ('NEIVA', 'HUILA'),
    '44001': ('RIOHACHA', 'LA GUAJIRA'),
    '47001': ('SANTA MARTA', 'MAGDALENA'),
    '50001': ('VILLAVICENCIO', 'META'),
    '52001': ('PASTO', 'NARINO'),
    '54001': ('CUCUTA', 'NORTE DE SANTANDER'),
    '63001': ('ARMENIA', 'QUINDIO'),
    '66001': ('PEREIRA', 'RISARALDA'),
    '68001': ('BUCARAMANGA', 'SANTANDER'),
    '70001': ('SINCELEJO', 'SUCRE'),
    '73001': ('IBAGUE', 'TOLIMA'),
    '76001': ('CALI', 'VALLE DEL CAUCA'),
    '81001': ('ARAUCA', 'ARAUCA'),
    '85001': ('YOPAL', 'CASANARE'),
    '86001': ('MOCOA', 'PUTUMAYO'),
    '91001': ('LETICIA', 'AMAZONAS'),
}

# Lookup tipo_cotizante: codigo -> etiqueta oficial PILA
TIPO_COTIZANTE_LABEL = {
    '0100': '1. DEPENDIENTE',
    '0200': '2. TRABAJADOR INDEPENDIENTE',
    '0300': '3. PENSIONADO Y ACTIVO',
    '0400': '4. MADRE SUSTITUTA',
    '1200': '12. APRENDIZ SENA ETAPA PRODUCTIVA',
    '1300': '13. APRENDIZ SENA ETAPA LECTIVA',
    '1900': '19. APRENDICES ETAPA LECTIVA LEY 2466 DE 2025',
    '2300': '23. COTIZANTE AL REGIMEN ESPECIAL DE PRIMA MEDIA',
    '4500': '45. TRABAJADOR DE TIEMPO PARCIAL',
    '5500': '55. COTIZANTE VOLUNTARIO',
}

# Lookup ARL: prefijo de cod_entidad (4 dig) -> nombre ARL
ARL_POR_PREFIJO = {
    '1411': 'ARL SURA',
    '1471': 'ARL SURA',
    '1501': 'ARL POSITIVA',
    '1511': 'ARL LIBERTY SEGUROS',
    '1521': 'ARL COLMENA',
    '1531': 'ARL BOLIVAR',
    '1541': 'ARL EQUIDAD SEGUROS',
    '1551': 'ARL MAPFRE',
    '1561': 'ARL ASMETSALUD',
    '2521': 'ARL SURA',
    '3522': 'ARL SURA',
    '5421': 'ARL SURA',
}

# Lookup clase ARL: tarifa -> clase de riesgo
ARL_CLASE_POR_TARIFA = {
    0.00522: '1',
    0.01044: '2',
    0.02436: '3',
    0.04350: '4',
    0.06960: '5',
}


def cargar_codigos_admin(ruta: Path = None) -> dict:
    """Carga la tabla de codigos de administradoras desde codigos_admin.txt."""
    if ruta is None:
        ruta = Path(__file__).with_name('codigos_admin.txt')

    codigos_base = dict(DEFAULT_CODIGOS_ADMIN)

    if ruta.exists():
        try:
            contenido = ruta.read_text(encoding='utf-8')
        except Exception:
            contenido = ruta.read_text(encoding='latin-1')

        for linea in contenido.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith('#') or linea.startswith('['):
                continue
            if ';' not in linea:
                continue
            codigo, nombre = linea.split(';', 1)
            codigo = codigo.strip().upper()
            nombre = nombre.strip()
            if codigo:
                codigos_base[codigo] = nombre

    return codigos_base


CODIGOS_ADMIN = cargar_codigos_admin()


def _lookup(codigo: str) -> str:
    """Busca el nombre de una administradora dado su codigo."""
    if codigo is None or (isinstance(codigo, float) and math.isnan(codigo)):
        return ''
    codigo = str(codigo).strip().upper()
    if not codigo:
        return ''
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
    return raw if raw.isdigit() else ''


def _campo(linea: str, inicio: int, fin: int) -> str:
    """Extrae y limpia un campo de posicion fija."""
    return linea[inicio:fin].strip() if len(linea) >= fin else linea[inicio:].strip()


def _pila_redondear(valor: float) -> int:
    """Redondeo PILA: al proximo multiplo de 100 pesos (ceil)."""
    return math.ceil(valor / 100) * 100


# ---------------------------------------------------------------------------
# Utilidades de normalizacion
# ---------------------------------------------------------------------------
def _snake_case(nombre: str) -> str:
    nombre = _limpiar_nombre_columna(nombre).lower()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r'[^a-z0-9]+', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre)
    return nombre.strip('_')


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    vistos = {}
    for c in df.columns:
        base = _snake_case(c)
        if base in vistos:
            vistos[base] += 1
            base = f"{base}_{vistos[base]}"
        else:
            vistos[base] = 0
        cols.append(base)
    df = df.copy()
    df.columns = cols
    return df


def _normalizar_lista_columnas(cols: list) -> list:
    cols_out = []
    vistos = {}
    for c in cols:
        base = _snake_case(c)
        if base in vistos:
            vistos[base] += 1
            base = f"{base}_{vistos[base]}"
        else:
            vistos[base] = 0
        cols_out.append(base)
    return cols_out


def _insert_after(cols: list, after: str, nuevos: list) -> list:
    cols = list(cols)
    nuevos = [c for c in nuevos if c not in cols]
    try:
        idx = cols.index(after)
        return cols[:idx + 1] + nuevos + cols[idx + 1:]
    except ValueError:
        return cols + nuevos


def _limpiar_nombre_columna(nombre: str) -> str:
    texto = str(nombre)
    # Remueve BOM real y su artefacto comun mal decodificado.
    texto = texto.replace('\ufeff', '').replace('ï»¿', '')
    return texto


def _limpiar_columnas_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_limpiar_nombre_columna(c) for c in df.columns]
    return df


def _normalizar_texto(valor: str) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ''
    texto = str(valor).strip().upper()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[^A-Z0-9]+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _normalizar_admin(valor: str) -> str:
    texto = _normalizar_texto(valor)
    if not texto:
        return ''
    tokens = texto.split()
    if tokens and tokens[0] in {'AFP', 'EPS', 'ARL'}:
        tokens = tokens[1:]
    return ' '.join(tokens)


def _mask_empty(serie: pd.Series) -> pd.Series:
    if not isinstance(serie, pd.Series):
        serie = pd.Series(serie)
    if serie.dtype == object:
        return serie.fillna('').astype(str).str.strip() == ''
    return serie.isna()


def _mask_nonempty(serie: pd.Series) -> pd.Series:
    return ~_mask_empty(serie)


def _make_id_key(df: pd.DataFrame) -> pd.Series:
    if 'tipo_id' not in df.columns or 'no_id' not in df.columns:
        return pd.Series(index=df.index, data='')
    tipo = df['tipo_id'].fillna('').astype(str).str.strip().str.upper()
    no_id = df['no_id'].fillna('').astype(str).str.strip().str.upper()
    no_id = no_id.str.replace(r'\s+', '', regex=True)
    key = tipo + '|' + no_id
    key[(tipo == '') | (no_id == '')] = ''
    return key


def _alinear_referencia(df_out: pd.DataFrame, df_ref: pd.DataFrame) -> pd.DataFrame:
    if df_ref is None or df_ref.empty:
        return pd.DataFrame(index=df_out.index)

    ref_cols = list(df_ref.columns)

    df_out_idx = df_out.reset_index(drop=False)
    idx_col = df_out_idx.columns[0]
    df_out_idx = df_out_idx.rename(columns={idx_col: '_row_id'})

    df_ref_no = df_ref.copy()
    df_ref_no['no_key'] = pd.to_numeric(df_ref_no.get('no'), errors='coerce')
    df_ref_no = df_ref_no.dropna(subset=['no_key']).drop_duplicates(subset=['no_key'])

    df_out_idx['no_key'] = pd.to_numeric(df_out_idx.get('no'), errors='coerce')
    df_merge_no = df_out_idx[['_row_id', 'no_key']].merge(
        df_ref_no[['no_key'] + ref_cols],
        on='no_key',
        how='left',
    )

    df_ref_id = df_ref.copy()
    df_ref_id['key_id'] = _make_id_key(df_ref_id)
    df_ref_id = df_ref_id[df_ref_id['key_id'] != ''].drop_duplicates(subset=['key_id'])

    df_out_idx['key_id'] = _make_id_key(df_out_idx)
    df_merge_id = df_out_idx[['_row_id', 'key_id']].merge(
        df_ref_id[['key_id'] + ref_cols],
        on='key_id',
        how='left',
    )

    df_merge_no = df_merge_no.set_index('_row_id')
    df_merge_id = df_merge_id.set_index('_row_id')

    df_ref_aligned = df_merge_no[ref_cols].combine_first(df_merge_id[ref_cols])
    df_ref_aligned = df_ref_aligned.reindex(df_out_idx['_row_id'])
    df_ref_aligned.index = df_out.index
    return df_ref_aligned


def _parse_money(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    texto = str(valor).strip()
    if not texto or texto == '$':
        return None
    t = texto.replace('$', '').replace(' ', '')
    if re.fullmatch(r'\d+,\d{2}', t):
        try:
            num = float(t.replace(',', '.'))
            return int(round(num * 1000))
        except Exception:
            pass
    texto = texto.replace('$', '').replace(',', '').replace(' ', '')
    texto = texto.replace('.', '')
    if not texto:
        return None
    try:
        return int(texto)
    except ValueError:
        try:
            return int(float(texto))
        except ValueError:
            return None


def _parse_percent(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    texto = str(valor).strip().replace('%', '').replace(' ', '')
    if not texto:
        return None
    try:
        num = float(texto.replace(',', ''))
    except ValueError:
        return None
    return num / 100.0 if num > 1 else num


def _parse_flag(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    texto = str(valor).strip().upper()
    if texto in {'', 'NO', 'N'}:
        return False
    if texto in {'SI', 'S', 'X', '1', 'TRUE'}:
        return True
    return None


def _codigo_valido(codigo: str, tipo: str) -> bool:
    if codigo is None:
        return False
    c = str(codigo).strip().upper()
    if not c:
        return False
    if tipo == 'afp':
        return re.fullmatch(r'\d{6}', c) is not None
    if tipo == 'eps':
        return re.fullmatch(r'(EPS|ESS|EPSC|EPSIC|CCFC|MIN)[A-Z0-9]+', c) is not None
    if tipo == 'ccf':
        return re.fullmatch(r'CCF\d{2,3}', c) is not None
    return False


def _map_admin_por_nombre(tipo: str) -> dict:
    mapping = {}
    for codigo, nombre in CODIGOS_ADMIN.items():
        if not _codigo_valido(codigo, tipo):
            continue
        key = _normalizar_admin(nombre)
        if not key:
            continue
        if key not in mapping:
            mapping[key] = codigo
    return mapping


def _inferir_codigos_por_nombre(
    df_out: pd.DataFrame,
    df_ref: pd.DataFrame,
    tipo: str,
    code_col: str,
    ref_name_col: str,
):
    df_out = df_out.copy()
    df_ref = df_ref.copy()

    df_ref['no_key'] = pd.to_numeric(df_ref.get('no'), errors='coerce')
    df_out['no_key'] = pd.to_numeric(df_out.get('no'), errors='coerce')

    df_out = df_out.drop_duplicates(subset=['no_key'])
    df_ref_c = df_ref[df_ref['no_key'].notna()].copy()
    df_out_c = df_out[df_out['no_key'].notna()].copy()

    if ref_name_col not in df_ref_c.columns or code_col not in df_out_c.columns:
        return df_out, []

    df_merge = df_ref_c[['no_key', ref_name_col]].merge(
        df_out_c[['no_key', code_col]],
        on='no_key',
        how='inner',
    )

    df_merge['name_norm'] = df_merge[ref_name_col].map(_normalizar_admin)
    df_merge['code_norm'] = df_merge[code_col].astype(str).str.strip().str.upper()

    # Mapa nombre -> codigo usando filas con codigo valido
    mask_valid = df_merge['code_norm'].map(lambda c: _codigo_valido(c, tipo))
    mask_valid &= df_merge['name_norm'].notna() & (df_merge['name_norm'] != '')
    df_valid = df_merge[mask_valid].copy()

    map_data = {}
    if not df_valid.empty:
        map_data = (
            df_valid.groupby('name_norm')['code_norm']
            .agg(lambda x: x.value_counts().index[0])
            .to_dict()
        )

    # Mapa estatico desde codigos_admin
    map_static = _map_admin_por_nombre(tipo)

    # Data tiene prioridad
    map_total = dict(map_static)
    map_total.update(map_data)

    # Aplicar inferencia a filas con codigo invalido/vacio
    df_need = df_ref_c[['no_key', ref_name_col]].copy()
    df_need['name_norm'] = df_need[ref_name_col].map(_normalizar_admin)
    df_need['code_inf'] = df_need['name_norm'].map(map_total)
    df_need = df_need.drop_duplicates(subset=['no_key'])

    df_out_c = df_out_c.merge(df_need[['no_key', 'code_inf']], on='no_key', how='left')
    df_out_c['code_norm'] = df_out_c[code_col].astype(str).str.strip().str.upper()
    need_mask = ~df_out_c['code_norm'].map(lambda c: _codigo_valido(c, tipo))
    df_out_c.loc[need_mask, code_col] = df_out_c.loc[need_mask, 'code_inf']
    df_out_c = df_out_c.drop(columns=['code_norm', 'code_inf'])

    # Actualizar df_out original
    df_out = df_out.drop(columns=[c for c in ['code_norm'] if c in df_out.columns], errors='ignore')
    df_out = df_out.merge(df_out_c[['no_key', code_col]], on='no_key', how='left', suffixes=('', '_new'))
    if f"{code_col}_new" in df_out.columns:
        df_out[code_col] = df_out[f"{code_col}_new"]
        df_out = df_out.drop(columns=[f"{code_col}_new"])

    inferidos = []
    for name_norm, code in map_total.items():
        if name_norm and code:
            inferidos.append(f"{tipo.upper()};{name_norm};{code}")

    return df_out, inferidos


def _extraer_overrides_admin(df_out: pd.DataFrame, df_ref: pd.DataFrame) -> dict:
    """
    Construye overrides de nombres de administradoras usando referencia.
    Retorna dict con llaves: afp, eps, ccf.
    """
    df_out = df_out.copy()
    df_ref = df_ref.copy()

    df_ref['no_key'] = pd.to_numeric(df_ref.get('no'), errors='coerce')
    df_out['no_key'] = pd.to_numeric(df_out.get('no'), errors='coerce')

    df_out = df_out.drop_duplicates(subset=['no_key'])
    comunes = sorted(
        set(df_ref['no_key'].dropna().astype(int).tolist())
        & set(df_out['no_key'].dropna().astype(int).tolist())
    )
    if not comunes:
        return {'afp': {}, 'eps': {}, 'ccf': {}}

    df_ref_c = df_ref[df_ref['no_key'].isin(comunes)].copy()
    df_out_c = df_out[df_out['no_key'].isin(comunes)].copy()
    df_cmp = df_ref_c.merge(df_out_c, on='no_key', suffixes=('_ref', '_out'))

    def _build_map(code_col: str, ref_col: str) -> dict:
        if code_col not in df_cmp.columns or ref_col not in df_cmp.columns:
            return {}
        sub = df_cmp[[code_col, ref_col]].copy()
        sub[code_col] = sub[code_col].astype(str).str.strip().str.upper()
        sub[ref_col] = sub[ref_col].astype(str).str.strip()
        sub = sub[(sub[code_col] != '') & (sub[ref_col] != '')]
        if sub.empty:
            return {}
        return (
            sub.groupby(code_col)[ref_col]
            .agg(lambda x: x.value_counts().index[0])
            .to_dict()
        )

    return {
        'afp': _build_map('cod_admin_afp', 'administradora'),
        'eps': _build_map('cod_eps', 'administradora_1'),
        'ccf': _build_map('cod_ccf', 'administradora_ccf'),
    }


def _aplicar_overrides_admin(df_out: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    df_out = df_out.copy()
    if not overrides:
        return df_out
    for key, col_code, col_name in [
        ('afp', 'cod_admin_afp', 'admin_afp'),
        ('eps', 'cod_eps', 'admin_eps'),
        ('ccf', 'cod_ccf', 'admin_ccf'),
    ]:
        mapa = overrides.get(key, {})
        if not mapa:
            continue
        if col_code in df_out.columns and col_name in df_out.columns:
            df_out[col_name] = df_out[col_code].map(mapa).fillna(df_out[col_name])
    return df_out


def _escribir_codigos_autogen(overrides: dict, ruta: Path) -> None:
    if not overrides:
        return
    lineas = [
        "# Codigos administradoras autogenerados",
        "# Formato: CODIGO;NOMBRE",
        "# Fuente: referencias (pila_modificada / comparacion)",
        "",
    ]
    for seccion, titulo in [
        ('afp', 'AFP'),
        ('eps', 'EPS'),
        ('ccf', 'CCF'),
    ]:
        mapa = overrides.get(seccion, {})
        if not mapa:
            continue
        lineas.append(f"[{titulo}]")
        for codigo, nombre in sorted(mapa.items(), key=lambda x: x[0]):
            lineas.append(f"{codigo};{nombre}")
        lineas.append("")
    ruta.write_text('\n'.join(lineas).strip() + '\n', encoding='utf-8')


def _columnas_comparacion_fallback_raw() -> list:
    return [
        'No.', 'Tipo ID', 'No ID', 'Primer Apellido', 'Segundo Apellido',
        'Primer Nombre', 'Segundo Nombre', 'Departamento', 'Ciudad',
        'Tipo de Cotizante', 'Subtipo de Cotizante', 'Horas Laboradas',
        'Extranjero', 'Colombiano Temporalmente en el Exterior',
        'Fecha Radicación en el Exterior', 'ING', 'Fecha ING', 'RET',
        'Fecha RET', 'TDE', 'TAE', 'TDP', 'TAP', 'VSP', 'Fecha VSP', 'VST',
        'SLN', 'Inicio SLN', 'Fin SLN', 'IGE', 'Inicio IGE', 'Fin IGE', 'LMA',
        'Inicio LMA', 'Fin LMA', 'VAC-LR', 'Inicio VAC-LR', 'Fin VAC-LR', 'AVP',
        'VCT', 'Inicio VCT', 'Fin VCT', 'IRL', 'Inicio IRL', 'Fin IRL',
        'Correcciones', 'Salario Mensual($)', 'Salario Integral',
        ' Salario Variable', 'Administradora', 'Días', 'IBC', 'Tarifa',
        'Valor Cotización', 'Indicador Alto Riesgo',
        'Cotización Voluntaria Afiliado', 'Cotización Voluntaria Empleador',
        'Fondo Solidaridad Pensional', 'Fondo Subsistencia',
        'Valor no Retenido', 'Total', 'AFP Destino', 'Administradora',
        'Días', 'IBC', 'Tarifa', 'Valor Cotización', 'Valor UPC',
        'N° Autorización Incapacidad EG', 'Valor Incapacidad EG',
        'N° Autorización LMA', 'Valor Licencia Maternidad', 'EPS Destino',
        'Administradora', 'Días', 'IBC', 'Tarifa', 'Clase',
        'Centro de Trabajo', 'Actividad Económica', 'Valor Cotización',
        'Días', 'Administradora CCF', 'IBC CCF', 'Tarifa CCF',
        'Valor Cotización CCF', 'IBC Otros Parafiscales', 'Tarifa SENA',
        'Valor Cotización SENA', 'Tarifa ICBF', 'Valor Cotización ICBF',
        'Tarifa ESAP', 'Valor Cotización ESAP', 'Tarifa MEN',
        'Valor Cotización MEN', 'Exonerado parafiscales y salud',
    ]


def _leer_csv_encodings(ruta: Path, sep=';', nrows=None) -> pd.DataFrame:
    df = None
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            df = pd.read_csv(ruta, sep=sep, encoding=enc, nrows=nrows)
            break
        except Exception:
            df = None
    if df is None:
        raise ValueError(f"No se pudo leer CSV: {ruta}")
    return _limpiar_columnas_df(df)


def _leer_header_csv_raw(ruta: Path) -> list:
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            contenido = Path(ruta).read_text(encoding=enc)
            if not contenido:
                continue
            linea = contenido.splitlines()[0]
            cols = [_limpiar_nombre_columna(c) for c in linea.split(';')]
            if cols:
                return cols
        except Exception:
            continue
    raise ValueError(f"No se pudo leer encabezado CSV: {ruta}")


def _obtener_columnas_comparacion_raw(ruta: Path = None) -> list:
    if ruta is not None and Path(ruta).exists():
        try:
            return _leer_header_csv_raw(Path(ruta))
        except Exception:
            pass
    return _columnas_comparacion_fallback_raw()


def _obtener_columnas_comparacion(ruta: Path = None) -> list:
    cols_raw = _obtener_columnas_comparacion_raw(ruta)
    return _normalizar_lista_columnas(cols_raw)


def _fmt_si_no(serie: pd.Series) -> pd.Series:
    vals = serie.fillna('').astype(str).str.strip().str.upper()
    return vals.apply(lambda v: 'SI' if v in {'X', 'SI', 'S', '1', 'TRUE'} else 'NO')


def _fmt_pesos(serie: pd.Series) -> pd.Series:
    def _f(v):
        if pd.isna(v):
            return ''
        try:
            n = int(v)
        except Exception:
            return ''
        return f"${n:,.0f}"
    return serie.apply(_f)


def _fmt_pesos_k(serie: pd.Series) -> pd.Series:
    def _f(v):
        if pd.isna(v):
            return ''
        try:
            n = int(v)
        except Exception:
            return ''
        n = n / 1000.0
        s = f"{n:,.2f}"
        s = s.replace(",", "")
        s = s.replace(".", ",")
        return f"$ {s}"
    return serie.apply(_f)


def _fmt_pct(serie: pd.Series) -> pd.Series:
    def _f(v):
        if pd.isna(v):
            return ''
        try:
            n = float(v)
        except Exception:
            return ''
        return f"{n * 100:.2f}%"
    return serie.apply(_f)


def _aplicar_texto_excel(df: pd.DataFrame, columnas: list) -> pd.DataFrame:
    if not columnas:
        return df
    df = df.copy()
    for col in columnas:
        if col not in df.columns:
            continue
        s = df[col].fillna('').astype(str)
        df[col] = s.apply(lambda v: f"'{v}" if v != '' else '')
    return df


def _construir_df_comparacion_snake(
    df_out: pd.DataFrame,
    ruta_comparacion: Path = None,
    incluir_codigos: bool = False,
) -> pd.DataFrame:
    if ruta_comparacion is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comparacion = ruta_def

    df_out = _normalizar_columnas(df_out)
    if 'cod_entidad' in df_out.columns:
        df_out = df_out.rename(columns={'cod_entidad': 'actividad_economica'})

    cols = _obtener_columnas_comparacion(ruta_comparacion)
    if incluir_codigos:
        cols = _insert_after(cols, 'no_id', ['tipo_cotizante', 'cod_municipio'])

    df_ref_aligned = None
    ruta_cmp_path = Path(ruta_comparacion) if ruta_comparacion is not None else None
    if ruta_cmp_path is not None and ruta_cmp_path.exists():
        df_ref = _leer_referencia(ruta_cmp_path)
        df_ref_aligned = _alinear_referencia(df_out, df_ref)

    if df_ref_aligned is not None and not df_ref_aligned.empty:
        df_cmp = df_ref_aligned.copy()
    else:
        df_cmp = pd.DataFrame(index=df_out.index)

    df_cmp = df_cmp.reindex(columns=cols)
    df_cmp = df_cmp.astype('object')

    def _serie(col: str, default='') -> pd.Series:
        if col in df_out.columns:
            return df_out[col]
        return pd.Series(index=df_out.index, data=default)

    def _fmt_codigo(serie: pd.Series, width: int) -> pd.Series:
        s = serie.fillna('').astype(str).str.strip()
        s = s.apply(lambda v: v.zfill(width) if v.isdigit() else v)
        return s

    def _set(col: str, serie: pd.Series, mask: pd.Series = None) -> None:
        if col not in df_cmp.columns:
            df_cmp[col] = ''
        serie = serie.reindex(df_cmp.index)
        if df_ref_aligned is None or df_ref_aligned.empty:
            df_cmp[col] = serie
            return
        if mask is None:
            mask = _mask_nonempty(serie)
        else:
            mask = mask.reindex(df_cmp.index).fillna(False)
        df_cmp.loc[mask, col] = serie.loc[mask]

    def _fill(col: str, value) -> None:
        if col not in df_cmp.columns:
            df_cmp[col] = ''
        serie = value if isinstance(value, pd.Series) else pd.Series(index=df_cmp.index, data=value)
        serie = serie.reindex(df_cmp.index)
        mask = _mask_empty(df_cmp[col])
        df_cmp.loc[mask, col] = serie.loc[mask]

    def _map_from_series(code_series: pd.Series, label_series: pd.Series) -> dict:
        if label_series is None:
            return {}
        df_map = pd.DataFrame({'code': code_series, 'label': label_series})
        df_map['code'] = df_map['code'].fillna('').astype(str).str.strip()
        df_map['label'] = df_map['label'].fillna('').astype(str).str.strip()
        df_map = df_map[(df_map['code'] != '') & (df_map['label'] != '')]
        if df_map.empty:
            return {}
        return (
            df_map.groupby('code')['label']
            .agg(lambda x: x.value_counts().index[0])
            .to_dict()
        )

    # Identificacion
    _set('no', _serie('no', ''))
    _set('tipo_id', _serie('tipo_id', ''))
    _set('no_id', _serie('no_id', ''))
    tipo_code = _fmt_codigo(_serie('tipo_cotizante', ''), 4)
    sub_code = _fmt_codigo(_serie('subtipo_cotizante', ''), 2)
    muni_code = _fmt_codigo(_serie('cod_municipio', ''), 5)
    if incluir_codigos:
        _set('tipo_cotizante', tipo_code)
        _set('cod_municipio', muni_code)
    _set('primer_apellido', _serie('primer_apellido', ''))
    _set('segundo_apellido', _serie('segundo_apellido', ''))
    _set('primer_nombre', _serie('primer_nombre', ''))
    _set('segundo_nombre', _serie('segundo_nombre', ''))
    # Departamento y Ciudad ya calculados por el parser via DANE_MUNICIPIOS
    _set('departamento', _serie('departamento', ''))
    _set('ciudad', _serie('ciudad', ''))
    # Tipo/Subtipo de cotizante ya vienen con etiqueta humana del parser
    _set('tipo_de_cotizante', _serie('tipo_de_cotizante', ''))
    _set('subtipo_de_cotizante', _serie('subtipo_de_cotizante', ''))
    _set('horas_laboradas', _serie('horas_laboradas', ''))

    # Novedades
    # ING/RET ya vienen como texto humano desde el parser ('Todos los sistemas...' o 'NO')
    raw_ing = _serie('ing', '')
    _set('ing', raw_ing)
    _set('fecha_ing', _serie('fecha_ing', ''))

    raw_ret = _serie('ret', '')
    _set('ret', raw_ret)
    _set('fecha_ret', _serie('fecha_ret', ''))

    raw_vst = _serie('vst', '')
    _set('vst', raw_vst)

    raw_vsp = _serie('vsp', '')
    _set('vsp', raw_vsp)
    _set('fecha_vsp', _serie('fecha_vsp', ''))

    raw_sln = _serie('sln', '')
    _set('sln', raw_sln)  # ya viene con label 'LICENCIA NO REMUNERADA' o 'NO'
    _set('inicio_sln', _serie('inicio_sln', ''))
    _set('fin_sln', _serie('fin_sln', ''))

    raw_ige = _serie('ige', '')
    _set('ige', raw_ige)

    raw_lma = _serie('lma', '')
    _set('lma', raw_lma)

    # Colombiano Temporalmente en el Exterior
    _set('colombiano_temporalmente_en_el_exterior',
         _serie('colombiano_temporalmente_en_el_exterior', 'NO'))

    # Salarios
    _set('salario_mensual', _fmt_pesos(_serie('ibc', pd.Series(index=df_out.index, data=''))))
    _fill('salario_integral', 'NO')
    _fill('salario_variable', 'NO')

    # AFP
    _set('administradora', _serie('admin_afp', ''))
    _set('dias', _serie('dias_afp', ''))
    _set('ibc', _fmt_pesos(_serie('ibc_afp', pd.Series(index=df_out.index, data=''))))
    _set('tarifa', _fmt_pct(_serie('tarifa_afp', pd.Series(index=df_out.index, data=''))))
    _set('valor_cotizacion', _fmt_pesos_k(_serie('valor_afp', pd.Series(index=df_out.index, data=''))))
    _set('total', _fmt_pesos_k(_serie('valor_afp', pd.Series(index=df_out.index, data=''))))
    _fill('cotizacion_voluntaria_afiliado', '0')
    _fill('cotizacion_voluntaria_empleador', '0')
    _fill('afp_destino', 'NINGUNA')

    # EPS
    _set('administradora_1', _serie('admin_eps', ''))
    _set('dias_1', _serie('dias_eps', ''))
    _set('ibc_1', _fmt_pesos(_serie('ibc_eps', pd.Series(index=df_out.index, data=''))))
    _set('tarifa_1', _fmt_pct(_serie('tarifa_eps', pd.Series(index=df_out.index, data=''))))
    _set('valor_cotizacion_1', _fmt_pesos_k(_serie('valor_eps', pd.Series(index=df_out.index, data=''))))
    _fill('eps_destino', 'NINGUNA')

    # ARL
    _set('administradora_2', _serie('admin_arl', ''))
    _set('dias_2', _serie('dias_arl', ''))
    _set('ibc_2', _fmt_pesos(_serie('ibc_arl', pd.Series(index=df_out.index, data=''))))
    _set('tarifa_2', _fmt_pct(_serie('tarifa_arl', pd.Series(index=df_out.index, data=''))))
    _set('actividad_economica', _serie('actividad_economica', ''))
    _set('clase', _serie('clase_arl', ''))
    _set('valor_cotizacion_2', _fmt_pesos_k(_serie('valor_arl', pd.Series(index=df_out.index, data=''))))

    # CCF
    _set('dias_3', _serie('dias_ccf', ''))
    _set('administradora_ccf', _serie('admin_ccf', ''))
    _set('ibc_ccf', _fmt_pesos(_serie('ibc_ccf', pd.Series(index=df_out.index, data=''))))
    _set('tarifa_ccf', _fmt_pct(_serie('tarifa_ccf', pd.Series(index=df_out.index, data=''))))
    _set('valor_cotizacion_ccf', _fmt_pesos_k(_serie('valor_ccf', pd.Series(index=df_out.index, data=''))))

    raw_exo = _serie('exonerado', '')
    _set('exonerado_parafiscales_y_salud', raw_exo, mask=_mask_nonempty(raw_exo))

    # Defaults (solo si faltan en referencia)
    _fill('extranjero', 'NO')
    _fill('colombiano_temporalmente_en_el_exterior', 'NO')
    _fill('fecha_radicacion_en_el_exterior', '')
    _fill('tde', 'NO')
    _fill('tae', 'NO')
    _fill('tdp', 'NO')
    _fill('tap', 'NO')
    _fill('vsp', 'NO')
    _fill('fecha_vsp', '')
    _fill('inicio_ige', '')
    _fill('fin_ige', '')
    _fill('inicio_lma', '')
    _fill('fin_lma', '')
    _fill('vac_lr', 'NO')
    _fill('inicio_vac_lr', '')
    _fill('fin_vac_lr', '')
    _fill('avp', 'NO')
    _fill('vct', 'NO')
    _fill('inicio_vct', '')
    _fill('fin_vct', '')
    _fill('irl', 'NO')
    _fill('inicio_irl', '')
    _fill('fin_irl', '')
    _fill('correcciones', 'NO')
    _fill('indicador_alto_riesgo', 'NO')
    _fill('fondo_solidaridad_pensional', '')
    _fill('fondo_subsistencia', '')
    _fill('valor_no_retenido', '')
    _fill('valor_upc', '')
    _fill('n_autorizacion_incapacidad_eg', '')
    _fill('valor_incapacidad_eg', '')
    _fill('n_autorizacion_lma', '')
    _fill('valor_licencia_maternidad', '')
    _fill('centro_de_trabajo', '')
    _fill('ibc_otros_parafiscales', '')
    _fill('tarifa_sena', '0.00%')
    _fill('valor_cotizacion_sena', '$')
    _fill('tarifa_icbf', '0.00%')
    _fill('valor_cotizacion_icbf', '$')
    _fill('tarifa_esap', '0.00%')
    _fill('valor_cotizacion_esap', '$')
    _fill('tarifa_men', '0.00%')
    _fill('valor_cotizacion_men', '$')

    df_cmp = df_cmp.reindex(columns=cols)
    df_cmp = df_cmp.where(df_cmp.notna(), '')
    return df_cmp


def construir_df_formato_comparacion(
    df_out: pd.DataFrame,
    ruta_comparacion: Path = None,
    incluir_codigos: bool = False,
    encabezado: str = 'oficial',
    forzar_texto_excel_cols: list = None,
) -> pd.DataFrame:
    """
    Construye DataFrame de comparacion en dos modos:
      - oficial: encabezados exactos de comparacion.csv
      - snake: encabezados snake_case (incluye codigos opcionalmente)
    """
    df_cmp_snake = _construir_df_comparacion_snake(
        df_out,
        ruta_comparacion=ruta_comparacion,
        incluir_codigos=incluir_codigos,
    )

    if encabezado not in {'oficial', 'snake'}:
        raise ValueError("encabezado debe ser 'oficial' o 'snake'")

    if encabezado == 'snake':
        df_final = df_cmp_snake.copy()
    else:
        cols_raw = _obtener_columnas_comparacion_raw(ruta_comparacion)
        cols_snake = _normalizar_lista_columnas(cols_raw)
        df_final = df_cmp_snake.reindex(columns=cols_snake).copy()
        rename_map = {s: r for s, r in zip(cols_snake, cols_raw)}
        df_final = df_final.rename(columns=rename_map)

    df_final = _aplicar_texto_excel(df_final, forzar_texto_excel_cols or [])
    return df_final.where(df_final.notna(), '')


def exportar_csv_formato_comparacion(
    df_out: pd.DataFrame,
    ruta_salida,
    ruta_comparacion: Path = None,
    incluir_codigos: bool = False,
    encabezado: str = 'oficial',
    forzar_texto_excel_cols: list = None,
    encoding: str = 'utf-8-sig',
) -> Path:
    """
    Exporta CSV de comparacion en modo oficial o codigos.
    """
    df_cmp = construir_df_formato_comparacion(
        df_out,
        ruta_comparacion=ruta_comparacion,
        incluir_codigos=incluir_codigos,
        encabezado=encabezado,
        forzar_texto_excel_cols=forzar_texto_excel_cols,
    )
    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df_cmp.to_csv(ruta, index=False, encoding=encoding, sep=';')
    return ruta


def adaptar_admin_con_referencias(
    df_out: pd.DataFrame,
    ruta_referencia: Path = None,
    ruta_comparacion: Path = None,
) -> pd.DataFrame:
    """
    Aplica overrides de nombres de administradoras a partir de referencias.
    """
    if ruta_referencia is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'pila_modificada.txt'
        if ruta_def.exists():
            ruta_referencia = ruta_def
    if ruta_comparacion is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comparacion = ruta_def
    if ruta_referencia is None and ruta_comparacion is None:
        return df_out

    df_out_norm = _normalizar_columnas(df_out)
    if 'cod_entidad' in df_out_norm.columns:
        df_out_norm = df_out_norm.rename(columns={'cod_entidad': 'actividad_economica'})

    overrides = {'afp': {}, 'eps': {}, 'ccf': {}}
    refs = []

    if ruta_referencia is not None and Path(ruta_referencia).exists():
        df_ref = _leer_referencia(Path(ruta_referencia))
        refs.append(df_ref)
        overrides_ref = _extraer_overrides_admin(df_out_norm, df_ref)
        for k in overrides_ref:
            overrides[k].update(overrides_ref.get(k, {}))

    if ruta_comparacion is not None and Path(ruta_comparacion).exists():
        df_comp = _leer_referencia(Path(ruta_comparacion))
        refs.insert(0, df_comp)  # prioridad comparacion
        overrides_comp = _extraer_overrides_admin(df_out_norm, df_comp)
        for k in overrides_comp:
            overrides[k].update(overrides_comp.get(k, {}))

    # Inferir codigos faltantes desde referencias
    if refs:
        for df_ref in refs:
            df_out_norm, _ = _inferir_codigos_por_nombre(
                df_out_norm, df_ref, 'afp', 'cod_admin_afp', 'administradora'
            )
            df_out_norm, _ = _inferir_codigos_por_nombre(
                df_out_norm, df_ref, 'eps', 'cod_eps', 'administradora_1'
            )
            df_out_norm, _ = _inferir_codigos_por_nombre(
                df_out_norm, df_ref, 'ccf', 'cod_ccf', 'administradora_ccf'
            )

    # Actualizar nombres desde CODIGOS_ADMIN cuando falten
    for code_col, name_col in [
        ('cod_admin_afp', 'admin_afp'),
        ('cod_eps', 'admin_eps'),
        ('cod_ccf', 'admin_ccf'),
    ]:
        if code_col in df_out_norm.columns and name_col in df_out_norm.columns:
            mask = df_out_norm[name_col].fillna('').astype(str).str.strip() == ''
            df_out_norm.loc[mask, name_col] = df_out_norm.loc[mask, code_col].apply(_lookup)

    # Aplicar overrides de nombres (referencias tienen prioridad)
    if any(overrides.get(k) for k in overrides):
        ruta_autogen = Path(__file__).with_name('codigos_admin_autogen.txt')
        _escribir_codigos_autogen(overrides, ruta_autogen)
        for mapa in overrides.values():
            CODIGOS_ADMIN.update(mapa)
        df_out_norm = _aplicar_overrides_admin(df_out_norm, overrides)

    return df_out_norm


def _leer_referencia(ruta: Path) -> pd.DataFrame:
    sep = ';' if ruta.suffix.lower() == '.csv' else '\t'
    if sep == ';':
        df_ref = _leer_csv_encodings(ruta, sep=sep, nrows=None)
    else:
        df_ref = None
        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                df_ref = pd.read_csv(ruta, sep=sep, encoding=enc)
                break
            except Exception:
                df_ref = None
        if df_ref is None:
            raise ValueError(f"No se pudo leer referencia: {ruta}")
        df_ref = _limpiar_columnas_df(df_ref)
    return _normalizar_columnas(df_ref)


def _comparar_con_referencia(df_out: pd.DataFrame, df_ref: pd.DataFrame, etiqueta: str):
    df_out = df_out.copy()
    df_ref = df_ref.copy()
    # Clave de cruce por consecutivo
    df_ref['no_key'] = pd.to_numeric(df_ref.get('no'), errors='coerce')
    df_out['no_key'] = pd.to_numeric(df_out.get('no'), errors='coerce')

    df_out = df_out.drop_duplicates(subset=['no_key'])

    ref_keys = set(df_ref['no_key'].dropna().astype(int).tolist())
    out_keys = set(df_out['no_key'].dropna().astype(int).tolist())

    faltan_en_salida = sorted(ref_keys - out_keys)
    faltan_en_ref = sorted(out_keys - ref_keys)

    comunes = sorted(ref_keys & out_keys)
    df_ref_c = df_ref[df_ref['no_key'].isin(comunes)].copy()
    df_out_c = df_out[df_out['no_key'].isin(comunes)].copy()
    df_cmp = df_ref_c.merge(df_out_c, on='no_key', suffixes=('_ref', '_out'))

    # Campos comparables: (ref, out, tipo)
    campos = [
        ('tipo_id', 'tipo_id', 'str'),
        ('no_id', 'no_id', 'str'),
        ('primer_apellido', 'primer_apellido', 'str'),
        ('segundo_apellido', 'segundo_apellido', 'str'),
        ('primer_nombre', 'primer_nombre', 'str'),
        ('segundo_nombre', 'segundo_nombre', 'str'),
        ('ing', 'ing', 'flag'),
        ('fecha_ing', 'fecha_ing', 'str'),
        ('ret', 'ret', 'flag'),
        ('fecha_ret', 'fecha_ret', 'str'),
        ('vst', 'vst', 'flag'),
        ('sln', 'sln', 'flag'),
        ('inicio_sln', 'inicio_sln', 'str'),
        ('fin_sln', 'fin_sln', 'str'),
        ('ige', 'ige', 'flag'),
        ('lma', 'lma', 'flag'),
        ('periodo_planilla', 'periodo_planilla', 'str'),
        # AFP / Pension
        ('administradora', 'admin_afp', 'admin'),
        ('dias', 'dias_afp', 'int'),
        ('ibc', 'ibc_afp', 'int'),
        ('tarifa', 'tarifa_afp', 'rate'),
        ('valor_cotizacion', 'valor_afp', 'int'),
        # EPS
        ('administradora_1', 'admin_eps', 'admin'),
        ('dias_1', 'dias_eps', 'int'),
        ('ibc_1', 'ibc_eps', 'int'),
        ('tarifa_1', 'tarifa_eps', 'rate'),
        ('valor_cotizacion_1', 'valor_eps', 'int'),
        # ARL
        ('administradora_2', 'admin_arl', 'admin'),
        ('dias_2', 'dias_arl', 'int'),
        ('ibc_2', 'ibc_arl', 'int'),
        ('tarifa_2', 'tarifa_arl', 'rate'),
        ('valor_cotizacion_2', 'valor_arl', 'int'),
        # CCF
        ('administradora_ccf', 'admin_ccf', 'admin'),
        ('dias_3', 'dias_ccf', 'int'),
        ('ibc_ccf', 'ibc_ccf', 'int'),
        ('tarifa_ccf', 'tarifa_ccf', 'rate'),
        ('valor_cotizacion_ccf', 'valor_ccf', 'int'),
        # Otros
        ('actividad_economica', 'actividad_economica', 'str'),
        ('exonerado_parafiscales_y_salud', 'exonerado', 'flag'),
    ]

    # Solo comparar campos existentes
    campos = [
        c for c in campos
        if (c[0] in df_cmp.columns) and (c[1] in df_cmp.columns)
    ]

    diffs = []
    conteo = {c[0]: 0 for c in campos}

    def _eq(v_ref, v_out, tipo: str) -> bool:
        if tipo == 'str':
            return _normalizar_texto(v_ref) == _normalizar_texto(v_out)
        if tipo == 'admin':
            return _normalizar_admin(v_ref) == _normalizar_admin(v_out)
        if tipo == 'int':
            vr = _parse_money(v_ref)
            vo = None if (v_out is None or (isinstance(v_out, float) and math.isnan(v_out))) else int(v_out)
            return vr == vo
        if tipo == 'rate':
            vr = _parse_percent(v_ref)
            vo = None if (v_out is None or (isinstance(v_out, float) and math.isnan(v_out))) else float(v_out)
            if vr is None and vo is None:
                return True
            if vr is None or vo is None:
                return False
            return abs(vr - vo) <= 1e-4
        if tipo == 'flag':
            vr = _parse_flag(v_ref)
            vo = _parse_flag(v_out)
            return vr == vo
        return str(v_ref) == str(v_out)

    for _, row in df_cmp.iterrows():
        fila_diffs = []
        for ref_col, out_col, tipo in campos:
            if not _eq(row[ref_col], row[out_col], tipo):
                conteo[ref_col] += 1
                fila_diffs.append(
                    f"{ref_col}: ref={row[ref_col]} | out={row[out_col]}"
                )
        if fila_diffs:
            diffs.append(
                f"no={row['no_key']} tipo_id={row.get('tipo_id','')} no_id={row.get('no_id','')} -> "
                + "; ".join(fila_diffs)
            )

    # Sugerencias de codigos admin desde referencia
    sugerencias = []
    for code_col, ref_col in [
        ('cod_admin_afp', 'administradora'),
        ('cod_eps', 'administradora_1'),
        ('cod_ccf', 'administradora_ccf'),
    ]:
        if code_col not in df_cmp.columns or ref_col not in df_cmp.columns:
            continue
        sub = df_cmp[[code_col, ref_col]].copy()
        sub[code_col] = sub[code_col].astype(str).str.strip().str.upper()
        sub['ref_norm'] = sub[ref_col].map(_normalizar_admin)
        sub = sub[(sub[code_col] != '') & (sub['ref_norm'] != '')]
        for codigo, grp in sub.groupby(code_col):
            nombre_ref = grp['ref_norm'].value_counts().index[0]
            nombre_actual = _normalizar_admin(CODIGOS_ADMIN.get(codigo, ''))
            if nombre_actual != nombre_ref:
                sugerencias.append(f"{codigo};{nombre_ref}")

    # Construir seccion
    lineas = []
    lineas.append(f"=== REFERENCIA: {etiqueta} ===")
    lineas.append(f"Filas referencia: {len(df_ref):,}")
    lineas.append(f"Filas salida: {len(df_out):,}")
    lineas.append(f"Coincidencias por no: {len(comunes):,}")
    lineas.append(f"Faltan en salida: {len(faltan_en_salida):,}")
    lineas.append(f"Faltan en referencia: {len(faltan_en_ref):,}")
    lineas.append("")
    lineas.append("DIFERENCIAS POR CAMPO")
    for k, v in sorted(conteo.items(), key=lambda x: x[0]):
        lineas.append(f"{k}: {v}")
    lineas.append("")
    lineas.append("DETALLE DIFERENCIAS")
    lineas.extend(diffs if diffs else ["(sin diferencias en campos comparados)"])
    lineas.append("")
    lineas.append("SUGERENCIAS CODIGOS_ADMIN (REFERENCIA)")
    lineas.extend(sorted(set(sugerencias)) if sugerencias else ["(sin sugerencias)"])
    lineas.append("")

    return lineas, sugerencias


def generar_reporte_inconsistencias(
    df_out: pd.DataFrame,
    ruta_referencia,
    ruta_reporte: Path = None,
    ruta_comparacion: Path = None,
) -> Path:
    """
    Compara la salida parseada con referencias (pila_modificada.txt y/o comparacion.csv)
    y genera un TXT con todas las diferencias.
    """
    ruta_referencia = Path(ruta_referencia)
    if ruta_comparacion is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comparacion = ruta_def
    if ruta_reporte is None:
        ruta_reporte = ruta_referencia.with_suffix('.reporte.txt')

    df_out = df_out.copy()
    df_out = _normalizar_columnas(df_out)
    if 'cod_entidad' in df_out.columns:
        df_out = df_out.rename(columns={'cod_entidad': 'actividad_economica'})

    df_ref = _leer_referencia(ruta_referencia)

    # Overrides desde referencias (comparacion tiene prioridad)
    overrides = _extraer_overrides_admin(df_out, df_ref)
    if ruta_comparacion:
        ruta_comparacion = Path(ruta_comparacion)
        if ruta_comparacion.exists():
            df_comp = _leer_referencia(ruta_comparacion)
            overrides_comp = _extraer_overrides_admin(df_out, df_comp)
            for k in overrides_comp:
                overrides[k].update(overrides_comp.get(k, {}))

    # Aplicar overrides para comparar con nombres "descifrados"
    df_out_cmp = _aplicar_overrides_admin(df_out, overrides)

    # Inferir codigos faltantes usando referencias
    inferidos = []
    df_out_cmp, inf = _inferir_codigos_por_nombre(
        df_out_cmp, df_ref, 'afp', 'cod_admin_afp', 'administradora'
    )
    inferidos.extend(inf)
    df_out_cmp, inf = _inferir_codigos_por_nombre(
        df_out_cmp, df_ref, 'eps', 'cod_eps', 'administradora_1'
    )
    inferidos.extend(inf)
    df_out_cmp, inf = _inferir_codigos_por_nombre(
        df_out_cmp, df_ref, 'ccf', 'cod_ccf', 'administradora_ccf'
    )
    inferidos.extend(inf)

    if ruta_comparacion and ruta_comparacion.exists():
        df_comp = _leer_referencia(ruta_comparacion)
        df_out_cmp, inf = _inferir_codigos_por_nombre(
            df_out_cmp, df_comp, 'afp', 'cod_admin_afp', 'administradora'
        )
        inferidos.extend(inf)
        df_out_cmp, inf = _inferir_codigos_por_nombre(
            df_out_cmp, df_comp, 'eps', 'cod_eps', 'administradora_1'
        )
        inferidos.extend(inf)
        df_out_cmp, inf = _inferir_codigos_por_nombre(
            df_out_cmp, df_comp, 'ccf', 'cod_ccf', 'administradora_ccf'
        )
        inferidos.extend(inf)

    # Guardar overrides autogenerados para uso futuro
    ruta_autogen = Path(__file__).with_name('codigos_admin_autogen.txt')
    _escribir_codigos_autogen(overrides, ruta_autogen)
    for mapa in overrides.values():
        CODIGOS_ADMIN.update(mapa)

    # Codigos sin nombre (solo depende de salida)
    codigos_sin_nombre = []
    if 'cod_admin_afp' in df_out_cmp.columns and 'admin_afp' in df_out_cmp.columns:
        mask = df_out_cmp['cod_admin_afp'].fillna('').astype(str).str.strip() != ''
        mask = mask & (df_out_cmp['admin_afp'].fillna('').astype(str).str.strip() == '')
        for cod in sorted(df_out_cmp.loc[mask, 'cod_admin_afp'].unique().tolist()):
            codigos_sin_nombre.append(f"AFP;{cod}")
    if 'cod_eps' in df_out_cmp.columns and 'admin_eps' in df_out_cmp.columns:
        mask = df_out_cmp['cod_eps'].fillna('').astype(str).str.strip() != ''
        mask = mask & (df_out_cmp['admin_eps'].fillna('').astype(str).str.strip() == '')
        for cod in sorted(df_out_cmp.loc[mask, 'cod_eps'].unique().tolist()):
            codigos_sin_nombre.append(f"EPS;{cod}")
    if 'cod_ccf' in df_out_cmp.columns and 'admin_ccf' in df_out_cmp.columns:
        mask = df_out_cmp['cod_ccf'].fillna('').astype(str).str.strip() != ''
        mask = mask & (df_out_cmp['admin_ccf'].fillna('').astype(str).str.strip() == '')
        for cod in sorted(df_out_cmp.loc[mask, 'cod_ccf'].unique().tolist()):
            codigos_sin_nombre.append(f"CCF;{cod}")

    lineas = []
    lineas.append("REPORTE DE INCONSISTENCIAS - PILA")
    lineas.append("")

    seccion, sugerencias = _comparar_con_referencia(df_out_cmp, df_ref, str(ruta_referencia))
    lineas.extend(seccion)

    if ruta_comparacion and ruta_comparacion.exists():
        df_comp = _leer_referencia(ruta_comparacion)
        seccion_comp, _ = _comparar_con_referencia(df_out_cmp, df_comp, str(ruta_comparacion))
        lineas.extend(seccion_comp)

    lineas.append("OVERRIDES APLICADOS (AUTOGEN)")
    if any(overrides.get(k) for k in overrides):
        for key, titulo in [('afp', 'AFP'), ('eps', 'EPS'), ('ccf', 'CCF')]:
            mapa = overrides.get(key, {})
            if not mapa:
                continue
            lineas.append(f"[{titulo}]")
            for codigo, nombre in sorted(mapa.items(), key=lambda x: x[0]):
                lineas.append(f"{codigo};{nombre}")
    else:
        lineas.append("(sin overrides)")
    lineas.append("")

    lineas.append("CODIGOS INFERIDOS (INGENIERIA INVERSA)")
    if inferidos:
        for item in sorted(set(inferidos)):
            lineas.append(item)
    else:
        lineas.append("(sin codigos inferidos)")
    lineas.append("")

    lineas.append("CODIGOS SIN NOMBRE")
    lineas.extend(codigos_sin_nombre if codigos_sin_nombre else ["(sin codigos faltantes)"])

    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text('\n'.join(lineas), encoding='utf-8')
    return ruta_reporte

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
    # Segundo nombre: [106:136] (30 chars), indicadores arrancan en 136
    rec['Segundo_Nombre']   = linea[106:136].strip() if len(linea) > 136 else linea[106:].strip()
    rec['Nombre_Completo']  = ' '.join(filter(None, [
        rec['Primer_Apellido'], rec['Segundo_Apellido'],
        rec['Primer_Nombre'],   rec['Segundo_Nombre'],
    ]))

    cod_muni = _campo(linea, 31, 36)
    rec['Cod_Municipio']     = cod_muni
    ciudad_info = DANE_MUNICIPIOS.get(cod_muni, ('', ''))
    rec['Ciudad']            = ciudad_info[0]
    rec['Departamento']      = ciudad_info[1]

    tipo_cot_raw             = _campo(linea, 25, 29)
    subtipo_raw              = _campo(linea, 29, 31)
    rec['Tipo_Cotizante']    = tipo_cot_raw
    rec['Subtipo_Cotizante'] = subtipo_raw
    rec['Tipo_De_Cotizante'] = TIPO_COTIZANTE_LABEL.get(tipo_cot_raw, tipo_cot_raw)
    rec['Subtipo_De_Cotizante'] = 'NINGUNO' if subtipo_raw.strip() in ('', 'X') else subtipo_raw

    # ── Indicadores de novedad ──────────────────────────────────────────────
    # Posiciones confirmadas empiricamente:
    # 136=ING, 137=RET, 142=VSP, 144=VST, 148=SLN(L)
    def _char(pos: int) -> str:
        return linea[pos] if len(linea) > pos else ' '

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
        chunk = linea[pos:pos + 10] if len(linea) > pos + 10 else ''
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', chunk)
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
    per_m = re.search(r'[SN](\d{2}-\d{2})', linea[490:540])
    rec['Periodo_Planilla'] = per_m.group(1) if per_m else ''

    rec['Forma_Salario'] = _char(200)  # F=Fijo, V=Variable

    # ── AFP / Pension ───────────────────────────────────────────────────────
    cod_admin_raw        = _campo(linea, 151, 159)
    rec['Cod_Admin_AFP'] = _afp_code_clean(cod_admin_raw)
    rec['Admin_AFP']     = _lookup(cod_admin_raw) or _lookup(rec['Cod_Admin_AFP'])

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

    # ── Tarifas: clase ARL ───────────────────────────────────────────────────
    # (bloque de tarifas ya procesado arriba; accedemos a t_arl aqui)
    _t_arl_for_clase = rec.get('Tarifa_ARL', 0.0) or 0.0
    _clase_arl = ''
    for _tref, _cls in ARL_CLASE_POR_TARIFA.items():
        if abs(_t_arl_for_clase - _tref) < 0.00001:
            _clase_arl = _cls
            break
    rec['Clase_ARL'] = _clase_arl

    # ── Fin de linea: horas laboradas y codigo entidad ───────────────────────
    eol_m = re.search(r'(\d{9})(\d{3})\s+(\d{7})\s*$', linea)
    if eol_m:
        rec['Horas_Laboradas'] = int(eol_m.group(2))
        cod_entidad            = eol_m.group(3)
        rec['Cod_Entidad']     = cod_entidad
        # ARL: prefijo 4 digitos del cod_entidad
        rec['Admin_ARL'] = ARL_POR_PREFIJO.get(cod_entidad[:4], '')
    else:
        rec['Horas_Laboradas'] = None
        rec['Cod_Entidad']     = ''
        rec['Admin_ARL']       = ''

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
    empleados_unicos = df['no_id'].nunique()   if 'no_id'    in df.columns else 0
    total_ibc        = df['ibc'].sum()          if 'ibc'      in df.columns else 0
    total_pension    = df['valor_afp'].sum()    if 'valor_afp' in df.columns else 0
    total_eps        = df['valor_eps'].sum()    if 'valor_eps' in df.columns else 0
    total_arl        = df['valor_arl'].sum()    if 'valor_arl' in df.columns else 0
    total_ccf        = df['valor_ccf'].sum()    if 'valor_ccf' in df.columns else 0

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
        print("Uso: python seguridad_social_parte1.py <archivo.TxT> [carpeta_salida] [referencia.txt] [comparacion.csv]")
        sys.exit(1)

    archivo_entrada = Path(sys.argv[1])
    carpeta_salida  = Path(sys.argv[2]) if len(sys.argv) > 2 else archivo_entrada.parent
    ruta_referencia = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    ruta_comparacion = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    print(f"Leyendo: {archivo_entrada}")
    with open(archivo_entrada, 'r', encoding='latin-1') as f:
        contenido = f.read()

    df, empresa, totales = parse_pila_txt(contenido)

    df = adaptar_admin_con_referencias(df, ruta_referencia, ruta_comparacion)

    nombre_csv = archivo_entrada.stem + '.csv'
    ruta_csv   = carpeta_salida / nombre_csv
    exportar_csv(df, ruta_csv)

    # Exportar CSV con formato comparacion
    ruta_comp_eff = ruta_comparacion if ruta_comparacion and ruta_comparacion.exists() else None
    if ruta_comp_eff is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comp_eff = ruta_def
    ruta_csv_cmp = carpeta_salida / (archivo_entrada.stem + '_comparacion.csv')
    exportar_csv_formato_comparacion(
        df,
        ruta_csv_cmp,
        ruta_comp_eff,
        incluir_codigos=False,
        encabezado='oficial',
    )
    print(f"CSV comparacion oficial generado: {ruta_csv_cmp}")

    ruta_csv_cmp_cod = carpeta_salida / (archivo_entrada.stem + '_comparacion_codigos.csv')
    exportar_csv_formato_comparacion(
        df,
        ruta_csv_cmp_cod,
        ruta_comp_eff,
        incluir_codigos=True,
        encabezado='snake',
        forzar_texto_excel_cols=['tipo_cotizante', 'cod_municipio'],
    )
    print(f"CSV comparacion codigos generado: {ruta_csv_cmp_cod}")

    ruta_ref_eff = ruta_referencia if ruta_referencia and ruta_referencia.exists() else None
    if ruta_ref_eff is None:
        ruta_def = Path(__file__).parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'pila_modificada.txt'
        if ruta_def.exists():
            ruta_ref_eff = ruta_def

    if ruta_ref_eff is not None:
        ruta_reporte = carpeta_salida / (archivo_entrada.stem + '_reporte.txt')
        generar_reporte_inconsistencias(df, ruta_ref_eff, ruta_reporte, ruta_comparacion)
        print(f"Reporte generado: {ruta_reporte}")

    resumen = resumen_planilla(df, empresa)
    print("\n=== RESUMEN ===")
    for k, v in resumen.items():
        print(f"  {k}: {v:,}" if isinstance(v, int) and v > 999 else f"  {k}: {v}")
    print(f"\nCSV generado: {ruta_csv}")
    print(f"Filas exportadas: {len(df):,}")
