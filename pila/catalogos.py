# -*- coding: utf-8 -*-
"""
Catalogos y tablas base para PILA.
"""

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


BASE_DIR = Path(__file__).resolve().parents[1]


def cargar_codigos_admin(ruta: Path = None) -> dict:
    """Carga la tabla de codigos de administradoras desde codigos_admin.txt."""
    if ruta is None:
        ruta = BASE_DIR / 'codigos_admin.txt'

    codigos_base = dict(DEFAULT_CODIGOS_ADMIN)

    if ruta.exists():
        for linea in ruta.read_text(encoding='utf-8').splitlines():
            linea = linea.strip()
            if not linea:
                continue
            if linea.startswith('#') or linea.startswith('['):
                continue
            if ';' not in linea:
                continue
            codigo, nombre = linea.split(';', 1)
            codigo = codigo.strip().upper()
            nombre = nombre.strip().upper()
            if codigo and nombre:
                codigos_base[codigo] = nombre

    return codigos_base


CODIGOS_ADMIN = cargar_codigos_admin()


def lookup_admin(codigo: str) -> str:
    """Busca nombre de administradora, con fallback AFP por ultimos 6 digitos."""
    if codigo is None:
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
