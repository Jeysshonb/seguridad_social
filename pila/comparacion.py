# -*- coding: utf-8 -*-
"""
Funciones de comparacion, overrides y exportacion.
"""

import math
import re
from pathlib import Path

import pandas as pd

from .catalogos import CODIGOS_ADMIN, lookup_admin
from .normalizacion import (
    _insert_after,
    _limpiar_columnas_df,
    _limpiar_nombre_columna,
    _mask_empty,
    _mask_nonempty,
    _normalizar_admin,
    _normalizar_columnas,
    _normalizar_lista_columnas,
)
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


def construir_codigos_autogen_text(overrides: dict) -> str:
    if not overrides:
        return ''
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
    return '\n'.join(lineas).strip() + '\n'


def _escribir_codigos_autogen(overrides: dict, ruta: Path) -> None:
    texto = construir_codigos_autogen_text(overrides)
    if not texto:
        return
    ruta.write_text(texto, encoding='utf-8')


def exportar_codigos_autogen(overrides: dict, ruta: Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    _escribir_codigos_autogen(overrides, ruta)
    return ruta


def _columnas_comparacion_fallback_raw() -> list:
    return [
        'No.', 'Tipo ID', 'No ID', 'Primer Apellido', 'Segundo Apellido',
        'Primer Nombre', 'Segundo Nombre', 'Departamento', 'Ciudad',
        'Tipo de Cotizante', 'Subtipo de Cotizante', 'Horas Laboradas',
        'Extranjero', 'Colombiano Temporalmente en el Exterior',
        'Fecha RadicaciÃ³n en el Exterior', 'ING', 'Fecha ING', 'RET',
        'Fecha RET', 'TDE', 'TAE', 'TDP', 'TAP', 'VSP', 'Fecha VSP', 'VST',
        'SLN', 'Inicio SLN', 'Fin SLN', 'IGE', 'Inicio IGE', 'Fin IGE', 'LMA',
        'Inicio LMA', 'Fin LMA', 'VAC-LR', 'Inicio VAC-LR', 'Fin VAC-LR', 'AVP',
        'VCT', 'Inicio VCT', 'Fin VCT', 'IRL', 'Inicio IRL', 'Fin IRL',
        'Correcciones', 'Salario Mensual($)', 'Salario Integral',
        ' Salario Variable', 'Administradora', 'DÃ­as', 'IBC', 'Tarifa',
        'Valor CotizaciÃ³n', 'Indicador Alto Riesgo',
        'CotizaciÃ³n Voluntaria Afiliado', 'CotizaciÃ³n Voluntaria Empleador',
        'Fondo Solidaridad Pensional', 'Fondo Subsistencia',
        'Valor no Retenido', 'Total', 'AFP Destino', 'Administradora',
        'DÃ­as', 'IBC', 'Tarifa', 'Valor CotizaciÃ³n', 'Valor UPC',
        'NÂ° AutorizaciÃ³n Incapacidad EG', 'Valor Incapacidad EG',
        'NÂ° AutorizaciÃ³n LMA', 'Valor Licencia Maternidad', 'EPS Destino',
        'Administradora', 'DÃ­as', 'IBC', 'Tarifa', 'Clase',
        'Centro de Trabajo', 'Actividad EconÃ³mica', 'Valor CotizaciÃ³n',
        'DÃ­as', 'Administradora CCF', 'IBC CCF', 'Tarifa CCF',
        'Valor CotizaciÃ³n CCF', 'IBC Otros Parafiscales', 'Tarifa SENA',
        'Valor CotizaciÃ³n SENA', 'Tarifa ICBF', 'Valor CotizaciÃ³n ICBF',
        'Tarifa ESAP', 'Valor CotizaciÃ³n ESAP', 'Tarifa MEN',
        'Valor CotizaciÃ³n MEN', 'Exonerado parafiscales y salud',
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
        ruta_def = Path(__file__).resolve().parents[1] / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
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


def obtener_overrides_admin(
    df_out: pd.DataFrame,
    ruta_referencia: Path = None,
    ruta_comparacion: Path = None,
) -> dict:
    """
    Devuelve overrides combinados desde referencia y comparacion.
    """
    overrides = {'afp': {}, 'eps': {}, 'ccf': {}}

    if ruta_referencia is not None and Path(ruta_referencia).exists():
        df_ref = _leer_referencia(Path(ruta_referencia))
        overrides_ref = _extraer_overrides_admin(df_out, df_ref)
        for k in overrides_ref:
            overrides[k].update(overrides_ref.get(k, {}))

    if ruta_comparacion is not None and Path(ruta_comparacion).exists():
        df_comp = _leer_referencia(Path(ruta_comparacion))
        overrides_comp = _extraer_overrides_admin(df_out, df_comp)
        for k in overrides_comp:
            overrides[k].update(overrides_comp.get(k, {}))

    return overrides


def adaptar_admin_con_referencias(
    df_out: pd.DataFrame,
    ruta_referencia: Path = None,
    ruta_comparacion: Path = None,
) -> pd.DataFrame:
    """
    Aplica overrides de nombres de administradoras a partir de referencias.
    """
    if ruta_comparacion is None:
        ruta_def = Path(__file__).resolve().parents[1] / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
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
            df_out_norm.loc[mask, name_col] = df_out_norm.loc[mask, code_col].apply(lookup_admin)

    # Aplicar overrides de nombres (referencias tienen prioridad)
    if any(overrides.get(k) for k in overrides):
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

    if 'error_parseo' in df_out.columns:
        df_out = df_out[df_out['error_parseo'].isna()]

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
        ruta_def = Path(__file__).resolve().parents[1] / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comparacion = ruta_def
    if ruta_reporte is None:
        ruta_reporte = ruta_referencia.with_suffix('.reporte.txt')

    df_out = df_out.copy()
    df_out = _normalizar_columnas(df_out)
    if 'cod_entidad' in df_out.columns:
        df_out = df_out.rename(columns={'cod_entidad': 'actividad_economica'})
    if 'error_parseo' in df_out.columns:
        df_out = df_out[df_out['error_parseo'].isna()]

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
