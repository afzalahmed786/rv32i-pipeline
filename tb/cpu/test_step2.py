import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

# decode-stage signal -> execute-stage copy held in the ID/EX register
ID_EX_SIGNALS = {
    "pc_d":              "pc_e",
    "read_reg1":         "read_reg1_e",
    "read_reg2":         "read_reg2_e",
    "immediate":         "immediate_e",
    "dest_reg":          "dest_reg_e",
    "f3":                "f3_e",
    "reg_write":         "reg_write_e",
    "mem_write":         "mem_write_e",
    "alu_source":        "alu_source_e",
    "write_back_source": "write_back_source_e",
    "alu_control":       "alu_control_e",
    "second_add_source": "second_add_source_e",
}

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

def sample(dut, names):
    return {name: int(getattr(dut, name).value) for name in names}

@cocotb.test()
async def id_ex_register_test(dut):
    """Step 2: execute stage sees the decode stage's data and control one cycle later"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    await RisingEdge(dut.clk)

    prev = sample(dut, ID_EX_SIGNALS.keys())
    for cycle in range(9):
        await RisingEdge(dut.clk)
        for decode_name, execute_name in ID_EX_SIGNALS.items():
            got = int(getattr(dut, execute_name).value)
            assert got == prev[decode_name], \
                f"cycle {cycle}: {execute_name} = {got:X}, expected {prev[decode_name]:X} (previous {decode_name})"
        prev = sample(dut, ID_EX_SIGNALS.keys())

@cocotb.test()
async def id_ex_reset_test(dut):
    """Step 2: reset clears the write enables held in the ID/EX register"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.reg_write_e.value) == 0, "reg_write_e must be 0 in reset"
    assert int(dut.mem_write_e.value) == 0, "mem_write_e must be 0 in reset"
    dut.rst_n.value = 1

@cocotb.test()
async def program_result_test(dut):
    """Step 2: the program still produces the right register and memory values"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(20):
        await RisingEdge(dut.clk)
    expected = {1: 1, 2: 2, 3: 3, 4: 4, 5: 3, 6: 0xDEADBEEF}
    for reg, value in expected.items():
        got = int(dut.regfile.registers[reg].value)
        assert got == value, f"x{reg} = {got:08X}, expected {value:08X}"
    got = int(dut.data_memory.mem[7].value)
    assert got == 3, f"mem[7] = {got:08X}, expected 00000003 (sw x5, 0x1C(x0))"

@cocotb.test()
async def upper_immediate_test(dut):
    """Step 2: LUI and AUIPC (second adder) use the executing instruction's pc and immediate"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    for _ in range(20):
        await RisingEdge(dut.clk)
    got = int(dut.regfile.registers[8].value)
    assert got == 0x12345000, f"x8 = {got:08X}, expected 12345000 (lui x8, 0x12345)"
    got = int(dut.regfile.registers[9].value)
    assert got == 0x00001028, f"x9 = {got:08X}, expected 00001028 (auipc x9, 0x1 at address 0x28)"
