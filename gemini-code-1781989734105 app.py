import streamlit as st
import ccxt
import pandas as pd
import time
import requests

# =====================================================================
# CONFIGURACIÓN DE NOTIFICACIONES (TELEGRAM)
# =====================================================================
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
st.set_page_config(page_title="Crypto Multi-Scanner", layout="wide")
st.title("🔍 Multi-Asset Momentum Scanner")
st.subheader("Monitoreo simultáneo de todo el mercado de Futuros Perpetuos")

# Inicializar historial de señales en caché de Streamlit
if 'historial_señales' not in st.session_state:
    st.session_state.historial_señales = []

# Barra lateral ajustable
st.sidebar.header("⚙️ Configuración del Escáner")
UMBRAL = st.sidebar.slider("Umbral de movimiento (%)", min_value=1.0, max_value=15.0, value=5.0, step=0.5)
VOLUMEN_MINIMO = st.sidebar.number_input("Volumen mínimo 24h (USDT)", value=5000000, step=1000000)

# Conexión autorizada y configurada a la Testnet
exchange = ccxt.binance({
    'apiKey': st.secrets["API_KEY_TESTNET"],
    'secret': st.secrets["SECRET_KEY_TESTNET"],
    'enableRateLimit': True,
    'options': {'defaultType': 'future', 'adjustForTimeDifference': True}
})
exchange.set_sandbox_mode(True)
exchange.urls['api']['public'] = 'https://testnet.binancefuture.com/fapi/v1'
exchange.urls['api']['private'] = 'https://testnet.binancefuture.com/fapi/v1'

# Contenedores dinámicos en la interfaz web
metrica_estado = st.empty()
st.write("---")
st.subheader("📜 Historial de Señales en Tiempo Real (Cualquier Moneda)")
tabla_señales = st.empty()

# Guardar registro de la última señal enviada por moneda para no saturar con el mismo mensaje
ultimas_alertas_enviadas = {}

# =====================================================================
# BUCLE DE ESCANEO MULTIMONEDA (OPTIMIZADO)
# =====================================================================
while True:
    try:
        # 1. Traer la información de todos los tickers
        tickers = exchange.fetch_tickers()
        
        # Lista temporal para armar las señales de este ciclo rápidamente
        nuevas_detecciones = []
        
        # 2. Filtrar y analizar rápido
        for symbol, info in tickers.items():
            # Descartar de golpe si no es un contrato perpetuo en USDT
            if not symbol.endswith(':USDT'):
                continue
                
            variacion = info.get('percentage', 0)
            volumen = info.get('quoteVolume', 0)
            precio_actual = info.get('last', 0)
            
            # Descartar si no cumple con el filtro de volumen
            if volumen < VOLUMEN_MINIMO or precio_actual == 0:
                continue

            # 3. Evaluar el umbral (1% o el que configures)
            direccion = None
            if variacion >= UMBRAL:
                direccion = "🚀 LONG (Subida Fuerte)"
            elif variacion <= -UMBRAL:
                direccion = "🩸 SHORT (Bajada Fuerte)"

            if direccion:
                hora_actual = time.strftime("%H:%M:%S")
                clave_alerta = f"{symbol}_{direccion}"
                tiempo_actual = time.time()
                
                # Controlar para no repetir la misma alerta en 15 minutos
                if clave_alerta not in ultimas_alertas_enviadas or (tiempo_actual - ultimas_alertas_enviadas[clave_alerta]) > 900:
                    ultimas_alertas_enviadas[clave_alerta] = tiempo_actual
                    
                    registro = {
                        "Hora": hora_actual,
                        "Par": symbol.split(':')[0],
                        "Dirección": direccion,
                        "Precio": f"{precio_actual}",
                        "Cambio 24h": f"{variacion:.2f}%"
                    }
                    st.session_state.historial_señales.insert(0, registro)
                    
                    # Despachar mensaje a Telegram
                    msg = f"⚠️ ¡SEÑAL DETECTADA!\n\nPar: {symbol.split(':')[0]}\nDirección: {direccion}\nPrecio: {precio_actual} USDT\nCambio: {variacion:.2f}%"
                    enviar_alerta_telegram(msg)

        # 4. Renderizar un solo cambio en la interfaz web (Evita congelamientos)
        if st.session_state.historial_señales:
            df = pd.DataFrame(st.session_state.historial_señales)
            tabla_señales.dataframe(df.head(50), use_container_width=True)
        else:
            tabla_señales.info(f"Vigilando mercados activos con Vol > {VOLUMEN_MINIMO:,} USDT. Esperando quiebre del {UMBRAL}%...")
            
        # Cambiar el mensaje de estado a éxito de forma limpia
        metrica_estado.success("🟢 Scanner Activo. Vigilando el mercado en tiempo real...")

    except Exception as e:
        metrica_estado.error(f"❌ Error de red o API: {str(e)[:50]}")
        print(f"Error detallado: {e}")

    # Pausa de 10 segundos antes de la siguiente vuelta
    time.sleep(10)
