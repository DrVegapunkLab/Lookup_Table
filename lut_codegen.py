"""Utilities shared by the GUI and tests for typed C LUT generation.

The generated LUT keeps interpolation in floating point while allowing the input/
breakpoint storage and table storage to use the common fixed-width C numeric
types. Integer data is quantized with round-to-nearest and validated before C
code is emitted, so range overflow or collapsed breakpoints become explicit
errors instead of silent bad code.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple
import re

import numpy as np


@dataclass(frozen=True)
class CTypeSpec:
    key: str
    label: str
    c_type: str
    lut_enum: str
    size_bytes: int
    is_integer: bool
    is_unsigned: bool = False
    min_value: float = 0.0
    max_value: float = 0.0
    float_digits: int = 17


_TYPE_LIST = [
    CTypeSpec("float64", "double (64 bit)", "double", "LUT_TYPE_FLOAT64", 8, False, float_digits=17),
    CTypeSpec("float32", "float (32 bit)", "float", "LUT_TYPE_FLOAT32", 4, False, float_digits=9),
    CTypeSpec("int8", "int8_t", "int8_t", "LUT_TYPE_INT8", 1, True, False, -(2**7), 2**7 - 1),
    CTypeSpec("uint8", "uint8_t", "uint8_t", "LUT_TYPE_UINT8", 1, True, True, 0, 2**8 - 1),
    CTypeSpec("int16", "int16_t", "int16_t", "LUT_TYPE_INT16", 2, True, False, -(2**15), 2**15 - 1),
    CTypeSpec("uint16", "uint16_t", "uint16_t", "LUT_TYPE_UINT16", 2, True, True, 0, 2**16 - 1),
    CTypeSpec("int32", "int32_t", "int32_t", "LUT_TYPE_INT32", 4, True, False, -(2**31), 2**31 - 1),
    CTypeSpec("uint32", "uint32_t", "uint32_t", "LUT_TYPE_UINT32", 4, True, True, 0, 2**32 - 1),
    # Keep limits as Python ints. They are exactly checked before conversion.
    CTypeSpec("int64", "int64_t", "int64_t", "LUT_TYPE_INT64", 8, True, False, -(2**63), 2**63 - 1),
    CTypeSpec("uint64", "uint64_t", "uint64_t", "LUT_TYPE_UINT64", 8, True, True, 0, 2**64 - 1),
]

C_TYPE_SPECS: Dict[str, CTypeSpec] = {spec.key: spec for spec in _TYPE_LIST}
C_TYPE_ORDER = tuple(spec.key for spec in _TYPE_LIST)


def get_type_spec(type_key: str) -> CTypeSpec:
    try:
        return C_TYPE_SPECS[type_key]
    except KeyError as exc:
        raise ValueError(f"Tipo C non supportato: {type_key}") from exc


def type_key_from_label(label: str) -> str:
    for spec in _TYPE_LIST:
        if spec.label == label:
            return spec.key
    raise ValueError(f"Tipo C non riconosciuto: {label}")


def _as_finite_1d(values: Iterable[float], role: str) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{role}: atteso un array monodimensionale.")
    if arr.size == 0:
        raise ValueError(f"{role}: array vuoto.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{role}: sono presenti NaN o Inf.")
    return arr


def quantize_values(values: Iterable[float], type_key: str, role: str) -> np.ndarray:
    """Quantize numeric values exactly as the generated C storage type will.

    Integer types use round-to-nearest. Floating types are cast to float32 or
    float64 and checked again for finite results.
    """
    spec = get_type_spec(type_key)
    arr = _as_finite_1d(values, role)

    if spec.is_integer:
        rounded = np.rint(arr)
        # Compare in longdouble to avoid turning uint64 max into the same float
        # as 2**64 during the range check.
        values_ld = rounded.astype(np.longdouble)
        min_ld = np.longdouble(spec.min_value)
        max_ld = np.longdouble(spec.max_value)
        if np.any(values_ld < min_ld) or np.any(values_ld > max_ld):
            low = float(np.min(arr))
            high = float(np.max(arr))
            raise ValueError(
                f"{role}: valori [{low:.17g}, {high:.17g}] fuori range per {spec.c_type} "
                f"[{spec.min_value}, {spec.max_value}]."
            )
        # Object integers avoid precision loss for 64-bit unsigned literals.
        return np.array([int(v) for v in rounded], dtype=object)

    if type_key == "float32":
        with np.errstate(over="ignore", invalid="ignore"):
            quantized = arr.astype(np.float32)
        if not np.all(np.isfinite(quantized)):
            raise ValueError(f"{role}: uno o più valori non sono rappresentabili come float.")
        return quantized

    return arr.astype(np.float64)


def prepare_typed_lut_data(
    breakpoints: Iterable[float],
    table: Iterable[float],
    breakpoint_type: str,
    table_type: str,
) -> Tuple[np.ndarray, np.ndarray]:
    bp = quantize_values(breakpoints, breakpoint_type, "Breakpoint")
    tab = quantize_values(table, table_type, "Tabella")

    if len(bp) < 2:
        raise ValueError("Servono almeno 2 breakpoint.")
    if len(bp) != len(tab):
        raise ValueError("Breakpoint e tabella devono avere la stessa lunghezza.")

    bp_ld = np.array([np.longdouble(v) for v in bp], dtype=np.longdouble)
    if not np.all(np.diff(bp_ld) > 0):
        spec = get_type_spec(breakpoint_type)
        raise ValueError(
            f"La quantizzazione a {spec.c_type} rende due o più breakpoint uguali/non crescenti. "
            "Usa un tipo più preciso oppure riduci la densità dei breakpoint."
        )

    return bp, tab


def estimate_lut_bytes(num_points: int, breakpoint_type: str, table_type: str, is_pow2: bool) -> int:
    if num_points < 0:
        raise ValueError("num_points non può essere negativo.")
    bp_size = get_type_spec(breakpoint_type).size_bytes
    table_size = get_type_spec(table_type).size_bytes
    if is_pow2:
        # x_min + spacing in breakpoint type, inv_spacing as long double metadata
        # is accounted conservatively as 16 bytes to avoid optimistic GUI claims.
        return num_points * table_size + (2 * bp_size) + 16
    return num_points * (bp_size + table_size)


def sanitize_c_identifier(name: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not out:
        out = "lut"
    if out[0].isdigit():
        out = "lut_" + out
    return out.lower()


def _format_integer(value: int, spec: CTypeSpec) -> str:
    iv = int(value)
    if spec.key == "int64":
        if iv == -(2**63):
            return "INT64_MIN"
        return f"INT64_C({iv})"
    if spec.key == "uint64":
        return f"UINT64_C({iv})"
    return str(iv)


def format_c_value(value, type_key: str) -> str:
    spec = get_type_spec(type_key)
    if spec.is_integer:
        return _format_integer(int(value), spec)

    fv = float(value)
    if type_key == "float32":
        text = format(np.float32(fv).item(), f".{spec.float_digits}g")
        if "e" not in text.lower() and "." not in text:
            text += ".0"
        return text + "f"

    text = format(fv, f".{spec.float_digits}g")
    if "e" not in text.lower() and "." not in text:
        text += ".0"
    return text


def _format_array(values: np.ndarray, type_key: str) -> str:
    return ", ".join(format_c_value(v, type_key) for v in values)


def _require_pow2_metadata(x_data: np.ndarray, pow2_n: int, breakpoint_type: str):
    if len(x_data) < 2:
        raise ValueError("EvenPow2Spacing richiede almeno 2 punti.")

    dx = 2.0 ** int(pow2_n)
    x_min_q = quantize_values([float(x_data[0])], breakpoint_type, "x_min")[0]
    dx_q = quantize_values([dx], breakpoint_type, "spacing")[0]

    x_min_ld = np.longdouble(x_min_q)
    dx_ld = np.longdouble(dx_q)
    if dx_ld <= 0:
        spec = get_type_spec(breakpoint_type)
        raise ValueError(
            f"La spaziatura 2^{pow2_n}={dx:.17g} non è rappresentabile come valore positivo in {spec.c_type}."
        )

    # Integer spacing must be represented exactly; silently changing 0.5 to 0
    # or 1 would make prelookup disagree with the generated table.
    if get_type_spec(breakpoint_type).is_integer and dx_ld != np.longdouble(dx):
        spec = get_type_spec(breakpoint_type)
        raise ValueError(
            f"La spaziatura 2^{pow2_n}={dx:.17g} non è rappresentabile esattamente in {spec.c_type}. "
            "Scegli float/double oppure una spaziatura intera."
        )

    expected = x_min_ld + np.arange(len(x_data), dtype=np.longdouble) * dx_ld
    actual = np.asarray(x_data, dtype=np.longdouble)
    # The optimizer may have tiny floating point construction noise; tolerate a
    # few ulps but reject a genuinely non-uniform grid.
    atol = max(abs(float(dx)) * 1e-12, 1e-15)
    if not np.allclose(actual.astype(np.float64), expected.astype(np.float64), rtol=1e-12, atol=atol):
        raise ValueError("I breakpoint non formano una griglia EvenPow2Spacing coerente con 2^N.")

    return x_min_q, dx_q, 1.0 / float(dx_ld)


def generate_c_lut(
    base_name: str,
    breakpoints: Iterable[float],
    table: Iterable[float],
    breakpoint_type: str = "float64",
    table_type: str = "float64",
    is_pow2: bool = False,
    pow2_n: int = 0,
    extrapolation: str = "EXTRAP_CLIP",
    source_x_name: str = "X",
    source_y_name: str = "Y",
) -> str:
    """Generate a checked 1D C LUT using the typed C API."""
    if extrapolation not in ("EXTRAP_CLIP", "EXTRAP_LINEAR"):
        raise ValueError(f"Metodo di estrapolazione non valido: {extrapolation}")

    bp_spec = get_type_spec(breakpoint_type)
    tab_spec = get_type_spec(table_type)
    base = sanitize_c_identifier(base_name)

    # Quantize table always. Standard breakpoints are quantized directly; pow2
    # stores only x_min/spacing and therefore validates those metadata instead.
    source_bp = _as_finite_1d(breakpoints, "Breakpoint")
    source_tab = _as_finite_1d(table, "Tabella")
    if len(source_bp) != len(source_tab):
        raise ValueError("Breakpoint e tabella devono avere la stessa lunghezza.")
    if len(source_bp) < 2:
        raise ValueError("Servono almeno 2 punti LUT.")

    if is_pow2:
        table_q = quantize_values(source_tab, table_type, "Tabella")
        x_min_q, spacing_q, inv_spacing = _require_pow2_metadata(source_bp, pow2_n, breakpoint_type)
        bp_q = None
    else:
        bp_q, table_q = prepare_typed_lut_data(source_bp, source_tab, breakpoint_type, table_type)

    lines = []
    lines.append("/* ==========================================\n")
    lines.append(" * Generato da: Simulink LUT Suite\n")
    lines.append(f" * Asse X: {source_x_name}\n")
    lines.append(f" * Asse Y: {source_y_name}\n")
    lines.append(f" * Tipo breakpoint/input: {bp_spec.c_type}\n")
    lines.append(f" * Tipo tabella: {tab_spec.c_type}\n")
    lines.append(" * Interpolazione: long double interna, output API double\n")
    lines.append(" * ========================================== */\n\n")
    lines.append("#include <math.h>\n")
    lines.append("#include <stdint.h>\n")
    lines.append('#include "simulink_lookup.h"\n\n')
    lines.append("#ifndef LUT_SIZE\n")
    lines.append("#define LUT_SIZE(x) ((int)(sizeof(x) / sizeof((x)[0])))\n")
    lines.append("#endif\n\n")

    if is_pow2:
        lines.append(
            f"static const {bp_spec.c_type} {base}_x_min = "
            f"{format_c_value(x_min_q, breakpoint_type)};\n"
        )
        lines.append(
            f"static const {bp_spec.c_type} {base}_x_spacing = "
            f"{format_c_value(spacing_q, breakpoint_type)}; /* 2^{int(pow2_n)} */\n"
        )
        lines.append(f"static const long double {base}_inv_spacing = {inv_spacing:.21g}L;\n\n")
        lines.append(
            f"static const {tab_spec.c_type} {base}_table[] = {{\n    "
            f"{_format_array(table_q, table_type)}\n}};\n\n"
        )
    else:
        lines.append(
            f"static const {bp_spec.c_type} {base}_breakpoints[] = {{\n    "
            f"{_format_array(bp_q, breakpoint_type)}\n}};\n\n"
        )
        lines.append(
            f"static const {tab_spec.c_type} {base}_table[] = {{\n    "
            f"{_format_array(table_q, table_type)}\n}};\n\n"
        )

    lines.append(f"LutStatus {base}_eval_checked({bp_spec.c_type} input, double *output)\n")
    lines.append("{\n")
    lines.append("    PrelookupResult kf;\n")
    lines.append("    long double interpolated;\n")
    lines.append("    LutStatus status;\n\n")
    lines.append("    if (output == 0) return LUT_ERR_NULL_PTR;\n")

    if is_pow2:
        lines.append(
            "    status = prelookup_pow2_typed((long double)input, "
            f"(long double){base}_x_min, (long double){base}_x_spacing, {base}_inv_spacing, "
            f"LUT_SIZE({base}_table), {extrapolation}, &kf);\n"
        )
    else:
        lines.append(
            "    status = prelookup_typed((long double)input, "
            f"{base}_breakpoints, LUT_SIZE({base}_breakpoints), {bp_spec.lut_enum}, "
            f"{extrapolation}, &kf);\n"
        )

    lines.append("    if (status != LUT_OK) return status;\n")
    lines.append(
        f"    status = interpolate_1d_typed(kf, {base}_table, LUT_SIZE({base}_table), "
        f"{tab_spec.lut_enum}, &interpolated);\n"
    )
    lines.append("    if (status != LUT_OK) return status;\n")
    lines.append("    *output = (double)interpolated;\n")
    lines.append("    return LUT_OK;\n")
    lines.append("}\n\n")

    lines.append(f"double {base}_eval({bp_spec.c_type} input)\n")
    lines.append("{\n")
    lines.append("    double output = NAN;\n")
    lines.append(f"    (void){base}_eval_checked(input, &output);\n")
    lines.append("    return output;\n")
    lines.append("}\n")

    return "".join(lines)


def prepare_deployed_lut_data(
    breakpoints: Iterable[float],
    table: Iterable[float],
    breakpoint_type: str,
    table_type: str,
    is_pow2: bool = False,
    pow2_n: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return the effective numeric LUT that the generated C code will use."""
    source_bp = _as_finite_1d(breakpoints, "Breakpoint")
    source_tab = _as_finite_1d(table, "Tabella")
    if len(source_bp) != len(source_tab):
        raise ValueError("Breakpoint e tabella devono avere la stessa lunghezza.")
    if len(source_bp) < 2:
        raise ValueError("Servono almeno 2 punti LUT.")

    if not is_pow2:
        bp_q, tab_q = prepare_typed_lut_data(source_bp, source_tab, breakpoint_type, table_type)
        return (
            np.array([float(v) for v in bp_q], dtype=float),
            np.array([float(v) for v in tab_q], dtype=float),
        )

    tab_q = quantize_values(source_tab, table_type, "Tabella")
    x_min_q, spacing_q, _ = _require_pow2_metadata(source_bp, pow2_n, breakpoint_type)
    x_min = float(x_min_q)
    spacing = float(spacing_q)
    bp_effective = x_min + np.arange(len(source_bp), dtype=float) * spacing
    return bp_effective, np.array([float(v) for v in tab_q], dtype=float)
