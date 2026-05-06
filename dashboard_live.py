import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard SPC Live - Questum", layout="wide")

# RUTA DE LA BASE DE DATOS LOCAL
RUTA_BD = "https://raw.githubusercontent.com/MaxGtov/bot-sedimento-gm/main/BD_LECTURAS_LIVE.xlsx"

# COLUMNAS QUE NO SON VARIABLES
COLUMNAS_METADATA = [
    'Bot_Fecha', 'Bot_Hoja', 'Bot_Linea', 
    'N° Medición', 'Fecha y hora', 
    'TELESIS - NÚMERO DE TELESIS', '#_Parte - Número de Parte del Producto', 
    'Capturador'
]

@st.cache_data(ttl=60)
def cargar_datos():
    if os.path.exists(RUTA_BD):
        df = pd.read_excel(RUTA_BD)
        df['Fecha y hora'] = pd.to_datetime(df['Fecha y hora'], errors='coerce')
        df['Bot_Fecha'] = pd.to_datetime(df['Bot_Fecha'], errors='coerce')
        return df
    return None

# ==========================================
# 2. ENCABEZADO
# ==========================================
st.title("🚀 Monitoreo SPC Multilínea en Tiempo Real")
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
        
        # Limpieza numérica y orden cronológico
        df_final[variable_sel] = pd.to_numeric(df_final[variable_sel], errors='coerce')
        df_grafica = df_final.dropna(subset=[variable_sel, 'Fecha y hora']).sort_values('Fecha y hora')

        # KPI's
        col1, col2, col3, col4 = st.columns(4)
        if not df_grafica.empty:
            prom = df_grafica[variable_sel].mean()
            with col1: st.metric("Muestras", len(df_grafica))
            with col2: st.metric("Media", f"{prom:.3f}")
            with col3: st.metric("Máximo", f"{df_grafica[variable_sel].max():.3f}")
            with col4: st.metric("Mínimo", f"{df_grafica[variable_sel].min():.3f}")

            # ==========================================
            # 5. GRÁFICA CON EJE X Y ETIQUETA DE ÚLTIMO DATO
            # ==========================================
            st.subheader(f"📊 Gráfico de Control: {variable_sel}")
            
            fig = px.line(df_grafica, 
                         x='Fecha y hora', 
                         y=variable_sel, 
                         markers=True,
                         hover_data=['N° Medición', 'Capturador'],
                         template="plotly_dark")

            # --- ETIQUETA DINÁMICA PARA EL ÚLTIMO DATO ---
            ultimo_punto = df_grafica.iloc[-1] # Obtenemos la última fila
            
            fig.add_annotation(
                x=ultimo_punto['Fecha y hora'],
                y=ultimo_punto[variable_sel],
                text=f"<b>Último: {ultimo_punto[variable_sel]:.3f}</b>",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-40, # Distancia hacia arriba del punto
                bgcolor="rgba(0, 255, 255, 0.9)", # Color Cian con opacidad
                font=dict(color="black", size=12),
                bordercolor="white",
                borderwidth=1
            )

            # MEJORAS DEL EJE X
            fig.update_xaxes(
                title_text='Fecha y Hora de Medición',
                type='date',
                tickformat="%d-%b %H:%M",
                tickangle=-45,
                rangeslider_visible=False 
            )

            fig.update_yaxes(title_text='Valor Medido')
            fig.add_hline(y=prom, line_dash="dash", line_color="cyan", annotation_text="Media")

            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("No hay datos numéricos en el rango seleccionado.")

    # TABLA
    st.markdown("---")
    st.subheader("📋 Datos en Bruto")
    st.dataframe(df_final.sort_values('Fecha y hora', ascending=False), use_container_width=True)

    if st.button("🔄 Actualizar"):
        st.cache_data.clear()
        st.rerun()
else:
    st.error("Esperando datos del Bot...")
