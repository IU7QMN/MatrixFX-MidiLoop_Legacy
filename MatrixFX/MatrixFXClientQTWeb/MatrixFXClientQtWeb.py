import sys
import os
import threading
import time
import serial
import serial.tools.list_ports

from PySide6.QtCore import QThread, Signal, Slot, QObject, QPropertyAnimation, QEasingCurve, Property, QRectF, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTextEdit, QLineEdit, QLabel, QGridLayout, QGroupBox, QCheckBox
)
from PySide6.QtGui import QFont, QPainter, QColor

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# --- 1. FORZA LA CARTELLA DI LAVORO ---
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# --- 2. GESTIONE PERCORSI PER PYINSTALLER ---
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 3. FLASK & SOCKETIO SETUP ---
template_folder = resource_path('templates')
flask_app = Flask(__name__, template_folder=template_folder)
flask_app.config['SECRET_KEY'] = 'secret_key'

socketio = SocketIO(flask_app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

# --- WIDGET PERSONALIZZATO: TOGGLE SWITCH STILE WEB ---
class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._thumb_position = 3.0

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.stateChanged.connect(self._start_animation)

    def _start_animation(self, state):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(35.0 if state == Qt.Checked or state == 2 else 3.0)
        self._anim.start()

    def get_thumb_position(self):
        return self._thumb_position

    def set_thumb_position(self, pos):
        self._thumb_position = pos
        self.update()

    thumb_position = Property(float, get_thumb_position, set_thumb_position)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self.isChecked())
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        bg_color = QColor("#28a745") if self.isChecked() else QColor("#007acc")
        p.setBrush(bg_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)

        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(self._thumb_position, 3.0, 22.0, 22.0))


# --- 4. MANAGER GLOBALE SERIALE E STATO ---
class SerialManager(QObject):
    data_received = Signal(str)
    status_changed = Signal(bool, str)
    mode_remote_changed = Signal(str)
    config_remote_changed = Signal(str, str)

    def __init__(self, config_file="commands.txt"):
        super().__init__()
        self.ser = None
        self.config_file = config_file
        self.running = False
        self.reader_thread = None
        self.current_mode = "FREQ"  # MODALITÀ FREQ PREDEFINITA
        self.current_port = ""
        self.current_baud = "115200"

    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def connect(self, port, baud):
        if not port:
            self.data_received.emit("No port selected.\n")
            return False, "No port selected."

        try:
            self.ser = serial.Serial(port, baudrate=int(baud), timeout=1)
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

    def load_config_and_presets(self):
        config = {
            "web_port": 47373,
            "serial_port": "",
            "baud_rate": 115200,
            "macros": []
        }

        if not os.path.exists(self.config_file):
            default_content = (
                "WEB_PORT=47373\n"
                "SERIAL_PORT=\n"
                "BAUD_RATE=115200\n"
            ) + "\n".join([f"Label {i+1}|COMMAND_{i+1}" for i in range(15)])
            
            with open(self.config_file, "w") as f:
                f.write(default_content)

        parsed_items = []
        try:
            with open(self.config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    if "=" in line and "|" not in line:
                        key, val = line.split("=", 1)
                        key = key.strip().upper()
                        val = val.strip()
                        if key == "WEB_PORT":
                            config["web_port"] = int(val) if val.isdigit() else 47373
                        elif key == "SERIAL_PORT":
                            config["serial_port"] = val
                        elif key == "BAUD_RATE":
                            config["baud_rate"] = int(val) if val.isdigit() else 115200
                        continue

                    if "|" in line:
                        label, cmd = line.split("|", 1)
                    else:
                        label, cmd = line, line
                    parsed_items.append((label.strip(), cmd.strip()))
        except Exception as e:
            print(f"Error reading {self.config_file}: {e}")

        macros = []
        for i in range(15):
            if i < len(parsed_items):
                macros.append({"label": parsed_items[i][0], "command": parsed_items[i][1]})
            else:
                macros.append({"label": f"Empty {i+1}", "command": ""})

        config["macros"] = macros
        self.current_port = config.get("serial_port", "")
        self.current_baud = str(config.get("baud_rate", 115200))
        return config

    def update_serial_config(self, new_port, new_baud):
        self.current_port = str(new_port)
        self.current_baud = str(new_baud)

        if not os.path.exists(self.config_file):
            self.load_config_and_presets()

        lines = []
        try:
            with open(self.config_file, "r") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {self.config_file} for update: {e}")
            return

        updated_port = False
        updated_baud = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if "=" in stripped and "|" not in stripped:
                key, _ = stripped.split("=", 1)
                key = key.strip().upper()
                if key == "SERIAL_PORT":
                    new_lines.append(f"SERIAL_PORT={new_port}\n")
                    updated_port = True
                    continue
                elif key == "BAUD_RATE":
                    new_lines.append(f"BAUD_RATE={new_baud}\n")
                    updated_baud = True
                    continue
            new_lines.append(line)

        prefix = []
        if not updated_port:
            prefix.append(f"SERIAL_PORT={new_port}\n")
        if not updated_baud:
            prefix.append(f"BAUD_RATE={new_baud}\n")

        final_lines = prefix + new_lines

        try:
            with open(self.config_file, "w") as f:
                f.writelines(final_lines)
        except Exception as e:
            print(f"Error updating {self.config_file}: {e}")


serial_mgr = SerialManager()


# --- 5. ENDPOINT WEBSOCKET FLASK-SOCKETIO ---
@flask_app.route('/')
def index():
    return render_template('index.html')

@socketio.on('get_initial_data')
def handle_initial_data():
    cfg = serial_mgr.load_config_and_presets()
    emit('initial_data', {
        'ports': serial_mgr.get_ports(),
        'macros': cfg["macros"],
        'connected': serial_mgr.is_connected(),
        'mode': serial_mgr.current_mode,
        'selected_port': serial_mgr.current_port,
        'selected_baud': serial_mgr.current_baud
    })

@socketio.on('refresh_ports')
def handle_refresh_ports():
    emit('ports_list', {'ports': serial_mgr.get_ports()})

@socketio.on('change_serial_settings')
def handle_change_serial_settings(data):
    port = data.get('port', serial_mgr.current_port)
    baud = str(data.get('baud', serial_mgr.current_baud))
    
    serial_mgr.current_port = port
    serial_mgr.current_baud = baud
    serial_mgr.update_serial_config(port, baud)

    serial_mgr.config_remote_changed.emit(port, baud)
    emit('serial_settings_changed', {'port': port, 'baud': baud}, broadcast=True)

@socketio.on('connect_serial')
def handle_connect(data):
    port = data.get('port')
    baud = int(data.get('baud', 115200))
    serial_mgr.connect(port, baud)

@socketio.on('disconnect_serial')
def handle_disconnect():
    serial_mgr.disconnect()

@socketio.on('change_mode')
def handle_change_mode(data):
    new_mode = data.get('mode', 'FREQ')
    serial_mgr.current_mode = new_mode
    serial_mgr.mode_remote_changed.emit(new_mode)
    emit('mode_changed', {'mode': new_mode}, broadcast=True)

@socketio.on('send_command')
def handle_send_command(data):
    text = data.get('command', '')
    mode = data.get('mode', serial_mgr.current_mode)
    if mode == 'FREQ' and text:
        text = f"B{text}*"
    serial_mgr.send(text)


# --- 6. INTERFACCIA PYSIDE6 (QT) ---
class SerialTerminalQt(QMainWindow):
    def __init__(self, initial_config=None):
        super().__init__()
        self.initial_config = initial_config or {}
        app_font = QFont("Consolas", 14)
        self.setFont(app_font)
        self.setWindowTitle("MatrixFXClientQT_18092026 by IU7QMN (Dual Qt/Web)")
        self.resize(850, 600)

        self.preset_buttons = []
        self.init_ui()
        self.refresh_ports()
        self.load_preset_commands()
        self.apply_initial_config()

        serial_mgr.data_received.connect(self.append_text)
        serial_mgr.status_changed.connect(self.on_status_changed)
        serial_mgr.mode_remote_changed.connect(self.on_remote_mode_changed)
        serial_mgr.config_remote_changed.connect(self.on_remote_config_changed)

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Barra superiore
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Port:"))
        self.combo_ports = QComboBox()
        self.combo_ports.currentTextChanged.connect(self.on_qt_serial_settings_changed)
        top_layout.addWidget(self.combo_ports)

        btn_refresh = QPushButton("Update")
        btn_refresh.clicked.connect(self.refresh_ports)
        top_layout.addWidget(btn_refresh)

        top_layout.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["1200", "2400", "4800","9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("115200")
        self.combo_baud.currentTextChanged.connect(self.on_qt_serial_settings_changed)
        top_layout.addWidget(self.combo_baud)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.btn_connect)

        layout.addLayout(top_layout)

        # Sezione Macro
        group_preset = QGroupBox("Macros (Label | Command)")
        grid_preset = QGridLayout()

        for i in range(15):
            btn = QPushButton(f"Macros {i+1}")
            btn.setEnabled(False)
            self.preset_buttons.append(btn)
            row = i // 5
            col = i % 5
            grid_preset.addWidget(btn, row, col)

        group_preset.setLayout(grid_preset)
        layout.addWidget(group_preset)

        # Selettore Modalità (Inizializzato su FREQ = Checked)
        mode_layout = QHBoxLayout()
        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet("font-weight: bold; color: #007acc; font-size: 11pt;")
        mode_layout.addWidget(lbl_mode)

        lbl_raw = QLabel("RAW")
        lbl_raw.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 11pt;")
        mode_layout.addWidget(lbl_raw)

        self.toggle_mode = ToggleSwitch()
        self.toggle_mode.setChecked(True)  # FREQ ATTIVA DI DEFAULT IN QT
        self.toggle_mode.toggled.connect(self.on_qt_mode_toggled)
        mode_layout.addWidget(self.toggle_mode)

        lbl_freq = QLabel("FREQ (B<cmd>*)")
        lbl_freq.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 11pt;")
        mode_layout.addWidget(lbl_freq)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Input Barra
        bottom_layout = QHBoxLayout()
        self.line_input = QLineEdit()
        self.line_input.setPlaceholderText("Write command and send...")
        self.line_input.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 10px;
                font-size: 14pt;
                font-weight: bold;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border: 1px solid #007acc;
            }
            QLineEdit:disabled {
                background-color: #181818;
                color: #555555;
            }
        """)
        self.line_input.returnPressed.connect(self.send_custom_data)
        self.line_input.setEnabled(False)
        bottom_layout.addWidget(self.line_input)

        # Pulsante SEND
        self.btn_send = QPushButton("SEND")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: 1px solid #005999;
                border-radius: 4px;
                padding: 10px 40px;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0098ff;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #555555;
                border-color: #222222;
            }
        """)
        self.btn_send.clicked.connect(self.send_custom_data)
        self.btn_send.setEnabled(False)
        bottom_layout.addWidget(self.btn_send)

        layout.addLayout(bottom_layout)

        # Terminale
        self.text_terminal = QTextEdit()
        self.text_terminal.setReadOnly(True)
        self.text_terminal.setStyleSheet("background-color: #121212; color: #00ff00; font-family: monospace; font-size: 14pt; font-weight: bold; border: 1px solid #333333;")
        layout.addWidget(self.text_terminal)

        self.setCentralWidget(main_widget)

    def load_preset_commands(self):
        cfg = serial_mgr.load_config_and_presets()
        macros = cfg["macros"]
        for i in range(15):
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

    def apply_initial_config(self):
        baud = str(self.initial_config.get("baud_rate", 115200))
        idx_baud = self.combo_baud.findText(baud)
        if idx_baud != -1:
            self.combo_baud.setCurrentIndex(idx_baud)

        port = self.initial_config.get("serial_port", "")
        if port:
            idx_port = self.combo_ports.findText(port)
            if idx_port != -1:
                self.combo_ports.setCurrentIndex(idx_port)
            else:
                self.combo_ports.addItem(port)
                self.combo_ports.setCurrentText(port)

    def refresh_ports(self):
        current = self.combo_ports.currentText()
        self.combo_ports.blockSignals(True)
        self.combo_ports.clear()
        self.combo_ports.addItems(serial_mgr.get_ports())
        if current and self.combo_ports.findText(current) != -1:
            self.combo_ports.setCurrentText(current)
        self.combo_ports.blockSignals(False)

    def toggle_connection(self):
        if serial_mgr.is_connected():
            serial_mgr.disconnect()
        else:
            port = self.combo_ports.currentText()
            baud = int(self.combo_baud.currentText())
            serial_mgr.update_serial_config(port, baud)
            serial_mgr.connect(port, baud)

    def on_qt_serial_settings_changed(self):
        port = self.combo_ports.currentText()
        baud = self.combo_baud.currentText()
        if port:
            serial_mgr.update_serial_config(port, baud)
            socketio.emit('serial_settings_changed', {'port': port, 'baud': baud})

    @Slot(str, str)
    def on_remote_config_changed(self, port, baud):
        self.combo_ports.blockSignals(True)
        self.combo_baud.blockSignals(True)

        idx_port = self.combo_ports.findText(port)
        if idx_port != -1:
            self.combo_ports.setCurrentIndex(idx_port)
        elif port:
            self.combo_ports.addItem(port)
            self.combo_ports.setCurrentText(port)

        idx_baud = self.combo_baud.findText(baud)
        if idx_baud != -1:
            self.combo_baud.setCurrentIndex(idx_baud)

        self.combo_ports.blockSignals(False)
        self.combo_baud.blockSignals(False)

    def on_qt_mode_toggled(self, checked):
        mode = "FREQ" if checked else "RAW"
        serial_mgr.current_mode = mode
        socketio.emit('mode_changed', {'mode': mode})

    @Slot(str)
    def on_remote_mode_changed(self, mode):
        self.toggle_mode.blockSignals(True)
        self.toggle_mode.setChecked(mode == "FREQ")
        self.toggle_mode.blockSignals(False)

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
            if self.toggle_mode.isChecked():
                text = f"B{text}*"
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


# --- 7. RUNNER FLASK ---
def run_flask(port):
    try:
        socketio.run(flask_app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error starting Web Server on port {port}: {e}")


if __name__ == "__main__":
    config = serial_mgr.load_config_and_presets()
    web_port = config.get("web_port", 47373)

    web_thread = threading.Thread(target=run_flask, args=(web_port,), daemon=True)
    web_thread.start()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    dark_stylesheet = """
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QGroupBox {
        border: 1px solid #333333;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        color: #007acc;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background-color: #3d3d3d;
        border-color: #007acc;
    }
    QPushButton:disabled {
        background-color: #181818;
        color: #555555;
        border-color: #222222;
    }
    QLineEdit, QComboBox {
        background-color: #252526;
        color: #ffffff;
        border: 1px solid #3d3d3d;
        border-radius: 3px;
        padding: 4px;
    }
    QComboBox::drop-down {
        border: 0px;
    }
    QComboBox QAbstractItemView {
        background-color: #252526;
        color: #ffffff;
        selection-background-color: #007acc;
    }
    """
    app.setStyleSheet(dark_stylesheet)

    window = SerialTerminalQt(initial_config=config)
    window.show()
    sys.exit(app.exec())