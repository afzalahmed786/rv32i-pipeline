# Builds test_imemory.hex for the bias program (no assembler needed).
# Run:  python3 make_program.py
#
# The program: a 16-iteration loop containing a branch that is taken only
# 1 time in 4 (when the counter is a multiple of 4). A BTB that predicts
# "taken" on every hit gets this branch wrong 3 times in 4; a 2-bit counter
# learns that it is usually NOT taken.
#
#   0x00  addi x1, x0, 16      loop counter = 16
#   0x04  addi x3, x0, 0       common-path count = 0
#   0x08  nop
#   0x0C  andi x4, x1, 3       loop: x4 = x1 % 4
#   0x10  beq  x4, x0, +8      -> 0x18   (taken when x1 = 16, 12, 8, 4: 4 of 16)
#   0x14  addi x3, x3, 1       common path, skipped when the branch is taken
#   0x18  addi x1, x1, -1
#   0x1C  bne  x1, x0, -16     -> 0x0C   (taken 15 times, then falls through)
#   0x20  addi x6, x0, 1       end marker
#   0x24  nop                  LAST_PC: the test stops when this reaches write-back
#
# Final state: x1 = 0, x3 = 12, x4 = 1 (last iteration: 1 % 4), x6 = 1

def r_type(f7, rs2, rs1, f3, rd, op):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

def i_type(imm, rs1, f3, rd, op):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

def b_type(imm, rs2, rs1, f3):
    imm &= 0x1FFF
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) \
         | (f3 << 12) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | 0b1100011

def addi(rd, rs1, imm): return i_type(imm, rs1, 0b000, rd, 0b0010011)
def andi(rd, rs1, imm): return i_type(imm, rs1, 0b111, rd, 0b0010011)
def beq(rs1, rs2, imm): return b_type(imm, rs2, rs1, 0b000)
def bne(rs1, rs2, imm): return b_type(imm, rs2, rs1, 0b001)
NOP = addi(0, 0, 0)

program = [
    addi(1, 0, 16),
    addi(3, 0, 0),
    NOP,
    andi(4, 1, 3),
    beq(4, 0, 8),
    addi(3, 3, 1),
    addi(1, 1, -1),
    bne(1, 0, -16),
    addi(6, 0, 1),
    NOP,
]
program += [NOP] * (128 - len(program))   # fill the rest of instruction memory

with open("test_imemory.hex", "w") as f:
    for word in program:
        f.write(f"{word:08X}\n")
with open("test_dmemory.hex", "w") as f:
    for _ in range(128):
        f.write("00000000\n")
print(f"wrote {len(program)} words")
