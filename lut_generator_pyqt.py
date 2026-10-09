import sys
from enum import Enum
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy.optimize import least_squares

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QTextEdit, QMessageBox,
    QGroupBox, QFormLayout, QDoubleSpinBox, QCheckBox, QTabWidget, QSpinBox
)
from PyQt5.QtGui import QFontDatabase

from lut_codegen import (
    C_TYPE_ORDER,
    C_TYPE_SPECS,
    estimate_lut_bytes,
    generate_c_lut,
    prepare_deployed_lut_data,
    type_key_from_label,
)


# =====================================================================
# MOTORE SIL - Software-In-the-Loop
# =====================================================================

class ExtrapMethod(Enum):
    EXTRAP_CLIP = 0
    EXTRAP_LINEAR = 1


@dataclass
class PrelookupResult:
    k: int
    f: float


def read_csv_robust(filepath: str) -> pd.DataFrame:
    """Lettura CSV tollerante: prova separatore automatico e fallback comuni."""
    attempts = [
        {"sep": None, "engine": "python"},
        {"sep": ";"},
        {"sep": ","},
        {"sep": "\t"},
    ]

    last_error = None
    for kwargs in attempts:
        try:
            df = pd.read_csv(filepath, **kwargs)
            if df.shape[1] >= 1:
                df.columns = [str(c).strip() for c in df.columns]
                return df
        except Exception as exc:
            last_error = exc

    raise ValueError(f"Impossibile leggere il CSV: {last_error}")


def clean_numeric_xy(df: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError("Colonne selezionate non presenti nel dataset.")
    if x_col == y_col:
        raise ValueError("Le colonne X e Y devono essere diverse.")

    out = df[[x_col, y_col]].copy()
    out[x_col] = pd.to_numeric(out[x_col], errors="coerce")
    out[y_col] = pd.to_numeric(out[y_col], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan).dropna()

    if len(out) < 2:
        raise ValueError("Servono almeno 2 campioni numerici validi.")

    return out


def validate_lut_inputs(bp: np.ndarray, table: Optional[np.ndarray] = None):
    bp = np.asarray(bp, dtype=float)

    if bp.ndim != 1:
        raise ValueError("I breakpoint devono essere un array monodimensionale.")

    if len(bp) < 2:
        raise ValueError("Servono almeno 2 breakpoint.")

    if not np.all(np.isfinite(bp)):
        raise ValueError("I breakpoint contengono NaN o Inf.")

    if not np.all(np.diff(bp) > 0):
        raise ValueError("I breakpoint devono essere strettamente crescenti.")

    if table is not None:
        table = np.asarray(table, dtype=float)

        if table.ndim != 1:
            raise ValueError("La tabella deve essere monodimensionale.")

        if len(table) != len(bp):
            raise ValueError("Breakpoint e tabella devono avere la stessa lunghezza.")

        if not np.all(np.isfinite(table)):
            raise ValueError("La tabella contiene NaN o Inf.")


def prelookup(
    u: float,
    bp: np.ndarray,
    num_points: int,
    extrap_method: ExtrapMethod
) -> PrelookupResult:
    if num_points < 2:
        raise ValueError("num_points deve essere almeno 2.")

    if not np.isfinite(u):
        raise ValueError("Input u non valido: NaN o Inf.")

    bp = np.asarray(bp, dtype=float)

    if len(bp) < num_points:
        raise ValueError("num_points è maggiore della lunghezza dei breakpoint.")

    if u <= bp[0]:
        k = 0
        denom = bp[1] - bp[0]
        f = 0.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - bp[0]) / denom

    elif u >= bp[num_points - 1]:
        k = num_points - 2
        denom = bp[k + 1] - bp[k]
        f = 1.0 if extrap_method == ExtrapMethod.EXTRAP_CLIP else (u - bp[k]) / denom

    else:
        k = np.searchsorted(bp[:num_points], u, side="right") - 1
        k = int(np.clip(k, 0, num_points - 2))
        denom = bp[k + 1] - bp[k]
        f = (u - bp[k]) / denom

    return PrelookupResult(k, float(f))


def prelookup_pow2(
    u: float,
    x_min: float,
    spacing: float,
    inv_spacing: float,
    num_points: int,
    extrap_method: ExtrapMethod
) -> PrelookupResult:
    if num_points < 2:
        raise ValueError("num_points deve essere almeno 2.")

    if spacing <= 0 or inv_spacing <= 0:
        raise ValueError("spacing e inv_spacing devono essere positivi.")

    if not np.isfinite(u):
        raise ValueError("Input u non valido: NaN o Inf.")

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
        k = int(np.floor(normalized))
        k = int(np.clip(k, 0, num_points - 2))
        f = normalized - k

    return PrelookupResult(k, float(f))


def interpolate_1d(kf: PrelookupResult, table: np.ndarray) -> float:
    table = np.asarray(table, dtype=float)

    if kf.k < 0 or kf.k + 1 >= len(table):
        raise IndexError("Indice LUT fuori range.")

    return float(table[kf.k] + kf.f * (table[kf.k + 1] - table[kf.k]))


def simulate_lut_vectorized(
    u: np.ndarray,
    x_lut: np.ndarray,
    y_lut: np.ndarray,
    extrap_method: ExtrapMethod
) -> np.ndarray:
    validate_lut_inputs(x_lut, y_lut)

    u = np.asarray(u, dtype=float)

    if extrap_method == ExtrapMethod.EXTRAP_CLIP:
        u_eval = np.clip(u, x_lut[0], x_lut[-1])
        return np.interp(u_eval, x_lut, y_lut)

    y = np.interp(u, x_lut, y_lut)

    left_mask = u < x_lut[0]
    right_mask = u > x_lut[-1]

    if np.any(left_mask):
        slope_left = (y_lut[1] - y_lut[0]) / (x_lut[1] - x_lut[0])
        y[left_mask] = y_lut[0] + slope_left * (u[left_mask] - x_lut[0])

    if np.any(right_mask):
        slope_right = (y_lut[-1] - y_lut[-2]) / (x_lut[-1] - x_lut[-2])
        y[right_mask] = y_lut[-1] + slope_right * (u[right_mask] - x_lut[-1])

    return y


# =====================================================================
# IDENTIFICAZIONE LUT
# =====================================================================

def identify_lut_by_binning(u: np.ndarray, y: np.ndarray, n_points: int):
    df = pd.DataFrame({"u": u, "y": y})
    df["u"] = pd.to_numeric(df["u"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    if len(df) < 2:
        raise ValueError("Dataset insufficiente per identificazione.")

    bins = pd.cut(df["u"], bins=n_points)
    lut_df = df.groupby(bins, observed=False).mean().dropna()

    x = lut_df["u"].to_numpy(dtype=float)
    y_lut = lut_df["y"].to_numpy(dtype=float)

    validate_lut_inputs(x, y_lut)
    return x, y_lut


def estimate_lut_xy_from_data(
    u: np.ndarray,
    y_meas: np.ndarray,
    n_points: int,
    extrap_method: ExtrapMethod = ExtrapMethod.EXTRAP_CLIP
):
    u = np.asarray(u, dtype=float)
    y_meas = np.asarray(y_meas, dtype=float)

    mask = np.isfinite(u) & np.isfinite(y_meas)
    u = u[mask]
    y_meas = y_meas[mask]

    if len(u) < max(2, n_points):
        raise ValueError("Troppi breakpoint rispetto ai dati disponibili.")

    if n_points < 2:
        raise ValueError("Servono almeno 2 breakpoint.")

    u_min = float(np.min(u))
    u_max = float(np.max(u))

    if not np.isfinite(u_min) or not np.isfinite(u_max) or u_max <= u_min:
        raise ValueError("Range input non valido.")

    x0 = np.linspace(u_min, u_max, n_points)

    df_init = (
        pd.DataFrame({"u": u, "y": y_meas})
        .sort_values("u")
        .groupby("u", as_index=False)
        .mean()
    )

    y0 = np.interp(x0, df_init["u"].values, df_init["y"].values)

    deltas0 = np.diff(x0)
    log_deltas0 = np.log(np.maximum(deltas0, 1e-9))

    p0 = np.concatenate([
        [x0[0]],
        log_deltas0,
        y0
    ])

    # Bounds:
    # x_start resta nel range dati.
    # le distanze sono positive via exp(log_delta), ma limitiamo per robustezza numerica.
    y_pad = max(1.0, float(np.nanstd(y_meas)) * 10.0)
    y_low = float(np.nanmin(y_meas) - y_pad)
    y_high = float(np.nanmax(y_meas) + y_pad)

    lower = np.concatenate([
        [u_min],
        np.full(n_points - 1, np.log((u_max - u_min) * 1e-9)),
        np.full(n_points, y_low)
    ])

    upper = np.concatenate([
        [u_max],
        np.full(n_points - 1, np.log((u_max - u_min) * 2.0)),
        np.full(n_points, y_high)
    ])

    def unpack_params(p):
        x_start = p[0]
        log_deltas = p[1:n_points]
        y_lut = p[n_points:]

        deltas = np.exp(log_deltas)
        x_lut = x_start + np.concatenate([[0.0], np.cumsum(deltas)])

        return x_lut, y_lut

    def residuals(p):
        x_lut, y_lut = unpack_params(p)

        # Penalità se l'ultimo breakpoint esce troppo dal range utile.
        penalty = []
        if x_lut[-1] < u_max:
            penalty.append((u_max - x_lut[-1]) * 10.0)
        if x_lut[0] > u_min:
            penalty.append((x_lut[0] - u_min) * 10.0)

        y_sim = simulate_lut_vectorized(u, x_lut, y_lut, extrap_method)
        res = y_sim - y_meas

        if penalty:
            res = np.concatenate([res, np.asarray(penalty)])

        return res

    res = least_squares(
        residuals,
        p0,
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=1.0,
        max_nfev=3000,
        x_scale="jac"
    )

    x_est, y_est = unpack_params(res.x)

    # Ordina e ripulisce nel caso di minime anomalie numeriche.
    order = np.argsort(x_est)
    x_est = x_est[order]
    y_est = y_est[order]

    validate_lut_inputs(x_est, y_est)

    return x_est, y_est, res.cost, res.success


# =====================================================================
# OTTIMIZZAZIONE LUT
# =====================================================================

def simplify_curve_rdp(x: np.ndarray, y: np.ndarray, tol: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    validate_lut_inputs(x, y)

    if tol < 0:
        raise ValueError("La tolleranza deve essere >= 0.")

    keep = np.zeros(len(x), dtype=bool)
    keep[0] = True
    keep[-1] = True

    stack = [(0, len(x) - 1)]

    while stack:
        start, end = stack.pop()

        if end <= start + 1:
            continue

        y_interp = np.interp(x[start:end + 1], [x[start], x[end]], [y[start], y[end]])
        err = np.abs(y[start:end + 1] - y_interp)

        idx_rel = int(np.argmax(err))
        max_err = float(err[idx_rel])

        if max_err > tol:
            idx_abs = start + idx_rel
            keep[idx_abs] = True
            stack.append((start, idx_abs))
            stack.append((idx_abs, end))

    return keep


# =====================================================================
# APPLICAZIONE GUI PRINCIPALE
# =====================================================================

class LUTGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulink LUT Suite - Optimizer, Validator & Identifier")
        self.resize(1300, 850)

        self.df = None
        self.val_df = None
        self.time_df = None

        self.opt_x = None
        self.opt_y = None
        self.is_pow2 = False
        self.pow2_N = 0

        self.identified_x = None
        self.identified_y = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_ident = QWidget()
        self.tab_opt = QWidget()
        self.tab_val = QWidget()

        self.tabs.addTab(self.tab_ident, "1. Identificazione")
        self.tabs.addTab(self.tab_opt, "2. Ottimizzatore & C Gen")
        self.tabs.addTab(self.tab_val, "3. Validazione SIL")

        self.setup_ident_tab()
        self.setup_opt_tab()
        self.setup_val_tab()

        self.combo_extrap_c.currentIndexChanged.connect(self.combo_val_extrap.setCurrentIndex)

    # -----------------------------------------------------------------
    # TAB 1
    # -----------------------------------------------------------------

    def setup_ident_tab(self):
        layout = QHBoxLayout(self.tab_ident)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        g1 = QGroupBox("1. Carica Log Temporale")
        l1 = QVBoxLayout()
        self.btn_load_time = QPushButton("Sfoglia Log CSV...")
        self.btn_load_time.clicked.connect(self.load_time_csv)
        self.lbl_file_time = QLabel("Nessun file selezionato")
        l1.addWidget(self.btn_load_time)
        l1.addWidget(self.lbl_file_time)
        g1.setLayout(l1)
        left_layout.addWidget(g1)

        g2 = QGroupBox("2. Configurazione Canali")
        f2 = QFormLayout()
        self.c_x = QComboBox()
        self.c_y = QComboBox()
        f2.addRow("Asse X / Input:", self.c_x)
        f2.addRow("Asse Y / Output target:", self.c_y)
        g2.setLayout(f2)
        left_layout.addWidget(g2)

        g3 = QGroupBox("3. Identificazione LUT")
        f3 = QFormLayout()

        self.combo_ident_method = QComboBox()
        self.combo_ident_method.addItems([
            "Media per bin",
            "Least Squares: stima X e Y"
        ])

        self.s_bins = QSpinBox()
        self.s_bins.setRange(2, 1000)
        self.s_bins.setValue(50)

        self.btn_run_ident = QPushButton("Estrai / Stima LUT")
        self.btn_run_ident.clicked.connect(self.run_identification)

        f3.addRow("Metodo:", self.combo_ident_method)
        f3.addRow("Numero breakpoint:", self.s_bins)
        f3.addRow(self.btn_run_ident)

        g3.setLayout(f3)
        left_layout.addWidget(g3)

        self.btn_send_to_opt = QPushButton("Invia LUT all'Ottimizzatore →")
        self.btn_send_to_opt.setEnabled(False)
        self.btn_send_to_opt.setStyleSheet("font-weight: bold; padding: 10px;")
        self.btn_send_to_opt.clicked.connect(self.send_to_optimizer)
        left_layout.addWidget(self.btn_send_to_opt)

        left_layout.addStretch()

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
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona Log CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not filepath:
            return

        try:
            self.time_df = read_csv_robust(filepath)
            self.lbl_file_time.setText(filepath.split("/")[-1])

            cols = self.time_df.columns.tolist()

            self.c_x.clear()
            self.c_y.clear()
            self.c_x.addItems(cols)
            self.c_y.addItems(cols)

            if len(cols) >= 2:
                self.c_y.setCurrentIndex(1)

            self.btn_send_to_opt.setEnabled(False)
            self.identified_x = None
            self.identified_y = None

        except Exception as e:
            QMessageBox.critical(self, "Errore di Lettura", str(e))

    def run_identification(self):
        if self.time_df is None:
            QMessageBox.warning(self, "Attenzione", "Carica prima un log temporale CSV.")
            return

        cx = self.c_x.currentText()
        cy = self.c_y.currentText()

        try:
            if not cx or not cy:
                raise ValueError("Seleziona le colonne X e Y.")

            df = clean_numeric_xy(self.time_df, cx, cy)

            n_bp = self.s_bins.value()
            method = self.combo_ident_method.currentText()

            if method == "Media per bin":
                self.identified_x, self.identified_y = identify_lut_by_binning(
                    df[cx].values,
                    df[cy].values,
                    n_bp
                )
                status_text = ""

            else:
                self.identified_x, self.identified_y, cost, ok = estimate_lut_xy_from_data(
                    df[cx].values,
                    df[cy].values,
                    n_bp,
                    extrap_method=ExtrapMethod.EXTRAP_CLIP
                )

                status_text = f"\nCost: {cost:.6g} | Convergenza: {'OK' if ok else 'non garantita'}"

                if not ok:
                    QMessageBox.warning(
                        self,
                        "Attenzione",
                        "L'ottimizzazione è terminata, ma il solver non ha dichiarato piena convergenza."
                    )

            validate_lut_inputs(self.identified_x, self.identified_y)

            y_fit = simulate_lut_vectorized(
                df[cx].values,
                self.identified_x,
                self.identified_y,
                ExtrapMethod.EXTRAP_CLIP
            )
            residuals = df[cy].values - y_fit
            rmse = np.sqrt(np.mean(residuals ** 2))
            mae = np.mean(np.abs(residuals))

            self.ax_id.clear()
            self.ax_id.scatter(
                df[cx],
                df[cy],
                alpha=0.1,
                s=2,
                label="Dati temporali grezzi",
                color="gray"
            )

            self.ax_id.plot(
                self.identified_x,
                self.identified_y,
                "r-o",
                label=f"LUT identificata ({method}, {len(self.identified_x)} punti)",
                markersize=4
            )

            self.ax_id.set_xlabel(cx)
            self.ax_id.set_ylabel(cy)
            self.ax_id.set_title(f"Identificazione LUT | MAE={mae:.4g}, RMSE={rmse:.4g}{status_text}")
            self.ax_id.legend()
            self.ax_id.grid(True, linestyle=":", alpha=0.6)
            self.fig_id.tight_layout()
            self.canvas_id.draw()

            self.btn_send_to_opt.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Errore Identificazione", str(e))

    def send_to_optimizer(self):
        if self.identified_x is None or self.identified_y is None:
            QMessageBox.warning(self, "Attenzione", "Prima identifica una LUT.")
            return

        col_x = self.c_x.currentText()
        col_y = self.c_y.currentText()

        self.df = pd.DataFrame({
            col_x: self.identified_x,
            col_y: self.identified_y
        })

        self.combo_x.blockSignals(True)
        self.combo_y.blockSignals(True)

        self.combo_x.clear()
        self.combo_x.addItems(self.df.columns)

        self.combo_y.clear()
        self.combo_y.addItems(self.df.columns)

        if len(self.df.columns) >= 2:
            self.combo_y.setCurrentIndex(1)

        self.combo_x.blockSignals(False)
        self.combo_y.blockSignals(False)

        self.set_opt_controls_enabled(True)
        self.lbl_file.setText("Dati importati da Identificazione")

        self.on_variables_changed()
        self.tabs.setCurrentIndex(1)

    # -----------------------------------------------------------------
    # TAB 2
    # -----------------------------------------------------------------

    def setup_opt_tab(self):
        main_layout = QHBoxLayout(self.tab_opt)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        g_file = QGroupBox("1. Carica Curva di Riferimento")
        l_file = QVBoxLayout()

        self.btn_load = QPushButton("Sfoglia CSV Statico...")
        self.btn_load.clicked.connect(self.load_opt_csv)

        self.lbl_file = QLabel("Nessun file selezionato")

        l_file.addWidget(self.btn_load)
        l_file.addWidget(self.lbl_file)

        g_file.setLayout(l_file)
        left_layout.addWidget(g_file)

        g_cols = QGroupBox("2. Assegnazione Colonne")
        f_cols = QFormLayout()

        self.combo_x = QComboBox()
        self.combo_y = QComboBox()

        f_cols.addRow("Asse X / Input:", self.combo_x)
        f_cols.addRow("Asse Y / Target:", self.combo_y)

        g_cols.setLayout(f_cols)
        left_layout.addWidget(g_cols)

        g_opt = QGroupBox("3. Ottimizzatore Memoria e CPU")
        f_opt = QFormLayout()

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setDecimals(6)
        self.spin_tol.setSingleStep(0.005)
        self.spin_tol.setValue(0.01)
        self.spin_tol.setMinimum(0.0)
        self.spin_tol.setMaximum(1e9)

        self.chk_pow2 = QCheckBox("Usa spaziatura EvenPow2Spacing O(1)")

        self.combo_extrap_c = QComboBox()
        self.combo_extrap_c.addItems([
            "Clip (EXTRAP_CLIP)",
            "Lineare (EXTRAP_LINEAR)"
        ])

        self.combo_bp_type = QComboBox()
        self.combo_table_type = QComboBox()
        type_labels = [C_TYPE_SPECS[key].label for key in C_TYPE_ORDER]
        self.combo_bp_type.addItems(type_labels)
        self.combo_table_type.addItems(type_labels)

        self.btn_optimize = QPushButton("Ottimizza LUT")
        self.btn_optimize.clicked.connect(self.optimize_lut)

        self.lbl_memory = QLabel("Punti: 0 → 0")

        f_opt.addRow("Tolleranza max errore:", self.spin_tol)
        f_opt.addRow("Estrapolazione:", self.combo_extrap_c)
        f_opt.addRow("Tipo input / breakpoint:", self.combo_bp_type)
        f_opt.addRow("Tipo tabella:", self.combo_table_type)
        f_opt.addRow("", self.chk_pow2)
        f_opt.addRow(self.btn_optimize)
        f_opt.addRow(self.lbl_memory)

        g_opt.setLayout(f_opt)
        left_layout.addWidget(g_opt)

        g_code = QGroupBox("4. Codice C Generato")
        l_code = QVBoxLayout()

        self.btn_generate = QPushButton("Genera Codice C")
        self.btn_generate.clicked.connect(self.generate_code)

        self.text_code = QTextEdit()
        self.text_code.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text_code.setReadOnly(True)

        l_code.addWidget(self.btn_generate)
        l_code.addWidget(self.text_code)

        g_code.setLayout(l_code)
        left_layout.addWidget(g_code)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.fig_opt, (self.ax_opt_main, self.ax_opt_err) = plt.subplots(
            2,
            1,
            gridspec_kw={"height_ratios": [3, 1]}
        )

        self.canvas_opt = FigureCanvas(self.fig_opt)
        self.toolbar_opt = NavigationToolbar(self.canvas_opt, self)

        right_layout.addWidget(self.toolbar_opt)
        right_layout.addWidget(self.canvas_opt)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        self.combo_x.currentIndexChanged.connect(self.on_variables_changed)
        self.combo_y.currentIndexChanged.connect(self.on_variables_changed)
        self.chk_pow2.stateChanged.connect(self.on_variables_changed)
        self.combo_bp_type.currentIndexChanged.connect(self.on_codegen_type_changed)
        self.combo_table_type.currentIndexChanged.connect(self.on_codegen_type_changed)

        self.set_opt_controls_enabled(False)

    def set_opt_controls_enabled(self, state: bool):
        self.combo_x.setEnabled(state)
        self.combo_y.setEnabled(state)
        self.spin_tol.setEnabled(state)
        self.chk_pow2.setEnabled(state)
        self.combo_extrap_c.setEnabled(state)
        self.combo_bp_type.setEnabled(state)
        self.combo_table_type.setEnabled(state)
        self.btn_optimize.setEnabled(state)
        self.btn_generate.setEnabled(state)

    def get_selected_c_types(self):
        bp_type = type_key_from_label(self.combo_bp_type.currentText())
        table_type = type_key_from_label(self.combo_table_type.currentText())
        return bp_type, table_type

    def update_memory_label(self):
        if self.df is None:
            return

        orig_x, _, _, _ = self.get_clean_data()
        bp_type, table_type = self.get_selected_c_types()
        original_bytes = estimate_lut_bytes(len(orig_x), bp_type, table_type, False)

        if self.opt_y is not None:
            optimized_bytes = estimate_lut_bytes(len(self.opt_y), bp_type, table_type, self.is_pow2)
            optimized_points = len(self.opt_y)
        else:
            optimized_bytes = original_bytes
            optimized_points = len(orig_x)

        reduction = 100 * (1 - optimized_bytes / original_bytes) if original_bytes > 0 else 0.0
        self.lbl_memory.setText(
            f"ROM stimata: {original_bytes} B → {optimized_bytes} B | "
            f"Punti: {len(orig_x)} → {optimized_points} | "
            f"Risparmio: {reduction:.1f}%"
        )

    def on_codegen_type_changed(self):
        self.text_code.clear()
        if self.df is None:
            return

        try:
            self.update_memory_label()
            x_data, y_data, _, _ = self.get_clean_data()
            if self.opt_x is not None and self.opt_y is not None:
                x_data, y_data = self.opt_x, self.opt_y
            bp_type, table_type = self.get_selected_c_types()
            prepare_deployed_lut_data(
                x_data, y_data, bp_type, table_type, self.is_pow2, self.pow2_N
            )
            if self.opt_x is not None and self.opt_y is not None:
                self.plot_opt_data()
            if hasattr(self, "ax_val_main"):
                self.ax_val_main.clear()
                self.ax_val_err.clear()
                self.lbl_sil_stats.setText("Tipo C cambiato. Riesegui la simulazione.")
                self.canvas_val.draw()
        except Exception as exc:
            self.lbl_memory.setText(f"Tipo C non compatibile con questa LUT: {exc}")

    def load_opt_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona CSV Curva Riferimento",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not filepath:
            return

        try:
            self.df = read_csv_robust(filepath)
            self.lbl_file.setText(filepath.split("/")[-1])

            cols = self.df.columns.tolist()

            self.combo_x.blockSignals(True)
            self.combo_y.blockSignals(True)

            self.combo_x.clear()
            self.combo_x.addItems(cols)

            self.combo_y.clear()
            self.combo_y.addItems(cols)

            if len(cols) >= 2:
                self.combo_y.setCurrentIndex(1)

            self.combo_x.blockSignals(False)
            self.combo_y.blockSignals(False)

            self.set_opt_controls_enabled(True)
            self.on_variables_changed()

        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def on_variables_changed(self):
        if self.df is None:
            return

        self.opt_x = None
        self.opt_y = None
        self.is_pow2 = False
        self.pow2_N = 0

        self.text_code.clear()
        self.lbl_memory.setText("Ottimizzazione resettata.")

        self.ax_opt_main.clear()
        self.ax_opt_err.clear()
        self.canvas_opt.draw()

        if hasattr(self, "ax_val_main"):
            self.ax_val_main.clear()
            self.ax_val_err.clear()
            self.lbl_sil_stats.setText("Modello cambiato. Riesegui la simulazione.")
            self.canvas_val.draw()

    def get_clean_data(self):
        if self.df is None:
            raise ValueError("Nessun dataset caricato.")

        cx = self.combo_x.currentText()
        cy = self.combo_y.currentText()

        if not cx or not cy:
            raise ValueError("Seleziona le colonne X e Y.")

        df_c = clean_numeric_xy(self.df, cx, cy)
        df_c = (
            df_c
            .sort_values(by=cx)
            .groupby(cx, as_index=False)
            .mean()
        )

        x_vals = df_c[cx].to_numpy(dtype=float)
        y_vals = df_c[cy].to_numpy(dtype=float)

        validate_lut_inputs(x_vals, y_vals)

        return x_vals, y_vals, cx, cy

    def optimize_lut(self):
        if self.df is None:
            QMessageBox.warning(self, "Attenzione", "Carica prima una curva di riferimento.")
            return

        try:
            orig_x, orig_y, _, _ = self.get_clean_data()
            tol = float(self.spin_tol.value())

            if self.chk_pow2.isChecked():
                x_min = float(orig_x[0])
                x_max = float(orig_x[-1])

                best_N = None
                best_opt_x = None
                best_opt_y = None

                for N in range(20, -31, -1):
                    dx = 2.0 ** N

                    if dx <= 0:
                        continue

                    num_int = int(np.ceil((x_max - x_min) / dx))

                    if num_int < 1:
                        continue

                    if num_int > 1_000_000:
                        continue

                    opt_x = x_min + np.arange(num_int + 1, dtype=float) * dx

                    # Deve rimanere una griglia perfettamente uniforme: mai appendere x_max
                    # come punto non allineato, altrimenti il C EvenPow2Spacing sarebbe errato.
                    while opt_x[-1] < x_max:
                        opt_x = x_min + np.arange(len(opt_x) + 1, dtype=float) * dx

                    opt_y = np.interp(opt_x, orig_x, orig_y)
                    y_test = np.interp(orig_x, opt_x, opt_y)

                    max_err = float(np.max(np.abs(orig_y - y_test)))

                    if max_err <= tol:
                        best_N = N
                        best_opt_x = opt_x
                        best_opt_y = opt_y
                        break

                if best_N is None:
                    QMessageBox.warning(
                        self,
                        "Attenzione",
                        "Impossibile trovare una spaziatura 2^N entro la tolleranza."
                    )
                    return

                self.opt_x = best_opt_x
                self.opt_y = best_opt_y
                self.is_pow2 = True
                self.pow2_N = best_N

            else:
                keep = simplify_curve_rdp(orig_x, orig_y, tol)
                self.opt_x = orig_x[keep]
                self.opt_y = orig_y[keep]
                self.is_pow2 = False

            validate_lut_inputs(self.opt_x, self.opt_y)

            # Verifica subito che il tipo C selezionato possa rappresentare la LUT
            # ottimizzata: overflow, unsigned con valori negativi e breakpoint
            # collassati vengono mostrati come errori espliciti nella GUI.
            bp_type, table_type = self.get_selected_c_types()
            prepare_deployed_lut_data(
                self.opt_x, self.opt_y, bp_type, table_type, self.is_pow2, self.pow2_N
            )
            self.update_memory_label()

            self.plot_opt_data()

        except Exception as e:
            QMessageBox.critical(self, "Errore di Ottimizzazione", str(e))

    def plot_opt_data(self):
        try:
            orig_x, orig_y, cx, cy = self.get_clean_data()

            self.ax_opt_main.clear()
            self.ax_opt_err.clear()

            self.ax_opt_main.plot(
                orig_x,
                orig_y,
                label="Dati riferimento",
                color="lightgray",
                linestyle="--",
                marker=".",
                markersize=2
            )

            if self.opt_x is not None and self.opt_y is not None:
                bp_type, table_type = self.get_selected_c_types()
                deployed_x, deployed_y = prepare_deployed_lut_data(
                    self.opt_x, self.opt_y, bp_type, table_type, self.is_pow2, self.pow2_N
                )
                lbl_base = (
                    f"EvenPow2Spacing dx={2.0 ** self.pow2_N:.6g}"
                    if self.is_pow2
                    else "RDP / Greedy robusto"
                )
                lbl = (
                    f"{lbl_base} | {C_TYPE_SPECS[bp_type].c_type} / "
                    f"{C_TYPE_SPECS[table_type].c_type}"
                )

                self.ax_opt_main.plot(
                    deployed_x,
                    deployed_y,
                    label=lbl,
                    color="blue",
                    marker="o",
                    markersize=4
                )

                # L'errore visualizzato include anche la quantizzazione del tipo C.
                y_interp = np.interp(orig_x, deployed_x, deployed_y)
                err = orig_y - y_interp

                self.ax_opt_err.plot(orig_x, err, color="red")
                self.ax_opt_err.fill_between(orig_x, err, 0, color="red", alpha=0.3)

                tol = float(self.spin_tol.value())
                self.ax_opt_err.axhline(tol, color="black", linestyle=":", alpha=0.5)
                self.ax_opt_err.axhline(-tol, color="black", linestyle=":", alpha=0.5)

                y_max = max(float(np.max(np.abs(err))), tol, 1e-12) * 1.5
                self.ax_opt_err.set_ylim(-y_max, y_max)

            else:
                self.ax_opt_main.plot(orig_x, orig_y, label="Raw", color="blue")

            self.ax_opt_main.set_title(f"LUT Design: {cy} vs {cx}")
            self.ax_opt_main.legend()
            self.ax_opt_main.grid(True, linestyle=":", alpha=0.6)

            self.ax_opt_err.set_title("Errore di Interpolazione")
            self.ax_opt_err.grid(True, linestyle=":", alpha=0.6)

            self.fig_opt.tight_layout()
            self.canvas_opt.draw()

        except Exception as e:
            QMessageBox.critical(self, "Errore Plot", str(e))

    def generate_code(self):
        try:
            x_data, y_data, cx, cy = self.get_clean_data()

            if self.opt_x is not None and self.opt_y is not None:
                x_data = self.opt_x
                y_data = self.opt_y

            validate_lut_inputs(x_data, y_data)
            bp_type, table_type = self.get_selected_c_types()
            extrap_str = (
                "EXTRAP_LINEAR"
                if self.combo_extrap_c.currentIndex() == 1
                else "EXTRAP_CLIP"
            )

            # Questa chiamata quantizza e valida prima di emettere il C.
            # In questo modo il codice non viene generato se il tipo scelto
            # causa overflow, perdita di monotonicita' o spacing pow2 invalido.
            base_name = f"lut_{cy}_vs_{cx}"
            c_code = generate_c_lut(
                base_name=base_name,
                breakpoints=x_data,
                table=y_data,
                breakpoint_type=bp_type,
                table_type=table_type,
                is_pow2=self.is_pow2,
                pow2_n=self.pow2_N,
                extrapolation=extrap_str,
                source_x_name=cx,
                source_y_name=cy,
            )
            self.text_code.setPlainText(c_code)

        except Exception as e:
            QMessageBox.critical(self, "Errore di Generazione", str(e))

    # -----------------------------------------------------------------
    # TAB 3
    # -----------------------------------------------------------------

    def setup_val_tab(self):
        main_layout = QHBoxLayout(self.tab_val)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)

        g_file = QGroupBox("1. Carica Dati di Validazione Reali CSV")
        l_file = QVBoxLayout()

        self.btn_load_val = QPushButton("Sfoglia CSV Validazione...")
        self.btn_load_val.clicked.connect(self.load_val_csv)

        self.lbl_file_val = QLabel("Nessun file selezionato")

        l_file.addWidget(self.btn_load_val)
        l_file.addWidget(self.lbl_file_val)

        g_file.setLayout(l_file)
        left_layout.addWidget(g_file)

        g_cfg = QGroupBox("2. Assegnazione Segnali")
        f_cfg = QFormLayout()

        self.combo_val_u = QComboBox()
        self.combo_val_y = QComboBox()

        self.combo_val_extrap = QComboBox()
        self.combo_val_extrap.addItems([
            "Clip (EXTRAP_CLIP)",
            "Lineare (EXTRAP_LINEAR)"
        ])

        f_cfg.addRow("Segnale Input X:", self.combo_val_u)
        f_cfg.addRow("Output reale Y:", self.combo_val_y)
        f_cfg.addRow("Fuori range:", self.combo_val_extrap)

        g_cfg.setLayout(f_cfg)
        left_layout.addWidget(g_cfg)

        g_run = QGroupBox("3. Esecuzione Modello SIL")
        l_run = QVBoxLayout()

        self.btn_run_sil = QPushButton("Simula LUT su dati reali")
        self.btn_run_sil.clicked.connect(self.run_sil_simulation)

        self.lbl_sil_stats = QLabel("Statistiche di validazione appariranno qui.")

        l_run.addWidget(self.btn_run_sil)
        l_run.addWidget(self.lbl_sil_stats)

        g_run.setLayout(l_run)
        left_layout.addWidget(g_run)

        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.fig_val, (self.ax_val_main, self.ax_val_err) = plt.subplots(
            2,
            1,
            gridspec_kw={"height_ratios": [3, 1]}
        )

        self.canvas_val = FigureCanvas(self.fig_val)
        self.toolbar_val = NavigationToolbar(self.canvas_val, self)

        right_layout.addWidget(self.toolbar_val)
        right_layout.addWidget(self.canvas_val)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        self.set_val_controls_enabled(False)

    def set_val_controls_enabled(self, state: bool):
        self.combo_val_u.setEnabled(state)
        self.combo_val_y.setEnabled(state)
        self.combo_val_extrap.setEnabled(state)
        self.btn_run_sil.setEnabled(state)

    def load_val_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona CSV Validazione",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not filepath:
            return

        try:
            self.val_df = read_csv_robust(filepath)
            self.lbl_file_val.setText(filepath.split("/")[-1])

            cols = self.val_df.columns.tolist()

            self.combo_val_u.clear()
            self.combo_val_u.addItems(cols)

            self.combo_val_y.clear()
            self.combo_val_y.addItems(cols)

            if len(cols) >= 2:
                self.combo_val_y.setCurrentIndex(1)

            self.set_val_controls_enabled(True)
            self.combo_val_extrap.setCurrentIndex(self.combo_extrap_c.currentIndex())

        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def run_sil_simulation(self):
        if self.val_df is None or self.df is None:
            QMessageBox.warning(
                self,
                "Attenzione",
                "Carica sia i dati nel Tab 2 sia i dati di validazione nel Tab 3."
            )
            return

        try:
            u_col = self.combo_val_u.currentText()
            y_real_col = self.combo_val_y.currentText()

            if not u_col or not y_real_col:
                raise ValueError("Seleziona input e output di validazione.")

            clean_val_df = clean_numeric_xy(self.val_df, u_col, y_real_col)

            u_val = clean_val_df[u_col].to_numpy(dtype=float)
            y_real = clean_val_df[y_real_col].to_numpy(dtype=float)

            if len(y_real) == 0:
                raise ValueError("Il dataset di validazione è vuoto o contiene solo valori non validi.")

            if self.opt_x is not None and self.opt_y is not None:
                lut_x = self.opt_x
                lut_y = self.opt_y
            else:
                lut_x, lut_y, _, _ = self.get_clean_data()

            validate_lut_inputs(lut_x, lut_y)

            # Simula esattamente i dati che finiranno nel C dopo la quantizzazione
            # del tipo selezionato, non soltanto la LUT double in memoria Python.
            bp_type, table_type = self.get_selected_c_types()
            lut_x, lut_y = prepare_deployed_lut_data(
                lut_x, lut_y, bp_type, table_type, self.is_pow2, self.pow2_N
            )
            validate_lut_inputs(lut_x, lut_y)

            num_points = len(lut_y)
            y_sim = np.zeros_like(u_val, dtype=float)

            extrap_val = (
                ExtrapMethod.EXTRAP_LINEAR
                if self.combo_val_extrap.currentIndex() == 1
                else ExtrapMethod.EXTRAP_CLIP
            )

            if self.is_pow2:
                dx = float(lut_x[1] - lut_x[0])
                inv_dx = 1.0 / dx

                for i, u_in in enumerate(u_val):
                    kf = prelookup_pow2(u_in, lut_x[0], dx, inv_dx, num_points, extrap_val)
                    y_sim[i] = interpolate_1d(kf, lut_y)

            else:
                for i, u_in in enumerate(u_val):
                    kf = prelookup(u_in, lut_x, num_points, extrap_val)
                    y_sim[i] = interpolate_1d(kf, lut_y)

            residuals = y_real - y_sim

            mae = float(np.mean(np.abs(residuals)))
            rmse = float(np.sqrt(np.mean(residuals ** 2)))
            max_err = float(np.max(np.abs(residuals)))
            bias = float(np.mean(residuals))

            self.lbl_sil_stats.setText(
                "Risultati SIL:\n"
                f"MAE: {mae:.6g}\n"
                f"RMSE: {rmse:.6g}\n"
                f"Errore max: {max_err:.6g}\n"
                f"Bias medio: {bias:.6g}"
            )

            self.ax_val_main.clear()
            self.ax_val_err.clear()

            time = np.arange(len(u_val))

            self.ax_val_main.plot(
                time,
                y_real,
                label="Y reale misurata",
                color="gray",
                linewidth=2
            )

            self.ax_val_main.plot(
                time,
                y_sim,
                label="Y simulata LUT SIL",
                color="blue",
                linestyle="--"
            )

            self.ax_val_main.set_title("Validazione System Identification")
            self.ax_val_main.set_ylabel(y_real_col)
            self.ax_val_main.legend()
            self.ax_val_main.grid(True, linestyle=":", alpha=0.6)
            self.ax_val_main.tick_params(labelbottom=False)

            self.ax_val_err.plot(
                time,
                residuals,
                color="red",
                label="Residuo reale - simulato"
            )

            self.ax_val_err.axhline(0, color="black", linewidth=1)
            self.ax_val_err.set_title("Analisi Residui")
            self.ax_val_err.set_xlabel("Campioni")
            self.ax_val_err.set_ylabel("Errore")
            self.ax_val_err.legend()
            self.ax_val_err.grid(True, linestyle=":", alpha=0.6)

            self.fig_val.tight_layout()
            self.canvas_val.draw()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore nella Simulazione SIL",
                f"Impossibile completare la simulazione.\n\nDettaglio: {str(e)}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = LUTGeneratorApp()
    window.show()

    sys.exit(app.exec_())
