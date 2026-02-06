import socket
import threading
import time
import os
import csv
import logging
import atexit
from datetime import datetime
from decouple import config
import serial

# Scapy imports
from scapy.all import sniff, Dot11, RadioTap
from led_manager import LEDManager, LEDState
from clock_manager import getFormattedTimestamp

# =========================== LOG CONFIG ==========================
script_dir = os.path.dirname(os.path.abspath(__file__))
CSV_DIR_NAME = 'macs_csv'
if not os.path.exists(CSV_DIR_NAME):
    os.makedirs(CSV_DIR_NAME)
session_mac_log_path = os.path.join(
    script_dir,
    CSV_DIR_NAME,
    f'macs_{getFormattedTimestamp("%Y-%m-%d_%H-%M-%S")}.csv'
)

with open(session_mac_log_path, "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["mac", "rssi", "snr", "timestamp"])

# =========================== GLOBALS ==========================
led = None
client_conn = None
server_socket = None

usb_serial = None
usb_connected = False

_last_mac_sent_ts = 0.0
_SEND_IDLE_SECONDS = 3.0
_error_latched = False
_yellow_latched = False

# =========================== CONFIG ==========================
TCP_PORT = config('TCP_PORT', default=5000, cast=int)

ENABLE_USB_SERIAL = config('ENABLE_USB_SERIAL', default=1, cast=bool)
USB_SERIAL_DEV = config('USB_SERIAL_DEV', default='/dev/ttyGS0')
USB_SERIAL_BAUD = config('USB_SERIAL_BAUD', default=115200, cast=int)

iface_wrl = config('WIFI_INTERFACE_NAME', default="wlan0", cast=str)
iface_mon = config('MONITOR_INTERFACE_NAME', default="mon0", cast=str)

log_level = config('LOG_LEVEL', default='INFO')

# =========================== LOGGING ==========================
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.ERROR),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_info(msg, print_to_console=False):
    if print_to_console:
        print(msg)
    logging.info(msg)

def log_error(msg, print_to_console=False):
    if print_to_console:
        print(msg)
    logging.error(msg)

# ==================== MONITOR MODE ====================
def check_status_mon():
    cmd = f"ifconfig | grep {iface_mon}"
    return iface_mon in os.popen(cmd).read()

def setup_monitor_mode():
    try:
        phy = os.popen(
            f"iw dev {iface_wrl} info | grep wiphy | awk '{{print \"phy\"$2}}'"
        ).read().strip() or "phy0"

        os.popen(f"iw phy {phy} interface add {iface_mon} type monitor")
        time.sleep(1)
        os.popen(f"ifconfig {iface_mon} up")
        time.sleep(2)

        log_info(f"Modo monitor ativo em {iface_mon}", True)
        return True
    except Exception as e:
        log_error(f"Erro monitor mode: {e}", True)
        return False

# ==================== LED ====================
def _led_set_state(state: LEDState):
    global _yellow_latched, _error_latched
    if not led:
        return

    if _error_latched and state not in (LEDState.ERROR, LEDState.SENDING_MACS):
        return

    if state == LEDState.ERROR:
        _error_latched = True
        _yellow_latched = False
    elif state == LEDState.SENDING_MACS:
        _error_latched = False
        _yellow_latched = False
    elif state == LEDState.IDLE_AFTER_SENDING:
        if not _error_latched:
            _yellow_latched = True

    led.set_state(state)

# ==================== TCP SERVER ====================
def start_tcp_server():
    global server_socket, client_conn

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", TCP_PORT))
    server_socket.listen(1)

    while True:
        conn, addr = server_socket.accept()
        client_conn = conn
        log_info(f"TCP conectado: {addr}", True)
        _led_set_state(LEDState.PAIRED)

        try:
            while conn.recv(1024):
                pass
        except:
            pass
        finally:
            client_conn = None
            conn.close()
            log_info("TCP desconectado", True)

# ==================== USB SERIAL ====================
def start_usb_serial():
    global usb_serial, usb_connected

    while True:
        if not ENABLE_USB_SERIAL:
            time.sleep(2)
            continue

        try:
            usb_serial = serial.Serial(
                USB_SERIAL_DEV,
                USB_SERIAL_BAUD,
                timeout=1
            )
            usb_connected = True
            log_info("USB Serial conectado", True)
            _led_set_state(LEDState.PAIRED)

            while usb_serial.is_open:
                time.sleep(1)

        except:
            usb_connected = False
            usb_serial = None
            time.sleep(2)

# ==================== ENVIO UNIFICADO ====================
def send_payload(msg: str):
    global client_conn, usb_serial, _last_mac_sent_ts

    sent = False

    if client_conn:
        try:
            client_conn.sendall(msg.encode())
            sent = True
        except:
            client_conn = None

    if usb_serial and usb_serial.is_open:
        try:
            usb_serial.write(msg.encode())
            sent = True
        except:
            pass

    if sent:
        _led_set_state(LEDState.SENDING_MACS)
        _last_mac_sent_ts = time.time()

# ==================== PACKET HANDLER ====================
def PacketHandler(pkt):
    if pkt.haslayer(Dot11) and pkt.type == 0 and pkt.subtype == 0x04:
        mac = pkt.addr2
        rssi = -100
        noise = -95

        if pkt.haslayer(RadioTap):
            rt = pkt[RadioTap]
            rssi = getattr(rt, 'dbm_antsignal', rssi)
            noise = getattr(rt, 'dbm_antnoise', noise)

        if rssi >= 0:
            rssi = -100

        snr = int(rssi - noise)
        timestamp = getFormattedTimestamp("%Y-%m-%d %H:%M:%S")

        with open(session_mac_log_path, "a", newline='') as f:
            csv.writer(f).writerow([mac, rssi, snr, timestamp])

        msg = f"{mac},{rssi},{snr},{timestamp}#"
        send_payload(msg)

# ==================== MAIN ====================
def main():
    global led

    if os.geteuid() != 0:
        print("Run as root")
        return

    led = LEDManager()
    led.start()
    atexit.register(led.stop)

    if not check_status_mon():
        setup_monitor_mode()

    threading.Thread(target=start_tcp_server, daemon=True).start()
    threading.Thread(target=start_usb_serial, daemon=True).start()

    def activity_watcher():
        while True:
            if client_conn or usb_connected:
                if time.time() - _last_mac_sent_ts > _SEND_IDLE_SECONDS:
                    _led_set_state(LEDState.IDLE_AFTER_SENDING)
            time.sleep(0.25)

    threading.Thread(target=activity_watcher, daemon=True).start()

    sniff(iface=iface_mon, prn=PacketHandler, store=0)

if __name__ == "__main__":
    main()
