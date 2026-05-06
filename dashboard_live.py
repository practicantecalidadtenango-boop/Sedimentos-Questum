import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y RUTAS
# ==========================================
st.set_page_config(page_title="Dashboard SPC Live - Questum", layout="wide")

# LECTURA DIRECTA DESDE LA MISMA CARPETA DEL REPOSITORIO
RUTA_BD = "BD_LECTURAS_LIVE.xlsx"

COLUMNAS_METADATA = [
    'Bot_Fecha', 'Bot_Hoja', 'Bot_Linea', 
    'N° Medición', 'Fecha y hora', 
    'TELESIS - NÚMERO DE TELESIS', '#_Parte - Número de Parte del Producto', 
    'Capturador'
]

# ==========================================
# 2. DICCIONARIO DE LÍMITES PREDEFINIDOS
# ==========================================
# El sistema buscará estas palabras clave en el nombre de la variable
LIMITES_PREDEFINIDOS = {
    "15-100": {"lsl": 0, "usl": 20000},
    "100-200": {"lsl": 0, "usl": 1200},
    "200-600": {"lsl": 0, "usl": 250},
    "600-1500": {"lsl": 0, "usl": 6},
    ">1500": {"lsl": 0, "usl": 0}
}

@st.cache_data(ttl=60)
def cargar_datos():
    try:
        df = pd.read_excel(RUTA_BD)
        df['Fecha y hora'] = pd.to_datetime(df['Fecha y hora'], errors='coerce')
        df['Bot_Fecha'] = pd.to_datetime(df['Bot_Fecha'], errors='coerce')
        return df
    except Exception as e:
        return None

# ==========================================
# 3. ENCABEZADO
# ==========================================
st.title("🚀 Monitoreo SPC Multilínea con Zonas Automáticas")
st.markdown("---")

df = cargar_datos()

if df is not None:
    # FILTROS LATERALES
    st.sidebar.header("⚙️ Configuración")
    lista_lineas = sorted(df['Bot_Linea'].dropna().unique())
    linea_sel = st.sidebar.selectbox("Línea:", lista_lineas)
    
    df_linea = df[df['Bot_Linea'] == linea_sel]
    lista_hojas = sorted(df_linea['Bot_Hoja'].dropna().unique())
    hoja_sel = st.sidebar.selectbox("Operación:", lista_hojas)

    df_final = df_linea[df_linea['Bot_Hoja'] == hoja_sel].copy()

    # DETECCIÓN DE VARIABLES
    columnas_vars = [c for c in df_final.columns if c not in COLUMNAS_METADATA and not c.startswith('Unnamed')]
    
    if columnas_vars:
        variable_sel = st.sidebar.selectbox("Variable a graficar:", columnas_vars)
        
        # --- BÚSQUEDA AUTOMÁTICA DE LÍMITES ---
        def_lsl = 0.0
        def_usl = 100.0
        
        for clave, limites in LIMITES_PREDEFINIDOS.items():
            if clave in variable_sel:
                def_lsl = float(limites["lsl"])
                def_usl = float(limites["usl"])
                break
        
        # --- CONFIGURACIÓN EN BARRA LATERAL ---
        with st.sidebar.expander("🛠️ Ajustar Zonas de Color"):
            st.caption("Límites cargados automáticamente:")
            lsl = st.number_input("Límite Inferior (LSL)", value=def_lsl, format="%.1f")
            usl = st.number_input("Límite Superior (USL)", value=def_usl, format="%.1f")
            
            if usl > 0:
                margen = st.slider("Margen de Advertencia (Amarillo) %", 0, 50, 15)
                rango = usl - lsl
                warning_upper = usl - (rango * margen / 100)
            else:
                st.info("Para límite máximo de 0, cualquier valor superior es rojo.")
                margen = 0
                warning_upper = 0

        # Limpieza numérica y orden
        df_final[variable_sel] = pd.to_numeric(df_final[variable_sel], errors='coerce')
        df_grafica = df_final.dropna(subset=[variable_sel, 'Fecha y hora']).sort_values('Fecha y hora')

        # KPI's
        col1, col2, col3, col4 = st.columns(4)
        if not df_grafica.empty:
            prom = df_grafica[variable_sel].mean()
            val_maximo = df_grafica[variable_sel].max()
            
            with col1: st.metric("Muestras", len(df_grafica))
            with col2: st.metric("Media", f"{prom:.2f}")
            with col3: 
                # Si el máximo supera el límite, lo pintamos de rojo en el KPI (Streamlit usa flechas rojas para valores negativos, pero simulamos alerta visual)
                st.metric("Máximo Detectado", f"{val_maximo:.2f}", delta="¡Fuera de límite!" if val_maximo > usl else "En regla", delta_color="inverse")
            with col4: st.metric("Mínimo", f"{df_grafica[variable_sel].min():.2f}")

            # ==========================================
            # 5. GRÁFICA CON ZONAS DE COLORES
            # ==========================================
            st.subheader(f"📊 Gráfico de Control SPC")
            
            fig = px.line(df_grafica, 
                         x='Fecha y hora', 
                         y=variable_sel, 
                         markers=True,
                         hover_data=['N° Medición', 'Capturador'],
                         template="plotly_dark")

            # Determinar el tope del gráfico visual (un poco más arriba del máximo medido o del límite)
            tope_grafico = max(usl * 1.2, val_maximo * 1.1)
            if tope_grafico == 0: tope_grafico = 10 # Por si todo es 0

            if usl > 0:
                # Zonas para variables normales
                # Verde (Zona Segura)
                fig.add_hrect(y0=lsl, y1=warning_upper, fillcolor="green", opacity=0.15, line_width=0, layer="below")
                # Amarillo (Zona de Riesgo)
                fig.add_hrect(y0=warning_upper, y1=usl, fillcolor="yellow", opacity=0.2, line_width=0, layer="below")
                # Rojo (Fuera de Especificación)
                fig.add_hrect(y0=usl, y1=tope_grafico, fillcolor="red", opacity=0.2, line_width=0, layer="below")
            else:
                # Zona para variable >1500 (Todo lo mayor a 0 es rojo)
                fig.add_hrect(y0=0, y1=tope_grafico, fillcolor="red", opacity=0.2, line_width=0, layer="below")

            # Etiqueta último dato
            ultimo = df_grafica.iloc[-1]
            fig.add_annotation(x=ultimo['Fecha y hora'], y=ultimo[variable_sel], 
                               text=f"<b>Último: {ultimo[variable_sel]:.1f}</b>",
                               showarrow=True, arrowhead=2, ay=-40, bgcolor="white", font=dict(color="black"))

            fig.update_xaxes(type='date', tickformat="%d-%b %H:%M", tickangle=-45)
            # Agregar línea del límite superior
            fig.add_hline(y=usl, line_dash="dash", line_color="red", annotation_text=f"Límite Máx ({usl})")

            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("No hay datos suficientes para graficar.")

    # TABLA
    st.markdown("---")
    st.subheader("📋 Registro de Mediciones Detallado")
    st.dataframe(df_final.sort_values('Fecha y hora', ascending=False), use_container_width=True)

    if st.button("🔄 Refrescar Gráficas"):
        st.cache_data.clear()
        st.rerun()
else:
    st.error("Esperando sincronización de datos desde el Bot...")
