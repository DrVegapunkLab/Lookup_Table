#include "simulink_lookup.h"

#include <math.h>

/* =====================================================================
 * API storica double
 * ===================================================================== */

LutStatus validate_breakpoints(const double* bp, int num_points) {
    int i;

    if (bp == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;

    for (i = 0; i < num_points; ++i) {
        if (!isfinite(bp[i])) return LUT_ERR_NON_FINITE;
    }

    for (i = 0; i < num_points - 1; ++i) {
        if (!(bp[i + 1] > bp[i])) return LUT_ERR_NON_MONOTONIC;
    }

    return LUT_OK;
}

LutStatus validate_pow2_spacing(double spacing, double inv_spacing, int num_points) {
    if (num_points < 2) return LUT_ERR_SIZE;
    if (!isfinite(spacing) || !isfinite(inv_spacing)) return LUT_ERR_NON_FINITE;
    if (!(spacing > 0.0) || !(inv_spacing > 0.0)) return LUT_ERR_BAD_SPACING;
    return LUT_OK;
}

PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method) {
    PrelookupResult result;
    int k;
    double f;

    if (bp == 0 || num_points < 2 || !isfinite(u)) {
        result.k = 0;
        result.f = 0.0;
        return result;
    }

    if (u <= bp[0]) {
        k = 0;
        f = (extrap_method == EXTRAP_CLIP) ? 0.0 : (u - bp[0]) / (bp[1] - bp[0]);
    } else if (u >= bp[num_points - 1]) {
        k = num_points - 2;
        f = (extrap_method == EXTRAP_CLIP) ? 1.0 : (u - bp[k]) / (bp[k + 1] - bp[k]);
    } else {
        int low = 0;
        int high = num_points - 1;

        while (low < high - 1) {
            int mid = low + (high - low) / 2;
            if (u < bp[mid]) high = mid;
            else low = mid;
        }

        k = low;
        f = (u - bp[k]) / (bp[k + 1] - bp[k]);
    }

    result.k = k;
    result.f = f;
    return result;
}

PrelookupResult prelookup_pow2(
    double u,
    double x_min,
    double spacing,
    double inv_spacing,
    int num_points,
    ExtrapMethod extrap_method
) {
    PrelookupResult result;
    int k;
    double f;
    double x_max;

    if (num_points < 2 || spacing <= 0.0 || inv_spacing <= 0.0 ||
        !isfinite(u) || !isfinite(x_min) || !isfinite(spacing) || !isfinite(inv_spacing)) {
        result.k = 0;
        result.f = 0.0;
        return result;
    }

    x_max = x_min + (num_points - 1) * spacing;

    if (u <= x_min) {
        k = 0;
        f = (extrap_method == EXTRAP_CLIP) ? 0.0 : (u - x_min) * inv_spacing;
    } else if (u >= x_max) {
        k = num_points - 2;
        f = (extrap_method == EXTRAP_CLIP) ? 1.0 : (u - (x_min + k * spacing)) * inv_spacing;
    } else {
        double normalized = (u - x_min) * inv_spacing;
        k = (int)normalized;

        if (k < 0) k = 0;
        else if (k > num_points - 2) k = num_points - 2;

        f = normalized - (double)k;
    }

    result.k = k;
    result.f = f;
    return result;
}

double interpolate_1d(PrelookupResult kf, const double* table) {
    double y0;
    double y1;

    if (table == 0 || kf.k < 0 || !isfinite(kf.f)) return 0.0;

    y0 = table[kf.k];
    y1 = table[kf.k + 1];

    return y0 + kf.f * (y1 - y0);
}

double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols) {
    int row;
    int col;
    int idx_00;
    int idx_10;
    int idx_01;
    int idx_11;
    double z00;
    double z10;
    double z01;
    double z11;
    double z0;
    double z1;

    if (table == 0 || num_cols < 2) return 0.0;

    row = kf_row.k;
    col = kf_col.k;

    if (row < 0 || col < 0) return 0.0;

    idx_00 = row * num_cols + col;
    idx_10 = (row + 1) * num_cols + col;
    idx_01 = row * num_cols + (col + 1);
    idx_11 = (row + 1) * num_cols + (col + 1);

    z00 = table[idx_00];
    z10 = table[idx_10];
    z01 = table[idx_01];
    z11 = table[idx_11];

    z0 = z00 + kf_row.f * (z10 - z00);
    z1 = z01 + kf_row.f * (z11 - z01);

    return z0 + kf_col.f * (z1 - z0);
}

double lookup2d(
    double u_row,
    double u_col,
    const double* row_bp,
    int num_rows,
    const double* col_bp,
    int num_cols,
    const double* table,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap
) {
    PrelookupResult kr = prelookup(u_row, row_bp, num_rows, row_extrap);
    PrelookupResult kc = prelookup(u_col, col_bp, num_cols, col_extrap);
    return interpolate_2d(kr, kc, table, num_cols);
}

double lookup2d_row_pow2(
    double u_row,
    double u_col,
    double row_min,
    double row_spacing,
    double row_inv_spacing,
    int num_rows,
    const double* col_bp,
    int num_cols,
    const double* table,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap
) {
    PrelookupResult kr = prelookup_pow2(u_row, row_min, row_spacing, row_inv_spacing, num_rows, row_extrap);
    PrelookupResult kc = prelookup(u_col, col_bp, num_cols, col_extrap);
    return interpolate_2d(kr, kc, table, num_cols);
}

double lookup2d_col_pow2(
    double u_row,
    double u_col,
    const double* row_bp,
    int num_rows,
    double col_min,
    double col_spacing,
    double col_inv_spacing,
    int num_cols,
    const double* table,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap
) {
    PrelookupResult kr = prelookup(u_row, row_bp, num_rows, row_extrap);
    PrelookupResult kc = prelookup_pow2(u_col, col_min, col_spacing, col_inv_spacing, num_cols, col_extrap);
    return interpolate_2d(kr, kc, table, num_cols);
}

double lookup2d_pow2(
    double u_row,
    double u_col,
    double row_min,
    double row_spacing,
    double row_inv_spacing,
    int num_rows,
    double col_min,
    double col_spacing,
    double col_inv_spacing,
    int num_cols,
    const double* table,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap
) {
    PrelookupResult kr = prelookup_pow2(u_row, row_min, row_spacing, row_inv_spacing, num_rows, row_extrap);
    PrelookupResult kc = prelookup_pow2(u_col, col_min, col_spacing, col_inv_spacing, num_cols, col_extrap);
    return interpolate_2d(kr, kc, table, num_cols);
}

/* =====================================================================
 * API typed
 * ===================================================================== */

size_t lut_data_type_size(LutDataType type) {
    switch (type) {
        case LUT_TYPE_FLOAT32: return sizeof(float);
        case LUT_TYPE_FLOAT64: return sizeof(double);
        case LUT_TYPE_INT8: return sizeof(int8_t);
        case LUT_TYPE_UINT8: return sizeof(uint8_t);
        case LUT_TYPE_INT16: return sizeof(int16_t);
        case LUT_TYPE_UINT16: return sizeof(uint16_t);
        case LUT_TYPE_INT32: return sizeof(int32_t);
        case LUT_TYPE_UINT32: return sizeof(uint32_t);
        case LUT_TYPE_INT64: return sizeof(int64_t);
        case LUT_TYPE_UINT64: return sizeof(uint64_t);
        default: return 0U;
    }
}

const char* lut_status_string(LutStatus status) {
    switch (status) {
        case LUT_OK: return "LUT_OK";
        case LUT_ERR_NULL_PTR: return "LUT_ERR_NULL_PTR";
        case LUT_ERR_SIZE: return "LUT_ERR_SIZE";
        case LUT_ERR_NON_MONOTONIC: return "LUT_ERR_NON_MONOTONIC";
        case LUT_ERR_BAD_SPACING: return "LUT_ERR_BAD_SPACING";
        case LUT_ERR_BAD_TYPE: return "LUT_ERR_BAD_TYPE";
        case LUT_ERR_NON_FINITE: return "LUT_ERR_NON_FINITE";
        case LUT_ERR_INDEX: return "LUT_ERR_INDEX";
        default: return "LUT_ERR_UNKNOWN";
    }
}

static LutStatus read_typed_value(
    const void* data,
    size_t index,
    LutDataType type,
    long double* value
) {
    if (data == 0 || value == 0) return LUT_ERR_NULL_PTR;

    switch (type) {
        case LUT_TYPE_FLOAT32:
            *value = (long double)((const float*)data)[index];
            break;
        case LUT_TYPE_FLOAT64:
            *value = (long double)((const double*)data)[index];
            break;
        case LUT_TYPE_INT8:
            *value = (long double)((const int8_t*)data)[index];
            break;
        case LUT_TYPE_UINT8:
            *value = (long double)((const uint8_t*)data)[index];
            break;
        case LUT_TYPE_INT16:
            *value = (long double)((const int16_t*)data)[index];
            break;
        case LUT_TYPE_UINT16:
            *value = (long double)((const uint16_t*)data)[index];
            break;
        case LUT_TYPE_INT32:
            *value = (long double)((const int32_t*)data)[index];
            break;
        case LUT_TYPE_UINT32:
            *value = (long double)((const uint32_t*)data)[index];
            break;
        case LUT_TYPE_INT64:
            *value = (long double)((const int64_t*)data)[index];
            break;
        case LUT_TYPE_UINT64:
            *value = (long double)((const uint64_t*)data)[index];
            break;
        default:
            return LUT_ERR_BAD_TYPE;
    }

    if (!isfinite(*value)) return LUT_ERR_NON_FINITE;
    return LUT_OK;
}

LutStatus validate_breakpoints_typed(const void* bp, int num_points, LutDataType type) {
    int i;
    long double prev;
    long double current;
    LutStatus status;

    if (bp == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;
    if (lut_data_type_size(type) == 0U) return LUT_ERR_BAD_TYPE;

    status = read_typed_value(bp, 0U, type, &prev);
    if (status != LUT_OK) return status;

    for (i = 1; i < num_points; ++i) {
        status = read_typed_value(bp, (size_t)i, type, &current);
        if (status != LUT_OK) return status;
        if (!(current > prev)) return LUT_ERR_NON_MONOTONIC;
        prev = current;
    }

    return LUT_OK;
}

LutStatus prelookup_typed(
    long double u,
    const void* bp,
    int num_points,
    LutDataType bp_type,
    ExtrapMethod extrap_method,
    PrelookupResult* result
) {
    int k;
    long double first;
    long double last;
    long double lower;
    long double upper;
    long double f;
    LutStatus status;

    if (result == 0 || bp == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;
    if (lut_data_type_size(bp_type) == 0U) return LUT_ERR_BAD_TYPE;
    if (!isfinite(u)) return LUT_ERR_NON_FINITE;

    status = read_typed_value(bp, 0U, bp_type, &first);
    if (status != LUT_OK) return status;
    status = read_typed_value(bp, (size_t)(num_points - 1), bp_type, &last);
    if (status != LUT_OK) return status;

    if (u <= first) {
        k = 0;
    } else if (u >= last) {
        k = num_points - 2;
    } else {
        int low = 0;
        int high = num_points - 1;

        while (low < high - 1) {
            int mid = low + (high - low) / 2;
            long double mid_value;
            status = read_typed_value(bp, (size_t)mid, bp_type, &mid_value);
            if (status != LUT_OK) return status;
            if (u < mid_value) high = mid;
            else low = mid;
        }
        k = low;
    }

    status = read_typed_value(bp, (size_t)k, bp_type, &lower);
    if (status != LUT_OK) return status;
    status = read_typed_value(bp, (size_t)(k + 1), bp_type, &upper);
    if (status != LUT_OK) return status;
    if (!(upper > lower)) return LUT_ERR_NON_MONOTONIC;

    if (u <= first && extrap_method == EXTRAP_CLIP) {
        f = 0.0L;
    } else if (u >= last && extrap_method == EXTRAP_CLIP) {
        f = 1.0L;
    } else {
        f = (u - lower) / (upper - lower);
    }

    if (!isfinite(f)) return LUT_ERR_NON_FINITE;
    result->k = k;
    result->f = (double)f;
    return LUT_OK;
}

LutStatus prelookup_pow2_typed(
    long double u,
    long double x_min,
    long double spacing,
    long double inv_spacing,
    int num_points,
    ExtrapMethod extrap_method,
    PrelookupResult* result
) {
    int k;
    long double f;
    long double x_max;

    if (result == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;
    if (!isfinite(u) || !isfinite(x_min) || !isfinite(spacing) || !isfinite(inv_spacing)) {
        return LUT_ERR_NON_FINITE;
    }
    if (!(spacing > 0.0L) || !(inv_spacing > 0.0L)) return LUT_ERR_BAD_SPACING;

    x_max = x_min + (long double)(num_points - 1) * spacing;
    if (!isfinite(x_max)) return LUT_ERR_NON_FINITE;

    if (u <= x_min) {
        k = 0;
        f = (extrap_method == EXTRAP_CLIP) ? 0.0L : (u - x_min) * inv_spacing;
    } else if (u >= x_max) {
        k = num_points - 2;
        f = (extrap_method == EXTRAP_CLIP)
            ? 1.0L
            : (u - (x_min + (long double)k * spacing)) * inv_spacing;
    } else {
        long double normalized = (u - x_min) * inv_spacing;
        k = (int)floorl(normalized);
        if (k < 0) k = 0;
        else if (k > num_points - 2) k = num_points - 2;
        f = normalized - (long double)k;
    }

    if (!isfinite(f)) return LUT_ERR_NON_FINITE;
    result->k = k;
    result->f = (double)f;
    return LUT_OK;
}

LutStatus interpolate_1d_typed(
    PrelookupResult kf,
    const void* table,
    int num_points,
    LutDataType table_type,
    long double* output
) {
    long double y0;
    long double y1;
    LutStatus status;

    if (table == 0 || output == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;
    if (lut_data_type_size(table_type) == 0U) return LUT_ERR_BAD_TYPE;
    if (kf.k < 0 || kf.k >= num_points - 1) return LUT_ERR_INDEX;
    if (!isfinite(kf.f)) return LUT_ERR_NON_FINITE;

    status = read_typed_value(table, (size_t)kf.k, table_type, &y0);
    if (status != LUT_OK) return status;
    status = read_typed_value(table, (size_t)(kf.k + 1), table_type, &y1);
    if (status != LUT_OK) return status;

    *output = y0 + (long double)kf.f * (y1 - y0);
    if (!isfinite(*output)) return LUT_ERR_NON_FINITE;
    return LUT_OK;
}

LutStatus interpolate_2d_typed(
    PrelookupResult kf_row,
    PrelookupResult kf_col,
    const void* table,
    int num_rows,
    int num_cols,
    LutDataType table_type,
    long double* output
) {
    int row;
    int col;
    size_t idx_00;
    size_t idx_10;
    size_t idx_01;
    size_t idx_11;
    long double z00;
    long double z10;
    long double z01;
    long double z11;
    long double z0;
    long double z1;
    LutStatus status;

    if (table == 0 || output == 0) return LUT_ERR_NULL_PTR;
    if (num_rows < 2 || num_cols < 2) return LUT_ERR_SIZE;
    if (lut_data_type_size(table_type) == 0U) return LUT_ERR_BAD_TYPE;
    if (!isfinite(kf_row.f) || !isfinite(kf_col.f)) return LUT_ERR_NON_FINITE;

    row = kf_row.k;
    col = kf_col.k;
    if (row < 0 || row >= num_rows - 1 || col < 0 || col >= num_cols - 1) return LUT_ERR_INDEX;

    idx_00 = (size_t)row * (size_t)num_cols + (size_t)col;
    idx_10 = (size_t)(row + 1) * (size_t)num_cols + (size_t)col;
    idx_01 = (size_t)row * (size_t)num_cols + (size_t)(col + 1);
    idx_11 = (size_t)(row + 1) * (size_t)num_cols + (size_t)(col + 1);

    status = read_typed_value(table, idx_00, table_type, &z00);
    if (status != LUT_OK) return status;
    status = read_typed_value(table, idx_10, table_type, &z10);
    if (status != LUT_OK) return status;
    status = read_typed_value(table, idx_01, table_type, &z01);
    if (status != LUT_OK) return status;
    status = read_typed_value(table, idx_11, table_type, &z11);
    if (status != LUT_OK) return status;

    z0 = z00 + (long double)kf_row.f * (z10 - z00);
    z1 = z01 + (long double)kf_row.f * (z11 - z01);
    *output = z0 + (long double)kf_col.f * (z1 - z0);

    if (!isfinite(*output)) return LUT_ERR_NON_FINITE;
    return LUT_OK;
}

LutStatus lookup2d_typed(
    long double u_row,
    long double u_col,
    const void* row_bp,
    int num_rows,
    LutDataType row_type,
    const void* col_bp,
    int num_cols,
    LutDataType col_type,
    const void* table,
    LutDataType table_type,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap,
    long double* output
) {
    PrelookupResult kr;
    PrelookupResult kc;
    LutStatus status;

    if (output == 0) return LUT_ERR_NULL_PTR;
    status = prelookup_typed(u_row, row_bp, num_rows, row_type, row_extrap, &kr);
    if (status != LUT_OK) return status;
    status = prelookup_typed(u_col, col_bp, num_cols, col_type, col_extrap, &kc);
    if (status != LUT_OK) return status;
    return interpolate_2d_typed(kr, kc, table, num_rows, num_cols, table_type, output);
}

LutStatus lookup2d_row_pow2_typed(
    long double u_row,
    long double u_col,
    long double row_min,
    long double row_spacing,
    long double row_inv_spacing,
    int num_rows,
    const void* col_bp,
    int num_cols,
    LutDataType col_type,
    const void* table,
    LutDataType table_type,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap,
    long double* output
) {
    PrelookupResult kr;
    PrelookupResult kc;
    LutStatus status;

    if (output == 0) return LUT_ERR_NULL_PTR;
    status = prelookup_pow2_typed(u_row, row_min, row_spacing, row_inv_spacing, num_rows, row_extrap, &kr);
    if (status != LUT_OK) return status;
    status = prelookup_typed(u_col, col_bp, num_cols, col_type, col_extrap, &kc);
    if (status != LUT_OK) return status;
    return interpolate_2d_typed(kr, kc, table, num_rows, num_cols, table_type, output);
}

LutStatus lookup2d_col_pow2_typed(
    long double u_row,
    long double u_col,
    const void* row_bp,
    int num_rows,
    LutDataType row_type,
    long double col_min,
    long double col_spacing,
    long double col_inv_spacing,
    int num_cols,
    const void* table,
    LutDataType table_type,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap,
    long double* output
) {
    PrelookupResult kr;
    PrelookupResult kc;
    LutStatus status;

    if (output == 0) return LUT_ERR_NULL_PTR;
    status = prelookup_typed(u_row, row_bp, num_rows, row_type, row_extrap, &kr);
    if (status != LUT_OK) return status;
    status = prelookup_pow2_typed(u_col, col_min, col_spacing, col_inv_spacing, num_cols, col_extrap, &kc);
    if (status != LUT_OK) return status;
    return interpolate_2d_typed(kr, kc, table, num_rows, num_cols, table_type, output);
}

LutStatus lookup2d_pow2_typed(
    long double u_row,
    long double u_col,
    long double row_min,
    long double row_spacing,
    long double row_inv_spacing,
    int num_rows,
    long double col_min,
    long double col_spacing,
    long double col_inv_spacing,
    int num_cols,
    const void* table,
    LutDataType table_type,
    ExtrapMethod row_extrap,
    ExtrapMethod col_extrap,
    long double* output
) {
    PrelookupResult kr;
    PrelookupResult kc;
    LutStatus status;

    if (output == 0) return LUT_ERR_NULL_PTR;
    status = prelookup_pow2_typed(u_row, row_min, row_spacing, row_inv_spacing, num_rows, row_extrap, &kr);
    if (status != LUT_OK) return status;
    status = prelookup_pow2_typed(u_col, col_min, col_spacing, col_inv_spacing, num_cols, col_extrap, &kc);
    if (status != LUT_OK) return status;
    return interpolate_2d_typed(kr, kc, table, num_rows, num_cols, table_type, output);
}
