import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

# Forwarding program at 0x40, with NO nops between dependent instructions:
#   0x40 addi x10, x0, 5
#   0x44 addi x11, x10, 3      x10 from the MEMORY stage          -> 8
#   0x48 add  x12, x10, x11    x10 from WRITE-BACK, x11 from MEMORY -> 13
#   0x4C sub  x13, x12, x12    both operands from MEMORY           -> 0
#   0x50 sw   x12, 0x20(x0)    store DATA from WRITE-BACK          -> mem[8] = 13
#   0x54 lui  x14, 0x1                                             -> 0x1000
#   0x58 addi x15, x14, 1      lui result from MEMORY (not an ALU result) -> 0x1001
#   0x5C addi x0, x12, 7       writes x0: must be ignored
#   0x60 add  x16, x0, x0      x0 must never be forwarded          -> 0
#   0x64 addi x18, x0, 1
#   0x68 addi x18, x18, 1      -> 2
#   0x6C add  x19, x18, x18    newest x18 (MEMORY) must win over older (WRITE-BACK) -> 4
#   0x70 addi x20, x0, 0x55
#   0x74 sw   x20, 0x24(x0)    store DATA from MEMORY              -> mem[9] = 0x55

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def run_program(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(45):
        await RisingEdge(dut.clk)

def reg(dut, n):
    return int(dut.core.regfile.registers[n].value)

def mem(dut, word):
    return int(dut.data_memory.mem[word].value)

@cocotb.test()
async def id_ex_source_regs_test(dut):
    """Step 5: the ID/EX register also carries the source register numbers"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    prev = (int(dut.core.source_reg1.value), int(dut.core.source_reg2.value))
    for cycle in range(30):
        await RisingEdge(dut.clk)
        got = (int(dut.core.source_reg1_e.value), int(dut.core.source_reg2_e.value))
        assert got == prev, f"cycle {cycle}: (source_reg1_e, source_reg2_e) = {got}, expected {prev}"
        prev = (int(dut.core.source_reg1.value), int(dut.core.source_reg2.value))

@cocotb.test()
async def forward_from_memory_test(dut):
    """Step 5: a result is forwarded from the MEMORY stage to the very next instruction"""
    await run_program(dut)
    assert reg(dut, 11) == 8, f"addi x11, x10, 3: x11 = {reg(dut, 11)}, expected 8 (x10 not forwarded from MEMORY)"
    assert reg(dut, 13) == 0, f"sub x13, x12, x12: x13 = {reg(dut, 13):08X}, expected 0"

@cocotb.test()
async def forward_from_write_back_test(dut):
    """Step 5: a result is forwarded from the WRITE-BACK stage, two instructions later"""
    await run_program(dut)
    assert reg(dut, 12) == 13, f"add x12, x10, x11: x12 = {reg(dut, 12)}, expected 13"

@cocotb.test()
async def forward_priority_test(dut):
    """Step 5: when both stages write the same register, the newer (MEMORY) value wins"""
    await run_program(dut)
    assert reg(dut, 19) == 4, f"add x19, x18, x18: x19 = {reg(dut, 19)}, expected 4 (2 from MEMORY, not 1 from WRITE-BACK)"

@cocotb.test()
async def forward_store_data_test(dut):
    """Step 5: the value a store writes to memory is forwarded too, not only ALU inputs"""
    await run_program(dut)
    assert mem(dut, 8) == 13, f"sw x12, 0x20(x0): mem[8] = {mem(dut, 8):08X}, expected 0000000D (from WRITE-BACK)"
    assert mem(dut, 9) == 0x55, f"sw x20, 0x24(x0): mem[9] = {mem(dut, 9):08X}, expected 00000055 (from MEMORY)"

@cocotb.test()
async def forward_non_alu_result_test(dut):
    """Step 5: a LUI result is forwarded correctly, even though it does not come from the ALU"""
    await run_program(dut)
    assert reg(dut, 14) == 0x1000, f"lui x14, 0x1: x14 = {reg(dut, 14):08X}, expected 00001000"
    assert reg(dut, 15) == 0x1001, f"addi x15, x14, 1: x15 = {reg(dut, 15):08X}, expected 00001001"

@cocotb.test()
async def forward_x0_test(dut):
    """Step 5: an instruction that 'writes' x0 must not be forwarded"""
    await run_program(dut)
    assert reg(dut, 0) == 0, "x0 must stay 0"
    assert reg(dut, 16) == 0, f"add x16, x0, x0: x16 = {reg(dut, 16):08X}, expected 0 (x0 was forwarded)"
