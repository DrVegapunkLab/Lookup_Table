#include "simulink_lookup.h"

LutStatus validate_breakpoints(const double* bp, int num_points) {
    int i;

    if (bp == 0) return LUT_ERR_NULL_PTR;
    if (num_points < 2) return LUT_ERR_SIZE;

    for (i = 0; i < num_points - 1; ++i) {
        if (!(bp[i + 1] > bp[i])) return LUT_ERR_NON_MONOTONIC;
    }

    return LUT_OK;
}

LutStatus validate_pow2_spacing(double spacing, double inv_spacing, int num_points) {
    if (num_points < 2) return LUT_ERR_SIZE;
    if (!(spacing > 0.0) || !(inv_spacing > 0.0)) return LUT_ERR_BAD_SPACING;
    return LUT_OK;
}

PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method) {
    PrelookupResult result;
    int k;
    double f;

    if (bp == 0 || num_points < 2) {
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

    if (num_points < 2 || spacing <= 0.0 || inv_spacing <= 0.0) {
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

    if (table == 0 || kf.k < 0) return 0.0;

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
