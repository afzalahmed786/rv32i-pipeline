import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

NOP = 0x00000013

# Branch / jump program at 0xC0:
#   0xC0  addi x1, x0, 1
#   0xC4  addi x2, x0, 2
#   0xC8  beq  x1, x2, +8      NOT taken            -> falls through to 0xCC
#   0xCC  addi x3, x0, 0x33    executed             -> x3 = 0x33
#   0xD0  bne  x1, x2, +12     TAKEN                -> 0xDC
#   0xD4  addi x4, x0, 0x44    wrong path: must be flushed (x4 stays 4)
#   0xD8  addi x5, x0, 0x55    wrong path: must be flushed (x5 stays 3)
#   0xDC  jal  x6, +12         -> 0xE8, x6 = 0xE0
#   0xE0  addi x7, x0, 0x77    wrong path: must be flushed (x7 stays 0)
#   0xE4  addi x8, x0, 0x88    wrong path: must be flushed (x8 stays 0x12345000)
#   0xE8  addi x9, x0, 0xF4
#   0xEC  jalr x29, 0(x9)      x9 forwarded from the MEMORY stage -> 0xF4, x29 = 0xF0
#   0xF0  addi x3, x0, 0xEE    wrong path: must be flushed (x3 stays 0x33)
#   0xF4  addi x31, x0, 0x1F
#   0xF8  addi x30, x0, 3
#   0xFC  addi x31, x31, 1     loop body, runs 3 times -> x31 = 0x22
#   0x100 addi x30, x30, -1
#   0x104 bne  x30, x0, -8     backward branch, x30 forwarded -> loops to 0xFC

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def run_program(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(140):
        await RisingEdge(dut.clk)

async def run_until_pc(dut, stage_pc, address, limit=140):
    for _ in range(limit):
        if int(getattr(dut, stage_pc).value) == address:
            return
        await RisingEdge(dut.clk)
    assert False, f"{stage_pc} never reached {address:X}"

def reg(dut, n):
    return int(dut.regfile.registers[n].value)

@cocotb.test()
async def branch_not_taken_test(dut):
    """Step 7: a branch that is not taken lets the next instruction run"""
    await run_program(dut)
    assert reg(dut, 3) == 0x33, f"x3 = {reg(dut, 3):08X}, expected 00000033 (0xCC after the not-taken beq)"

@cocotb.test()
async def branch_taken_flush_test(dut):
    """Step 7: a taken branch jumps, and the two wrongly fetched instructions never write"""
    await run_program(dut)
    assert reg(dut, 4) == 4, f"x4 = {reg(dut, 4):08X}: the instruction at 0xD4 ran after the taken bne"
    assert reg(dut, 5) == 3, f"x5 = {reg(dut, 5):08X}: the instruction at 0xD8 ran after the taken bne"

@cocotb.test()
async def jal_test(dut):
    """Step 7: jal jumps, writes the return address, and flushes the wrong path"""
    await run_program(dut)
    assert reg(dut, 6) == 0xE0, f"jal x6: x6 = {reg(dut, 6):08X}, expected 000000E0"
    assert reg(dut, 7) == 0, f"x7 = {reg(dut, 7):08X}: the instruction at 0xE0 ran after jal"
    assert reg(dut, 8) == 0x12345000, f"x8 = {reg(dut, 8):08X}: the instruction at 0xE4 ran after jal"

@cocotb.test()
async def jalr_test(dut):
    """Step 7: jalr jumps to a register value (forwarded), writes the return address, and flushes"""
    await run_program(dut)
    assert reg(dut, 29) == 0xF0, f"jalr x29: x29 = {reg(dut, 29):08X}, expected 000000F0"
    assert reg(dut, 3) == 0x33, f"x3 = {reg(dut, 3):08X}: the instruction at 0xF0 ran after jalr"
    assert reg(dut, 31) != 0, "the jalr target 0xF4 was never reached"

@cocotb.test()
async def backward_branch_loop_test(dut):
    """Step 7: a backward branch loops the right number of times"""
    await run_program(dut)
    assert reg(dut, 30) == 0, f"loop counter x30 = {reg(dut, 30):08X}, expected 0"
    assert reg(dut, 31) == 0x22, f"x31 = {reg(dut, 31):08X}, expected 00000022 (loop body should run 3 times)"

@cocotb.test()
async def flush_timing_test(dut):
    """Step 7: the cycle after a taken branch in execute, fetch is at the target and decode/execute hold bubbles"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await run_until_pc(dut, "pc_e", 0xD0)          # bne x1, x2, +12 in execute
    await RisingEdge(dut.clk)
    assert int(dut.pc.value) == 0xDC, f"fetch should be at the branch target 0xDC, pc = {int(dut.pc.value):X}"
    assert int(dut.instruction_d.value) == NOP, \
        f"decode should hold a nop (flushed), instruction_d = {int(dut.instruction_d.value):08X}"
    assert int(dut.reg_write_e.value) == 0 and int(dut.mem_write_e.value) == 0, \
        "execute should hold a bubble (flushed), but it would write"
