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
# BUCLE DE ESCANEO MULTIMONEDA
# =====================================================================
while True:
    try:
        metrica_estado.info("🔄 Escaneando todos los pares de futuros en Binance...")
        
        # 1. Traer la información de TODOS los tickers del mercado en un solo paso
        tickers = exchange.fetch_tickers()
        
        # 2. Filtrar y analizar par por par
        for symbol, info in tickers.items():
            # Filtrar solo contratos perpetuos lineales que liquiden en USDT (ej: BTC/USDT:USDT)
            if not symbol.endswith(':USDT'):
                continue
                
            # Obtener datos de cambio porcentual y volumen
            variacion = info.get('percentage', 0)  # Variación en las últimas 24h o vela actual según exchange
            volumen = info.get('quoteVolume', 0)   # Volumen comercializado en USDT
            precio_actual = info.get('last', 0)
            
            # Filtrar por volumen mínimo configurado para evitar monedas basura
            if volumen < VOLUMEN_MINIMO:
                continue

            # 3. Evaluar si supera el umbral configurado
            direccion = None
            if variacion >= UMBRAL:
                direccion = "🚀 LONG (Subida Fuerte)"
            elif variacion <= -UMBRAL:
                direccion = "🩸 SHORT (Bajada Fuerte)"

            if direccion:
                hora_actual = time.strftime("%H:%M:%S")
                # Crear clave única combinando el par y la dirección
                clave_alerta = f"{symbol}_{direccion}"
                
                # Evitar mandar alertas repetidas de la misma moneda si ocurrieron hace menos de 15 minutos
                tiempo_actual = time.time()
                if clave_alerta not in ultimas_alertas_enviadas or (tiempo_actual - ultimas_alertas_enviadas[clave_alerta]) > 900:
                    
                    nueva_señal = {
                        "Hora": hora_actual,
                        "Par": symbol.split(':')[0], # Limpia el nombre a 'BTC/USDT'
                        "Dirección": direccion,
                        "Precio": f"{precio_actual}",
                        "Cambio 24h": f"{variacion:.2f}%"
                    }
                    
                    # Insertar al inicio de nuestra tabla web
                    st.session_state.historial_señales.insert(0, nueva_señal)
                    ultimas_alertas_enviadas[clave_alerta] = tiempo_actual
                    
                    # Despachar mensaje a Telegram
                    msg = f"⚠️ ¡MOVIMIENTO DETECTADO EN EL MERCADO!\n\nPar: {symbol.split(':')[0]}\nDirección: {direccion}\nPrecio: {precio_actual} USDT\nCambio: {variacion:.2f}%"
                    enviar_alerta_telegram(msg)

        # 4. Refrescar tabla en la interfaz web
        if st.session_state.historial_señales:
            df = pd.DataFrame(st.session_state.historial_señales)
            # Limitar la tabla visual a las últimas 50 señales para no saturar el navegador
            tabla_señales.dataframe(df.head(50), use_container_width=True)
        else:
            tabla_señales.info(f"Escaneando activamente mercados con Vol > {VOLUMEN_MINIMO:,} USDT. Esperando que alguna cripto rompa el {UMBRAL}%...")
            
        metrica_estado.success("🟢 Scanner Activo. Vigilando más de 100 criptomonedas simultáneamente...")

    except Exception as e:
        metrica_estado.error(f"❌ Error de red o API: {str(e)[:50]}")
        print(f"Error detallado: {e}")

    # Pausa de 10 segundos antes de volver a escanear todo el mercado
    time.sleep(10)
