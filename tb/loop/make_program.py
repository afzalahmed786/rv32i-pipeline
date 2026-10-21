# Builds test_imemory.hex for the loop program (no assembler needed).
# Run:  python3 make_program.py
#
# The program: a nested loop (outer 3 times, inner 10 times) that also calls
# a small function every outer iteration. Every branch and jump runs many
# times, so a branch predictor has something to learn.
#
#   0x00  addi x1, x0, 0       sum = 0
#   0x04  addi x3, x0, 3       outer counter = 3
#   0x08  addi x2, x0, 10      outer: inner counter = 10
#   0x0C  add  x1, x1, x2      inner: sum += inner counter
#   0x10  addi x2, x2, -1
#   0x14  bne  x2, x0, -8      -> 0x0C   (taken 9 times, then falls through)
#   0x18  jal  x5, +24         -> 0x30   call func, x5 = 0x1C
#   0x1C  addi x3, x3, -1
#   0x20  bne  x3, x0, -24     -> 0x08   (taken 2 times, then falls through)
#   0x24  jal  x0, +20         -> 0x38   skip over the function
#   0x28  addi x7, x0, 1       never runs (x7 must stay 0)
#   0x2C  addi x7, x0, 2       never runs
#   0x30  addi x4, x4, 1       func: count calls
#   0x34  jalr x0, 0(x5)       return to 0x1C
#   0x38  addi x6, x0, 1       end marker
#   0x3C  nop                  LAST_PC: the test stops when this reaches write-back
#
# Final state: x1 = 3 * (10+9+...+1) = 165, x2 = 0, x3 = 0, x4 = 3,
#              x5 = 0x1C, x6 = 1, x7 = 0

def r_type(f7, rs2, rs1, f3, rd, op):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

def i_type(imm, rs1, f3, rd, op):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op

def b_type(imm, rs2, rs1, f3):
    imm &= 0x1FFF
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) \
         | (f3 << 12) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | 0b1100011

def j_type(imm, rd):
    imm &= 0x1FFFFF
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | (((imm >> 11) & 1) << 20) \
         | (((imm >> 12) & 0xFF) << 12) | (rd << 7) | 0b1101111

def addi(rd, rs1, imm): return i_type(imm, rs1, 0b000, rd, 0b0010011)
def add(rd, rs1, rs2):  return r_type(0, rs2, rs1, 0b000, rd, 0b0110011)
def bne(rs1, rs2, imm): return b_type(imm, rs2, rs1, 0b001)
def jal(rd, imm):       return j_type(imm, rd)
def jalr(rd, rs1, imm): return i_type(imm, rs1, 0b000, rd, 0b1100111)
NOP = addi(0, 0, 0)

program = [
    addi(1, 0, 0),
    addi(3, 0, 3),
    addi(2, 0, 10),
    add(1, 1, 2),
    addi(2, 2, -1),
    bne(2, 0, -8),
    jal(5, 24),
    addi(3, 3, -1),
    bne(3, 0, -24),
    jal(0, 20),
    addi(7, 0, 1),
    addi(7, 0, 2),
    addi(4, 4, 1),
    jalr(0, 5, 0),
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
