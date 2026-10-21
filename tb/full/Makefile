# Makefile

# defaults
SIM ?= verilator
TOPLEVEL_LANG ?= verilog
EXTRA_ARGS += --trace --trace-structs
EXTRA_ARGS += -Wno-fatal
WAVES = 1

VERILOG_SOURCES += $(PWD)/../../src/riscv_pkg.sv
VERILOG_SOURCES += $(PWD)/../../src/cpu.sv
VERILOG_SOURCES += $(PWD)/../../src/memory.sv
VERILOG_SOURCES += $(PWD)/../../src/control.sv
VERILOG_SOURCES += $(PWD)/../../src/regfile.sv
VERILOG_SOURCES += $(PWD)/../../src/signext.sv
VERILOG_SOURCES += $(PWD)/../../src/alu.sv
VERILOG_SOURCES += $(PWD)/../../src/load_store_decoder.sv
VERILOG_SOURCES += $(PWD)/../../src/reader.sv
VERILOG_SOURCES += $(PWD)/../../src/btb.sv
# use VHDL_SOURCES for VHDL files

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL = cpu

# MODULE is the basename of the Python test file
MODULE ?= test_full_program

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

waves:
	gtkwave dump.vcd
