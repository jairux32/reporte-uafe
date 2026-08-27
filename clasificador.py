"""Clasificación de escrituras notariales en categorías por tipo de acto."""
import re

REGLAS = [
    (r"PATRIMONIO FAMILIAR", "Patrimonio Familiar"),
    (r"\bHIPOTECA\b|\bPRENDA\b|REQUERIMIENTO AL DEUDOR", "Hipotecas y Garantías"),
    (r"\bPODER\b|PROCURACIÓN|MANDATO", "Poderes y Procuraciones"),
    (r"COMPRAVENTA|TRANSFERENCIA DE DOMINIO|RATIFICACIÓN.*COMPRA", "Compraventas y Transferencias"),
    (r"SOCIEDADES|CESIÓN DE DERECHOS DE SOCIOS|CESIÓN DE PARTICIPACIONES|ADMINISTRADOR COMÚN",
     "Sociedades y Participaciones"),
    (r"DECLARACIÓN JURAMENTADA|SUPERVIVENCIA|INFORMACIÓN SUMARIA|FE DE LA",
     "Declaraciones Juramentadas"),
    (r"SOCIEDAD CONYUGAL|DIVORCIO|GANANCIALES|SALIDA DEL PAÍS", "Familia y Régimen Conyugal"),
    (r"POSESIÓN EFECTIVA|PARTICIÓN|ADJUDICACIÓN|MONTEPÍO", "Sucesiones y Herencias"),
    (r"AMOJONAMIENTO|UNIFICACIÓN DE LOTES|USUFRUCTO|COMODATO|ARRENDAMIENTO|DESAHUCIO|PROMESA",
     "Contratos y Bienes Inmuebles"),
    (r"DONACIÓN", "Donaciones"),
    (r"PROTOCOLIZACIÓN|ACLARATORIA|AMPLIATORIA|RECTIFICATORIA|RATIFICATORIA|CESIÓN DE DERECHOS",
     "Protocolizaciones y Otros Actos"),
]

CATEGORIA_DEFAULT = "Protocolizaciones y Otros Actos"


def clasificar(objeto: str) -> str:
    texto = (objeto or "").upper()
    for patron, categoria in REGLAS:
        if re.search(patron, texto):
            return categoria
    return CATEGORIA_DEFAULT


def categoria_principal(objetos: list[str]) -> str:
    """Clasifica usando el objeto principal (primero) de la escritura."""
    return clasificar(objetos[0] if objetos else "")
