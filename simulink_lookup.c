#include "simulink_lookup.h"

// --- Prelookup Block Implementation ---
PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method) {
    PrelookupResult result;
    int k;
    double f;

    if (u <= bp[0]) {
        k = 0;
        f = (extrap_method == EXTRAP_CLIP) ? 0.0 : (u - bp[0]) / (bp[1] - bp[0]);
    } 
    else if (u >= bp[num_points - 1]) {
        k = num_points - 2; 
        f = (extrap_method == EXTRAP_CLIP) ? 1.0 : (u - bp[k]) / (bp[k + 1] - bp[k]);
    } 
    else {
        // Binary search for in-range inputs
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

// --- 1D Interpolation Using Prelookup ---
double interpolate_1d(PrelookupResult kf, const double* table) {
    double y0 = table[kf.k];
    double y1 = table[kf.k + 1];
    
    // y = y0 + f * (y1 - y0)
    return y0 + kf.f * (y1 - y0);
}

// --- 2D Interpolation Using Prelookup ---
double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols) {
    // Determine the 4 corners of the 2D grid for bilinear interpolation
    // Using row-major indexing: index = row * num_cols + col
    int idx_00 = kf_row.k * num_cols + kf_col.k;
    int idx_10 = (kf_row.k + 1) * num_cols + kf_col.k;
    int idx_01 = kf_row.k * num_cols + (kf_col.k + 1);
    int idx_11 = (kf_row.k + 1) * num_cols + (kf_col.k + 1);

    double y00 = table[idx_00];
    double y10 = table[idx_10];
    double y01 = table[idx_01];
    double y11 = table[idx_11];

    // 1. Interpolate along the rows (dimension 1)
    double val0 = y00 + kf_row.f * (y10 - y00);
    double val1 = y01 + kf_row.f * (y11 - y01);

    // 2. Interpolate along the columns (dimension 2)
    return val0 + kf_col.f * (val1 - val0);
}