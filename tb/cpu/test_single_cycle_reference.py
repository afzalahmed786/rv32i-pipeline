import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

def binary_to_hex(bin_str):
    hex_str = hex(int(str(bin_str), 2))[2:]
    return hex_str.zfill(8).upper()

def hex_to_bin(hex_str):
    bin_str = bin(int(str(hex_str), 16))[2:]
    return bin_str.zfill(32).upper()

async def cpu_reset(dut):
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

@cocotb.test()
async def cpu_init_test(dut):
    """Reset the CPU and check for a good imem read"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)
    assert binary_to_hex(dut.core.pc.value) == "00000000"

    imem = []
    with open("test_imemory.hex", "r") as file:
        for line in file:
            line_content = line.strip()
            if line_content:
                imem.append(hex_to_bin(line_content))

    for counter in range(5):
        expected = imem[counter]
        assert binary_to_hex(dut.core.instruction.value) == binary_to_hex(expected), \
            f"instr {counter}: got {binary_to_hex(dut.core.instruction.value)}, exp {binary_to_hex(expected)}"
        await RisingEdge(dut.clk)

@cocotb.test()
async def cpu_instr_test(dut):
    """Run instructions and check results"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await cpu_reset(dut)

    # ---- LW: lw x18, 0x8(x0) ----
    print("\n\nTESTING LW\n\n")
    await RisingEdge(dut.clk)   # lw x18 executes, x18 <= DEADBEEF
    assert binary_to_hex(dut.core.regfile.registers[18].value) == "DEADBEEF", \
        f"x18 = {binary_to_hex(dut.core.regfile.registers[18].value)}"

    # ---- SW: sw x18, 0xC(x0) ----
    print("\n\nTESTING SW\n\n")
    test_address = int(0xC / 4)
    await RisingEdge(dut.clk)   # sw executes, mem[3] <= DEADBEEF
    assert binary_to_hex(dut.data_memory.mem[test_address].value) == "DEADBEEF", \
        f"mem[3] = {binary_to_hex(dut.data_memory.mem[test_address].value)}"

    # ---- LW: lw x19, 0x10(x0)  (memory holds 0x00000AAA) ----
    print("\n\nTESTING LW x19\n\n")
    await RisingEdge(dut.clk)   # write-back clocks 0x00000AAA into x19
    assert binary_to_hex(dut.core.regfile.registers[19].value) == "00000AAA", \
        f"x19 = {binary_to_hex(dut.core.regfile.registers[19].value)}"

    # ---- ADD: add x20, x18, x19 ----
    print("\n\nTESTING ADD\n\n")
    expected_add = (0xDEADBEEF + 0x00000AAA) & 0xFFFFFFFF   # 0xDEADC999
    await RisingEdge(dut.clk)   # write-back clocks the sum into x20
    got = binary_to_hex(dut.core.regfile.registers[20].value)
    assert got == f"{expected_add:08X}", f"x20 = {got}, expected {expected_add:08X}"

    # ---- AND: and x21, x18, x20 ----
    print("\n\nTESTING AND\n\n")
    expected_and = 0xDEADBEEF & expected_add               # 0xDEAD8889
    await RisingEdge(dut.clk)   # write-back clocks the AND into x21
    got = binary_to_hex(dut.core.regfile.registers[21].value)
    assert got == f"{expected_and:08X}", f"x21 = {got}, expected {expected_and:08X}"


    print("\n\nTESTING OR\n\n")
    await RisingEdge(dut.clk) # lw x5 0x14(x0) | x5 <= 125F552D
    assert binary_to_hex(dut.core.regfile.registers[5].value) == "125F552D"
    await RisingEdge(dut.clk) # lw x6 0x18(x0) | x6 <= 7F4FD46A
    assert binary_to_hex(dut.core.regfile.registers[6].value) == "7F4FD46A"
    await RisingEdge(dut.clk) # or x7 x5 x6 | x7 <= 7F5FD56F
    assert binary_to_hex(dut.core.regfile.registers[7].value) == "7F5FD56F"

    print("\n\nTESTING BEQ\n\n")

    # 0x20: beq x6,x7,0xC  #1 NOT taken (x6 != x7) -> falls through to 0x24
    assert binary_to_hex(dut.core.instruction.value) == "00730663"
    await RisingEdge(dut.clk)

    # 0x24: lw x22, 0x8(x0)  -> x22 <= DEADBEEF
    assert binary_to_hex(dut.core.instruction.value) == "00802B03"
    await RisingEdge(dut.clk)

    # 0x28: beq x18,x22,0x10  #2 TAKEN (x18==x22) -> jumps to 0x38
    assert binary_to_hex(dut.core.regfile.registers[22].value) == "DEADBEEF"
    assert binary_to_hex(dut.core.instruction.value) == "01690863"
    await RisingEdge(dut.clk)

    # 0x38: lw x22, 0x0(x0)  -> x22 <= AEAEAEAE
    assert binary_to_hex(dut.core.instruction.value) == "00002B03"
    await RisingEdge(dut.clk)

    # 0x3C: beq x22,x22,-0x8  #3 TAKEN (x22==x22) -> jumps back to 0x34
    assert binary_to_hex(dut.core.regfile.registers[22].value) == "AEAEAEAE"
    assert binary_to_hex(dut.core.instruction.value) == "FF6B0CE3"
    await RisingEdge(dut.clk)

    # 0x34: beq x0,x0,0xC  #4 TAKEN (x0==x0) -> jumps to 0x40
    assert binary_to_hex(dut.core.instruction.value) == "00000663"
    await RisingEdge(dut.clk)

    # 0x40: final nop
    assert binary_to_hex(dut.core.instruction.value) == "00000013"

    print("\n\nBEQ TEST PASSED\n\n")

    # Check test's init state
    print("\n\nTESTING JAL\n\n")
    await RisingEdge(dut.clk)
    assert binary_to_hex(dut.core.instruction.value) == "00C000EF"
    assert binary_to_hex(dut.core.pc.value) == "00000044"
    await RisingEdge(dut.clk) # jal x1 0xC
    # Check new state & ra (x1) register value
    assert binary_to_hex(dut.core.instruction.value) == "FFDFF0EF"
    assert binary_to_hex(dut.core.pc.value) == "00000050"
    assert binary_to_hex(dut.core.regfile.registers[1].value) == "00000048" # stored old pc + 4
    await RisingEdge(dut.clk) # jal x1 -4
    # Check new state & ra (x1) register value
    assert binary_to_hex(dut.core.instruction.value) == "00C000EF"
    assert binary_to_hex(dut.core.pc.value) == "0000004C"
    assert binary_to_hex(dut.core.regfile.registers[1].value) == "00000054" # stored old pc + 4
    await RisingEdge(dut.clk) # jal x1 0xC
    # Check new state & ra (x1) register value
    assert binary_to_hex(dut.core.instruction.value) == "00C02383"
    assert binary_to_hex(dut.core.pc.value) == "00000058"
    assert binary_to_hex(dut.core.regfile.registers[1].value) == "00000050" # stored old pc + 4
    await RisingEdge(dut.clk) # lw x7 0xC(x0)
    assert binary_to_hex(dut.core.regfile.registers[7].value) == "DEADBEEF"


    print("\n\nTESTING ADDI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "1AB38D13"
    assert not binary_to_hex(dut.core.regfile.registers[26].value) == "DEADC09A"
    await RisingEdge(dut.clk) # addi x26 x7 0x1AB
    assert binary_to_hex(dut.core.instruction.value) == "F2130C93"
    assert binary_to_hex(dut.core.regfile.registers[26].value) == "DEADC09A"
    await RisingEdge(dut.clk) # addi x25 x6 0xF21
    assert binary_to_hex(dut.core.regfile.registers[25].value) == "7F4FD38B"

    print("\n\nTESTING AUIPC\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "1F1FA297"
    await RisingEdge(dut.clk)
    assert binary_to_hex(dut.core.regfile.registers[5].value) == "1F1FA064"
    print("\n\nTESTING LUI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "2F2FA2B7"
    await RisingEdge(dut.clk)
    assert binary_to_hex(dut.core.regfile.registers[5].value) == "2F2FA000"

    print("\n\nTESTING SLTI\n\n")
    assert binary_to_hex(dut.core.regfile.registers[19].value) == "00000AAA"
    assert binary_to_hex(dut.core.instruction.value) == "FFF9AB93"
    await RisingEdge(dut.clk) # slti x23 x19 0xFFF
    assert binary_to_hex(dut.core.regfile.registers[23].value) == "00000000"
    await RisingEdge(dut.clk) # slti x23 x23 0x001
    assert binary_to_hex(dut.core.regfile.registers[23].value) == "00000001"

    print("\n\nTESTING SLTIU\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "FFF9BB13"
    await RisingEdge(dut.clk) # sltiu x22 x19 0xFFF
    assert binary_to_hex(dut.core.regfile.registers[22].value) == "00000001"
    await RisingEdge(dut.clk) # sltiu x22 x19 0x001
    assert binary_to_hex(dut.core.regfile.registers[22].value) == "00000000"
    print("\n\nTESTING XORI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "AAA94913"
    await RisingEdge(dut.clk) # xori x18 x19 0xAAA
    assert binary_to_hex(dut.core.regfile.registers[18].value) == "21524445"
    await RisingEdge(dut.clk) # xori x19 x18 0x000
    assert (
        binary_to_hex(dut.core.regfile.registers[19].value) ==
        binary_to_hex(dut.core.regfile.registers[18].value)
    )
    
    print("\n\nTESTING ANDI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "0F03FD93"
    await RisingEdge(dut.clk)   # andi x27, x7, 0x0F0
    assert binary_to_hex(dut.core.regfile.registers[27].value) == "000000E0"

    print("\n\nTESTING SLLI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "00499E13"
    await RisingEdge(dut.clk)   # slli x28, x19, 4
    assert binary_to_hex(dut.core.regfile.registers[28].value) == "15244450"

    print("\n\nTESTING SRLI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "004A5F13"
    await RisingEdge(dut.clk)   # srli x30, x20, 4  (negative input, logical: zero-fill)
    assert binary_to_hex(dut.core.regfile.registers[30].value) == "0DEADC99"

    print("\n\nTESTING SRAI\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "404A5E93"
    await RisingEdge(dut.clk)   # srai x29, x20, 4  (negative input, arithmetic: sign-fill)
    assert binary_to_hex(dut.core.regfile.registers[29].value) == "FDEADC99"
    assert binary_to_hex(dut.core.instruction.value) == "4089DF93"
    await RisingEdge(dut.clk)   # srai x31, x19, 8  (positive input: fills with 0s)
    assert binary_to_hex(dut.core.regfile.registers[31].value) == "00215244"

    print("\n\nTESTING SUB\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "413A0433"
    await RisingEdge(dut.clk)   # sub x8, x20, x19
    assert binary_to_hex(dut.core.regfile.registers[8].value) == "BD5B8554"
    
    print("\n\nTESTING SLL\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "001A14B3"
    await RisingEdge(dut.clk)   # sll x9, x20, x1  (x1 = 0x50 -> shift by 16)
    assert binary_to_hex(dut.core.regfile.registers[9].value) == "C9990000"

    print("\n\nTESTING SLT\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "013A2533"
    await RisingEdge(dut.clk)   # slt x10, x20, x19  (signed: neg < pos)
    assert binary_to_hex(dut.core.regfile.registers[10].value) == "00000001"

    print("\n\nTESTING SLTU\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "013A35B3"
    await RisingEdge(dut.clk)   # sltu x11, x20, x19  (unsigned: DEAD.. > 2152..)
    assert binary_to_hex(dut.core.regfile.registers[11].value) == "00000000"

    print("\n\nTESTING XOR\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "013A4633"
    await RisingEdge(dut.clk)   # xor x12, x20, x19
    assert binary_to_hex(dut.core.regfile.registers[12].value) == "FFFF8DDC"
    
    print("\n\nTESTING B-TYPE\n\n")
    x17_before = binary_to_hex(dut.core.regfile.registers[17].value)

    # ---- BNE ----
    assert binary_to_hex(dut.core.pc.value) == "000000AC"
    assert binary_to_hex(dut.core.instruction.value) == "013A1463"
    await RisingEdge(dut.clk)   # bne x20, x19, +8  -> TAKEN
    assert binary_to_hex(dut.core.pc.value) == "000000B4"

    assert binary_to_hex(dut.core.instruction.value) == "01399463"
    await RisingEdge(dut.clk)   # bne x19, x19, +8  -> NOT taken
    assert binary_to_hex(dut.core.pc.value) == "000000B8"

    # ---- BLT (signed) ----
    assert binary_to_hex(dut.core.instruction.value) == "013A4463"
    await RisingEdge(dut.clk)   # blt x20, x19, +8  -> TAKEN (neg < pos)
    assert binary_to_hex(dut.core.pc.value) == "000000C0"

    assert binary_to_hex(dut.core.instruction.value) == "0149C463"
    await RisingEdge(dut.clk)   # blt x19, x20, +8  -> NOT taken
    assert binary_to_hex(dut.core.pc.value) == "000000C4"

    # ---- BGE (signed) ----
    assert binary_to_hex(dut.core.instruction.value) == "0149D463"
    await RisingEdge(dut.clk)   # bge x19, x20, +8  -> TAKEN (pos >= neg)
    assert binary_to_hex(dut.core.pc.value) == "000000CC"

    assert binary_to_hex(dut.core.instruction.value) == "013A5463"
    await RisingEdge(dut.clk)   # bge x20, x19, +8  -> NOT taken
    assert binary_to_hex(dut.core.pc.value) == "000000D0"

    assert binary_to_hex(dut.core.instruction.value) == "0139D463"
    await RisingEdge(dut.clk)   # bge x19, x19, +8  -> TAKEN (equal)
    assert binary_to_hex(dut.core.pc.value) == "000000D8"

    # ---- BLTU (unsigned) ----
    assert binary_to_hex(dut.core.instruction.value) == "0149E463"
    await RisingEdge(dut.clk)   # bltu x19, x20, +8 -> TAKEN
    assert binary_to_hex(dut.core.pc.value) == "000000E0"

    assert binary_to_hex(dut.core.instruction.value) == "013A6463"
    await RisingEdge(dut.clk)   # bltu x20, x19, +8 -> NOT taken
    assert binary_to_hex(dut.core.pc.value) == "000000E4"

    # ---- BGEU (unsigned) ----
    assert binary_to_hex(dut.core.instruction.value) == "013A7463"
    await RisingEdge(dut.clk)   # bgeu x20, x19, +8 -> TAKEN
    assert binary_to_hex(dut.core.pc.value) == "000000EC"

    assert binary_to_hex(dut.core.instruction.value) == "0149F463"
    await RisingEdge(dut.clk)   # bgeu x19, x20, +8 -> NOT taken
    assert binary_to_hex(dut.core.pc.value) == "000000F0"

    assert binary_to_hex(dut.core.instruction.value) == "0139F463"
    await RisingEdge(dut.clk)   # bgeu x19, x19, +8 -> TAKEN (equal)
    assert binary_to_hex(dut.core.pc.value) == "000000F8"


    print("\n\nTESTING JALR\n\n")
    x17_before = binary_to_hex(dut.core.regfile.registers[17].value)

    assert binary_to_hex(dut.core.pc.value) == "000000F8"
    assert binary_to_hex(dut.core.instruction.value) == "00000117"
    await RisingEdge(dut.clk)   # auipc x2, 0
    assert binary_to_hex(dut.core.regfile.registers[2].value) == "000000F8"

    assert binary_to_hex(dut.core.instruction.value) == "011101E7"
    await RisingEdge(dut.clk)   # jalr x3, 17(x2) -> 0x109 & ~1 = 0x108
    assert binary_to_hex(dut.core.pc.value) == "00000108"
    assert binary_to_hex(dut.core.regfile.registers[3].value) == "00000100"   # link = old pc + 4

    assert binary_to_hex(dut.core.instruction.value) == "00418267"
    await RisingEdge(dut.clk)   # jalr x4, 4(x3) -> 0x104 (backward)
    assert binary_to_hex(dut.core.pc.value) == "00000104"
    assert binary_to_hex(dut.core.regfile.registers[4].value) == "0000010C"   # link = old pc + 4

    assert binary_to_hex(dut.core.regfile.registers[17].value) == x17_before   # poison skipped
    assert binary_to_hex(dut.core.instruction.value) == "00C18067"
    await RisingEdge(dut.clk)   # jalr x0, 12(x3) -> 0x10C
    assert binary_to_hex(dut.core.pc.value) == "0000010C"
    print("\n\nJALR PASSED\n\n")

    print("\n\nTESTING SB\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "008020A3"
    await RisingEdge(dut.clk) # sw x8 0x1(x0)
    assert binary_to_hex(dut.data_memory.mem[1].value) == "00000000" # remains UNFAZED
    await RisingEdge(dut.clk) # sb x8 0x6(x0)
    assert binary_to_hex(dut.data_memory.mem[1].value) == "00540000"

    print("\n\nTESTING SH\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "00801E23"
    assert binary_to_hex(dut.data_memory.mem[7].value) == "00000000"
    await RisingEdge(dut.clk) # sh x8 0x1C(x0) | lower half <= 8554
    assert binary_to_hex(dut.data_memory.mem[7].value) == "00008554"

    assert binary_to_hex(dut.core.instruction.value) == "01201F23"
    await RisingEdge(dut.clk) # sh x18 0x1E(x0) | upper half <= 4445, lower half kept
    assert binary_to_hex(dut.data_memory.mem[7].value) == "44458554"

    assert binary_to_hex(dut.core.instruction.value) == "028010A3"
    await RisingEdge(dut.clk) # sh x8 0x21(x0) | misaligned -> no write
    assert binary_to_hex(dut.data_memory.mem[8].value) == "00000000" # remains UNFAZED
    assert binary_to_hex(dut.data_memory.mem[7].value) == "44458554"

    print("\n\nTESTING LB / LBU / LH / LHU\n\n")
    assert binary_to_hex(dut.core.instruction.value) == "01000393"
    await RisingEdge(dut.clk) # addi x7 x0 0x10
    assert binary_to_hex(dut.core.regfile.registers[7].value) == "00000010"

    assert binary_to_hex(dut.core.instruction.value) == "FFF3A903"
    await RisingEdge(dut.clk) # lw x18 -1(x7) | addr 0xF misaligned -> no write
    assert binary_to_hex(dut.core.regfile.registers[18].value) == "21524445" # remains UNFAZED

    assert binary_to_hex(dut.core.instruction.value) == "FFF38903"
    await RisingEdge(dut.clk) # lb x18 -1(x7) | addr 0xF -> byte DE, sign extended
    assert binary_to_hex(dut.core.regfile.registers[18].value) == "FFFFFFDE"

    assert binary_to_hex(dut.core.instruction.value) == "FFD3C983"
    await RisingEdge(dut.clk) # lbu x19 -3(x7) | addr 0xD -> byte BE, zero extended
    assert binary_to_hex(dut.core.regfile.registers[19].value) == "000000BE"

    assert binary_to_hex(dut.core.instruction.value) == "FFD39A03"
    await RisingEdge(dut.clk) # lh x20 -3(x7) | addr 0xD misaligned -> no write
    assert binary_to_hex(dut.core.regfile.registers[20].value) == "DEADC999" # remains UNFAZED

    assert binary_to_hex(dut.core.instruction.value) == "FFA39A03"
    await RisingEdge(dut.clk) # lh x20 -6(x7) | addr 0xA -> half DEAD, sign extended
    assert binary_to_hex(dut.core.regfile.registers[20].value) == "FFFFDEAD"

    assert binary_to_hex(dut.core.instruction.value) == "FFD3DA83"
    await RisingEdge(dut.clk) # lhu x21 -3(x7) | addr 0xD misaligned -> no write
    assert binary_to_hex(dut.core.regfile.registers[21].value) == "DEAD8889" # remains UNFAZED

    assert binary_to_hex(dut.core.instruction.value) == "FFA3DA83"
    await RisingEdge(dut.clk) # lhu x21 -6(x7) | addr 0xA -> half DEAD, zero extended
    assert binary_to_hex(dut.core.regfile.registers[21].value) == "0000DEAD"

    