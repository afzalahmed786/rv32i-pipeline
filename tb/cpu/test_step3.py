import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

# execute-stage signal -> memory-stage copy held in the EX/MEM register
EX_MEM_SIGNALS = {
    "alu_result":          "alu_result_m",
    "read_reg2_e":         "read_reg2_m",
    "pc_e":                "pc_m",
    "pc_plus_second_add":  "pc_plus_second_add_m",
    "dest_reg_e":          "dest_reg_m",
    "f3_e":                "f3_m",
    "reg_write_e":         "reg_write_m",
    "mem_write_e":         "mem_write_m",
    "write_back_source_e": "write_back_source_m",
}

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

def sample(dut, names):
    return {name: int(getattr(dut.core, name).value) for name in names}

@cocotb.test()
async def ex_mem_register_test(dut):
    """Step 3: memory stage sees the execute stage's results and control one cycle later"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await RisingEdge(dut.clk)

    prev = sample(dut, EX_MEM_SIGNALS.keys())
    for cycle in range(14):
        await RisingEdge(dut.clk)
        for execute_name, memory_name in EX_MEM_SIGNALS.items():
            got = int(getattr(dut.core, memory_name).value)
            assert got == prev[execute_name], \
                f"cycle {cycle}: {memory_name} = {got:X}, expected {prev[execute_name]:X} (previous {execute_name})"
        prev = sample(dut, EX_MEM_SIGNALS.keys())

@cocotb.test()
async def ex_mem_reset_test(dut):
    """Step 3: reset clears the write enables held in the EX/MEM register"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.core.reg_write_m.value) == 0, "reg_write_m must be 0 in reset"
    assert int(dut.core.mem_write_m.value) == 0, "mem_write_m must be 0 in reset"
    dut.rst_n.value = 1

@cocotb.test()
async def store_timing_test(dut):
    """Step 3: the store happens in the memory stage, one cycle after the ALU computes its address"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    # sw x5, 0x1C(x0) is at address 0x1C: wait until it is in the memory stage
    for _ in range(30):
        await RisingEdge(dut.clk)
        if int(dut.core.mem_write_m.value) == 1:
            break
    else:
        assert False, "mem_write_m never went high: the sw never reached the memory stage"
    assert int(dut.core.pc_m.value) == 0x1C, f"store in memory stage has pc_m = {int(dut.core.pc_m.value):X}, expected 1C"
    assert int(dut.core.alu_result_m.value) == 0x1C, "store address (alu_result_m) should be 0x1C"
    assert int(dut.core.read_reg2_m.value) == 3, "store data (read_reg2_m) should be x5 = 3"
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    got = int(dut.data_memory.mem[7].value)
    assert got == 3, f"mem[7] = {got:08X}, expected 00000003"
