# pykmclib - Python re-development of KMCLib
#
# Entry point for the CMake build.  scikit-build-core invokes this file and
# installs whatever is declared with install() into the wheel.
#
# The KMCLib C++ sources themselves live, unmodified, in third_party/KMCLib/.
# Nothing here patches them: all build adaptation (pybind11 bindings, generated
# mpiflag.h, md5 extraction) happens in cxx/.

cmake_minimum_required(VERSION 3.21...4.2)

project(pykmclib LANGUAGES C CXX)

if(NOT DEFINED SKBUILD_PROJECT_NAME)
  # Allow a plain "cmake -S . -B build" session outside of a PEP 517 build.
  set(SKBUILD_PROJECT_NAME pykmclib)
endif()

option(KMC_ENABLE_MPI "Compile the KMCLib core with MPI support (experimental)" OFF)
set(KMC_CXX_STANDARD "17" CACHE STRING "C++ standard used to compile the KMCLib core")

add_subdirectory(cxx)
