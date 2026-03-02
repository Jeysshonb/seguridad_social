# -*- coding: utf-8 -*-
"""PILA processing package."""

from .catalogos import CODIGOS_ADMIN
from .parser import parse_pila_txt, exportar_csv, resumen_planilla
from .comparacion import (
    construir_df_formato_comparacion,
    exportar_csv_formato_comparacion,
    adaptar_admin_con_referencias,
    generar_reporte_inconsistencias,
    obtener_overrides_admin,
    construir_codigos_autogen_text,
    exportar_codigos_autogen,
)
from .validacion import validar_planilla, generar_reporte_validaciones

__all__ = [
    'CODIGOS_ADMIN',
    'parse_pila_txt',
    'exportar_csv',
    'resumen_planilla',
    'construir_df_formato_comparacion',
    'exportar_csv_formato_comparacion',
    'adaptar_admin_con_referencias',
    'generar_reporte_inconsistencias',
    'obtener_overrides_admin',
    'construir_codigos_autogen_text',
    'exportar_codigos_autogen',
    'validar_planilla',
    'generar_reporte_validaciones',
]
