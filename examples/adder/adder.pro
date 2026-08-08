#  File Name:         adder.pro
#  Description:        OSVVM Scripts build for the GHDL Studio adder example
#
#  Prerequisites:
#    1. TCL (tclsh) and GHDL on PATH
#    2. OSVVM Scripts / OsvvmLibraries installed
#       https://github.com/OSVVM/OSVVM-Scripts
#    3. OSVVM utility library built once, e.g.:
#         build <OsvvmLibraries>/osvvm
#       (or build <OsvvmLibraries>/OsvvmLibraries.pro)
#
#  Run with GHDL Studio (OSVVM mode):
#    Settings → TCL executable + OSVVM Scripts path
#    Startup → OSVVM mode → select this file → Build .pro (OSVVM)
#
#  Or manually:
#    tclsh
#    source <OsvvmLibraries>/Scripts/StartUp.tcl
#    build <path-to>/examples/adder/adder.pro
#

SetVHDLVersion 2008
SetSaveWaves true

library work
analyze adder.vhd
analyze adder_tb.vhd
TestName adder_tb
simulate adder_tb
