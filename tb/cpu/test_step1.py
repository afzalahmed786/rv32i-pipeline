import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

NOP = 0x00000013

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

@cocotb.test()
async def if_id_register_test(dut):
    """Step 1: decode stage sees the fetch stage's pc and instruction one cycle later"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)

    prev_pc = int(dut.pc.value)
    prev_instr = int(dut.instruction.value)
    for cycle in range(6):
        await RisingEdge(dut.clk)
        assert int(dut.pc_d.value) == prev_pc, \
            f"cycle {cycle}: pc_d = {int(dut.pc_d.value):08X}, expected {prev_pc:08X}"
        assert int(dut.instruction_d.value) == prev_instr, \
            f"cycle {cycle}: instruction_d = {int(dut.instruction_d.value):08X}, expected {prev_instr:08X}"
        assert int(dut.pc.value) == prev_pc + 4, \
            f"cycle {cycle}: pc = {int(dut.pc.value):08X}, expected {prev_pc + 4:08X}"
        prev_pc = int(dut.pc.value)
        prev_instr = int(dut.instruction.value)

@cocotb.test()
async def if_id_reset_test(dut):
    """Step 1: reset loads a nop into the IF/ID register"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.instruction_d.value) == NOP, \
        f"instruction_d = {int(dut.instruction_d.value):08X} in reset, expected a nop"
    assert int(dut.pc_d.value) == 0
    dut.rst_n.value = 1

@cocotb.test()
async def program_result_test(dut):
    """Step 1: addi x1..x4 still produce the right register values"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(12):
        await RisingEdge(dut.clk)
    for reg in range(1, 5):
        got = int(dut.regfile.registers[reg].value)
        assert got == reg, f"x{reg} = {got}, expected {reg}"
