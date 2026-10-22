import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

# Final check: run the original single-cycle test program (written with no nops,
# full of back-to-back dependencies, loads, branches and jumps) on the pipeline,
# and compare the final state with the single-cycle CPU's final state.
#
# The expected values were recorded by running the same program and data memory
# on the single-cycle CPU in /home/afzal/single_cycle until it reached the final
# nop at 0x13C.

LAST_PC = 0x13C   # address of the final nop; everything before it has finished

EXPECTED_REGS = [
    0x00000000, 0x00000050, 0x000000F8, 0x00000100,
    0x0000010C, 0x2F2FA000, 0x7F4FD46A, 0x00000010,
    0xBD5B8554, 0xC9990000, 0x00000001, 0x00000000,
    0xFFFF8DDC, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0xFFFFFFDE, 0x000000BE,
    0xFFFFDEAD, 0x0000DEAD, 0x00000000, 0x00000001,
    0x00000000, 0x7F4FD38B, 0xDEADC09A, 0x000000E0,
    0x15244450, 0xFDEADC99, 0x0DEADC99, 0x00215244,
]

EXPECTED_MEM = [
    0xAEAEAEAE, 0x00540000, 0xDEADBEEF, 0xDEADBEEF,
    0x00000AAA, 0x125F552D, 0x7F4FD46A, 0x44458554,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
]

# Branch statistics (baseline for the branch predictor work).
# Sampled on the falling edge, in the middle of the cycle, when all signals have settled.
# Every instruction spends exactly one cycle in EXECUTE, so each branch/jump is counted once.
stats = {"branches": 0, "branches_taken": 0, "jumps": 0, "flushes": 0}
branch_log = []   # (pc of the branch, taken?)

async def branch_monitor(dut):
    while True:
        await FallingEdge(dut.clk)
        if int(dut.rst_n.value) == 0:
            continue
        taken = int(dut.core.actual_taken.value)
        if int(dut.core.branch_e.value):
            stats["branches"] += 1
            stats["branches_taken"] += taken
            branch_log.append((int(dut.core.pc_e.value), taken))
        if int(dut.core.jump_e.value):
            stats["jumps"] += 1
        stats["flushes"] += int(dut.core.mispredict.value)

@cocotb.test()
async def full_program_test(dut):
    """Step 8: the pipeline ends in the same state as the single-cycle CPU"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    cocotb.start_soon(branch_monitor(dut))

    # wait until the final nop reaches write-back: every earlier instruction has completed
    cycles = 0
    while int(dut.core.pc_w.value) != LAST_PC:
        await RisingEdge(dut.clk)
        cycles += 1
        assert cycles < 200, "the final instruction never reached write-back"
    await RisingEdge(dut.clk)
    print(f"pipeline finished the program in {cycles} cycles (single-cycle CPU: 68 cycles)")
    print(f"branches: {stats['branches']} (taken: {stats['branches_taken']}), "
          f"jumps: {stats['jumps']}, flushes: {stats['flushes']} "
          f"-> {2 * stats['flushes']} cycles lost to flushes")
    for pc, taken in branch_log:
        print(f"  branch at 0x{pc:03X}: {'taken' if taken else 'not taken'}")

    errors = []
    for n, want in enumerate(EXPECTED_REGS):
        got = int(dut.core.regfile.registers[n].value)
        if got != want:
            errors.append(f"x{n} = {got:08X}, expected {want:08X}")
    for n, want in enumerate(EXPECTED_MEM):
        got = int(dut.data_memory.mem[n].value)
        if got != want:
            errors.append(f"mem[{n}] = {got:08X}, expected {want:08X}")
    assert not errors, "final state differs from the single-cycle CPU:\n  " + "\n  ".join(errors)
