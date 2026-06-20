import streamlit as st
import ccxt
import pandas as pd
import time
import requests

# =====================================================================
# CONFIGURACIÓN DE NOTIFICACIONES (TELEGRAM LEÍDA DESDE SECRETS)
# =====================================================================
# Ahora lee de forma segura las credenciales que guardaste en Advanced Settings
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def enviar_alerta_telegram(mensaje):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Error enviando Telegram: {e}")

# =====================================================================
# CONFIGURACIÓN DE LA INTERFAZ WEB (STREAMLIT)
# =====================================================================
st.set_page_config(page_title="Crypto Momentum Scanner", layout="wide")
st.title("📊 Crypto Momentum Scanner & Signals")
st.subheader("Rastreador de movimientos agresivos en Futuros Perpetuos")

# Inicializar el estado de la aplicación para guardar el historial de señales
if 'historial_señales' not in st.session_state:
    st.session_state.historial_señales = []

# Barra lateral con parámetros configurables por el usuario
st.sidebar.header("⚙️ Configuración de la Estrategia")
SYMBOL_INPUT = st.sidebar.text_input("Par a operar (Binance)", value="BTC/USDT")
TIMEFRAME = st.sidebar.selectbox("Temporalidad", ["15m", "4h"], index=0)
UMBRAL = st.sidebar.slider("Umbral de movimiento (%)", min_value=1.0, max_value=15.0, value=5.0, step=0.5)

# Conexión segura usando tus credenciales guardadas en Secrets
exchange = ccxt.binance({
    'apiKey': st.secrets["API_KEY_TESTNET"],
    'secret': st.secrets["SECRET_KEY_TESTNET"],
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True, # CORRECCIÓN 1: Evita errores de sincronización de reloj en la nube
    }
})

# Forzar a la app a usar el entorno Testnet en la nube
exchange.set_sandbox_mode(True)

# CORRECCIÓN 2: Usar los servidores específicos de Testnet para datos públicos
# Esto evita que los servidores genéricos de Binance bloqueen la IP de Streamlit
exchange.urls['api']['public'] = 'https://testnet.binancefuture.com/fapi/v1'
exchange.urls['api']['private'] = 'https://testnet.binancefuture.com/fapi/v1'
# Métricas principales en pantalla
col1, col2, col3 = st.columns(3)
metrica_precio = col1.empty()
metrica_variacion = col2.empty()
metrica_estado = col3.empty()

st.write("---")
st.subheader("📜 Historial de Señales Detectadas")
tabla_señales = st.empty()

# =====================================================================
# BUCLE EN VIVO DENTRO DE LA PÁGINA WEB
# =====================================================================
while True:
    try:
        # Validar y adaptar la nomenclatura del par para asegurar compatibilidad en CCXT
        symbol = SYMBOL_INPUT.strip().upper()
        if "/" in symbol and ":" not in symbol:
            symbol = f"{symbol}:{symbol.split('/')[1]}"

        # 1. Obtener datos del Exchange
        velas = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=2)
        if len(velas) >= 2:
            vela_actual = velas[-1]
            precio_apertura = vela_actual[1]
            precio_actual = vela_actual[4]
            variacion = ((precio_actual - precio_apertura) / precio_apertura) * 100
            
            # 2. Actualizar las métricas en la web en tiempo real
            metrica_precio.metric(label=f"Precio Actual ({symbol})", value=f"{precio_actual:.2f} USDT")
            metrica_variacion.metric(
                label=f"Variación Vela {TIMEFRAME}", 
                value=f"{variacion:.2f}%", 
                delta=f"{variacion:.2f}%"
            )
            metrica_estado.metric(label="Estado del Scanner", value="🟢 Buscando señal...")

            # 3. Lógica de detección de señales
            direccion = None
            if variacion >= UBRAL:
                direccion = "🚀 LONG (COMPRA AGRESIVA)"
            elif variacion <= -UMBRAL:
                direccion = "🩸 SHORT (VENTA AGRESIVA)"

            # Si se detecta una señal, guardarla y notificar
            if direccion:
                hora_actual = time.strftime("%Y-%m-%d %H:%M:%S")
                nueva_señal = {
                    "Hora": hora_actual,
                    "Par": symbol,
                    "Dirección": direccion,
                    "Precio Entrada": precio_actual,
                    "Variación": f"{variacion:.2f}%"
                }
                
                # Evitar duplicar la misma señal consecutivamente
                if not st.session_state.historial_señales or st.session_state.historial_señales[0]["Dirección"] != direccion:
                    st.session_state.historial_señales.insert(0, nueva_señal)
                    
                    # Enviar Telegram
                    msg = f"⚠️ ¡SEÑAL DETECTADA!\n\nPar: {symbol}\nDirección: {direccion}\nPrecio: {precio_actual} USDT\nVariación: {variacion:.2f}%"
                    enviar_alerta_telegram(msg)
            
            # 4. Renderizar la tabla de señales en la web
            if st.session_state.historial_señales:
                df = pd.DataFrame(st.session_state.historial_señales)
                tabla_señales.dataframe(df, use_container_width=True)
            else:
                tabla_señales.info("Aún no se han detectado movimientos que superen el umbral establecido.")

    except Exception as e:
        # Muestra el tipo de error en la interfaz para que sepamos la causa exacta si falla
        metrica_estado.metric(label="Estado del Scanner", value=f"❌ Error: {str(e)[:20]}")
        print(f"Error detallado en el bucle: {e}")

    # Pausa de 5 segundos antes de refrescar
    time.sleep(5)
