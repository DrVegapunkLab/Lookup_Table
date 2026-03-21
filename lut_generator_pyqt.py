import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QFileDialog, QTextEdit, QMessageBox, QGroupBox, 
                             QFormLayout, QDoubleSpinBox, QCheckBox)
from PyQt5.QtGui import QFontDatabase

class LUTGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulink LUT Optimizer & C Generator (PyQt5)")
        self.resize(1200, 800)

        # Stato dell'applicazione
        self.df = None
        self.filepath = ""
        self.opt_x = None
        self.opt_y = None
        self.is_pow2 = False
        self.pow2_N = 0

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- PANNELLO SINISTRO (Controlli) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # 1. Caricamento
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

        # 2. Configurazione Colonne
        group_cols = QGroupBox("2. Assegnazione Dati")
        form_layout = QFormLayout()
        self.combo_x = QComboBox()
        self.combo_y = QComboBox()
        form_layout.addRow("Asse X (Breakpoints):", self.combo_x)
        form_layout.addRow("Asse Y (Table Data):", self.combo_y)
        group_cols.setLayout(form_layout)
        left_layout.addWidget(group_cols)

        # 3. Ottimizzazione
        group_opt = QGroupBox("3. Ottimizzatore Memoria (Tolerance)")
        opt_layout = QFormLayout()
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.005)
        self.spin_tol.setValue(0.01) # Tolleranza default
        
        self.chk_pow2 = QCheckBox("Usa spaziatura EvenPow2Spacing (CPU max)")
        self.chk_pow2.setToolTip("Elimina la ricerca binaria. L'asse X diventa a passi di 2^N.")
        
        self.btn_optimize = QPushButton("Ottimizza LUT")
        self.btn_optimize.clicked.connect(self.optimize_lut)
        
        self.lbl_memory = QLabel("Punti: 0 -> 0 (0% risparmio)")
        
        opt_layout.addRow("Tolleranza Assoluta:", self.spin_tol)
        opt_layout.addRow("", self.chk_pow2)
        opt_layout.addRow(self.btn_optimize)
        opt_layout.addRow(self.lbl_memory)
        group_opt.setLayout(opt_layout)
        left_layout.addWidget(group_opt)

        # 4. Codice Output
        group_code = QGroupBox("4. Codice C Generato")
        code_layout = QVBoxLayout()
        self.btn_generate = QPushButton("Genera Codice C")
        self.btn_generate.clicked.connect(self.generate_code)
        
        self.text_code = QTextEdit()
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.text_code.setFont(fixed_font)
        self.text_code.setReadOnly(True)
        self.text_code.setPlaceholderText("// Il codice C apparirà qui...")
        
        code_layout.addWidget(self.btn_generate)
        code_layout.addWidget(self.text_code)
        group_code.setLayout(code_layout)
        left_layout.addWidget(group_code)

        # --- PANNELLO DESTRO (Grafico con Subplots) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.fig, (self.ax_main, self.ax_err) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]})
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # Segnali
        self.combo_x.currentIndexChanged.connect(self.on_variables_changed)
        self.combo_y.currentIndexChanged.connect(self.on_variables_changed)
        self.chk_pow2.stateChanged.connect(self.on_variables_changed)

        self.set_controls_enabled(False)

    def set_controls_enabled(self, state):
        self.combo_x.setEnabled(state)
        self.combo_y.setEnabled(state)
        self.spin_tol.setEnabled(state)
        self.chk_pow2.setEnabled(state)
        self.btn_optimize.setEnabled(state)
        self.btn_generate.setEnabled(state)

    def load_csv(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleziona File CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
        
        if filepath:
            try:
                self.df = pd.read_csv(filepath)
                self.filepath = filepath
                self.lbl_file.setText(filepath.split('/')[-1])
                
                self.combo_x.blockSignals(True)
                self.combo_y.blockSignals(True)
                columns = self.df.columns.tolist()
                self.combo_x.clear()
                self.combo_y.clear()
                self.combo_x.addItems(columns)
                self.combo_y.addItems(columns)
                if len(columns) >= 2:
                    self.combo_y.setCurrentIndex(1)
                self.combo_x.blockSignals(False)
                self.combo_y.blockSignals(False)
                
                self.set_controls_enabled(True)
                self.on_variables_changed()
                
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile leggere:\n{str(e)}")

    def on_variables_changed(self):
        if self.df is None: return
        self.opt_x, self.opt_y = None, None
        self.is_pow2 = False
        self.text_code.clear()
        self.lbl_memory.setText("Ottimizzazione resettata. Clicca 'Ottimizza LUT'.")
        self.plot_data()

    def get_clean_data(self):
        col_x = self.combo_x.currentText()
        col_y = self.combo_y.currentText()
        df_clean = self.df[[col_x, col_y]].dropna().sort_values(by=col_x)
        return df_clean[col_x].values, df_clean[col_y].values, col_x, col_y

    def optimize_lut(self):
        if self.df is None: return
        orig_x, orig_y, _, _ = self.get_clean_data()
        tolerance = self.spin_tol.value()
        
        if self.chk_pow2.isChecked():
            # --- ALGORITMO EvenPow2Spacing ---
            x_min, x_max = orig_x[0], orig_x[-1]
            best_N = None
            best_opt_x = None
            best_opt_y = None
            
            # Proviamo potenze di 2 decrescenti (da dx grande a dx piccolo)
            # Da 2^10 (1024) fino a 2^-20 (~0.000001)
            for N in range(10, -20, -1):
                dx = 2.0 ** N
                num_intervals = int(np.ceil((x_max - x_min) / dx))
                
                # Creiamo i punti equispaziati che coprono l'intero range
                opt_x = x_min + np.arange(num_intervals + 1) * dx
                
                # Interpoliamo per trovare i valori Y corrispondenti
                opt_y = np.interp(opt_x, orig_x, orig_y)
                
                # Valutiamo l'errore rispetto alla curva originale ad alta risoluzione
                y_test = np.interp(orig_x, opt_x, opt_y)
                max_err = np.max(np.abs(orig_y - y_test))
                
                if max_err <= tolerance:
                    best_N = N
                    best_opt_x = opt_x
                    best_opt_y = opt_y
                    break # Abbiamo trovato il dx più grande possibile!
            
            if best_N is not None:
                self.opt_x, self.opt_y = best_opt_x, best_opt_y
                self.is_pow2 = True
                self.pow2_N = best_N
            else:
                QMessageBox.warning(self, "Attenzione", "Impossibile trovare una spaziatura 2^N per questa tolleranza.")
                return

        else:
            # --- ALGORITMO GREEDY (Risparmio ROM asimmetrico) ---
            keep_mask = np.ones(len(orig_x), dtype=bool)
            while True:
                idx_kept = np.where(keep_mask)[0]
                if len(idx_kept) <= 2: break

                min_error = float('inf')
                best_idx_to_drop = -1

                for i in range(1, len(idx_kept) - 1):
                    test_mask = keep_mask.copy()
                    test_mask[idx_kept[i]] = False
                    y_interp = np.interp(orig_x, orig_x[test_mask], orig_y[test_mask])
                    max_err = np.max(np.abs(orig_y - y_interp))
                    
                    if max_err < min_error:
                        min_error = max_err
                        best_idx_to_drop = idx_kept[i]

                if min_error <= tolerance:
                    keep_mask[best_idx_to_drop] = False
                else:
                    break
            self.opt_x, self.opt_y = orig_x[keep_mask], orig_y[keep_mask]
            self.is_pow2 = False
        
        # Statistiche memoria (nel caso Pow2 non salviamo l'array X!)
        bytes_orig = len(orig_x) * 2 * 8 # double = 8 bytes per X e Y
        if self.is_pow2:
            bytes_opt = len(self.opt_y) * 8 # Solo array Y!
        else:
            bytes_opt = len(self.opt_x) * 2 * 8 # Array X e Y
            
        reduction = 100 * (1.0 - bytes_opt / bytes_orig)
        self.lbl_memory.setText(f"Memoria (ROM): {bytes_orig} B -> {bytes_opt} B ({reduction:.1f}% risparmio)")
        
        self.plot_data()

    def plot_data(self):
        if self.df is None: return
        try:
            orig_x, orig_y, col_x, col_y = self.get_clean_data()
            self.ax_main.clear()
            self.ax_err.clear()
            
            self.ax_main.plot(orig_x, orig_y, label="Dati Originali CSV", color='lightgray', linestyle='--', marker='.', markersize=4)
            
            if self.opt_x is not None and self.opt_y is not None:
                lbl = f"EvenPow2Spacing (dx={2.0**self.pow2_N})" if self.is_pow2 else f"Greedy Ottimizzata"
                self.ax_main.plot(self.opt_x, self.opt_y, label=lbl, color='b', marker='o', linestyle='-')
                self.ax_main.scatter(self.opt_x, self.opt_y, color='red', s=50, zorder=5)
                
                y_interp = np.interp(orig_x, self.opt_x, self.opt_y)
                error = orig_y - y_interp
                
                self.ax_err.plot(orig_x, error, color='red')
                self.ax_err.fill_between(orig_x, error, 0, color='red', alpha=0.3)
                
                tol = self.spin_tol.value()
                self.ax_err.axhline(tol, color='black', linestyle=':', alpha=0.5)
                self.ax_err.axhline(-tol, color='black', linestyle=':', alpha=0.5)
                y_max = max(abs(np.max(error)), tol) * 1.5
                self.ax_err.set_ylim(-y_max, y_max)
            else:
                self.ax_main.plot(orig_x, orig_y, label="Da ottimizzare", color='b', marker='.', linestyle='-')
                self.ax_err.plot(orig_x, np.zeros_like(orig_x), color='gray', linestyle='--')
                self.ax_err.set_ylim(-1, 1)

            self.ax_main.set_title(f"Comparison Plot: {col_y} vs {col_x}")
            self.ax_main.set_ylabel(col_y)
            self.ax_main.legend()
            self.ax_main.grid(True, linestyle=':', alpha=0.6)
            self.ax_main.tick_params(labelbottom=False)
            
            self.ax_err.set_xlabel(col_x)
            self.ax_err.set_ylabel("Errore")
            self.ax_err.grid(True, linestyle=':', alpha=0.6)
            
            self.fig.tight_layout()
            self.canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Errore", str(e))

    def generate_code(self):
        if self.df is None: return
        col_x = self.combo_x.currentText()
        col_y = self.combo_y.currentText()
        
        if self.opt_x is not None:
            x_data, y_data = self.opt_x, self.opt_y
        else:
            x_data, y_data = self.get_clean_data() # ERRORE QUI
        
        y_str = ", ".join([f"{val:.6f}" for val in y_data])
        num_points = len(y_data)
        
        if self.is_pow2:
            # --- C CODE PER EVEN_POW_2 ---
            x_min = x_data[0]
            dx = 2.0 ** self.pow2_N
            inv_dx = 1.0 / dx
            
            c_code = (
                f"// --- OTTMIZZAZIONE EVEN POW 2 SPACING ---\n"
                f"// Asse X: {col_x} | Asse Y: {col_y}\n"
                f"// Nota: Array X rimosso per risparmiare ROM. Calcolo indice in O(1).\n\n"
                f"const int NUM_POINTS = {num_points};\n"
                f"const double X_MIN = {x_min:.6f};\n"
                f"const double X_SPACING = {dx:.6f}; // 2^{self.pow2_N}\n"
                f"const double INV_SPACING = {inv_dx:.6f}; // (1.0 / X_SPACING) per evitare divisioni\n\n"
                f"const double table_data[] = {{\n    {y_str}\n}};\n\n"
                f"// Struttura risultato (Index e Fraction)\n"
                f"typedef struct {{\n    int k;\n    double f;\n}} PrelookupResult;\n\n"
                f"// Funzione ultra-veloce senza ciclo While:\n"
                f"PrelookupResult fast_prelookup(double u) {{\n"
                f"    PrelookupResult res;\n"
                f"    if (u <= X_MIN) {{\n"
                f"        res.k = 0;\n"
                f"        res.f = 0.0; // Extrap_Clip\n"
                f"    }} else if (u >= X_MIN + (NUM_POINTS - 1)*X_SPACING) {{\n"
                f"        res.k = NUM_POINTS - 2;\n"
                f"        res.f = 1.0; // Extrap_Clip\n"
                f"    }} else {{\n"
                f"        // Magia di EvenPow2Spacing: Nessuna ricerca necessaria!\n"
                f"        double normalized = (u - X_MIN) * INV_SPACING;\n"
                f"        res.k = (int)normalized;\n"
                f"        res.f = normalized - res.k;\n"
                f"    }}\n"
                f"    return res;\n"
                f"}}\n"
            )
        else:
            # --- C CODE STANDARD (GREEDY) ---
            x_str = ", ".join([f"{val:.6f}" for val in x_data])
            status = "Ottimizzazione Greedy" if self.opt_x is not None else "Nessuna Ottimizzazione"
            c_code = (
                f"// --- STANDARD LOOKUP TABLE ({status}) ---\n"
                f"// Asse X: {col_x} | Asse Y: {col_y}\n\n"
                f"const int NUM_POINTS = {num_points};\n\n"
                f"const double breakpoints[] = {{\n    {x_str}\n}};\n\n"
                f"const double table_data[] = {{\n    {y_str}\n}};\n"
            )
            
        self.text_code.setPlainText(c_code)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = LUTGeneratorApp()
    window.show()
    sys.exit(app.exec_())