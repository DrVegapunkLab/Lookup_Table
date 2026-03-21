#ifndef SIMULINK_LOOKUP_H
#define SIMULINK_LOOKUP_H

// Define the extrapolation methods for the Prelookup block
typedef enum {
    EXTRAP_CLIP,
    EXTRAP_LINEAR
} ExtrapMethod;

// Structure to act like the "Index and fraction as bus" output
typedef struct {
    int k;      // Index
    double f;   // Fraction
} PrelookupResult;

// --- Block Functions ---

// Prelookup Block
PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method);

// 1D Interpolation Using Prelookup Block (Linear point-slope)
double interpolate_1d(PrelookupResult kf, const double* table);

// 2D Interpolation Using Prelookup Block (Linear point-slope)
// Note: Assumes a flattened 2D array in Row-Major (C-style) order.
double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols);

#endif // SIMULINK_LOOKUP_H