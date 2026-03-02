# -*- coding: utf-8 -*-
"""
Validaciones y reportes de calidad de datos.
"""

import re
import pandas as pd

from .catalogos import DANE_MUNICIPIOS, lookup_admin
from .normalizacion import _mask_empty, _normalizar_admin


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


def _serie_codigos_desconocidos(serie: pd.Series) -> list:
    if serie is None:
        return []
    vals = serie.fillna('').astype(str).str.strip().str.upper()
    out = []
    for v in vals.unique().tolist():
        if not v:
            continue
        if lookup_admin(v) == '':
            out.append(v)
    return sorted(set(out))


def validar_planilla(df: pd.DataFrame, info_empresa: dict, info_totales: dict) -> dict:
    """
    Ejecuta validaciones basicas sobre el DataFrame parseado.
    Retorna un dict con KPIs y detalles para UI o reporte.
    """
    df = df.copy()

    errores_parseo = pd.DataFrame()
    registros_desconocidos = pd.DataFrame()
    if 'error_parseo' in df.columns:
        errores_parseo = df[df['error_parseo'].notna()].copy()
        registros_desconocidos = errores_parseo[errores_parseo['error_parseo'] == 'tipo_registro_desconocido']

    df_ok = df
    if 'error_parseo' in df_ok.columns:
        df_ok = df_ok[df_ok['error_parseo'].isna()]

    criticos = [
        'no', 'tipo_id', 'no_id',
        'primer_apellido', 'primer_nombre',
        'cod_municipio',
    ]
    criticos_presentes = [c for c in criticos if c in df_ok.columns]
    criticos_faltantes = [c for c in criticos if c not in df_ok.columns]

    df_missing = pd.DataFrame()
    if criticos_presentes:
        masks = {c: _mask_empty(df_ok[c]) for c in criticos_presentes}
        mask_any = None
        for m in masks.values():
            mask_any = m if mask_any is None else (mask_any | m)
        if mask_any is None:
            mask_any = pd.Series(False, index=df_ok.index)

        base_cols = [c for c in ['num_linea', 'no', 'tipo_id', 'no_id'] if c in df_ok.columns]
        df_missing = df_ok.loc[mask_any, base_cols].copy()
        faltantes = []
        for idx in df_missing.index:
            campos = [c for c, m in masks.items() if m.loc[idx]]
            faltantes.append(', '.join(campos))
        df_missing['campos_faltantes'] = faltantes

    # Codigos desconocidos
    codigos_desconocidos = {
        'afp': _serie_codigos_desconocidos(df_ok.get('cod_admin_afp')),
        'eps': _serie_codigos_desconocidos(df_ok.get('cod_eps')),
        'ccf': _serie_codigos_desconocidos(df_ok.get('cod_ccf')),
    }

    # Municipios fuera de DANE
    municipios_desconocidos = []
    if 'cod_municipio' in df_ok.columns:
        vals = df_ok['cod_municipio'].fillna('').astype(str).str.strip()
        municipios_desconocidos = sorted({v for v in vals if v and v not in DANE_MUNICIPIOS})

    # Inconsistencias admin: codigo vs nombre
    inconsistencias = []
    for code_col, name_col, tipo in [
        ('cod_admin_afp', 'admin_afp', 'afp'),
        ('cod_eps', 'admin_eps', 'eps'),
        ('cod_ccf', 'admin_ccf', 'ccf'),
    ]:
        if code_col not in df_ok.columns or name_col not in df_ok.columns:
            continue
        sub = df_ok[[code_col, name_col]].copy()
        sub[code_col] = sub[code_col].fillna('').astype(str).str.strip().str.upper()
        sub[name_col] = sub[name_col].fillna('').astype(str).str.strip()
        sub = sub[sub[code_col] != '']
        for codigo, grp in sub.groupby(code_col):
            nombre = grp[name_col].value_counts().index[0]
            nombre_norm = _normalizar_admin(nombre)
            catalogo = lookup_admin(codigo)
            if not catalogo:
                continue
            catalogo_norm = _normalizar_admin(catalogo)
            if nombre_norm and catalogo_norm and nombre_norm != catalogo_norm:
                inconsistencias.append({
                    'tipo': tipo,
                    'codigo': codigo,
                    'nombre': nombre,
                    'nombre_catalogo': catalogo,
                })

    df_incons = pd.DataFrame(inconsistencias)

    # Totales calculados
    totales_calc = {
        'total_registros': len(df_ok),
        'total_ibc': int(df_ok['ibc'].sum()) if 'ibc' in df_ok.columns else 0,
        'total_afp': int(df_ok['valor_afp'].sum()) if 'valor_afp' in df_ok.columns else 0,
        'total_eps': int(df_ok['valor_eps'].sum()) if 'valor_eps' in df_ok.columns else 0,
        'total_arl': int(df_ok['valor_arl'].sum()) if 'valor_arl' in df_ok.columns else 0,
        'total_ccf': int(df_ok['valor_ccf'].sum()) if 'valor_ccf' in df_ok.columns else 0,
    }

    totales_tipo06 = []
    if isinstance(info_totales, dict):
        raw = info_totales.get('numeros_extraidos', '')
        if raw:
            for item in raw.split('|'):
                item = item.strip()
                if not item:
                    continue
                try:
                    totales_tipo06.append(int(item))
                except Exception:
                    pass

    kpis = {
        'errores_parseo': len(errores_parseo),
        'registros_desconocidos': len(registros_desconocidos),
        'campos_criticos_vacios': len(df_missing),
        'codigos_desconocidos': sum(len(v) for v in codigos_desconocidos.values()),
        'municipios_desconocidos': len(municipios_desconocidos),
        'inconsistencias_admin': len(df_incons),
    }

    return {
        'kpis': kpis,
        'errores_parseo': errores_parseo,
        'registros_desconocidos': registros_desconocidos,
        'campos_criticos_vacios': df_missing,
        'codigos_desconocidos': codigos_desconocidos,
        'municipios_desconocidos': municipios_desconocidos,
        'inconsistencias_admin': df_incons,
        'totales_calculados': totales_calc,
        'totales_tipo06': totales_tipo06,
        'criticos_presentes': criticos_presentes,
        'criticos_faltantes': criticos_faltantes,
        'info_empresa': info_empresa or {},
    }


def generar_reporte_validaciones(df: pd.DataFrame, info_empresa: dict, info_totales: dict) -> str:
    datos = validar_planilla(df, info_empresa, info_totales)

    lineas = []
    lineas.append('REPORTE VALIDACIONES PILA')
    lineas.append('')

    empresa = (info_empresa or {}).get('razon_social', '') if isinstance(info_empresa, dict) else ''
    nit = (info_empresa or {}).get('nit', '') if isinstance(info_empresa, dict) else ''
    if empresa or nit:
        lineas.append(f"Empresa: {empresa}")
        lineas.append(f"NIT: {nit}")
        lineas.append('')

    kpis = datos['kpis']
    lineas.append('RESUMEN')
    lineas.append(f"Errores parseo: {kpis['errores_parseo']}")
    lineas.append(f"Registros tipo desconocido: {kpis['registros_desconocidos']}")
    lineas.append(f"Campos criticos vacios: {kpis['campos_criticos_vacios']}")
    lineas.append(f"Codigos desconocidos: {kpis['codigos_desconocidos']}")
    lineas.append(f"Municipios desconocidos: {kpis['municipios_desconocidos']}")
    lineas.append(f"Inconsistencias admin: {kpis['inconsistencias_admin']}")
    lineas.append('')

    if datos['criticos_faltantes']:
        lineas.append('COLUMNAS CRITICAS AUSENTES')
        lineas.extend(datos['criticos_faltantes'])
        lineas.append('')

    # Errores de parseo
    lineas.append('ERRORES PARSEO')
    if datos['errores_parseo'].empty:
        lineas.append('(sin errores)')
    else:
        for row in datos['errores_parseo'].itertuples(index=False):
            num_linea = getattr(row, 'num_linea', '')
            tipo_registro = getattr(row, 'tipo_registro', '')
            err = getattr(row, 'error_parseo', '')
            raw = getattr(row, 'raw', '')
            lineas.append(f"linea={num_linea} tipo={tipo_registro} error={err} raw={raw}")
    lineas.append('')

    # Campos criticos
    lineas.append('CAMPOS CRITICOS VACIOS')
    df_missing = datos['campos_criticos_vacios']
    if df_missing.empty:
        lineas.append('(sin faltantes)')
    else:
        for row in df_missing.itertuples(index=False):
            num_linea = getattr(row, 'num_linea', '')
            no = getattr(row, 'no', '')
            tipo_id = getattr(row, 'tipo_id', '')
            no_id = getattr(row, 'no_id', '')
            faltan = getattr(row, 'campos_faltantes', '')
            lineas.append(f"linea={num_linea} no={no} tipo_id={tipo_id} no_id={no_id} faltan={faltan}")
    lineas.append('')

    # Codigos desconocidos
    lineas.append('CODIGOS DESCONOCIDOS')
    for key in ['afp', 'eps', 'ccf']:
        vals = datos['codigos_desconocidos'].get(key, [])
        lineas.append(f"{key.upper()}: {', '.join(vals) if vals else '(sin codigos)'}")
    lineas.append('')

    # Municipios
    lineas.append('MUNICIPIOS DESCONOCIDOS')
    if datos['municipios_desconocidos']:
        lineas.extend(datos['municipios_desconocidos'])
    else:
        lineas.append('(sin municipios)')
    lineas.append('')

    # Inconsistencias admin
    lineas.append('INCONSISTENCIAS ADMIN')
    df_inc = datos['inconsistencias_admin']
    if df_inc.empty:
        lineas.append('(sin inconsistencias)')
    else:
        for row in df_inc.itertuples(index=False):
            lineas.append(
                f"{row.tipo.upper()} codigo={row.codigo} nombre={row.nombre} catalogo={row.nombre_catalogo}"
            )
    lineas.append('')

    # Totales
    lineas.append('TOTALES CALCULADOS')
    for k, v in datos['totales_calculados'].items():
        lineas.append(f"{k}: {v}")
    lineas.append('')

    lineas.append('NUMEROS EXTRAIDOS TIPO 06')
    if datos['totales_tipo06']:
        lineas.append(' | '.join(str(v) for v in datos['totales_tipo06']))
    else:
        lineas.append('(sin numeros)')

    return '\n'.join(lineas) + '\n'
