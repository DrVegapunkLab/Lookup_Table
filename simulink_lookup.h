#ifndef SIMULINK_LOOKUP_H
#define SIMULINK_LOOKUP_H

// Metodi di estrapolazione
typedef enum {
    EXTRAP_CLIP,
    EXTRAP_LINEAR
} ExtrapMethod;

// Struttura risultato (Indice e Frazione)
typedef struct {
    int k;
    double f;
} PrelookupResult;

// --- Funzioni Prelookup ---

// 1. Prelookup Standard (con ricerca binaria O(log N))
PrelookupResult prelookup(double u, const double* bp, int num_points, ExtrapMethod extrap_method);

// 2. Prelookup Ultra-Veloce per EvenPow2Spacing (O(1) senza array X)
PrelookupResult prelookup_pow2(double u, double x_min, double spacing, double inv_spacing, int num_points, ExtrapMethod extrap_method);

// --- Funzioni Interpolazione ---

// Interpolazione 1D (Lineare)
double interpolate_1d(PrelookupResult kf, const double* table);

// Interpolazione 2D (Bilineare)
double interpolate_2d(PrelookupResult kf_row, PrelookupResult kf_col, const double* table, int num_cols);

#endif // SIMULINK_LOOKUP_H