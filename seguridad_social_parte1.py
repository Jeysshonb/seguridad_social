# -*- coding: utf-8 -*-
"""
seguridad_social_parte1.py
Wrapper publico para compatibilidad con funciones PILA.
"""

from pathlib import Path
import pandas as pd

from pila.parser import parse_pila_txt, exportar_csv, resumen_planilla
from pila.comparacion import (
    construir_df_formato_comparacion,
    exportar_csv_formato_comparacion,
    adaptar_admin_con_referencias,
    generar_reporte_inconsistencias,
)
from pila.validacion import validar_planilla, generar_reporte_validaciones

__all__ = [
    'parse_pila_txt',
    'exportar_csv',
    'resumen_planilla',
    'construir_df_formato_comparacion',
    'exportar_csv_formato_comparacion',
    'adaptar_admin_con_referencias',
    'generar_reporte_inconsistencias',
    'validar_planilla',
    'generar_reporte_validaciones',
]


# ---------------------------------------------------------------------------
# CLI rapido
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Uso: python seguridad_social_parte1.py <archivo.TxT> [carpeta_salida] [referencia.txt] [comparacion.csv]")
        sys.exit(1)

    archivo_entrada = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2]) if len(sys.argv) > 2 else archivo_entrada.parent
    ruta_referencia = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    ruta_comparacion = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    print(f"Leyendo: {archivo_entrada}")
    with open(archivo_entrada, 'r', encoding='latin-1') as f:
        contenido = f.read()

    df, empresa, totales = parse_pila_txt(contenido)
    df = adaptar_admin_con_referencias(df, ruta_referencia, ruta_comparacion)

    df_ok = df
    if 'error_parseo' in df_ok.columns:
        df_ok = df_ok[df_ok['error_parseo'].isna()]

    nombre_csv = archivo_entrada.stem + '.csv'
    ruta_csv = carpeta_salida / nombre_csv
    exportar_csv(df_ok, ruta_csv)

    # Exportar CSV con formato comparacion
    ruta_comp_eff = ruta_comparacion if ruta_comparacion and ruta_comparacion.exists() else None
    if ruta_comp_eff is None:
        ruta_def = Path(__file__).resolve().parent / 'seguridad_archivos' / 'NOMINA REGULAR' / 'comparacion.csv'
        if ruta_def.exists():
            ruta_comp_eff = ruta_def
    ruta_csv_cmp = carpeta_salida / (archivo_entrada.stem + '_comparacion.csv')
    exportar_csv_formato_comparacion(
        df_ok,
        ruta_csv_cmp,
        ruta_comp_eff,
        incluir_codigos=False,
        encabezado='oficial',
    )
    print(f"CSV comparacion oficial generado: {ruta_csv_cmp}")

    ruta_csv_cmp_cod = carpeta_salida / (archivo_entrada.stem + '_comparacion_codigos.csv')
    exportar_csv_formato_comparacion(
        df_ok,
        ruta_csv_cmp_cod,
        ruta_comp_eff,
        incluir_codigos=True,
        encabezado='snake',
        forzar_texto_excel_cols=['tipo_cotizante', 'cod_municipio'],
    )
    print(f"CSV comparacion codigos generado: {ruta_csv_cmp_cod}")

    ruta_ref_eff = ruta_referencia if ruta_referencia and ruta_referencia.exists() else None

    if ruta_ref_eff is not None:
        ruta_reporte = carpeta_salida / (archivo_entrada.stem + '_reporte.txt')
        generar_reporte_inconsistencias(df_ok, ruta_ref_eff, ruta_reporte, ruta_comparacion)
        print(f"Reporte generado: {ruta_reporte}")

    resumen = resumen_planilla(df_ok, empresa)
    print("\n=== RESUMEN ===")
    for k, v in resumen.items():
        print(f"  {k}: {v:,}" if isinstance(v, int) and v > 999 else f"  {k}: {v}")
    print(f"\nCSV generado: {ruta_csv}")
    print(f"Filas exportadas: {len(df_ok):,}")
