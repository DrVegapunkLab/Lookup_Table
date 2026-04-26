#ifndef SIMULINK_LOOKUP_H
#define SIMULINK_LOOKUP_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    EXTRAP_CLIP = 0,
    EXTRAP_LINEAR = 1
} ExtrapMethod;

typedef struct {
    int k;
    double f;
} PrelookupResult;

typedef enum {
    LUT_OK = 0,
    LUT_ERR_NULL_PTR = -1,
    LUT_ERR_SIZE = -2,
    LUT_ERR_NON_MONOTONIC = -3,
    LUT_ERR_BAD_SPACING = -4
} LutStatus;

#define LUT_SIZE(x) ((int)(sizeof(x) / sizeof((x)[0])))

LutStatus validate_breakpoints(const double* bp, int num_points);
LutStatus validate_pow2_spacing(double spacing, double inv_spacing, int num_points);

PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method);
PrelookupResult prelookup_pow2(double u, double x_min, double spacing, double inv_spacing, int num_points, ExtrapMethod extrap_method);

double interpolate_1d(PrelookupResult kf, const double* table);

/*
 * Interpolazione 2D bilineare.
 * Convenzione memoria C row-major:
 * table[row * num_cols + col]
 */
double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols);

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
);

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
);

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
);

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
);

#ifdef __cplusplus
}
#endif

#endif
