import tkinter as tk
import serial
import threading

try:
    with open("setcmd.txt", "r", encoding="utf-8") as file:
        riga1 = file.readline()
        riga2 = file.readline()
        riga3 = file.readline()
        riga4 = file.readline()
        riga5 = file.readline()
        
except:
    riga1 = "none"
    riga2 = "none"
    riga3 = "none"
    riga4 = "none"
    riga5 = "none"



class SerialGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MatrixFX by IU7QMN")
        self.root.geometry("600x500")
        self.root.configure(background="royalblue")
        self.root.resizable(True, True)
        self.serial_port = None
        self.is_connected = False

        # --- GUI Elements ---
        # Port Entry & Baud Rate
        tk.Label(root, text="COM Port (e.g., COM3 or /dev/ttyACM0):" , font=("Helvetica", 12)).pack(pady=5)
        self.port_entry = tk.Entry(root, font=("Helvetica", 12))
        self.port_entry.insert(0, "COM3")
        self.port_entry.pack(pady=5)

        # Connect/Disconnect Button
        self.btn_connect = tk.Button(root, text="Connect", font=("Helvetica", 12), command=self.toggle_connection, bg="green", fg="white")
        self.btn_connect.pack()

        # Command Entry
        tk.Label(root, text="Frequency/Raw Command:", font=("Helvetica", 12)).pack(pady=5)
        self.cmd = tk.Entry(root, font=("Helvetica", 14))
        self.cmd.pack(pady=5)
        # send command
        self.send_freq = tk.Button(root, text="SEND FREQUENCY", font=("Helvetica", 11), command=lambda: self.send_data('B' + self.cmd.get() + '*'), state=tk.DISABLED, width=15, height=1)
        self.send_freq.pack()
        self.send_raw = tk.Button(root, text="SEND RAW CMD", font=("Helvetica", 11), command=lambda: self.send_data(self.cmd.get()), state=tk.DISABLED, width=15, height=1)
        self.send_raw.pack()

        # Receive Display
        tk.Label(root, text="Received Data:", font=("Helvetica", 12)).pack()
        self.receive_text = tk.Text(root, font=("Helvetica", 14), height=8, width=50)
        self.receive_text.pack()

        # Action Buttons
        tk.Label(root, text="MACRO BUTTONS", font=("Helvetica", 12)).pack(pady=5)

        self.macro1 = tk.Button(root, text=riga1, font=("Helvetica", 12), command=lambda: self.send_data(riga1), state=tk.DISABLED, width=15, height=2)
        self.macro1.pack(side='left')

        self.macro2 = tk.Button(root, text=riga2, font=("Helvetica", 12), command=lambda: self.send_data(riga2), state=tk.DISABLED, width=15, height=2)
        self.macro2.pack(side='left')

        self.macro3 = tk.Button(root, text=riga3, font=("Helvetica", 12), command=lambda: self.send_data(riga3), state=tk.DISABLED, width=15, height=2)
        self.macro3.pack(side='left')

        self.macro4 = tk.Button(root, text=riga4, font=("Helvetica", 12), command=lambda: self.send_data(riga4), state=tk.DISABLED, width=15, height=2)
        self.macro4.pack(side='left')
        
        self.macro5 = tk.Button(root, text=riga5, font=("Helvetica", 12), command=lambda: self.send_data(riga5), state=tk.DISABLED, width=15, height=2)
        self.macro5.pack(side='left')

        self.macroC = tk.Button(root, text="(#)", font=("Helvetica", 12), command=lambda: self.send_data("#"), state=tk.DISABLED, width=15, height=2)
        self.macroC.pack(side='left')
        

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_entry.get()
            try:
                # 9600 is a common baud rate, adjust as needed
                self.serial_port = serial.Serial(port, 115200, timeout=1) 
                self.is_connected = True
                self.btn_connect.config(text="Disconnect", bg="red")
                self.send_freq.config(state=tk.NORMAL)
                self.send_raw.config(state=tk.NORMAL)
                self.macro1.config(state=tk.NORMAL)
                self.macro2.config(state=tk.NORMAL)
                self.macro3.config(state=tk.NORMAL)
                self.macro4.config(state=tk.NORMAL)
                self.macro5.config(state=tk.NORMAL)
                self.macroC.config(state=tk.NORMAL)
                
                
                # Start a background thread to listen for incoming serial data
                threading.Thread(target=self.read_serial, daemon=True).start()
            except Exception as e:
                self.receive_text.insert(tk.END, f"Error: {e}\n")
        else:
            self.serial_port.close()
            self.is_connected = False
            self.btn_connect.config(text="Connect", bg="green")
            self.send_freq.config(state=tk.DISABLE)
            self.send_raw.config(state=tk.DISABLE)
            self.macro1.config(state=tk.DISABLE)
            self.macro2.config(state=tk.DISABLE)
            self.macro3.config(state=tk.DISABLE)
            self.macro4.config(state=tk.DISABLE)
            self.macro5.config(state=tk.DISABLE)
            self.macroC.config(state=tk.DISABLE)
            
    def send_data(self, data):
        if self.is_connected and self.serial_port:
            self.serial_port.write(data.encode('utf-8'))

    def read_serial(self):
        while self.is_connected:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode('utf-8').strip()
                    self.receive_text.insert(tk.END, f"{data}\n")
                    self.receive_text.see(tk.END) # Auto-scroll to the bottom
            except:
                break

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialGUI(root)
    root.mainloop()
