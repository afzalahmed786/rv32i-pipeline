import cocotb
from collections import Counter
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

# Branch predictor benchmark: a loop with a branch taken only 1 time in 4
# (see make_program.py). This is where 2-bit counters beat "hit = taken".
# The predictor may change how many cycles the program takes, never the final state.

LAST_PC = 0x24   # address of the final nop; everything before it has finished

EXPECTED_REGS = {1: 0, 3: 12, 4: 1, 6: 1}

# Sampled on the falling edge, in the middle of the cycle, when all signals have settled.
# Every instruction spends exactly one cycle in EXECUTE, so each branch/jump is counted once.
stats = {"branches": 0, "branches_taken": 0, "jumps": 0, "flushes": 0}
flushes_by_pc = Counter()

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
        if int(dut.core.mispredict.value):
            stats["flushes"] += 1
            flushes_by_pc[int(dut.core.pc_e.value)] += 1

@cocotb.test()
async def bias_program_test(dut):
    """Mostly-not-taken branch: correct final state, and report branch statistics"""
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
    print(f"bias program finished in {cycles} cycles")
    print(f"branches: {stats['branches']} (taken: {stats['branches_taken']}), "
          f"jumps: {stats['jumps']}, flushes: {stats['flushes']} "
          f"-> {2 * stats['flushes']} cycles lost to flushes")
    for pc, n in sorted(flushes_by_pc.items()):
        print(f"  flushes at pc 0x{pc:02X}: {n}")

    errors = []
    for n, want in EXPECTED_REGS.items():
        got = int(dut.core.regfile.registers[n].value)
        if got != want:
            errors.append(f"x{n} = {got:08X}, expected {want:08X}")
    assert not errors, "wrong final state:\n  " + "\n  ".join(errors)
