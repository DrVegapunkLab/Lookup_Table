#include "simulink_lookup.h"

// --- Prelookup Standard (Binary Search) ---
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

// --- Prelookup Ottimizzato EvenPow2 (O(1) Math) ---
PrelookupResult prelookup_pow2(double u, double x_min, double spacing, double inv_spacing, int num_points, ExtrapMethod extrap_method) {
    PrelookupResult result;
    int k;
    double f;
    double x_max = x_min + (num_points - 1) * spacing;

    if (u <= x_min) {
        k = 0;
        f = (extrap_method == EXTRAP_CLIP) ? 0.0 : (u - x_min) * inv_spacing;
    }
    else if (u >= x_max) {
        k = num_points - 2;
        // Ricava il valore X dell'ultimo intervallo valido
        double bp_k = x_min + k * spacing;
        f = (extrap_method == EXTRAP_CLIP) ? 1.0 : (u - bp_k) * inv_spacing;
    }
    else {
        // Nessuna ricerca! Calcolo matematico diretto.
        double normalized = (u - x_min) * inv_spacing;
        k = (int)normalized;
        f = normalized - k;
    }

    result.k = k;
    result.f = f;
    return result;
}

// --- 1D Interpolation ---
double interpolate_1d(PrelookupResult kf, const double* table) {
    double y0 = table[kf.k];
    double y1 = table[kf.k + 1];
    return y0 + kf.f * (y1 - y0);
}

// --- 2D Interpolation ---
double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols) {
    int idx_00 = kf_row.k * num_cols + kf_col.k;
    int idx_10 = (kf_row.k + 1) * num_cols + kf_col.k;
    int idx_01 = kf_row.k * num_cols + (kf_col.k + 1);
    int idx_11 = (kf_row.k + 1) * num_cols + (kf_col.k + 1);

    double y00 = table[idx_00];
    double y10 = table[idx_10];
    double y01 = table[idx_01];
    double y11 = table[idx_11];

    double val0 = y00 + kf_row.f * (y10 - y00);
    double val1 = y01 + kf_row.f * (y11 - y01);

    return val0 + kf_col.f * (val1 - val0);
}