import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

# memory-stage signal -> write-back-stage copy held in the MEM/WB register
MEM_WB_SIGNALS = {
    "alu_result_m":              "alu_result_w",
    "mem_read_write_back_data":  "mem_read_write_back_data_w",
    "mem_read_write_back_valid": "mem_read_write_back_valid_w",
    "pc_m":                      "pc_w",
    "pc_plus_second_add_m":      "pc_plus_second_add_w",
    "dest_reg_m":                "dest_reg_w",
    "reg_write_m":               "reg_write_w",
    "write_back_source_m":       "write_back_source_w",
}

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

def sample(dut, names):
    return {name: int(getattr(dut.core, name).value) for name in names}

async def run_until_pc(dut, stage_pc, address, limit=30):
    """Clock until the instruction at `address` is in the stage whose pc is `stage_pc`"""
    for _ in range(limit):
        if int(getattr(dut.core, stage_pc).value) == address:
            return
        await RisingEdge(dut.clk)
    assert False, f"{stage_pc} never reached {address:X}"

@cocotb.test()
async def mem_wb_register_test(dut):
    """Step 4: write-back stage sees the memory stage's results and control one cycle later"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await RisingEdge(dut.clk)

    prev = sample(dut, MEM_WB_SIGNALS.keys())
    for cycle in range(15):
        await RisingEdge(dut.clk)
        for memory_name, wb_name in MEM_WB_SIGNALS.items():
            got = int(getattr(dut.core, wb_name).value)
            assert got == prev[memory_name], \
                f"cycle {cycle}: {wb_name} = {got:X}, expected {prev[memory_name]:X} (previous {memory_name})"
        prev = sample(dut, MEM_WB_SIGNALS.keys())

@cocotb.test()
async def mem_wb_reset_test(dut):
    """Step 4: reset clears the register write enable held in the MEM/WB register"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.core.reg_write_w.value) == 0, "reg_write_w must be 0 in reset"
    dut.rst_n.value = 1

@cocotb.test()
async def write_back_timing_test(dut):
    """Step 4: add x5 (address 0x10) writes x5 while it is in the write-back stage, not earlier"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await run_until_pc(dut, "pc_m", 0x10)
    assert int(dut.core.regfile.registers[5].value) == 0, \
        "x5 was already written while add x5 was only in the memory stage"
    await run_until_pc(dut, "pc_w", 0x10)
    assert int(dut.core.regfile.registers[5].value) == 0, \
        "x5 changed before add x5 finished its write-back cycle"
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.core.regfile.registers[5].value) == 3, "x5 should be 3 after add x5 leaves write-back"

@cocotb.test()
async def regfile_same_cycle_test(dut):
    """Step 4: decode reads a register in the same cycle write-back writes it, and sees the new value"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    # sw x5, 0x1C(x0) is in decode while add x5 (0x10) is in write-back
    await run_until_pc(dut, "pc_d", 0x1C)
    assert int(dut.core.pc_w.value) == 0x10, f"expected add x5 in write-back, pc_w = {int(dut.core.pc_w.value):X}"
    got = int(dut.core.read_reg2.value)
    assert got == 3, f"sw reads x5 = {got} in decode, expected 3 (the value being written back this cycle)"
