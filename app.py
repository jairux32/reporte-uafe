import io
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from clasificador import categoria_principal
from nacionalidad import clasificar_identificacion
from parser import leer_escrituras

st.set_page_config(
    page_title="Dashboard Protocolo Notarial",
    page_icon="📊",
    layout="wide",
)

CARPETA_TEMPORAL = Path(tempfile.gettempdir()) / "dashboard_uafe" / uuid.uuid4().hex

COLORES = px.colors.qualitative.Set2
MONTO = "$ %,.0f"


@st.cache_data
def cargar_datos(rutas_str):
    df = leer_escrituras([Path(r) for r in rutas_str])
    df["categoria"] = df["objetos"].apply(categoria_principal)
    return df


def archivos_predeterminados():
    raiz = Path(__file__).parent
    return sorted(
        list(raiz.glob("*.xls")) + list(raiz.glob("*.xlsx"))
    )


def exportar_excel(df, resumen, personas):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.drop(columns=["objetos", "otorgantes", "beneficiarios"]).to_excel(
            writer, sheet_name="Escrituras", index=False
        )
        resumen.to_excel(writer, sheet_name="Resumen categorias")
        personas.to_excel(writer, sheet_name="Personas", index=False)
    return buffer.getvalue()


def expandir_participantes(df_base):
    """Convierte las listas de otorgantes/beneficiarios en filas individuales
    con su clasificación de nacionalidad."""
    filas = []
    for _, fila in df_base.iterrows():
        for rol, columna in (("Otorgante", "otorgantes"), ("Beneficiario", "beneficiarios")):
            for nombre, identificacion in fila[columna]:
                clasificacion = clasificar_identificacion(identificacion)
                filas.append(
                    {
                        "persona": nombre,
                        "identificacion": identificacion,
                        "rol": rol,
                        "numero": fila["numero"],
                        "mes": fila["mes"],
                        "categoria": fila["categoria"],
                        "valor_factura": fila["valor_factura"],
                        "cuantia": fila["cuantia"],
                        **clasificacion,
                    }
                )
    personas = pd.DataFrame(filas)
    if personas.empty:
        return personas
    orden_nacionalidad = {
        "Ecuatoriana": 0, "Extranjera": 1, "Por verificar": 2,
        "Sin identificar": 3,
    }
    personas["_orden"] = personas["nacionalidad"].map(orden_nacionalidad).fillna(9)
    personas = personas.sort_values(
        ["_orden", "es_extranjero", "persona"], na_position="last"
    ).drop(columns="_orden")
    return personas


st.title("📊 Dashboard de Protocolo Notarial")
st.caption("Consolidación y análisis de índices de escrituras del Sistema Informático Notarial")

with st.sidebar:
    st.header("📁 Archivos de entrada")
    archivos_subidos = st.file_uploader(
        "Sube los índices de protocolo (.xls / .xlsx)",
        type=["xls", "xlsx"],
        accept_multiple_files=True,
    )

    if archivos_subidos:
        fuentes = []
        for archivo in archivos_subidos:
            temporal = CARPETA_TEMPORAL / archivo.name
            temporal.parent.mkdir(exist_ok=True)
            temporal.write_bytes(archivo.getvalue())
            fuentes.append(temporal)
        st.success(f"{len(fuentes)} archivo(s) cargado(s)")
    else:
        fuentes = archivos_predeterminados()
        if fuentes:
            st.info(
                "Usando los archivos de ejemplo del proyecto:\n\n"
                + "\n".join(f"- {f.name}" for f in fuentes)
            )
        else:
            st.warning("Sube al menos un archivo para comenzar.")

if not fuentes:
    st.stop()

df = cargar_datos([str(f) for f in fuentes])

with st.sidebar:
    st.divider()
    st.header("🔎 Filtros")

    meses = sorted(m for m in df["mes"].dropna().unique())
    meses_sel = st.multiselect("Mes", meses, default=meses)

    categorias = sorted(df["categoria"].dropna().unique())
    categorias_sel = st.multiselect("Categoría", categorias, default=categorias)

    estados = sorted(df["estado"].dropna().unique())
    estados_sel = st.multiselect("Estado", estados, default=estados)

    busqueda = st.text_input("Búsqueda libre (objeto, otorgante, beneficiario)")

filtro = (
    df["mes"].isin(meses_sel)
    & df["categoria"].isin(categorias_sel)
    & df["estado"].isin(estados_sel)
)
if busqueda:
    texto_busqueda = (
        df["objetos"].apply(lambda x: " ".join(x))
        + " "
        + df["otorgantes"].apply(lambda x: " ".join(n for n, _ in x))
        + " "
        + df["beneficiarios"].apply(lambda x: " ".join(n for n, _ in x))
    )
    filtro &= texto_busqueda.str.contains(busqueda, case=False, na=False)
datos = df[filtro]

if datos.empty:
    st.warning("No hay escrituras que cumplan los filtros seleccionados.")
    st.stop()

total = len(datos)
ingresos = datos["valor_factura"].sum()
cuantia = datos["cuantia"].sum()
fojas = int(datos["fojas"].sum())
pct_for = (datos["estado"] == "FOR").mean() * 100

st.subheader("Indicadores generales")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Escrituras", f"{total:,}")
k2.metric("Ingresos (facturas)", f"$ {ingresos:,.2f}")
k3.metric("Factura promedio", f"$ {ingresos / total:,.2f}")
k4.metric("Cuantía registrada", f"$ {cuantia:,.0f}")
k5.metric("Fojas consumidas", f"{fojas:,}")
k6.metric("Autorizadas (FOR)", f"{pct_for:.1f}%")

tab_resumen, tab_clasificacion, tab_finanzas, tab_personas, tab_nacionalidad, tab_temporal, tab_datos = st.tabs(
    [
        "📌 Resumen",
        "🗂️ Clasificación",
        "💰 Finanzas",
        "👥 Personas",
        "🌍 Nacionalidad",
        "📅 Temporalidad",
        "📋 Datos",
    ]
)

with tab_resumen:
    col1, col2 = st.columns([3, 2])

    por_mes = datos.groupby("mes").agg(
        escrituras=("numero", "count"), ingresos=("valor_factura", "sum")
    )
    figura_mes = go.Figure()
    figura_mes.add_bar(
        x=por_mes.index, y=por_mes["escrituras"], name="Escrituras",
        marker_color=COLORES[0], text=por_mes["escrituras"],
    )
    figura_mes.add_scatter(
        x=por_mes.index, y=por_mes["ingresos"], name="Ingresos ($)",
        yaxis="y2", mode="lines+markers", line=dict(color=COLORES[2], width=3),
    )
    figura_mes.update_layout(
        title="Escrituras e ingresos por mes",
        yaxis=dict(title="Escrituras"),
        yaxis2=dict(title="Ingresos ($)", overlaying="y", side="right"),
        xaxis=dict(title="Mes"),
        legend=dict(orientation="h", y=-0.2),
    )
    col1.plotly_chart(figura_mes, width='stretch')

    conteo_estado = datos["estado"].value_counts()
    figura_estado = px.pie(
        names=conteo_estado.index,
        values=conteo_estado.values,
        title="Estado de escrituras",
        hole=0.45,
        color_discrete_sequence=COLORES,
    )
    figura_estado.update_traces(textinfo="value+percent")
    col2.plotly_chart(figura_estado, width='stretch')

    st.plotly_chart(
        go.Figure(
            go.Scatter(
                x=datos.sort_values("fecha")["fecha"],
                y=[1] * len(datos),
                mode="markers",
                marker=dict(size=10, color=COLORES[1], symbol="square"),
                text=datos.sort_values("fecha")["numero"],
                hovertemplate="%{x|%d/%m/%Y %H:%M}<br>%{text}<extra></extra>",
            )
        ).update_layout(
            title="Línea de tiempo de otorgamiento de escrituras",
            yaxis=dict(visible=False),
            xaxis=dict(title="Fecha de otorgamiento"),
            height=220,
        ),
        width='stretch',
    )

with tab_clasificacion:
    col1, col2 = st.columns([2, 3])

    conteo_cat = datos["categoria"].value_counts().reset_index()
    conteo_cat.columns = ["Categoría", "Escrituras"]
    conteo_cat["%"] = (conteo_cat["Escrituras"] / total * 100).round(1)
    figura_cat = px.pie(
        conteo_cat,
        names="Categoría",
        values="Escrituras",
        title="Distribución por categoría de acto",
        hole=0.35,
        color_discrete_sequence=COLORES,
    )
    figura_cat.update_traces(textinfo="percent")
    col1.plotly_chart(figura_cat, width='stretch')

    por_categoria = (
        datos.groupby("categoria")
        .agg(
            escrituras=("numero", "count"),
            ingresos=("valor_factura", "sum"),
            cuantia=("cuantia", "sum"),
            fojas=("fojas", "sum"),
            factura_promedio=("valor_factura", "mean"),
        )
        .sort_values("escrituras", ascending=False)
    )
    por_categoria["% escrituras"] = (por_categoria["escrituras"] / total * 100).round(1)
    figura_barra = px.bar(
        por_categoria.reset_index(),
        x="escrituras",
        y="categoria",
        orientation="h",
        text="escrituras",
        title="Escrituras por categoría",
        color="escrituras",
        color_continuous_scale="Teal",
    )
    figura_barra.update_layout(showlegend=False, yaxis=dict(autorange="reversed"))
    col2.plotly_chart(figura_barra, width='stretch')

    st.subheader("Resumen por categoría")
    st.dataframe(
        por_categoria.style.format(
            {
                "ingresos": "$ {:,.2f}",
                "cuantia": "$ {:,.0f}",
                "factura_promedio": "$ {:,.2f}",
                "fojas": "{:,.0f}",
            }
        ),
        width='stretch',
    )

    with st.expander("📄 Detalle por tipo exacto de acto"):
        por_tipo = (
            datos.groupby(["categoria", "objeto"])
            .agg(escrituras=("numero", "count"), ingresos=("valor_factura", "sum"))
            .sort_values("escrituras", ascending=False)
        )
        por_tipo["%"] = (por_tipo["escrituras"] / total * 100).round(1)
        st.dataframe(
            por_tipo.style.format({"ingresos": "$ {:,.2f}"}),
            width='stretch',
        )

with tab_finanzas:
    col1, col2 = st.columns(2)

    ingresos_mes = datos.pivot_table(
        index="mes", columns="categoria", values="valor_factura", aggfunc="sum", fill_value=0
    )
    figura_ingresos = go.Figure()
    for i, categoria in enumerate(ingresos_mes.columns):
        figura_ingresos.add_bar(
            x=ingresos_mes.index, y=ingresos_mes[categoria], name=categoria,
            marker_color=COLORES[i % len(COLORES)],
        )
    figura_ingresos.update_layout(
        title="Ingresos por mes y categoría (barras apiladas)",
        barmode="stack",
        yaxis=dict(title="Ingresos ($)"),
        legend=dict(orientation="h", y=-0.25),
    )
    col1.plotly_chart(figura_ingresos, width='stretch')

    ingresos_cat = (
        datos.groupby("categoria")["valor_factura"].sum().sort_values(ascending=False)
    )
    figura_ingresos_cat = px.bar(
        ingresos_cat.reset_index(),
        x="valor_factura",
        y="categoria",
        orientation="h",
        text=ingresos_cat.values,
        title="Ingresos por categoría",
        color="valor_factura",
        color_continuous_scale="Viridis",
    )
    figura_ingresos_cat.update_traces(texttemplate="$ %{x:,.0f}")
    figura_ingresos_cat.update_layout(showlegend=False, yaxis=dict(autorange="reversed"))
    col2.plotly_chart(figura_ingresos_cat, width='stretch')

    col3, col4 = st.columns(2)
    con_cuantia = datos[datos["cuantia"].notna()]
    top_cuantia = con_cuantia.nlargest(10, "cuantia")[
        ["numero", "fecha", "objeto", "cuantia", "otorgantes"]
    ].copy()
    top_cuantia["otorgantes"] = top_cuantia["otorgantes"].apply(
        lambda x: ", ".join(n for n, _ in x)
    )
    figura_cuantia = px.bar(
        top_cuantia, x="cuantia", y="numero", orientation="h",
        title="Top 10 escrituras por cuantía", text="cuantia",
        hover_data=["objeto"],
    )
    figura_cuantia.update_traces(texttemplate="$ %{x:,.0f}")
    figura_cuantia.update_layout(yaxis=dict(autorange="reversed"))
    col3.plotly_chart(figura_cuantia, width='stretch')

    figura_hist = px.histogram(
        datos, x="valor_factura", nbins=30,
        title="Distribución del valor de facturas",
        color_discrete_sequence=[COLORES[0]],
    )
    figura_hist.update_layout(
        xaxis=dict(title="Valor factura sin IVA ($)"),
        yaxis=dict(title="Escrituras"),
        showlegend=False,
    )
    col4.plotly_chart(figura_hist, width='stretch')

    totales_fin = {
        "Ingresos totales (sin IVA)": f"$ {ingresos:,.2f}",
        "Factura mínima": f"$ {datos['valor_factura'].min():,.2f}",
        "Factura máxima": f"$ {datos['valor_factura'].max():,.2f}",
        "Escrituras con cuantía registrada": f"{len(con_cuantia)} ({len(con_cuantia) / total * 100:.1f}%)",
        "Cuantía total registrada": f"$ {cuantia:,.2f}",
        "Cuantía promedio": f"$ {con_cuantia['cuantia'].mean():,.2f}" if not con_cuantia.empty else "—",
    }
    st.dataframe(
        pd.DataFrame(totales_fin.items(), columns=["Indicador", "Valor"]),
        hide_index=True,
        width='stretch',
    )

with tab_personas:
    col1, col2 = st.columns(2)

    participantes = expandir_participantes(datos)
    otorgantes_exp = participantes[participantes["rol"] == "Otorgante"]
    beneficiarios_exp = participantes[participantes["rol"] == "Beneficiario"]

    top_otorgantes = (
        otorgantes_exp.groupby(["persona", "identificacion"])
        .agg(escrituras=("numero", "nunique"), monto=("valor_factura", "sum"))
        .sort_values("escrituras", ascending=False)
        .head(15)
        .reset_index()
    )
    top_otorgantes["nacionalidad"] = top_otorgantes["identificacion"].apply(
        lambda i: clasificar_identificacion(i)["nacionalidad"]
    )
    figura_otorgantes = px.bar(
        top_otorgantes.head(10),
        x="escrituras", y="persona", orientation="h", text="escrituras",
        title="Top 10 otorgantes (personas que otorgan)",
        hover_data=["identificacion", "monto"],
        color_discrete_sequence=[COLORES[1]],
    )
    figura_otorgantes.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
    col1.plotly_chart(figura_otorgantes, width='stretch')

    top_beneficiarios = (
        beneficiarios_exp.groupby(["persona", "identificacion"])
        .agg(escrituras=("numero", "nunique"), monto=("valor_factura", "sum"))
        .sort_values("escrituras", ascending=False)
        .head(15)
        .reset_index()
    )
    top_beneficiarios["nacionalidad"] = top_beneficiarios["identificacion"].apply(
        lambda i: clasificar_identificacion(i)["nacionalidad"]
    )
    figura_beneficiarios = px.bar(
        top_beneficiarios.head(10),
        x="escrituras", y="persona", orientation="h", text="escrituras",
        title="Top 10 beneficiarios (a favor de)",
        hover_data=["identificacion", "monto"],
        color_discrete_sequence=[COLORES[3]],
    )
    figura_beneficiarios.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
    col2.plotly_chart(figura_beneficiarios, width='stretch')

    col3, col4 = st.columns(2)
    col3.dataframe(
        top_otorgantes.style.format({"monto": "$ {:,.2f}"}),
        width='stretch',
    )
    col4.dataframe(
        top_beneficiarios.style.format({"monto": "$ {:,.2f}"}),
        width='stretch',
    )

    col5, col6 = st.columns(2)
    col5.metric("Otorgantes únicos", f"{otorgantes_exp['identificacion'].nunique():,}")
    col6.metric("Beneficiarios únicos", f"{beneficiarios_exp['identificacion'].nunique():,}")

with tab_nacionalidad:
    st.caption(
        "Clasificación según el documento de identidad registrado en el protocolo: "
        "cédulas y RUC ecuatorianos validados con dígito verificador (SRI); "
        "cualquier otro documento se considera extranjero. El país de origen de un "
        "pasaporte no consta en los archivos fuente."
    )

    personas_unicas = (
        participantes.drop_duplicates(subset=["identificacion"])
        if not participantes.empty
        else participantes
    )
    total_personas = len(personas_unicas)
    n_ecuatorianas = (personas_unicas["nacionalidad"] == "Ecuatoriana").sum()
    n_extranjeras = (personas_unicas["nacionalidad"] == "Extranjera").sum()
    n_verificar = (personas_unicas["nacionalidad"] == "Por verificar").sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Personas y entidades únicas", f"{total_personas:,}")
    k2.metric("Ecuatorianas", f"{n_ecuatorianas:,}", f"{n_ecuatorianas / total_personas * 100:.1f}%")
    k3.metric("Extranjeras", f"{n_extranjeras:,}", f"{n_extranjeras / total_personas * 100:.1f}%" if n_extranjeras else None)
    k4.metric("Por verificar", f"{n_verificar:,}")
    k5.metric(
        "Provincias de origen",
        f"{personas_unicas.loc[personas_unicas['provincia'] != '—', 'provincia'].nunique():,}",
    )

    col1, col2 = st.columns([2, 3])

    composicion = (
        personas_unicas.groupby(["nacionalidad", "tipo_documento"])
        .size()
        .reset_index(name="personas")
        .sort_values("personas", ascending=False)
    )
    figura_composicion = px.pie(
        composicion,
        names="tipo_documento",
        values="personas",
        title="Composición de participantes por tipo de documento",
        hole=0.4,
        color_discrete_sequence=COLORES,
    )
    figura_composicion.update_traces(textinfo="percent")
    col1.plotly_chart(figura_composicion, width='stretch')

    provincias = (
        personas_unicas[personas_unicas["provincia"] != "—"]["provincia"]
        .value_counts()
        .reset_index()
    )
    provincias.columns = ["Provincia", "Personas"]
    figura_provincias = px.bar(
        provincias.head(15),
        x="Personas",
        y="Provincia",
        orientation="h",
        text="Personas",
        title="Provincia de emisión de la cédula (top 15)",
        color="Personas",
        color_continuous_scale="Teal",
    )
    figura_provincias.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
    col2.plotly_chart(figura_provincias, width='stretch')

    st.subheader("Participantes extranjeros y documentos por verificar")
    columna_extranjeros = st.columns(1)[0]
    extranjeros_tabla = personas_unicas[
        personas_unicas["nacionalidad"].isin(["Extranjera", "Por verificar"])
    ][
        ["persona", "identificacion", "nacionalidad", "pais", "tipo_documento",
         "provincia"]
    ].rename(
        columns={
            "persona": "Nombre",
            "identificacion": "Identificación",
            "nacionalidad": "Nacionalidad",
            "pais": "País",
            "tipo_documento": "Tipo de documento",
            "provincia": "Provincia",
        }
    )
    if extranjeros_tabla.empty:
        columna_extranjeros.info("No hay participantes extranjeros en la selección actual.")
    else:
        columna_extranjeros.dataframe(extranjeros_tabla, width='stretch', hide_index=True)

    with st.expander("👤 Ver todas las personas y entidades con su clasificación"):
        st.dataframe(
            personas_unicas[
                ["persona", "identificacion", "rol", "nacionalidad", "pais",
                 "tipo_documento", "provincia"]
            ].rename(
                columns={
                    "persona": "Nombre",
                    "identificacion": "Identificación",
                    "rol": "Rol",
                    "nacionalidad": "Nacionalidad",
                    "pais": "País",
                    "tipo_documento": "Tipo de documento",
                    "provincia": "Provincia",
                }
            ),
            width='stretch',
            hide_index=True,
        )

with tab_temporal:
    col1, col2 = st.columns([3, 2])

    por_dia = datos.groupby("dia").agg(
        escrituras=("numero", "count"), ingresos=("valor_factura", "sum")
    )
    figura_dia = go.Figure()
    figura_dia.add_bar(
        x=por_dia.index, y=por_dia["escrituras"], name="Escrituras",
        marker_color=COLORES[0],
    )
    figura_dia.add_scatter(
        x=por_dia.index, y=por_dia["ingresos"], name="Ingresos ($)",
        yaxis="y2", mode="lines", line=dict(color=COLORES[2], width=2),
    )
    figura_dia.update_layout(
        title="Actividad diaria: escrituras e ingresos",
        yaxis=dict(title="Escrituras"),
        yaxis2=dict(title="Ingresos ($)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=-0.25),
    )
    col1.plotly_chart(figura_dia, width='stretch')

    orden_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    por_semana = datos["dia_semana"].value_counts().reindex(orden_semana).fillna(0)
    figura_semana = px.bar(
        x=por_semana.index, y=por_semana.values,
        title="Escrituras por día de la semana",
        text=por_semana.values.astype(int),
        color=por_semana.values,
        color_continuous_scale="Teal",
    )
    figura_semana.update_layout(
        xaxis=dict(title=None), yaxis=dict(title="Escrituras"), showlegend=False
    )
    col2.plotly_chart(figura_semana, width='stretch')

    col3, col4 = st.columns(2)
    fojas_mes = datos.groupby("mes")["fojas"].sum()
    figura_fojas = px.bar(
        x=fojas_mes.index, y=fojas_mes.values,
        title="Fojas de protocolo consumidas por mes",
        text=fojas_mes.values.astype(int),
        color_discrete_sequence=[COLORES[4]],
    )
    figura_fojas.update_layout(
        xaxis=dict(title="Mes"), yaxis=dict(title="Fojas"), showlegend=False
    )
    col3.plotly_chart(figura_fojas, width='stretch')

    por_hora = datos["fecha"].dt.hour.value_counts().sort_index()
    figura_hora = px.bar(
        x=por_hora.index, y=por_hora.values,
        title="Otorgamientos por hora del día",
        text=por_hora.values.astype(int),
        color_discrete_sequence=[COLORES[5]],
    )
    figura_hora.update_layout(
        xaxis=dict(title="Hora", dtick=1), yaxis=dict(title="Escrituras"), showlegend=False
    )
    col4.plotly_chart(figura_hora, width='stretch')

with tab_datos:
    st.subheader("Explorador de escrituras")

    tabla = datos.copy()
    tabla["extranjeros"] = tabla["otorgantes"].apply(
        lambda lista: ", ".join(n for n, i in lista if clasificar_identificacion(i)["es_extranjero"])
    ) + tabla["beneficiarios"].apply(
        lambda lista: ", ".join(n for n, i in lista if clasificar_identificacion(i)["es_extranjero"])
    )
    columnas_mostrar = [
        "numero", "fecha", "estado", "objeto", "categoria", "cuantia",
        "fojas", "folio_desde", "folio_hasta", "factura", "valor_factura",
        "n_otorgantes", "n_beneficiarios", "extranjeros", "archivo",
    ]
    tabla = tabla[columnas_mostrar]
    tabla["fecha"] = tabla["fecha"].dt.strftime("%d/%m/%Y %H:%M")

    st.dataframe(tabla, width='stretch', height=450)

    columnas_excel = st.columns([1, 1, 4])
    with columnas_excel[0]:
        excel_bytes = exportar_excel(
            datos, por_categoria, participantes
        )
        st.download_button(
            "⬇️ Descargar consolidado Excel",
            data=excel_bytes,
            file_name="consolidado_escrituras.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with columnas_excel[1]:
        st.download_button(
            "⬇️ Descargar CSV",
            data=tabla.to_csv(index=False).encode("utf-8-sig"),
            file_name="consolidado_escrituras.csv",
            mime="text/csv",
        )

st.divider()
st.caption(
    f"Fuente: {len(fuentes)} archivo(s) · {total:,} escrituras · "
    f"Generado con Streamlit + Plotly"
)
