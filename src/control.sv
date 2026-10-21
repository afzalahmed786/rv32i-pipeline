module control (
    input logic [6:0] op,
    input logic [2:0] func3,
    input logic [6:0] func7,
    output logic [3:0] alu_control,
    output logic [2:0] imm_source,
    output logic mem_write,
    output logic reg_write,
    output logic alu_source,
    output logic [1:0] write_back_source,
    output logic second_add_source,
    output logic branch,
    output logic jump
);

import riscv_pkg::*;

alu_op_t alu_op;
always_comb begin
    reg_write         = 1'b0;
    imm_source        = 3'b000;
    mem_write         = 1'b0;
    alu_op            = ALU_OP_LOAD_STORE;
    alu_source        = 1'b0;
    write_back_source = 2'b00;
    second_add_source = 1'b0;
    branch            = 1'b0;
    jump              = 1'b0;

    case (op)
        OPCODE_I_TYPE_LOAD : begin
            reg_write = 1'b1; alu_source = 1'b1; write_back_source = 2'b01;
        end
        OPCODE_S_TYPE : begin
            imm_source = 3'b001; mem_write = 1'b1; alu_source = 1'b1;
        end
        OPCODE_R_TYPE : begin
            reg_write = 1'b1; alu_op = ALU_OP_MATH;
        end
        OPCODE_I_TYPE_ALU : begin
            reg_write = 1'b1; alu_source = 1'b1; alu_op = ALU_OP_MATH;
        end
        OPCODE_B_TYPE : begin
            imm_source = 3'b010; alu_op = ALU_OP_BRANCHES; branch = 1'b1;
        end
        OPCODE_J_TYPE : begin
            reg_write = 1'b1; imm_source = 3'b011;
            write_back_source = 2'b10; jump = 1'b1;
        end
        OPCODE_J_TYPE_JALR : begin
            reg_write = 1'b1;
            alu_source = 1'b1;
            write_back_source = 2'b10;
            jump = 1'b1;
        end
        OPCODE_U_TYPE_LUI : begin
            reg_write = 1'b1; imm_source = 3'b100;
            write_back_source = 2'b11; second_add_source = 1'b1;
        end
        OPCODE_U_TYPE_AUIPC : begin
            reg_write = 1'b1; imm_source = 3'b100;
            write_back_source = 2'b11; second_add_source = 1'b0;
        end
        default : ;
    endcase
end

always_comb begin
    case(alu_op)
        ALU_OP_LOAD_STORE : alu_control = ALU_ADD;
        ALU_OP_MATH : begin
            case (func3)
                F3_ADD_SUB : alu_control = (func7[5]& op[5]) ? ALU_SUB : ALU_ADD;
                F3_AND     : alu_control = ALU_AND;
                F3_OR      : alu_control = ALU_OR;
                F3_SLT     : alu_control = ALU_SLT;
                F3_SLTU    : alu_control = ALU_SLTU;
                F3_XOR     : alu_control = ALU_XOR;
                F3_SLL     : alu_control = ALU_SLL;
                F3_SRL_SRA : alu_control = func7[5] ? ALU_SRA : ALU_SRL;
            endcase
        end
        ALU_OP_BRANCHES : case (func3)
                F3_BEQ, F3_BNE   : alu_control = ALU_SUB;
                F3_BLT, F3_BGE   : alu_control = ALU_SLT;
                F3_BLTU, F3_BGEU : alu_control = ALU_SLTU;
                default: alu_control = ALU_SUB;
            endcase
        default : alu_control = ALU_SLTU;
    endcase
end

endmodule
