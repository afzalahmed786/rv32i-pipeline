// Simulation top level: the CPU core plus its instruction and data memories.
// The memories live here, outside the core, so the core can be synthesized
// on its own (on a chip they would be SRAM macros or off-chip memory).
// Each testbench directory provides ./test_imemory.hex and ./test_dmemory.hex.
module top (
    input logic clk,
    input logic rst_n
);

logic [31:0] imem_addr;
logic [31:0] imem_rdata;
logic [31:0] dmem_addr;
logic [31:0] dmem_wdata;
logic        dmem_we;
logic [3:0]  dmem_be;
logic [31:0] dmem_rdata;

cpu core (
    .clk(clk),
    .rst_n(rst_n),
    .imem_addr(imem_addr),
    .imem_rdata(imem_rdata),
    .dmem_addr(dmem_addr),
    .dmem_wdata(dmem_wdata),
    .dmem_we(dmem_we),
    .dmem_be(dmem_be),
    .dmem_rdata(dmem_rdata)
);

memory #(.mem_init("./test_imemory.hex"))
instruction_memory (
    .clk(clk),
    .address(imem_addr),
    .write_data(32'b0),
    .write_enable(1'b0),
    .rst_n(1'b1),
    .byte_enable(4'b0000),
    .read_data(imem_rdata)
);

memory #(.mem_init("./test_dmemory.hex"))
data_memory (
    .clk(clk),
    .address(dmem_addr),
    .write_data(dmem_wdata),
    .write_enable(dmem_we),
    .byte_enable(dmem_be),
    .rst_n(1'b1),
    .read_data(dmem_rdata)
);

endmodule
