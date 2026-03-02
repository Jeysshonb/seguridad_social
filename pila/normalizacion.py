# -*- coding: utf-8 -*-
"""
Funciones de normalizacion y limpieza de columnas/texto.
"""

import math
import re
import unicodedata
import pandas as pd


def _limpiar_nombre_columna(nombre: str) -> str:
    texto = str(nombre)
    # Remueve BOM real y su artefacto comun mal decodificado.
    texto = texto.replace('\ufeff', '').replace('Ã¯Â»Â¿', '')
    return texto


def _limpiar_columnas_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_limpiar_nombre_columna(c) for c in df.columns]
    return df


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
