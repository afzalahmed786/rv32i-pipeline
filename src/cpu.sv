module cpu (
    input logic clk,
    input logic rst_n
);

import riscv_pkg::*;

logic [31:0] pc;
logic [31:0] pc_next;
logic [31:0] pc_target;
logic [31:0] pc_plus_four;
logic [31:0] pc_plus_second_add;
assign pc_target = (op_e == OPCODE_J_TYPE_JALR) ? {alu_result[31:1], 1'b0} : pc_e + immediate_e;
assign pc_plus_four = pc+4;
wire [31:0] instruction;

logic stall;

assign stall = (write_back_source_e == 2'b01) && (dest_reg_e != 5'b00000) && (dest_reg_e == source_reg1 || dest_reg_e == source_reg2);

logic pred_taken;
logic [31:0] pred_target;
logic pred_taken_d;
logic [31:0] pred_target_d;
logic [31:0] pc_d;
logic [31:0] instruction_d;
logic btb_hit;
logic btb_hit_taken;

btb #(.ENTRIES(16)) branch_pred(
    .clk(clk),
    .rst_n(rst_n),
    .lookup_pc(pc),
    .update_en(branch_e || jump_e),
    .update_pc(pc_e),
    .update_taken(actual_taken),
    .update_target(pc_target),
    .hit(btb_hit),
    .hit_taken(btb_hit_taken),
    .hit_target(pred_target)
);

assign pred_taken = btb_hit && btb_hit_taken;

always_ff @(posedge clk) begin
    if(!rst_n || mispredict) begin
        instruction_d <= 32'h00000013;
        pc_d <= 0;
        pred_taken_d <= 1'b0;
        pred_target_d <= 32'h00000000;
    end
    else if (!stall) begin
        instruction_d <= instruction;
        pc_d <= pc;
        pred_taken_d <= pred_taken;
        pred_target_d <= pred_target;
    end
end

always_comb begin : pc_select
    if(mispredict)
        pc_next = redirect_pc;
    else if (pred_taken)
        pc_next = pred_target;
    else
        pc_next = pc_plus_four;
end

always_comb begin : second_add_select
    case(second_add_source_e)
        1'b0 : pc_plus_second_add = pc_e + immediate_e;
        default : pc_plus_second_add = immediate_e;
    endcase
end

always_ff @(posedge clk) begin
    if (!rst_n) begin
        pc <= 32'b0;
    end else if (!stall) begin
         pc <= pc_next;
    end
end

logic wb_valid;

memory #(.mem_init("./test_imemory.hex"))
instruction_memory (
    .clk(clk),
    .address(pc),
    .write_data(32'b0),
    .write_enable(1'b0),
    .rst_n(1'b1),
    .byte_enable(4'b0000),
    .read_data(instruction)
);

logic [6:0] op;
logic [2:0] f3;
assign op = instruction_d[6:0];
assign f3 = instruction_d[14:12];

wire alu_zero;
wire [3:0] alu_control;
wire [2:0] imm_source;
wire mem_write;
wire reg_write;
wire alu_source;
wire [1:0] write_back_source;
wire actual_taken;
wire second_add_source;
wire branch;
wire jump;

control control_unit(
    .op(op),
    .func3(f3),
    .func7(instruction_d[31:25]),
    .second_add_source(second_add_source),
    .alu_control(alu_control),
    .imm_source(imm_source),
    .mem_write(mem_write),
    .reg_write(reg_write),
    .alu_source(alu_source),
    .write_back_source(write_back_source),
    .branch(branch),
    .jump(jump)
);

logic [31:0] pc_e;
logic mispredict;
logic [31:0] redirect_pc;
logic [31:0] read_reg1_e;
logic [31:0] read_reg2_e;
logic [4:0] source_reg1_e;
logic [4:0] source_reg2_e;
logic [31:0] immediate_e;
logic [4:0] dest_reg_e;
logic [2:0] f3_e;
logic reg_write_e;
logic mem_write_e;
logic alu_source_e;
logic [1:0] write_back_source_e;
logic [3:0] alu_control_e;
logic second_add_source_e;
logic branch_e;
logic jump_e;
logic [6:0] op_e;
logic pred_taken_e;
logic [31:0] pred_target_e;

logic take_branch;
always_comb begin
    case (f3_e)
        F3_BEQ  : take_branch = alu_zero;
        F3_BNE  : take_branch = ~alu_zero;
        F3_BLT  : take_branch = ~alu_zero;
        F3_BGE  : take_branch = alu_zero;
        F3_BLTU : take_branch = ~alu_zero;
        F3_BGEU : take_branch = alu_zero;
        default: take_branch = 1'b0;
    endcase
end

assign actual_taken = (take_branch & branch_e) | jump_e;
assign mispredict = (actual_taken != pred_taken_e) || (actual_taken && pred_target_e != pc_target);

assign redirect_pc = actual_taken ? pc_target : pc_e+4;

logic [4:0] source_reg1;
assign source_reg1 = instruction_d[19:15];
logic [4:0] source_reg2;
assign source_reg2 = instruction_d[24:20];
logic [4:0] dest_reg;
assign dest_reg = instruction_d[11:7];

wire [31:0] read_reg1;
wire [31:0] read_reg2;
wire [31:0] mem_read;
wire [31:0] alu_result;

logic [31:0] write_back_data;

wire [31:0] mem_read_write_back_data;
wire mem_read_write_back_valid;

always_comb begin : write_back_source_select
    case (write_back_source_w)
        2'b00 : begin
            write_back_data = alu_result_w;
            wb_valid = 1'b1;
        end
        2'b01:  begin
            write_back_data = mem_read_write_back_data_w;
            wb_valid = mem_read_write_back_valid_w;
        end
        2'b10 : begin
            write_back_data = pc_w + 4;
            wb_valid = 1'b1;
        end
        2'b11: begin
            write_back_data = pc_plus_second_add_w;
            wb_valid = 1'b1;
        end
        default: begin
            write_back_data = alu_result_w;
            wb_valid = 1'b1;
        end
    endcase
end

logic [31:0] forward_m;

always_comb begin : write_back_source_forward
    case (write_back_source_m)
        2'b00, 2'b01 : begin
            forward_m = alu_result_m;
        end
        2'b10 : begin
            forward_m = pc_m + 4;
        end
        2'b11: begin
            forward_m = pc_plus_second_add_m;
        end
        default: begin
            forward_m = alu_result_m;
        end
    endcase
end

regfile regfile(
    .clk(clk),
    .rst_n(rst_n),
    .address1(source_reg1),
    .address2(source_reg2),
    .read_data1(read_reg1),
    .read_data2(read_reg2),
    .write_enable(reg_write_w & wb_valid),
    .write_data(write_back_data),
    .address3(dest_reg_w)
);

logic [24:0] raw_imm;
assign raw_imm = instruction_d[31:7];
wire [31:0] immediate;

signext sign_extender(
    .raw_src(raw_imm),
    .imm_source(imm_source),
    .immediate(immediate)
);

always_ff @(posedge clk) begin
    if (!rst_n || stall || mispredict) begin
        pc_e <= 32'h00000000;
        read_reg1_e <= 32'h00000000;
        read_reg2_e <= 32'h00000000;
        immediate_e <= 32'h00000000;
        dest_reg_e <= 5'b00000;
        f3_e <= 3'b000;
        reg_write_e <= 1'b0;
        mem_write_e <= 1'b0;
        alu_source_e <= 1'b0;
        write_back_source_e <= 2'b00;
        alu_control_e <= 4'b0000;
        second_add_source_e <= 1'b0;
        source_reg1_e <= 5'b00000;
        source_reg2_e <= 5'b00000;
        branch_e <= 1'b0;
        jump_e <= 1'b0;
        op_e <= 7'b0000000;
        pred_taken_e <= 1'b0;
        pred_target_e <= 32'h00000000;
    end
    else begin
        pc_e <= pc_d;
        read_reg1_e <= read_reg1;
        read_reg2_e <= read_reg2;
        immediate_e <= immediate;
        dest_reg_e <= dest_reg;
        f3_e <= f3;
        reg_write_e <= reg_write;
        mem_write_e <= mem_write;
        alu_source_e <= alu_source;
        write_back_source_e <= write_back_source;
        alu_control_e <= alu_control;
        second_add_source_e <= second_add_source;
        source_reg1_e <= source_reg1;
        source_reg2_e <= source_reg2;
        branch_e <= branch;
        jump_e <= jump;
        op_e <= op;
        pred_taken_e <= pred_taken_d;
        pred_target_e <= pred_target_d;

    end
end

logic [31:0] alu_src2;

logic [31:0] forward_a;

logic [31:0] forward_b;

always_comb begin : forwardA
    if (source_reg1_e == dest_reg_m && reg_write_m == 1'b1 && dest_reg_m != 5'b00000) begin
        forward_a = forward_m;
    end
    else if (source_reg1_e == dest_reg_w && reg_write_w && dest_reg_w != 5'b00000) begin
        forward_a = write_back_data;
    end
    else begin
        forward_a = read_reg1_e;
    end
end

always_comb begin : forwardB
    if (source_reg2_e == dest_reg_m && reg_write_m == 1'b1 && dest_reg_m != 5'b00000) begin
        forward_b = forward_m;
    end
    else if (source_reg2_e == dest_reg_w && reg_write_w && dest_reg_w != 5'b00000) begin
        forward_b = write_back_data;
    end
    else begin
        forward_b = read_reg2_e;
    end
end

always_comb begin : alu_source_select
    case (alu_source_e)
        1'b1:    alu_src2 = immediate_e;
        default: alu_src2 = forward_b;
    endcase
end

alu alu_inst(
    .alu_control(alu_control_e),
    .src1(forward_a),
    .src2(alu_src2),
    .alu_result(alu_result),
    .zero(alu_zero)
);

wire [3:0] mem_byte_enable;
wire [31:0] mem_write_data;

logic [31:0] alu_result_m;
logic [31:0] read_reg2_m;
logic [31:0] pc_m;
logic [31:0] pc_plus_second_add_m;
logic [4:0] dest_reg_m;
logic [2:0] f3_m;
logic mem_write_m;
logic reg_write_m;
logic [1:0] write_back_source_m;

always_ff @(posedge clk) begin
    if (!rst_n) begin
        alu_result_m <= 32'h00000000;
        f3_m <= 3'b000;
        read_reg2_m <= 32'h00000000;
        pc_m <= 32'h00000000;
        dest_reg_m <= 5'b00000;
        mem_write_m <= 1'b0;
        reg_write_m <= 1'b0;
        write_back_source_m <= 2'b00;
        pc_plus_second_add_m <= 32'h00000000;
    end
    else begin
        alu_result_m <= alu_result;
        f3_m <= f3_e;
        read_reg2_m <= forward_b;
        pc_m <= pc_e;
        dest_reg_m <= dest_reg_e;
        mem_write_m <= mem_write_e;
        reg_write_m <= reg_write_e;
        write_back_source_m <= write_back_source_e;
        pc_plus_second_add_m <= pc_plus_second_add;
    end
end

load_store_decoder ls_decode(
    .alu_result_address(alu_result_m),
    .byte_enable(mem_byte_enable),
    .reg_read(read_reg2_m),
    .f3(f3_m),
    .write_data(mem_write_data)
);

memory #(.mem_init("./test_dmemory.hex"))
data_memory (
    .clk(clk),
    .address({alu_result_m[31:2], 2'b00}),
    .write_data(mem_write_data),
    .write_enable(mem_write_m),
    .byte_enable(mem_byte_enable),
    .rst_n(1'b1),
    .read_data(mem_read)
);

reader reader_inst(
    .mem_data(mem_read),
    .be_mask(mem_byte_enable),
    .f3(f3_m),
    .wb_data(mem_read_write_back_data),
    .valid(mem_read_write_back_valid)
);

logic [31:0] alu_result_w;
logic [31:0] mem_read_write_back_data_w;
logic        mem_read_write_back_valid_w;
logic [31:0] pc_w;
logic [31:0] pc_plus_second_add_w;
logic [4:0]  dest_reg_w;
logic        reg_write_w;
logic [1:0]  write_back_source_w;

always_ff @(posedge clk) begin
    if (!rst_n) begin
        alu_result_w                <= 32'h00000000;
        mem_read_write_back_data_w  <= 32'h00000000;
        mem_read_write_back_valid_w <= 1'b0;
        pc_w                        <= 32'h00000000;
        pc_plus_second_add_w        <= 32'h00000000;
        dest_reg_w                  <= 5'b00000;
        reg_write_w                 <= 1'b0;
        write_back_source_w         <= 2'b00;
    end
    else begin
        alu_result_w                <= alu_result_m;
        mem_read_write_back_data_w  <= mem_read_write_back_data;
        mem_read_write_back_valid_w <= mem_read_write_back_valid;
        pc_w                        <= pc_m;
        pc_plus_second_add_w        <= pc_plus_second_add_m;
        dest_reg_w                  <= dest_reg_m;
        reg_write_w                 <= reg_write_m;
        write_back_source_w         <= write_back_source_m;
    end
end

endmodule
