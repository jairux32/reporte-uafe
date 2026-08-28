"""Clasificación de personas por tipo de documento y nacionalidad.

Clasifica según el número de identificación registrado en el protocolo:
- Cédula ecuatoriana válida (10 dígitos, dígito verificador correcto)
- RUC ecuatoriano válido (13 dígitos: persona natural, jurídica o entidad pública)
- Cualquier otro formato se considera documento extranjero (pasaporte, cédula
  o documento de identidad de otro país)
"""
import re

PROVINCIAS = {
    "01": "Azuay", "02": "Bolívar", "03": "Cañar", "04": "Carchi",
    "05": "Chimborazo", "06": "Cotopaxi", "07": "El Oro", "08": "Esmeraldas",
    "09": "Guayas", "10": "Imbabura", "11": "Loja", "12": "Los Ríos",
    "13": "Manabí", "14": "Morona Santiago", "15": "Napo", "16": "Pastaza",
    "17": "Pichincha", "18": "Tungurahua", "19": "Zamora Chinchipe",
    "20": "Galápagos", "21": "Sucumbíos", "22": "Orellana",
    "23": "Santo Domingo de los Tsáchilas", "24": "Santa Elena",
}

PAIS_PREFIJO = {
    "AR": "Argentina", "BO": "Bolivia", "BR": "Brasil", "CA": "Canadá",
    "CL": "Chile", "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba",
    "DE": "Alemania", "DO": "República Dominicana", "EC": "Ecuador",
    "ES": "España", "FR": "Francia", "GT": "Guatemala", "HN": "Honduras",
    "IT": "Italia", "MX": "México", "NI": "Nicaragua", "PA": "Panamá",
    "PE": "Perú", "PT": "Portugal", "PY": "Paraguay", "SV": "El Salvador",
    "US": "Estados Unidos", "UY": "Uruguay", "VE": "Venezuela",
}

RE_SOLO_DIGITOS = re.compile(r"^\d+$")


def _validar_cedula(numero: str) -> bool:
    if not RE_SOLO_DIGITOS.match(numero) or len(numero) != 10:
        return False
    if numero[:2] not in PROVINCIAS or numero[2] > "5":
        return False
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = sum(
        (d * c - 9) if d * c > 9 else d * c
        for d, c in zip(map(int, numero[:9]), coeficientes)
    )
    verificador = (10 - suma % 10) % 10
    return verificador == int(numero[9])


def _validar_ruc_juridico_o_publico(numero: str) -> bool:
    if not RE_SOLO_DIGITOS.match(numero) or len(numero) != 13:
        return False
    if numero[:2] not in PROVINCIAS or numero[10:13] != "001":
        return False
    if numero[2] == "9":
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        digitos = numero[:9]
        posicion_verificador = 9
    elif numero[2] == "6":
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        digitos = numero[:8]
        posicion_verificador = 8
    else:
        return False
    suma = sum(d * c for d, c in zip(map(int, digitos), coeficientes))
    verificador = 11 - suma % 11
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        return False
    return verificador == int(numero[posicion_verificador])


def clasificar_identificacion(identificacion: str) -> dict:
    """Devuelve tipo de documento, nacionalidad y provincia de origen."""
    texto = (identificacion or "").strip().upper()
    resultado = {
        "tipo_documento": "No registrado",
        "nacionalidad": "Sin identificar",
        "pais": "—",
        "provincia": "—",
        "es_extranjero": None,
    }
    if not texto:
        return resultado

    if _validar_cedula(texto):
        resultado.update(
            tipo_documento="Cédula ecuatoriana",
            nacionalidad="Ecuatoriana",
            provincia=PROVINCIAS.get(texto[:2], "—"),
            es_extranjero=False,
        )
    elif RE_SOLO_DIGITOS.match(texto) and len(texto) == 13 and texto[2] == "6":
        if _validar_ruc_juridico_o_publico(texto):
            resultado.update(
                tipo_documento="RUC entidad pública",
                nacionalidad="Ecuatoriana",
                provincia=PROVINCIAS.get(texto[:2], "—"),
                es_extranjero=False,
            )
        else:
            resultado.update(
                tipo_documento="RUC no válido",
                nacionalidad="Por verificar",
                es_extranjero=None,
            )
    elif RE_SOLO_DIGITOS.match(texto) and len(texto) == 13 and texto[2] == "9":
        if _validar_ruc_juridico_o_publico(texto):
            resultado.update(
                tipo_documento="RUC persona jurídica",
                nacionalidad="Ecuatoriana",
                provincia=PROVINCIAS.get(texto[:2], "—"),
                es_extranjero=False,
            )
        else:
            resultado.update(
                tipo_documento="RUC no válido",
                nacionalidad="Por verificar",
                es_extranjero=None,
            )
    elif RE_SOLO_DIGITOS.match(texto) and len(texto) == 13 and texto[10:13] == "001":
        if _validar_cedula(texto[:10]):
            resultado.update(
                tipo_documento="RUC persona natural",
                nacionalidad="Ecuatoriana",
                provincia=PROVINCIAS.get(texto[:2], "—"),
                es_extranjero=False,
            )
        else:
            resultado.update(
                tipo_documento="RUC no válido",
                nacionalidad="Por verificar",
                es_extranjero=None,
            )
    elif re.match(r"^[A-Z]{2}\d", texto) and texto[:2] in PAIS_PREFIJO:
        resultado.update(
            tipo_documento="Documento extranjero con código de país",
            nacionalidad="Extranjera",
            pais=PAIS_PREFIJO[texto[:2]],
            es_extranjero=True,
        )
    else:
        resultado.update(
            tipo_documento="Pasaporte o documento extranjero",
            nacionalidad="Extranjera",
            pais="Por determinar",
            es_extranjero=True,
        )
    return resultado
