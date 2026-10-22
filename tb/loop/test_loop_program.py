import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

# Branch predictor benchmark: a nested loop with a function call (see make_program.py).
# Every branch and jump runs many times, so this is where a predictor can help.
# The predictor may change how many cycles the program takes, never the final state.

LAST_PC = 0x3C   # address of the final nop; everything before it has finished

EXPECTED_REGS = {1: 165, 2: 0, 3: 0, 4: 3, 5: 0x1C, 6: 1, 7: 0}

# Sampled on the falling edge, in the middle of the cycle, when all signals have settled.
# Every instruction spends exactly one cycle in EXECUTE, so each branch/jump is counted once.
stats = {"branches": 0, "branches_taken": 0, "jumps": 0, "flushes": 0}

async def branch_monitor(dut):
    while True:
        await FallingEdge(dut.clk)
        if int(dut.rst_n.value) == 0:
            continue
        if int(dut.core.branch_e.value):
            stats["branches"] += 1
            stats["branches_taken"] += int(dut.core.actual_taken.value)
        if int(dut.core.jump_e.value):
            stats["jumps"] += 1
        stats["flushes"] += int(dut.core.mispredict.value)

@cocotb.test()
async def loop_program_test(dut):
    """Nested loop + function call: correct final state, and report branch statistics"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    cocotb.start_soon(branch_monitor(dut))

    cycles = 0
    while int(dut.core.pc_w.value) != LAST_PC:
        await RisingEdge(dut.clk)
        cycles += 1
        assert cycles < 500, "the final instruction never reached write-back"
    await RisingEdge(dut.clk)
    print(f"loop program finished in {cycles} cycles")
    print(f"branches: {stats['branches']} (taken: {stats['branches_taken']}), "
          f"jumps: {stats['jumps']}, flushes: {stats['flushes']} "
          f"-> {2 * stats['flushes']} cycles lost to flushes")

    errors = []
    for n, want in EXPECTED_REGS.items():
        got = int(dut.core.regfile.registers[n].value)
        if got != want:
            errors.append(f"x{n} = {got:08X}, expected {want:08X}")
    assert not errors, "wrong final state:\n  " + "\n  ".join(errors)
