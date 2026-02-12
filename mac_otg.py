import threading
import time
import os
import csv
import logging
import atexit
import serial
from bluepy.btle import Scanner, DefaultDelegate
from decouple import config

# Scapy imports
from scapy.all import sniff, Dot11, RadioTap
from led_manager import LEDManager, LEDState
from clock_manager import getFormattedTimestamp

# =========================== CONFIG ==========================
USB_SERIAL_DEV = config('USB_SERIAL_DEV', default='/dev/ttyGS0')
USB_SERIAL_BAUD = config('USB_SERIAL_BAUD', default=115200, cast=int)
iface_wrl = config('WIFI_INTERFACE_NAME', default="wlan0", cast=str)
iface_mon = config('MONITOR_INTERFACE_NAME', default="mon0", cast=str)
log_level = config('LOG_LEVEL', default='INFO')

# =========================== GLOBALS ==========================
led = None
usb_serial = None  # Objeto da conexão serial
usb_connected = False
serial_lock = threading.Lock() # Controlador de envio entre mac e bluetooth

script_dir = os.path.dirname(os.path.abspath(__file__))
CSV_DIR_NAME = 'macs_csv'
if not os.path.exists(CSV_DIR_NAME):
    os.makedirs(CSV_DIR_NAME)
session_mac_log_path = os.path.join(
    script_dir,
    CSV_DIR_NAME,
    f'macs_{getFormattedTimestamp("%Y-%m-%d_%H-%M-%S")}.csv'
)

# Inicializa CSV
with open(session_mac_log_path, "w", newline='') as f:
    csv.writer(f).writerow(["mac", "rssi", "snr", "timestamp"])

# =========================== LOGGING ==========================
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.ERROR),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_info(msg):
    logging.info(msg)

def log_error(msg):
    logging.error(msg)

# ==================== MONITOR MODE ====================
def check_status_mon():
    cmd = f"ifconfig | grep {iface_mon}"
    return iface_mon in os.popen(cmd).read()

def setup_monitor_mode():
    try:
        phy = os.popen(f"iw dev {iface_wrl} info | grep wiphy | awk '{{print \"phy\"$2}}'").read().strip() or "phy0"
        os.popen(f"iw phy {phy} interface add {iface_mon} type monitor")
        time.sleep(1)
        os.popen(f"ifconfig {iface_mon} up")
        time.sleep(2)
        log_info(f"Modo Monitor Ativo: {iface_mon}")
        return True
    except Exception as e:
        log_error(f"Erro Monitor Mode: {e}")
        return False

# ==================== GERENCIADOR SERIAL (THREAD) ====================
def serial_maintainer():
    """
    Mantém a conexão serial viva. Se cair, tenta reconectar.
    """
    global usb_serial, usb_connected, led
    
    log_info("Iniciando gerenciador serial...")

    while True:
        # 1. Verifica se o arquivo de dispositivo existe (Driver carregado)
        if not os.path.exists(USB_SERIAL_DEV):
            usb_connected = False
            time.sleep(1)
            continue

        # 2. Se não estiver conectado, tenta conectar
        if usb_serial is None or not usb_serial.is_open:
            try:
                usb_serial = serial.Serial(
                    USB_SERIAL_DEV, 
                    USB_SERIAL_BAUD, 
                    timeout=1, 
                    write_timeout=0
                )
                usb_connected = True
                log_info(f"Serial conectado em {USB_SERIAL_DEV}")
                led.set_state(LEDState.PAIRED) # Verde Piscando (Conectado, aguardando dados)
            except Exception as e:
                usb_connected = False
                usb_serial = None
                # Se falhar, volta para Azul (Buscando)
                led.set_state(LEDState.READY_TO_CONNECT)
                time.sleep(2)
        else:
            # Já está conectado, apenas dorme para não gastar CPU
            time.sleep(1)

# ==================== SNIFFER (MAIN) ====================
def PacketHandler(pkt):
    global usb_serial, usb_connected, led

    # Ensure packet has WiFi layer (Dot11) and is a Management frame (type 0)
    # subtype 4 is 'Probe Request' (devices looking for wifi)
    if pkt.haslayer(Dot11) and pkt.type == 0 and pkt.subtype == 0x04:
        try:
            # 1. Get MAC Address (Source Address)
            mac = pkt.addr2
            
            # 2. Extract Signal Info safely
            rssi = -100   # Default weak value
            noise = -95   # Default noise floor
            
            if pkt.haslayer(RadioTap):
                rt = pkt[RadioTap]
                
                # Check if the field exists before accessing
                # (Some drivers strip these fields)
                if hasattr(rt, 'dbm_antsignal') and rt.dbm_antsignal is not None:
                    rssi = int(rt.dbm_antsignal)
                
                if hasattr(rt, 'dbm_antnoise') and rt.dbm_antnoise is not None:
                    noise = int(rt.dbm_antnoise)
                else:
                    pass 

           
            # SNR = Signal - Noise
            
            snr = rssi - noise
            
            # Sanity check: If RSSI is still default, the packet might be malformed
            if rssi == -100:
                return 

            timestamp = getFormattedTimestamp("%Y-%m-%d %H:%M:%S")
            
            # 1. Salva no CSV sempre (Backup)
            with open(session_mac_log_path, "a", newline='') as f:
                csv.writer(f).writerow([mac, rssi, snr, timestamp])

            # 2. Envia via Serial (Se conectado)
            with serial_lock:
                if usb_connected and usb_serial and usb_serial.is_open:
                    msg = f"{mac},{rssi},{snr},{timestamp}#"
                    try:
                        usb_serial.write((msg + "\n").encode())
                        led.set_state(LEDState.SENDING_MACS)
                    except Exception as e:
                        log_error(f"Erro de envio: {e}")
                        usb_serial.close()
                        usb_connected = False

        except Exception as e:
            log_error(f"Erro no handler: {e}")

# ==================== MONITOR DE ATIVIDADE (LED) ====================
def activity_watcher():
    """
    Se parar de enviar dados por 3 segundos, volta o LED para 'Conectado' (Verde Piscando)
    ao invés de ficar travado no 'Enviando' (Verde Sólido).
    """
    global led
    while True:
        time.sleep(0.5)
        # Se o estado atual é "Enviando", mas não enviamos nada recentemente...
        # (Neste código simplificado, o LEDManager não tem timer automático de reset,
        # então forçamos manualmente se necessário, ou confiamos no fluxo).
        
        # Uma abordagem simples: O PacketHandler seta SENDING_MACS.
        # Se passar um tempo sem packets, voltamos para PAIRED.
        # Como o LEDManager é simples, vamos deixar o PacketHandler controlar o pulso.
        pass

def bluetooth_scanner():
    global usb_serial, usb_connected, led
    
    log_info("Iniciando Scanner BLE (Modo Passivo)...")
    
    # O Scanner do bluepy precisa de permissão root (sudo)
    scanner = Scanner()
    
    while True:
        try:
            # Escaneia por 4 segundos. 
            # Isso bloqueia a thread por 4s, coletando todos os "beacons" ao redor.
            devices = scanner.scan(4.0)
            
            timestamp = getFormattedTimestamp("%Y-%m-%d %H:%M:%S")
            
            for dev in devices:
                mac = dev.addr
                rssi = dev.rssi
                
                
                # --- ZONA CRÍTICA: ENVIO SERIAL ---
                with serial_lock: 
                    # 1. Salva no CSV
                    with open(session_mac_log_path, "a", newline='') as f:
                        # Adicionamos o prefixo BLE para diferenciar do WiFi
                        csv.writer(f).writerow([f"BLE-{mac}", rssi, timestamp])

                    # 2. Envia para o Android via USB
                    if usb_connected and usb_serial and usb_serial.is_open:
                        # Formato: BLE:mac,rssi,snr,timestamp#
                        msg = f"BLE:{mac},{rssi},{timestamp}#"
                        try:
                            usb_serial.write((msg + "\n").encode())
                            led.set_state(LEDState.SENDING_MACS)
                        except Exception as e:
                            log_error(f"Erro envio BLE: {e}")
                # ----------------------------------
                
        except Exception as e:
            # Às vezes o hardware de bluetooth reseta ou falha.
            # Esperamos um pouco e tentamos de novo.
            log_error(f"Erro no scan BLE: {e}")
            time.sleep(2)

# ==================== MAIN ====================
def main():
    global led

    if os.geteuid() != 0:
        print("Precisa de root!")
        return

    led = LEDManager()
    led.start()
    atexit.register(led.stop)
    
    # Estado inicial: Azul Sólido (Script rodando, sem serial ainda)
    led.set_state(LEDState.READY_TO_CONNECT)

    if not check_status_mon():
        setup_monitor_mode()

    # Inicia thread que cuida da conexão serial
    threading.Thread(target=serial_maintainer, daemon=True).start()

    # Inicia thread do Bluetooth 
    threading.Thread(target=bluetooth_scanner, daemon=True).start()

    log_info("Iniciando Sniffer (Tempo Real)...")
    sniff(iface=iface_mon, prn=PacketHandler, store=0)

if __name__ == "__main__":
    main()