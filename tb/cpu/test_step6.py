import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

# Load-use program at 0x80:
#   0x80 addi x21, x0, 0x77
#   0x84 sw   x21, 0x28(x0)       mem[10] = 0x77
#   0x88 lw   x22, 0x28(x0)
#   0x8C add  x23, x22, x22       load-use on BOTH operands        -> 0xEE
#   0x90 lw   x24, 0x28(x0)
#   0x94 addi x25, x24, 1         load-use on operand A            -> 0x78
#   0x98 lw   x26, 0x28(x0)
#   0x9C sw   x26, 0x2C(x0)       load-use on the STORE DATA       -> mem[11] = 0x77
#   0xA0 lw   x27, 0x28(x0)
#   0xA4 nop                      (nothing depends on the load: no stall needed)
#   0xA8 add  x28, x27, x27       two instructions after the load: forwarding alone -> 0xEE

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def run_until_pc(dut, stage_pc, address, limit=80):
    for _ in range(limit):
        if int(getattr(dut, stage_pc).value) == address:
            return
        await RisingEdge(dut.clk)
    assert False, f"{stage_pc} never reached {address:X}"

def reg(dut, n):
    return int(dut.regfile.registers[n].value)

@cocotb.test()
async def load_use_results_test(dut):
    """Step 6: an instruction that uses a load's result right after the load gets the loaded value"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(70):
        await RisingEdge(dut.clk)
    assert reg(dut, 22) == 0x77, f"lw x22: x22 = {reg(dut, 22):08X}, expected 00000077"
    assert reg(dut, 23) == 0xEE, f"add x23, x22, x22: x23 = {reg(dut, 23):08X}, expected 000000EE"
    assert reg(dut, 25) == 0x78, f"addi x25, x24, 1: x25 = {reg(dut, 25):08X}, expected 00000078"
    got = int(dut.data_memory.mem[11].value)
    assert got == 0x77, f"sw x26, 0x2C(x0): mem[11] = {got:08X}, expected 00000077"
    assert reg(dut, 28) == 0xEE, f"add x28, x27, x27: x28 = {reg(dut, 28):08X}, expected 000000EE"

@cocotb.test()
async def stall_holds_fetch_and_decode_test(dut):
    """Step 6: during a load-use stall, fetch and decode keep their instructions for one cycle"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    # lw x22 (0x88) in execute, add x23 (0x8C) in decode: this is the load-use case
    await run_until_pc(dut, "pc_d", 0x8C)
    assert int(dut.pc_e.value) == 0x88, f"expected lw x22 in execute, pc_e = {int(dut.pc_e.value):X}"
    pc_fetch = int(dut.pc.value)
    await RisingEdge(dut.clk)
    assert int(dut.pc_d.value) == 0x8C, \
        f"decode moved on during the stall: pc_d = {int(dut.pc_d.value):X}, expected 8C"
    assert int(dut.pc.value) == pc_fetch, \
        f"fetch moved on during the stall: pc = {int(dut.pc.value):X}, expected {pc_fetch:X}"
    await RisingEdge(dut.clk)
    assert int(dut.pc_e.value) == 0x8C, \
        f"after the stall, add x23 should be in execute: pc_e = {int(dut.pc_e.value):X}"
    assert int(dut.pc_m.value) == 0x88 or int(dut.pc_w.value) == 0x88, "lw x22 should be one stage further on"

@cocotb.test()
async def stall_inserts_bubble_test(dut):
    """Step 6: during the stall, execute receives a bubble that writes nothing"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await run_until_pc(dut, "pc_d", 0x8C)
    await RisingEdge(dut.clk)
    # the instruction now in execute is the bubble, not a second copy of add x23
    assert int(dut.reg_write_e.value) == 0, "bubble in execute has reg_write_e = 1: it would write a register"
    assert int(dut.mem_write_e.value) == 0, "bubble in execute has mem_write_e = 1: it would write memory"

@cocotb.test()
async def no_stall_without_load_use_test(dut):
    """Step 6: no stall when the instruction after a load does not use its result"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    # lw x27 (0xA0) in execute, nop (0xA4) in decode: no dependency
    await run_until_pc(dut, "pc_d", 0xA4)
    assert int(dut.pc_e.value) == 0xA0, f"expected lw x27 in execute, pc_e = {int(dut.pc_e.value):X}"
    await RisingEdge(dut.clk)
    assert int(dut.pc_d.value) == 0xA8, \
        f"pipeline stalled although nothing used the load: pc_d = {int(dut.pc_d.value):X}, expected A8"
