#  File Name:         adder.pro
#  Description:        OSVVM Scripts build for the GHDL Studio adder example
#
#  Prerequisites:
#    1. TCL (tclsh) and GHDL on PATH
#    2. OsvvmLibraries installed with the osvvm utility submodule, e.g.:
#         git clone --recursive https://github.com/OSVVM/OsvvmLibraries
#       https://github.com/OSVVM/OSVVM-Scripts
#
#  Run with GHDL Studio (OSVVM mode):
#    Settings → TCL executable + OSVVM Scripts path (…/OsvvmLibraries/Scripts)
#    Startup → OSVVM mode → select this file → Build .pro (OSVVM)
#
#  Or manually:
#    tclsh
#    source <OsvvmLibraries>/Scripts/StartUp.tcl
#    build <path-to>/examples/adder/adder.pro
#

SetVHDLVersion 2008
SetSaveWaves true

# Resolve OsvvmLibraries root as set by StartUp.tcl / StartUpShared.tcl:
#   ::osvvm::OsvvmHomeDirectory  (namespace)
#   ::OsvvmLibraries             (global alias — NOT ::osvvm::OsvvmLibraries)
if {[info exists ::osvvm::OsvvmHomeDirectory] && $::osvvm::OsvvmHomeDirectory ne ""} {
  set _osvvmRoot $::osvvm::OsvvmHomeDirectory
} elseif {[info exists ::OsvvmLibraries] && $::OsvvmLibraries ne ""} {
  set _osvvmRoot $::OsvvmLibraries
} elseif {[info exists ::osvvm::OsvvmScriptDirectory]} {
  set _osvvmRoot [file normalize [file join $::osvvm::OsvvmScriptDirectory ..]]
} else {
  error "OSVVM StartUp.tcl did not set OsvvmHomeDirectory / OsvvmLibraries.\n\
Source …/OsvvmLibraries/Scripts/StartUp.tcl before build."
}

# Compile the OSVVM utility library (library osvvm). Required because adder_tb
# uses:  library osvvm; context osvvm.OsvvmContext;
set _osvvmUtil [file normalize [file join $_osvvmRoot osvvm]]
if {![file isdirectory $_osvvmUtil]} {
  error "OSVVM utility library not found at '${_osvvmUtil}'.\n\
Clone OsvvmLibraries with submodules:\n\
  git clone --recursive https://github.com/OSVVM/OsvvmLibraries\n\
Or:  cd OsvvmLibraries && git submodule update --init osvvm"
}
include $_osvvmUtil

library work
analyze adder.vhd
analyze adder_tb.vhd
TestName adder_tb
simulate adder_tb
