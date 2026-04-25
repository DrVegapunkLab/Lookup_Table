import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QFileDialog, QTextEdit, QMessageBox, QGroupBox, 
                             QFormLayout, QDoubleSpinBox, QCheckBox, QTabWidget, QSpinBox)
from PyQt5.QtGui import QFontDatabase
from enum import Enum
from dataclasses import dataclass

# =====================================================================
# MOTORE SIL (Software-In-the-Loop) - Porting della libreria C in Python
# =====================================================================
class ExtrapMethod(Enum):
    EXTRAP_CLIP = 0
    EXTRAP_LINEAR = 1

@dataclass
class PrelookupResult:
    k: int
    f: float

def prelookup(u: float, bp: np.ndarray, num_points: int, extrap_method: ExtrapMethod) -> PrelookupResult:
    if u <= bp[0]:
        k = 0
        f = 0.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - bp[0]) / (bp[1] - bp[0])
    elif u >= bp[num_points - 1]:
        k = num_points - 2
        f = 1.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - bp[k]) / (bp[k + 1] - bp[k])
    else:
        low = 0
        high = num_points - 1
        while low < high - 1:
            mid = low + (high - low) // 2
            if u < bp[mid]: high = mid
            else: low = mid
        k = low
        f = (u - bp[k]) / (bp[k + 1] - bp[k])
    return PrelookupResult(k, f)

def prelookup_pow2(u: float, x_min: float, spacing: float, inv_spacing: float, num_points: int, extrap_method: ExtrapMethod) -> PrelookupResult:
    x_max = x_min + (num_points - 1) * spacing
    if u <= x_min:
        k = 0
        f = 0.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - x_min) * inv_spacing
    elif u >= x_max:
        k = num_points - 2
        bp_k = x_min + k * spacing
        f = 1.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - bp_k) * inv_spacing
    else:
        normalized = (u - x_min) * inv_spacing
        k = int(normalized)
        f = normalized - k
    return PrelookupResult(k, f)

def interpolate_1d(kf: PrelookupResult, table: np.ndarray) -> float:
    return table[kf.k] + kf.f * (table[kf.k + 1] - table[kf.k])

# =====================================================================
# APPLICAZIONE GUI PRINCIPALE
# =====================================================================
class LUTGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulink LUT Suite - Optimizer, Validator & Identifier")
        self.resize(1300, 850)

        # Stato Condiviso
        self.df = None          # Dati Riferimento (Tab 2)
        self.val_df = None      # Dati Validazione (Tab 3)
        self.time_df = None     # Dati Temporali Grezzi (Tab 1)
        
        self.opt_x = None       # Array X Ottimizzato
        self.opt_y = None       # Array Y Ottimizzato
        self.is_pow2 = False
        self.pow2_N = 0

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_ident = QWidget()
        self.tab_opt = QWidget()
        self.tab_val = QWidget()

        self.tabs.addTab(self.tab_ident, "1. Identificazione (da Serie Temporali)")
        self.tabs.addTab(self.tab_opt, "2. Ottimizzatore Memoria & C Gen")
        self.tabs.addTab(self.tab_val, "3. Validazione SIL (System ID)")

        self.setup_ident_tab()
        self.setup_opt_tab()
        self.setup_val_tab()

    # -----------------------------------------------------------------
    # TAB 1: IDENTIFICAZIONE DA SERIE TEMPORALI
    # -----------------------------------------------------------------
    def setup_ident_tab(self):
        layout = QHBoxLayout(self.tab_ident)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # 1. Carica CSV Temporale
        g1 = QGroupBox("1. Carica Log Temporale (Es. Acquisizione)")
        l1 = QVBoxLayout()
        self.btn_load_time = QPushButton("Sfoglia Log CSV...")
        self.btn_load_time.clicked.connect(self.load_time_csv)
        self.lbl_file_time = QLabel("Nessun file selezionato")
        l1.addWidget(self.btn_load_time)
        l1.addWidget(self.lbl_file_time)
        g1.setLayout(l1)
        left_layout.addWidget(g1)

        # 2. Configurazione Canali
        g2 = QGroupBox("2. Configurazione Canali")
        f2 = QFormLayout()
        self.c_x = QComboBox()
        self.c_y = QComboBox()
        f2.addRow("Asse X (Input):", self.c_x)
        f2.addRow("Asse Y (Output target):", self.c_y)
        g2.setLayout(f2)
        left_layout.addWidget(g2)

        # 3. Parametri Identificazione
        g3 = QGroupBox("3. Identificazione tramite Binning")
        f3 = QFormLayout()
        self.s_bins = QSpinBox()
        self.s_bins.setRange(5, 1000)
        self.s_bins.setValue(50)
        self.s_bins.setToolTip("Dividi l'asse X in N intervalli e fai la media della Y in ciascuno.")
        
        self.btn_run_ident = QPushButton("Estrai LUT Media")
        self.btn_run_ident.clicked.connect(self.run_identification)
        
        f3.addRow("Numero di Breakpoint (Bin):", self.s_bins)
        f3.addRow(self.btn_run_ident)
        g3.setLayout(f3)
        left_layout.addWidget(g3)

        # 4. Esportazione
        self.btn_send_to_opt = QPushButton("Invia LUT estratta all'Ottimizzatore ->")
        self.btn_send_to_opt.setEnabled(False)
        self.btn_send_to_opt.setStyleSheet("font-weight: bold; padding: 10px;")
        self.btn_send_to_opt.clicked.connect(self.send_to_optimizer)
        left_layout.addWidget(self.btn_send_to_opt)
        left_layout.addStretch()

        # Plot Destro
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.fig_id, self.ax_id = plt.subplots()
        self.canvas_id = FigureCanvas(self.fig_id)
        self.toolbar_id = NavigationToolbar(self.canvas_id, self)
        
        right_layout.addWidget(self.toolbar_id)
        right_layout.addWidget(self.canvas_id)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel)

    def load_time_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleziona Log CSV", "", "CSV Files (*.csv)")
        if filepath:
            self.time_df = pd.read_csv(filepath)
            self.lbl_file_time.setText(filepath.split('/')[-1])
            cols = self.time_df.columns.tolist()
            self.c_x.clear()
            self.c_y.clear()
            self.c_x.addItems(cols)
            self.c_y.addItems(cols)
            if len(cols) >= 2: self.c_y.setCurrentIndex(1)

    def run_identification(self):
        if self.time_df is None: return
        cx = self.c_x.currentText()
        cy = self.c_y.currentText()
        
        df = self.time_df[[cx, cy]].dropna()
        
        # Algoritmo di Binning
        bins = pd.cut(df[cx], bins=self.s_bins.value())
        lut_df = df.groupby(bins, observed=False).mean().dropna()
        
        self.identified_x = lut_df[cx].values
        self.identified_y = lut_df[cy].values

        # Disegna il grafico
        self.ax_id.clear()
        self.ax_id.scatter(df[cx], df[cy], alpha=0.1, s=2, label="Dati Temporali Grezzi", color='gray')
        self.ax_id.plot(self.identified_x, self.identified_y, 'r-o', label=f"LUT Media ({len(self.identified_x)} punti)", markersize=4)
        
        self.ax_id.set_xlabel(cx)
        self.ax_id.set_ylabel(cy)
        self.ax_id.set_title("Identificazione Curva da Serie Temporale")
        self.ax_id.legend()
        self.ax_id.grid(True, linestyle=':', alpha=0.6)
        self.fig_id.tight_layout()
        self.canvas_id.draw()

        self.btn_send_to_opt.setEnabled(True)

    def send_to_optimizer(self):
        # Trasferisce i dati identificati al Tab 2
        col_x = self.c_x.currentText()
        col_y = self.c_y.currentText()
        
        self.df = pd.DataFrame({col_x: self.identified_x, col_y: self.identified_y})
        
        self.combo_x.blockSignals(True)
        self.combo_y.blockSignals(True)
        self.combo_x.clear(); self.combo_x.addItems(self.df.columns)
        self.combo_y.clear(); self.combo_y.addItems(self.df.columns)
        self.combo_y.setCurrentIndex(1)
        self.combo_x.blockSignals(False)
        self.combo_y.blockSignals(False)
        
        self.set_opt_controls_enabled(True)
        self.lbl_file.setText("Dati importati da Identificazione")
        self.on_variables_changed()
        
        self.tabs.setCurrentIndex(1) # Sposta l'utente sul Tab 2

    # -----------------------------------------------------------------
    # TAB 2: OTTIMIZZATORE MEMORIA & C GEN
    # -----------------------------------------------------------------
    def setup_opt_tab(self):
        main_layout = QHBoxLayout(self.tab_opt)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # 1. Carica CSV
        group_file = QGroupBox("1. Carica Curva di Riferimento (CSV)")
        file_layout = QVBoxLayout()
        self.btn_load = QPushButton("Sfoglia CSV Statico...")
        self.btn_load.clicked.connect(self.load_opt_csv)
        self.lbl_file = QLabel("Nessun file selezionato")
        file_layout.addWidget(self.btn_load)
        file_layout.addWidget(self.lbl_file)
        group_file.setLayout(file_layout)
        left_layout.addWidget(group_file)

        # 2. Assegnazione
        group_cols = QGroupBox("2. Assegnazione Colonne")
        form_layout = QFormLayout()
        self.combo_x = QComboBox()
        self.combo_y = QComboBox()
        form_layout.addRow("Asse X (Input):", self.combo_x)
        form_layout.addRow("Asse Y (Target):", self.combo_y)
        group_cols.setLayout(form_layout)
        left_layout.addWidget(group_cols)

        # 3. Ottimizzatore
        group_opt = QGroupBox("3. Ottimizzatore Memoria e CPU")
        opt_layout = QFormLayout()
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.005)
        self.spin_tol.setValue(0.01)
        self.chk_pow2 = QCheckBox("Usa spaziatura EvenPow2Spacing (O(1))")
        self.btn_optimize = QPushButton("Ottimizza LUT")
        self.btn_optimize.clicked.connect(self.optimize_lut)
        self.lbl_memory = QLabel("Punti: 0 -> 0 (0% risparmio)")
        
        opt_layout.addRow("Tolleranza (Max Err):", self.spin_tol)
        opt_layout.addRow("", self.chk_pow2)
        opt_layout.addRow(self.btn_optimize)
        opt_layout.addRow(self.lbl_memory)
        group_opt.setLayout(opt_layout)
        left_layout.addWidget(group_opt)

        # 4. Codice C
        group_code = QGroupBox("4. Codice C Generato")
        code_layout = QVBoxLayout()
        self.btn_generate = QPushButton("Genera Codice C")
        self.btn_generate.clicked.connect(self.generate_code)
        self.text_code = QTextEdit()
        self.text_code.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text_code.setReadOnly(True)
        code_layout.addWidget(self.btn_generate)
        code_layout.addWidget(self.text_code)
        group_code.setLayout(code_layout)
        left_layout.addWidget(group_code)

        # Plot Destro
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.fig_opt, (self.ax_opt_main, self.ax_opt_err) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]})
        self.canvas_opt = FigureCanvas(self.fig_opt)
        self.toolbar_opt = NavigationToolbar(self.canvas_opt, self)
        right_layout.addWidget(self.toolbar_opt)
        right_layout.addWidget(self.canvas_opt)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        self.combo_x.currentIndexChanged.connect(self.on_variables_changed)
        self.combo_y.currentIndexChanged.connect(self.on_variables_changed)
        self.chk_pow2.stateChanged.connect(self.on_variables_changed)
        self.set_opt_controls_enabled(False)

    def set_opt_controls_enabled(self, state):
        self.combo_x.setEnabled(state)
        self.combo_y.setEnabled(state)
        self.spin_tol.setEnabled(state)
        self.chk_pow2.setEnabled(state)
        self.btn_optimize.setEnabled(state)
        self.btn_generate.setEnabled(state)

    def load_opt_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleziona CSV Curva Riferimento", "", "CSV Files (*.csv)")
        if filepath:
            self.df = pd.read_csv(filepath)
            self.lbl_file.setText(filepath.split('/')[-1])
            self.combo_x.blockSignals(True)
            self.combo_y.blockSignals(True)
            cols = self.df.columns.tolist()
            self.combo_x.clear(); self.combo_x.addItems(cols)
            self.combo_y.clear(); self.combo_y.addItems(cols)
            if len(cols) >= 2: self.combo_y.setCurrentIndex(1)
            self.combo_x.blockSignals(False)
            self.combo_y.blockSignals(False)
            self.set_opt_controls_enabled(True)
            self.on_variables_changed()

    def on_variables_changed(self):
        if self.df is None: return
        self.opt_x, self.opt_y = None, None
        self.is_pow2 = False
        self.text_code.clear()
        self.lbl_memory.setText("Ottimizzazione resettata.")
        self.plot_opt_data()

    def get_clean_data(self):
        cx, cy = self.combo_x.currentText(), self.combo_y.currentText()
        df_c = self.df[[cx, cy]].dropna().sort_values(by=cx)
        return df_c[cx].values, df_c[cy].values, cx, cy

    def optimize_lut(self):
        if self.df is None: return
        orig_x, orig_y, _, _ = self.get_clean_data()
        tol = self.spin_tol.value()
        
        if self.chk_pow2.isChecked():
            x_min, x_max = orig_x[0], orig_x[-1]
            best_N, best_opt_x, best_opt_y = None, None, None
            for N in range(10, -20, -1):
                dx = 2.0 ** N
                num_int = int(np.ceil((x_max - x_min) / dx))
                opt_x = x_min + np.arange(num_int + 1) * dx
                opt_y = np.interp(opt_x, orig_x, orig_y)
                y_test = np.interp(orig_x, opt_x, opt_y)
                if np.max(np.abs(orig_y - y_test)) <= tol:
                    best_N, best_opt_x, best_opt_y = N, opt_x, opt_y
                    break
            if best_N is not None:
                self.opt_x, self.opt_y, self.is_pow2, self.pow2_N = best_opt_x, best_opt_y, True, best_N
            else:
                QMessageBox.warning(self, "Attenzione", "Impossibile trovare spaziatura 2^N per questa tolleranza.")
                return
        else:
            keep = np.ones(len(orig_x), dtype=bool)
            while True:
                idx = np.where(keep)[0]
                if len(idx) <= 2: break
                min_err, best_idx = float('inf'), -1
                for i in range(1, len(idx) - 1):
                    tm = keep.copy()
                    tm[idx[i]] = False
                    yi = np.interp(orig_x, orig_x[tm], orig_y[tm])
                    merr = np.max(np.abs(orig_y - yi))
                    if merr < min_err: min_err, best_idx = merr, idx[i]
                if min_err <= tol: keep[best_idx] = False
                else: break
            self.opt_x, self.opt_y, self.is_pow2 = orig_x[keep], orig_y[keep], False
        
        b_o = len(orig_x) * 16 
        b_opt = len(self.opt_y) * 8 if self.is_pow2 else len(self.opt_x) * 16
        reduction = 100 * (1 - b_opt / b_o) if b_o > 0 else 0
        self.lbl_memory.setText(f"ROM: {b_o} B -> {b_opt} B ({reduction:.1f}% risp.)")
        self.plot_opt_data()

    def plot_opt_data(self):
        if self.df is None: return
        orig_x, orig_y, cx, cy = self.get_clean_data()
        self.ax_opt_main.clear(); self.ax_opt_err.clear()
        
        self.ax_opt_main.plot(orig_x, orig_y, label="Dati Riferimento", color='lightgray', linestyle='--', marker='.', markersize=2)
        
        if self.opt_x is not None:
            lbl = f"EvenPow2Spacing (dx={2.0**self.pow2_N})" if self.is_pow2 else "Greedy"
            self.ax_opt_main.plot(self.opt_x, self.opt_y, label=lbl, color='b', marker='o')
            err = orig_y - np.interp(orig_x, self.opt_x, self.opt_y)
            self.ax_opt_err.plot(orig_x, err, color='red')
            self.ax_opt_err.fill_between(orig_x, err, 0, color='red', alpha=0.3)
            tol = self.spin_tol.value()
            self.ax_opt_err.axhline(tol, color='k', linestyle=':', alpha=0.5)
            self.ax_opt_err.axhline(-tol, color='k', linestyle=':', alpha=0.5)
            y_max = max(abs(np.max(err)), tol) * 1.5
            self.ax_opt_err.set_ylim(-y_max, y_max)
        else:
            self.ax_opt_main.plot(orig_x, orig_y, label="Raw (Da ottimizzare)", color='b')
            
        self.ax_opt_main.set_title(f"LUT Design: {cy} vs {cx}"); self.ax_opt_main.legend(); self.ax_opt_main.grid(True, linestyle=':', alpha=0.6)
        self.ax_opt_err.set_title("Errore di Interpolazione"); self.ax_opt_err.grid(True, linestyle=':', alpha=0.6)
        self.fig_opt.tight_layout(); self.canvas_opt.draw()

    def generate_code(self):
        if self.df is None: return
        x_data, y_data, cx, cy = self.get_clean_data()
        if self.opt_x is not None: x_data, y_data = self.opt_x, self.opt_y
        
        num_points = len(y_data)
        y_str = ", ".join([f"{v:.6f}" for v in y_data])
        
        c_code = f"// ==========================================\n"
        c_code += f"// Generato da: Simulink LUT Suite\n"
        c_code += f"// Asse X: {cx} | Asse Y: {cy}\n"
        c_code += f"// ==========================================\n\n"
        c_code += f"#include \"simulink_lookup.h\"\n\n"

        if self.is_pow2:
            dx = 2.0 ** self.pow2_N
            c_code += f"const int NUM_POINTS = {num_points};\n"
            c_code += f"const double X_MIN = {x_data[0]:.6f};\n"
            c_code += f"const double X_SPACING = {dx:.6f}; // 2^{self.pow2_N}\n"
            c_code += f"const double INV_SPACING = {1.0/dx:.6f};\n\n"
            c_code += f"const double table_data[] = {{\n    {y_str}\n}};\n"
        else:
            x_str = ", ".join([f"{v:.6f}" for v in x_data])
            c_code += f"const int NUM_POINTS = {num_points};\n\n"
            c_code += f"const double breakpoints[] = {{\n    {x_str}\n}};\n\n"
            c_code += f"const double table_data[] = {{\n    {y_str}\n}};\n"
            
        self.text_code.setPlainText(c_code)


    # -----------------------------------------------------------------
    # TAB 3: VALIDAZIONE SIL E SYSTEM ID
    # -----------------------------------------------------------------
    def setup_val_tab(self):
        main_layout = QHBoxLayout(self.tab_val)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        # 1. Carica CSV Validazione
        group_file = QGroupBox("1. Carica Dati di Validazione Reali (CSV)")
        file_layout = QVBoxLayout()
        self.btn_load_val = QPushButton("Sfoglia CSV Validazione...")
        self.btn_load_val.clicked.connect(self.load_val_csv)
        self.lbl_file_val = QLabel("Nessun file selezionato")
        file_layout.addWidget(self.btn_load_val)
        file_layout.addWidget(self.lbl_file_val)
        group_file.setLayout(file_layout)
        left_layout.addWidget(group_file)

        # 2. Configurazione
        group_cfg = QGroupBox("2. Assegnazione Segnali Acquisiti")
        form_layout = QFormLayout()
        self.combo_val_u = QComboBox()
        self.combo_val_y = QComboBox()
        form_layout.addRow("Segnale di Input (X):", self.combo_val_u)
        form_layout.addRow("Output Misurato Reale (Y):", self.combo_val_y)
        group_cfg.setLayout(form_layout)
        left_layout.addWidget(group_cfg)

        # 3. Esecuzione SIL
        group_run = QGroupBox("3. Esecuzione Modello SIL")
        run_layout = QVBoxLayout()
        self.btn_run_sil = QPushButton("Simula LUT su dati reali")
        self.btn_run_sil.clicked.connect(self.run_sil_simulation)
        self.lbl_sil_stats = QLabel("Statistiche di validazione appariranno qui.")
        run_layout.addWidget(self.btn_run_sil)
        run_layout.addWidget(self.lbl_sil_stats)
        group_run.setLayout(run_layout)
        left_layout.addWidget(group_run)
        
        left_layout.addStretch()

        # Plot Destro
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.fig_val, (self.ax_val_main, self.ax_val_err) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]})
        self.canvas_val = FigureCanvas(self.fig_val)
        self.toolbar_val = NavigationToolbar(self.canvas_val, self)
        
        right_layout.addWidget(self.toolbar_val)
        right_layout.addWidget(self.canvas_val)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        self.set_val_controls_enabled(False)

    def set_val_controls_enabled(self, state):
        self.combo_val_u.setEnabled(state)
        self.combo_val_y.setEnabled(state)
        self.btn_run_sil.setEnabled(state)

    def load_val_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleziona CSV Validazione", "", "CSV Files (*.csv)")
        if filepath:
            self.val_df = pd.read_csv(filepath)
            self.lbl_file_val.setText(filepath.split('/')[-1])
            cols = self.val_df.columns.tolist()
            self.combo_val_u.clear(); self.combo_val_u.addItems(cols)
            self.combo_val_y.clear(); self.combo_val_y.addItems(cols)
            if len(cols) >= 2: self.combo_val_y.setCurrentIndex(1)
            self.set_val_controls_enabled(True)

    def run_sil_simulation(self):
        if self.val_df is None or self.df is None:
            QMessageBox.warning(self, "Attenzione", "Carica sia i dati nel Tab 2 (Ottimizzatore) che nel Tab 3 (Validazione).")
            return

        u_col = self.combo_val_u.currentText()
        y_real_col = self.combo_val_y.currentText()
        
        clean_val_df = self.val_df[[u_col, y_real_col]].dropna()
        u_val = clean_val_df[u_col].values
        y_real = clean_val_df[y_real_col].values

        if self.opt_x is not None:
            lut_x, lut_y = self.opt_x, self.opt_y
        else:
            lut_x, lut_y, _, _ = self.get_clean_data()
        
        num_points = len(lut_y)
        y_sim = np.zeros_like(u_val)

        # Simula C in Python
        for i, u_in in enumerate(u_val):
            if self.is_pow2:
                dx = 2.0 ** self.pow2_N
                inv_dx = 1.0 / dx
                kf = prelookup_pow2(u_in, lut_x[0], dx, inv_dx, num_points, ExtrapMethod.EXTRAP_CLIP)
            else:
                kf = prelookup(u_in, lut_x, num_points, ExtrapMethod.EXTRAP_CLIP)
            y_sim[i] = interpolate_1d(kf, lut_y)

        # Calcolo Errore
        residuals = y_real - y_sim
        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals**2))
        max_err = np.max(np.abs(residuals))

        self.lbl_sil_stats.setText(f"Risultati SIL:\nMAE: {mae:.4f} | RMSE: {rmse:.4f} | Errore Max: {max_err:.4f}")

        self.ax_val_main.clear()
        self.ax_val_err.clear()

        time = np.arange(len(u_val))

        self.ax_val_main.plot(time, y_real, label="Y Reale Misurata", color='gray', linewidth=2)
        self.ax_val_main.plot(time, y_sim, label="Y Simulata (LUT SIL)", color='blue', linestyle='--')
        self.ax_val_main.set_title("Validazione System Identification")
        self.ax_val_main.set_ylabel(y_real_col)
        self.ax_val_main.legend()
        self.ax_val_main.grid(True, linestyle=':', alpha=0.6)
        self.ax_val_main.tick_params(labelbottom=False)

        self.ax_val_err.plot(time, residuals, color='red', label="Residuo (Reale - Simulato)")
        self.ax_val_err.axhline(0, color='black', linewidth=1)
        self.ax_val_err.set_title("Analisi Residui")
        self.ax_val_err.set_xlabel("Campioni")
        self.ax_val_err.set_ylabel("Errore")
        self.ax_val_err.legend()
        self.ax_val_err.grid(True, linestyle=':', alpha=0.6)

        self.fig_val.tight_layout()
        self.canvas_val.draw()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = LUTGeneratorApp()
    window.show()
    sys.exit(app.exec_())