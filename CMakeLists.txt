cmake_minimum_required(VERSION 3.10)
project(SimulinkLookup C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED True)

# Crea la libreria (usata in tutti i tuoi futuri progetti)
add_library(simulink_lookup simulink_lookup.c)
target_include_directories(simulink_lookup PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# Crea l'eseguibile di test
add_executable(simulink_example main.c)
target_link_libraries(simulink_example simulink_lookup)