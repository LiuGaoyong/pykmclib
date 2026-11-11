# Build glue for the KMCLib C++ core and its Python extension module.
#
# Layout:
#   third_party/KMCLib/c++/src/*.cpp    pristine upstream sources (never edited)
#   third_party/KMCLib/c++/custom/*.cpp upstream example rate calculators
#   third_party/KMCLib/c++/externals/zip/md5.tar.gz  public-domain MD5
#   cxx/bindings/*.cpp                  pybind11 bindings (this repository)
#
# Upstream's own CMakeLists.txt files are intentionally NOT used: they require
# CMake 2.8 (rejected by CMake >= 4), use the removed cmake_force_cxx_compiler
# module, compile with -Werror and write generated headers into the source
# tree.  Everything below replaces that machinery.

set(KMC_ROOT "${PROJECT_SOURCE_DIR}/third_party/KMCLib/c++")
set(KMC_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen")

# ---------------------------------------------------------------------------
# Generated mpiflag.h (upstream generates this into its source tree instead)
# ---------------------------------------------------------------------------
if(KMC_ENABLE_MPI)
  set(KMC_RUNMPI true)
else()
  set(KMC_RUNMPI false)
endif()
file(MAKE_DIRECTORY "${KMC_GEN_DIR}")
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/mpiflag.h.in" "${KMC_GEN_DIR}/mpiflag.h" @ONLY)

# ---------------------------------------------------------------------------
# MD5: extracted from the upstream tarball into the build tree.
#
# hash.cpp includes "externals/md5.h", so the include root must expose an
# externals/ subdirectory; the tarball itself unpacks to md5/{md5.h,md5.c}.
# md5.c is compiled as C++ because upstream links the C++-mangled MD5_*
# symbols (hash.cpp has no extern "C").
# ---------------------------------------------------------------------------
set(MD5_DIR "${CMAKE_CURRENT_BINARY_DIR}/md5")
if(NOT EXISTS "${MD5_DIR}/externals/md5.c")
  file(ARCHIVE_EXTRACT INPUT "${KMC_ROOT}/externals/zip/md5.tar.gz" DESTINATION "${MD5_DIR}")
  file(MAKE_DIRECTORY "${MD5_DIR}/externals")
  file(COPY_FILE "${MD5_DIR}/md5/md5.h" "${MD5_DIR}/externals/md5.h")
  file(COPY_FILE "${MD5_DIR}/md5/md5.c" "${MD5_DIR}/externals/md5.c")
endif()

# ---------------------------------------------------------------------------
# KMCLib core: static library
# ---------------------------------------------------------------------------
file(GLOB KMC_SOURCES CONFIGURE_DEPENDS "${KMC_ROOT}/src/*.cpp")
list(SORT KMC_SOURCES)

add_library(kmc_core STATIC ${KMC_SOURCES} "${MD5_DIR}/externals/md5.c")
set_source_files_properties("${MD5_DIR}/externals/md5.c" PROPERTIES LANGUAGE CXX)

target_include_directories(kmc_core
  PUBLIC
    "${KMC_ROOT}/src"
  PRIVATE
    "${KMC_GEN_DIR}"
    "${MD5_DIR}"
)

set_target_properties(kmc_core PROPERTIES
  CXX_STANDARD "${KMC_CXX_STANDARD}"
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF
  POSITION_INDEPENDENT_CODE ON          # static lib ends up inside a module
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/lib"
)

# The 2016-era sources trip plenty of modern diagnostics; keep them visible but
# non-fatal, and silence the two known-noisy classes.
if(MSVC)
  target_compile_options(kmc_core PRIVATE /W3 /EHsc /bigobj)
  target_compile_definitions(kmc_core PRIVATE
    _CRT_SECURE_NO_WARNINGS _USE_MATH_DEFINES NOMINMAX)
else()
  target_compile_options(kmc_core PRIVATE
    -Wall -Wextra
    -Wno-unused-parameter
    -Wno-deprecated-declarations
  )
endif()

if(KMC_ENABLE_MPI)
  find_package(MPI REQUIRED COMPONENTS CXX)
  target_link_libraries(kmc_core PUBLIC MPI::MPI_CXX)
endif()

# ---------------------------------------------------------------------------
# The upstream example rate calculators (C++ side)
# ---------------------------------------------------------------------------
file(GLOB KMC_CUSTOM_SOURCES CONFIGURE_DEPENDS "${KMC_ROOT}/custom/*.cpp")
list(SORT KMC_CUSTOM_SOURCES)

add_library(kmc_custom STATIC ${KMC_CUSTOM_SOURCES})
target_include_directories(kmc_custom PUBLIC "${KMC_ROOT}/src" "${KMC_ROOT}/custom" PRIVATE "${KMC_GEN_DIR}")
set_target_properties(kmc_custom PROPERTIES
  CXX_STANDARD "${KMC_CXX_STANDARD}"
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF
  POSITION_INDEPENDENT_CODE ON
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/lib"
)
if(MSVC)
  target_compile_options(kmc_custom PRIVATE /W3 /EHsc /bigobj)
  target_compile_definitions(kmc_custom PRIVATE
    _CRT_SECURE_NO_WARNINGS _USE_MATH_DEFINES NOMINMAX)
endif()

# ---------------------------------------------------------------------------
# pybind11 extension module
#
# The pybind11 CMake package ships inside the PyPI wheel under
# site-packages/pybind11/share/cmake/pybind11, which is not on any default
# CMake search path, so ask pybind11 itself where it lives.
# ---------------------------------------------------------------------------
find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process(
  COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmakedir
  OUTPUT_VARIABLE _pybind11_cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET
)
if(_pybind11_cmake_dir)
  list(APPEND CMAKE_PREFIX_PATH "${_pybind11_cmake_dir}")
endif()
find_package(pybind11 CONFIG REQUIRED)

file(GLOB KMC_BINDING_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/bindings/*.cpp")
list(SORT KMC_BINDING_SOURCES)

pybind11_add_module(_backend MODULE ${KMC_BINDING_SOURCES})
target_link_libraries(_backend PRIVATE kmc_core kmc_custom)
target_include_directories(_backend PRIVATE
  "${KMC_ROOT}/src"
  "${KMC_ROOT}/custom"
  "${KMC_GEN_DIR}"
  "${MD5_DIR}"
)
set_target_properties(_backend PROPERTIES
  CXX_STANDARD "${KMC_CXX_STANDARD}"
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF
)
if(MSVC)
  target_compile_options(_backend PRIVATE /W3 /EHsc /bigobj /utf-8)
  target_compile_definitions(_backend PRIVATE
    _CRT_SECURE_NO_WARNINGS _USE_MATH_DEFINES NOMINMAX)
endif()

# ---------------------------------------------------------------------------
# Install into the wheel
# ---------------------------------------------------------------------------
install(TARGETS _backend
  LIBRARY DESTINATION "${SKBUILD_PROJECT_NAME}/Backend"
  RUNTIME DESTINATION "${SKBUILD_PROJECT_NAME}/Backend"
)

message(STATUS "pykmclib: KMCLib core from ${KMC_ROOT}")
message(STATUS "pykmclib: pybind11 from ${pybind11_INCLUDE_DIRS}")
message(STATUS "pykmclib: MPI ${KMC_ENABLE_MPI}")
