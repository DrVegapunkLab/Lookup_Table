import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QFileDialog, QTextEdit, QMessageBox, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase

class LUTGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulink LUT to C Generator (PyQt5)")
        self.resize(1100, 700)

        self.df = None
        self.filepath = ""

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- LEFT PANEL (Controls & Code) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # 1. Load CSV Group
        group_file = QGroupBox("1. Carica File CSV")
        file_layout = QVBoxLayout()
        self.btn_load = QPushButton("Sfoglia CSV...")
        self.btn_load.clicked.connect(self.load_csv)
        self.lbl_file = QLabel("Nessun file selezionato")
        self.lbl_file.setWordWrap(True)
        file_layout.addWidget(self.btn_load)
        file_layout.addWidget(self.lbl_file)
        group_file.setLayout(file_layout)
        left_layout.addWidget(group_file)

        # 2. Select Columns Group
        group_cols = QGroupBox("2. Configura Assegnazione Dati")
        form_layout = QFormLayout()
        self.combo_x = QComboBox()
        self.combo_y = QComboBox()
        form_layout.addRow("Asse X (Breakpoints):", self.combo_x)
        form_layout.addRow("Asse Y (Table Data):", self.combo_y)
        group_cols.setLayout(form_layout)
        left_layout.addWidget(group_cols)

        # 3. Actions Group
        group_actions = QGroupBox("3. Azioni")
        actions_layout = QHBoxLayout()
        self.btn_plot = QPushButton("Aggiorna Grafico")
        self.btn_plot.clicked.connect(self.plot_data)
        self.btn_generate = QPushButton("Genera Codice C")
        self.btn_generate.clicked.connect(self.generate_code)
        actions_layout.addWidget(self.btn_plot)
        actions_layout.addWidget(self.btn_generate)
        group_actions.setLayout(actions_layout)
        left_layout.addWidget(group_actions)

        # 4. Code Output
        group_code = QGroupBox("Codice C Generato (copia nel main.c)")
        code_layout = QVBoxLayout()
        self.text_code = QTextEdit()
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.text_code.setFont(fixed_font)
        self.text_code.setReadOnly(True)
        code_layout.addWidget(self.text_code)
        group_code.setLayout(code_layout)
        left_layout.addWidget(group_code)

        # --- RIGHT PANEL (Plot) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Matplotlib Figure
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # Initial state
        self.set_controls_enabled(False)

    def set_controls_enabled(self, state):
        self.combo_x.setEnabled(state)
        self.combo_y.setEnabled(state)
        self.btn_plot.setEnabled(state)
        self.btn_generate.setEnabled(state)

    def load_csv(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleziona File CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
        
        if filepath:
            try:
                # Leggiamo il file CSV
                self.df = pd.read_csv(filepath)
                self.filepath = filepath
                self.lbl_file.setText(filepath.split('/')[-1])
                
                # Popoliamo i combobox con i nomi delle colonne
                columns = self.df.columns.tolist()
                self.combo_x.clear()
                self.combo_y.clear()
                self.combo_x.addItems(columns)
                self.combo_y.addItems(columns)
                
                if len(columns) >= 2:
                    self.combo_y.setCurrentIndex(1)
                
                self.set_controls_enabled(True)
                self.text_code.clear()
                
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile leggere il file CSV:\n{str(e)}")

    def plot_data(self):
        if self.df is None:
            return
            
        col_x = self.combo_x.currentText()
        col_y = self.combo_y.currentText()
        
        try:
            x_data = self.df[col_x].values
            y_data = self.df[col_y].values
            
            self.ax.clear()
            self.ax.plot(x_data, y_data, marker='o', linestyle='-', color='b')
            self.ax.set_title(f"Lookup Table: {col_y} vs {col_x}")
            self.ax.set_xlabel(col_x)
            self.ax.set_ylabel(col_y)
            self.ax.grid(True)
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.critical(self, "Errore di Plot", f"Assicurati che le colonne contengano dati numerici.\n{str(e)}")

    def generate_code(self):
        if self.df is None:
            return
            
        col_x = self.combo_x.currentText()
        col_y = self.combo_y.currentText()
        
        try:
            # Estraiamo e puliamo i dati (rimuoviamo eventuali NaN)
            df_clean = self.df[[col_x, col_y]].dropna()
            
            # Ordiniamo i dati in base alla X (i breakpoint devono essere monotoni crescenti per la binary search)
            df_clean = df_clean.sort_values(by=col_x)
            
            x_data = df_clean[col_x].values
            y_data = df_clean[col_y].values
            num_points = len(x_data)
            
            # Formattiamo gli array in stile C
            x_str = ", ".join([f"{val:.4f}" for val in x_data])
            y_str = ", ".join([f"{val:.4f}" for val in y_data])
            
            c_code = (
                f"// Dati estratti da: {self.lbl_file.text()}\n"
                f"// Asse X: {col_x}\n"
                f"// Asse Y: {col_y}\n\n"
                f"const int NUM_POINTS = {num_points};\n\n"
                f"const double breakpoints[] = {{\n    {x_str}\n}};\n\n"
                f"const double table_data[] = {{\n    {y_str}\n}};\n\n"
                "/*\nEsempio di utilizzo con la libreria:\n\n"
                "double input_val = 15.5;\n"
                "PrelookupResult kf = prelookup(input_val, breakpoints, NUM_POINTS, EXTRAP_LINEAR);\n"
                "double output_val = interpolate_1d(kf, table_data);\n"
                "*/"
            )
            
            self.text_code.setPlainText(c_code)
            
        except Exception as e:
            QMessageBox.critical(self, "Errore di Generazione", f"Impossibile generare il codice.\n{str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Imposta uno stile moderno
    app.setStyle("Fusion") 
    window = LUTGeneratorApp()
    window.show()
    sys.exit(app.exec_())