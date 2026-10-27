create_clock -name core_clk -period 40 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks core_clk]
set_input_delay 8.0 -clock core_clk [get_ports {rst_n imem_rdata[*] dmem_rdata[*]}]
set_output_delay 8.0 -clock core_clk [get_ports {imem_addr[*] dmem_addr[*] dmem_wdata[*] dmem_we dmem_be[*]}]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 -pin Y [get_ports {rst_n imem_rdata[*] dmem_rdata[*]}]
set_load 0.033442 [get_ports {imem_addr[*] dmem_addr[*] dmem_wdata[*] dmem_we dmem_be[*]}]
set_max_fanout 20 [current_design] 
set_max_transition 0.75 [current_design] 
set_timing_derate -early 0.95
set_timing_derate -late 1.05
