"""Lectura y consolidación de índices de protocolo notarial (.xls / .xlsx).

Cada escritura puede ocupar varias filas: la fila principal tiene el número de
escritura y las filas siguientes (sin número) agregan objetos, otorgantes o
beneficiarios adicionales.
"""
import re
from pathlib import Path

import pandas as pd

RE_NUMERO_ESCRITURA = re.compile(r"^\d+P\d+$")
RE_DINERO = re.compile(r"[^0-9.\-]")

ENCABEZADO = "Escritura No."

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}

COLUMNAS = [
    "numero", "fecha", "estado", "objeto",
    "otorga", "id_otorga", "a_favor", "id_a_favor",
    "cuantia", "folio_desde", "folio_hasta", "fojas",
    "factura", "valor_factura",
]


def _texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or pd.isna(valor):
        return ""
    return str(valor).strip()


def _dinero(valor):
    """Convierte '$ 35,371.80' -> 35371.80. Devuelve None si no hay valor."""
    texto = _texto(valor)
    if not texto:
        return None
    limpio = RE_DINERO.sub("", texto)
    try:
        return float(limpio) if limpio not in ("", ".", "-") else None
    except ValueError:
        return None


def _entero(valor):
    texto = _texto(valor)
    if not texto:
        return None
    try:
        return int(float(texto))
    except ValueError:
        return None


def _fecha(valor):
    texto = _texto(valor)
    if not texto:
        return None
    return pd.to_datetime(texto, format="%d/%m/%Y %H:%M", errors="coerce")


def _ubicar_encabezado(hoja: pd.DataFrame) -> int:
    for i in range(min(15, len(hoja))):
        for valor in hoja.iloc[i].astype(str).str.strip():
            if valor == ENCABEZADO:
                return i
    raise ValueError("No se encontró la fila de encabezado 'Escritura No.'")


def _ubicar_columna_numero(hoja: pd.DataFrame, fila: int) -> int:
    for j, valor in hoja.iloc[fila].items():
        if _texto(valor) == ENCABEZADO:
            return j
    raise ValueError("No se encontró la columna 'Escritura No.'")


def _leer_hoja(ruta: Path) -> pd.DataFrame:
    hoja = pd.read_excel(ruta, sheet_name=0, header=None)
    fila_enc = _ubicar_encabezado(hoja)
    col_num = _ubicar_columna_numero(hoja, fila_enc)

    registros = []
    actual = None

    for i in range(fila_enc + 1, len(hoja)):
        fila = hoja.iloc[i]
        celdas = [_texto(fila.iloc[col_num + k]) if col_num + k < len(fila) else ""
                  for k in range(len(COLUMNAS))]
        valores = dict(zip(COLUMNAS, celdas))

        if RE_NUMERO_ESCRITURA.match(valores["numero"]):
            if actual is not None:
                registros.append(actual)
            actual = {
                "numero": valores["numero"],
                "fecha": _fecha(valores["fecha"]),
                "estado": valores["estado"],
                "objetos": [],
                "otorgantes": [],
                "beneficiarios": [],
                "cuantia": _dinero(valores["cuantia"]),
                "folio_desde": _entero(valores["folio_desde"]),
                "folio_hasta": _entero(valores["folio_hasta"]),
                "fojas": _entero(valores["fojas"]),
                "factura": valores["factura"],
                "valor_factura": _dinero(valores["valor_factura"]),
            }
            if valores["objeto"]:
                actual["objetos"].append(valores["objeto"])
            if valores["otorga"]:
                actual["otorgantes"].append((valores["otorga"], valores["id_otorga"]))
            if valores["a_favor"]:
                actual["beneficiarios"].append((valores["a_favor"], valores["id_a_favor"]))
        elif actual is not None:
            if valores["objeto"]:
                actual["objetos"].append(valores["objeto"])
            if valores["otorga"]:
                par = (valores["otorga"], valores["id_otorga"])
                if par not in actual["otorgantes"]:
                    actual["otorgantes"].append(par)
            if valores["a_favor"]:
                par = (valores["a_favor"], valores["id_a_favor"])
                if par not in actual["beneficiarios"]:
                    actual["beneficiarios"].append(par)

    if actual is not None:
        registros.append(actual)

    df = pd.DataFrame(registros)
    df["archivo"] = ruta.name
    return df


def leer_escrituras(rutas) -> pd.DataFrame:
    """Lee uno o varios archivos y devuelve el DataFrame consolidado."""
    frames = [_leer_hoja(Path(r)) for r in rutas]
    consolidado = pd.concat(frames, ignore_index=True)

    consolidado["objeto"] = consolidado["objetos"].apply(lambda x: x[0] if x else "")
    consolidado["n_objetos"] = consolidado["objetos"].apply(len)
    consolidado["n_otorgantes"] = consolidado["otorgantes"].apply(len)
    consolidado["n_beneficiarios"] = consolidado["beneficiarios"].apply(len)
    consolidado["mes"] = consolidado["fecha"].dt.strftime("%Y-%m")
    consolidado["dia"] = consolidado["fecha"].dt.date
    consolidado["dia_semana"] = consolidado["fecha"].dt.weekday.map(DIAS_SEMANA)
    return consolidado
