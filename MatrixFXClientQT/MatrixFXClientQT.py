import sys
import os
import serial
import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTextEdit, QLineEdit, QLabel, QGridLayout, QGroupBox
)
from PySide6.QtGui import QFont

# --- Thread per la lettura seriale asincrona ---
class SerialReaderThread(QThread):
    data_received = Signal(str)

    def __init__(self, serial_port):
        super().__init__()
        self.ser = serial_port
        self.running = True

    def run(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='replace')
                    if line:
                        self.data_received.emit(line)
            except Exception as e:
                self.data_received.emit(f"\n[Read error: {str(e)}]\n")
                break

    def stop(self):
        self.running = False
        self.wait()


# --- Interfaccia Grafica Principale ---
class SerialTerminal(QMainWindow):
    def __init__(self, config_file="commands.txt"):
        super().__init__()
        app_font = QFont("Consolas", 14)  # Nome font e dimensione in punti (pt)
        self.setFont(app_font)
        self.setWindowTitle("MatrixFXClientQT by IU7QMN")
        self.resize(800, 600)

        self.ser = None
        self.reader_thread = None
        self.config_file = config_file
        self.preset_buttons = []

        self.init_ui()
        self.refresh_ports()
        self.load_preset_commands()

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # --- 1. Barra superiore: Selezione porta e Baudrate ---
        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel("Port:"))
        self.combo_ports = QComboBox()
        top_layout.addWidget(self.combo_ports)

        btn_refresh = QPushButton("Update")
        btn_refresh.clicked.connect(self.refresh_ports)
        top_layout.addWidget(btn_refresh)

        top_layout.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.combo_baud.setCurrentText("115200")
        top_layout.addWidget(self.combo_baud)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.btn_connect)

        layout.addLayout(top_layout)

        # --- 2. Sezione Comandi Macro (10 Pulsanti) ---
        group_preset = QGroupBox("Macros (Label | Command)")
        grid_preset = QGridLayout()

        for i in range(10):
            btn = QPushButton(f"Macros {i+1}")
            btn.setEnabled(False)
            self.preset_buttons.append(btn)
            
            # Disposizione su 2 righe da 5 pulsanti
            row = i // 5
            col = i % 5
            grid_preset.addWidget(btn, row, col)

        group_preset.setLayout(grid_preset)
        layout.addWidget(group_preset)

        # --- 3. Area Monitor (Output Seriale) ---
        self.text_terminal = QTextEdit()
        self.text_terminal.setReadOnly(True)
        self.text_terminal.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace; font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.text_terminal)

        # --- 4. Barra inferiore: Invio dati manuale ---
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

        self.setCentralWidget(main_widget)

    def load_preset_commands(self):
        """Legge il file di testo nel formato Label|Comando e aggiorna i pulsanti."""
        if not os.path.exists(self.config_file):
            # Crea un file di esempio predefinito se non esiste
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
                    
                    # Parsing della riga nel formato "Label|Comando"
                    if "|" in line:
                        label, cmd = line.split("|", 1)
                    else:
                        label, cmd = line, line
                    
                    parsed_items.append((label.strip(), cmd.strip()))
        except Exception as e:
            self.text_terminal.append(f"Read Error {self.config_file}: {str(e)}\n")

        # Assegna etichette e comandi ai 10 pulsanti
        for i in range(10):
            btn = self.preset_buttons[i]
            if i < len(parsed_items):
                label_text, cmd_text = parsed_items[i]
                btn.setText(label_text)
                btn.setToolTip(f"Command: {cmd_text}")  # Mostra il comando al passaggio del mouse
                
                # Scollega eventuali slot precedenti e assegna il nuovo comando
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
                
                btn.clicked.connect(lambda checked=False, cmd=cmd_text: self.write_to_serial(cmd))
            else:
                btn.setText(f"Empty {i+1}")
                btn.setToolTip("")

    def refresh_ports(self):
        """Scansiona le porte seriali disponibili."""
        self.combo_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.combo_ports.addItem(port.device)

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def set_controls_enabled(self, is_connected):
        """Abilita o disabilita i controlli in base allo stato della connessione."""
        self.btn_connect.setText("Disconnect" if is_connected else "Connect")
        self.combo_ports.setEnabled(not is_connected)
        self.combo_baud.setEnabled(not is_connected)
        self.line_input.setEnabled(is_connected)
        self.btn_send.setEnabled(is_connected)

        # Abilita solo i pulsanti macro con un contenuto valido
        for btn in self.preset_buttons:
            if is_connected and not btn.text().startswith("Empty"):
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)

    def connect_serial(self):
        port = self.combo_ports.currentText()
        baud = int(self.combo_baud.currentText())

        if not port:
            self.text_terminal.append("No port selected.\n")
            return

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=1)
            
            self.reader_thread = SerialReaderThread(self.ser)
            self.reader_thread.data_received.connect(self.append_text)
            self.reader_thread.start()

            self.set_controls_enabled(True)
            self.text_terminal.append(f"--- Connected on {port} at {baud} baud ---\n")

        except Exception as e:
            self.text_terminal.append(f"Impossible to open the COM port {port}: {str(e)}\n")

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()

        if self.ser and self.ser.is_open:
            self.ser.close()

        self.set_controls_enabled(False)
        self.text_terminal.append("\n--- Disconnected ---\n")

    def write_to_serial(self, text):
        """Invia una stringa sulla porta seriale."""
        if text and self.ser and self.ser.is_open:
            data_to_send = text + "\n"
            self.ser.write(data_to_send.encode('utf-8'))
            self.text_terminal.append(f"> {text}\n")

    def send_custom_data(self):
        """Invia il testo digitato nel QLineEdit."""
        text = self.line_input.text()
        if text:
            self.write_to_serial(text)
            self.line_input.clear()

    @Slot(str)
    def append_text(self, text):
        self.text_terminal.insertPlainText(text)
        self.text_terminal.verticalScrollBar().setValue(
            self.text_terminal.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        self.disconnect_serial()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialTerminal()
    window.show()
    sys.exit(app.exec())