module regfile (
    input logic clk,
    input logic rst_n,
    input logic [4:0] address1,
    input logic [4:0] address2,
    output logic [31:0] read_data1,
    output logic [31:0] read_data2,

    input logic write_enable,
    input logic [31:0] write_data,
    input logic [4:0] address3
);

import riscv_pkg::*;

reg [31:0] registers [0:31];

always @(posedge clk) begin
    if(rst_n == 1'b0) begin
        for(int i = 0; i < 32;i++) begin
            registers[i] <= 32'b0;
        end
    end
    else if(write_enable == 1'b1 && address3 != 0) begin
        registers[address3] <= write_data;
    end
end

always_comb begin: readLogic
    if (write_enable && address3 != 0 && address3 == address1)
        read_data1 = write_data;
    else
        read_data1 = registers[address1];

    if (write_enable && address3 != 0 && address3 == address2)
        read_data2 = write_data;
    else
        read_data2 = registers[address2];
end

endmodule
