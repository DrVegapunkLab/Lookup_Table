#ifndef SIMULINK_LOOKUP_H
#define SIMULINK_LOOKUP_H

#include <stddef.h>
#include <stdint.h>

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
    LUT_ERR_BAD_SPACING = -4,
    LUT_ERR_BAD_TYPE = -5,
    LUT_ERR_NON_FINITE = -6,
    LUT_ERR_INDEX = -7
} LutStatus;

/*
 * Tipi numerici supportati dalle API typed.
 * Si usano tipi a larghezza fissa per evitare ambiguita' tra piattaforme
 * (per esempio sizeof(long) cambia tra ABI differenti).
 */
typedef enum {
    LUT_TYPE_FLOAT32 = 0,
    LUT_TYPE_FLOAT64 = 1,
    LUT_TYPE_INT8 = 2,
    LUT_TYPE_UINT8 = 3,
    LUT_TYPE_INT16 = 4,
    LUT_TYPE_UINT16 = 5,
    LUT_TYPE_INT32 = 6,
    LUT_TYPE_UINT32 = 7,
    LUT_TYPE_INT64 = 8,
    LUT_TYPE_UINT64 = 9
} LutDataType;

#define LUT_SIZE(x) ((int)(sizeof(x) / sizeof((x)[0])))

/* API storica double: mantenuta per compatibilita'. */
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

/* ------------------------------------------------------------------
 * API typed: float/double + interi signed/unsigned da 8 a 64 bit.
 *
 * I dati vengono letti nel loro tipo nativo e convertiti a long double per
 * i calcoli intermedi. PrelookupResult mantiene f in double per compatibilita'
 * con l'API esistente. Le funzioni restituiscono LutStatus invece di
 * nascondere gli errori.
 * ------------------------------------------------------------------ */

size_t lut_data_type_size(LutDataType type);
const char* lut_status_string(LutStatus status);

LutStatus validate_breakpoints_typed(const void* bp, int num_points, LutDataType type);

LutStatus prelookup_typed(
    long double u,
    const void* bp,
    int num_points,
    LutDataType bp_type,
    ExtrapMethod extrap_method,
    PrelookupResult* result
);

LutStatus prelookup_pow2_typed(
    long double u,
    long double x_min,
    long double spacing,
    long double inv_spacing,
    int num_points,
    ExtrapMethod extrap_method,
    PrelookupResult* result
);

LutStatus interpolate_1d_typed(
    PrelookupResult kf,
    const void* table,
    int num_points,
    LutDataType table_type,
    long double* output
);

LutStatus interpolate_2d_typed(
    PrelookupResult kf_row,
    PrelookupResult kf_col,
    const void* table,
    int num_rows,
    int num_cols,
    LutDataType table_type,
    long double* output
);

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
);

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
);

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
);

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
);

#ifdef __cplusplus
}
#endif

#endif
