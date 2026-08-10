import sys
import os
import threading
import time
import serial
import serial.tools.list_ports

from PySide6.QtCore import QThread, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTextEdit, QLineEdit, QLabel, QGridLayout, QGroupBox
)
from PySide6.QtGui import QFont

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# --- 1. FORZA LA CARTELLA DI LAVORO (Fix avvio da Desktop/Collegamento) ---
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# --- 2. GESTIONE PERCORSI PER PYINSTALLER ---
def resource_path(relative_path):
    """Ottiene il percorso assoluto delle risorse, compatibile con lo script e PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 3. FLASK & SOCKETIO SETUP ---
template_folder = resource_path('templates')
flask_app = Flask(__name__, template_folder=template_folder)
flask_app.config['SECRET_KEY'] = 'secret_key'

# Configurazione SocketIO con async_mode='threading'
socketio = SocketIO(flask_app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

# --- 4. MANAGER GLOBALE SERIALE E STATO ---
class SerialManager(QObject):
    data_received = Signal(str)
    status_changed = Signal(bool, str)

    def __init__(self, config_file="commands.txt"):
        super().__init__()
        self.ser = None
        self.config_file = config_file
        self.running = False
        self.reader_thread = None

    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def connect(self, port, baud):
        if not port:
            self.data_received.emit("No port selected.\n")
            return False, "No port selected."

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=1)
            self.running = True
            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()

            msg = f"--- Connected on {port} at {baud} baud ---\n"
            self.status_changed.emit(True, msg)
            socketio.emit('connection_status', {'connected': True, 'message': msg})
            return True, msg
        except Exception as e:
            msg = f"Impossible to open COM port {port}: {str(e)}\n"
            self.data_received.emit(msg)
            socketio.emit('connection_status', {'connected': False, 'message': msg})
            return False, msg

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        msg = "\n--- Disconnected ---\n"
        self.status_changed.emit(False, msg)
        socketio.emit('connection_status', {'connected': False, 'message': msg})

    def send(self, text):
        if text and self.is_connected():
            data_to_send = text + "\n"
            self.ser.write(data_to_send.encode('utf-8'))
            msg = f"> {text}\n"
            self.data_received.emit(msg)
            socketio.emit('serial_data', {'data': msg})

    def _read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='replace')
                    if line:
                        self.data_received.emit(line)
                        socketio.emit('serial_data', {'data': line})
                else:
                    time.sleep(0.02)
            except Exception as e:
                err_msg = f"\n[Read error: {str(e)}]\n"
                self.data_received.emit(err_msg)
                socketio.emit('serial_data', {'data': err_msg})
                break

    def load_preset_commands(self):
        if not os.path.exists(self.config_file):
            default_cmds = [f"Label {i+1}|COMMAND_{i+1}" for i in range(10)]
            with open(self.config_file, "w") as f:
                f.write("\n".join(default_cmds))

        parsed_items = []
        try:
            with open(self.config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if "|" in line:
                        label, cmd = line.split("|", 1)
                    else:
                        label, cmd = line, line
                    parsed_items.append((label.strip(), cmd.strip()))
        except Exception as e:
            print(f"Error reading {self.config_file}: {e}")

        macros = []
        for i in range(10):
            if i < len(parsed_items):
                macros.append({"label": parsed_items[i][0], "command": parsed_items[i][1]})
            else:
                macros.append({"label": f"Empty {i+1}", "command": ""})
        return macros


# Istanza condivisa
serial_mgr = SerialManager()


# --- 5. ENDPOINT WEBSOCKET FLASK-SOCKETIO ---
@flask_app.route('/')
def index():
    return render_template('index.html')

@socketio.on('get_initial_data')
def handle_initial_data():
    emit('initial_data', {
        'ports': serial_mgr.get_ports(),
        'macros': serial_mgr.load_preset_commands(),
        'connected': serial_mgr.is_connected()
    })

@socketio.on('refresh_ports')
def handle_refresh_ports():
    emit('ports_list', {'ports': serial_mgr.get_ports()})

@socketio.on('connect_serial')
def handle_connect(data):
    port = data.get('port')
    baud = int(data.get('baud', 115200))
    serial_mgr.connect(port, baud)

@socketio.on('disconnect_serial')
def handle_disconnect():
    serial_mgr.disconnect()

@socketio.on('send_command')
def handle_send_command(data):
    text = data.get('command', '')
    serial_mgr.send(text)


# --- 6. INTERFACCIA PYSIDE6 (QT) ---
class SerialTerminalQt(QMainWindow):
    def __init__(self):
        super().__init__()
        app_font = QFont("Consolas", 14)
        self.setFont(app_font)
        self.setWindowTitle("MatrixFXClientQT_20062026 by IU7QMN (Dual Qt/Web)")
        self.resize(850, 500)

        self.preset_buttons = []
        self.init_ui()
        self.refresh_ports()
        self.load_preset_commands()

        serial_mgr.data_received.connect(self.append_text)
        serial_mgr.status_changed.connect(self.on_status_changed)

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Barra superiore
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Port:"))
        self.combo_ports = QComboBox()
        top_layout.addWidget(self.combo_ports)

        btn_refresh = QPushButton("Update")
        btn_refresh.clicked.connect(self.refresh_ports)
        top_layout.addWidget(btn_refresh)

        top_layout.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["1200", "2400", "4800","9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("115200")
        top_layout.addWidget(self.combo_baud)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.btn_connect)

        layout.addLayout(top_layout)

        # Sezione Macro
        group_preset = QGroupBox("Macros (Label | Command)")
        grid_preset = QGridLayout()

        for i in range(10):
            btn = QPushButton(f"Macros {i+1}")
            btn.setEnabled(False)
            self.preset_buttons.append(btn)
            row = i // 5
            col = i % 5
            grid_preset.addWidget(btn, row, col)

        group_preset.setLayout(grid_preset)
        layout.addWidget(group_preset)

        # Input Barra
        bottom_layout = QHBoxLayout()
        self.line_input = QLineEdit()
        self.line_input.setPlaceholderText("Write command and send...")
        self.line_input.returnPressed.connect(self.send_custom_data)
        self.line_input.setEnabled(False)
        bottom_layout.addWidget(self.line_input)

        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self.send_custom_data)
        self.btn_send.setEnabled(False)
        bottom_layout.addWidget(self.btn_send)

        layout.addLayout(bottom_layout)

        # Area Terminale Monitor
        self.text_terminal = QTextEdit()
        self.text_terminal.setReadOnly(True)
        self.text_terminal.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace; font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.text_terminal)

        self.setCentralWidget(main_widget)

    def load_preset_commands(self):
        macros = serial_mgr.load_preset_commands()
        for i in range(10):
            btn = self.preset_buttons[i]
            label = macros[i]["label"]
            cmd = macros[i]["command"]
            btn.setText(label)
            btn.setToolTip(f"Command: {cmd}" if cmd else "")

            try:
                btn.clicked.disconnect()
            except RuntimeError:
                pass

            if cmd:
                btn.clicked.connect(lambda checked=False, c=cmd: serial_mgr.send(c))

    def refresh_ports(self):
        self.combo_ports.clear()
        self.combo_ports.addItems(serial_mgr.get_ports())

    def toggle_connection(self):
        if serial_mgr.is_connected():
            serial_mgr.disconnect()
        else:
            port = self.combo_ports.currentText()
            baud = int(self.combo_baud.currentText())
            serial_mgr.connect(port, baud)

    @Slot(bool, str)
    def on_status_changed(self, is_connected, message):
        self.btn_connect.setText("Disconnect" if is_connected else "Connect")
        self.combo_ports.setEnabled(not is_connected)
        self.combo_baud.setEnabled(not is_connected)
        self.line_input.setEnabled(is_connected)
        self.btn_send.setEnabled(is_connected)

        for btn in self.preset_buttons:
            if is_connected and not btn.text().startswith("Empty"):
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)

        self.append_text(message)

    def send_custom_data(self):
        text = self.line_input.text()
        if text:
            serial_mgr.send(text)
            self.line_input.clear()

    @Slot(str)
    def append_text(self, text):
        self.text_terminal.insertPlainText(text)
        self.text_terminal.verticalScrollBar().setValue(
            self.text_terminal.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        serial_mgr.disconnect()
        event.accept()


# --- 7. RUNNER FLASK CON CATCH ECCEZIONI ---
def run_flask():
    try:
        socketio.run(flask_app, host='0.0.0.0', port=47373, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error starting Web Server: {e}")


if __name__ == "__main__":
    # Avvio del Thread Server Web
    web_thread = threading.Thread(target=run_flask, daemon=True)
    web_thread.start()

    # Avvio applicazione Qt
    app = QApplication(sys.argv)
    window = SerialTerminalQt()
    window.show()
    sys.exit(app.exec())