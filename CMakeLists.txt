cmake_minimum_required(VERSION 3.10)

# Nome del progetto e linguaggio (C)
project(SimulinkLookup C)

# Specifica lo standard C (il C99 è perfetto per questo tipo di librerie matematiche)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED True)

# 1. Crea la libreria (di default sarà una libreria statica .a / .lib)
add_library(simulink_lookup simulink_lookup.c)

# (Opzionale) Specifica le cartelle degli header per la libreria
target_include_directories(simulink_lookup PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# 2. Crea l'eseguibile dal file main
add_executable(simulink_example main.c)

# 3. Collega la libreria all'eseguibile
target_link_libraries(simulink_example simulink_lookup)