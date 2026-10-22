# RV32I 5-Stage Pipelined CPU with Dynamic Branch Prediction

A 5-stage pipelined RISC-V (RV32I) processor in SystemVerilog, with full data
forwarding, load-use hazard detection, and a 16-entry Branch Target Buffer (BTB)
with 2-bit saturating counters. Verified with cocotb testbenches on Verilator.

## Results

Cycles to run each benchmark, and pipeline flushes caused by mispredicted
branches and jumps (each flush costs 2 cycles):

| Benchmark | Static not-taken | BTB | BTB + 2-bit counters |
|-----------|------------------|-----|----------------------|
| `loop`: nested loop + function call | 189 cycles / 36 flushes | **135** / 9 | **135** / 9 |
| `bias`: loop with a branch taken 1 in 4 | 123 / 19 | 115 / 15 | **99** / 7 |
| `full`: straight-line test program | 110 / 16 | 110 / 16 | 110 / 16 |

- **`loop`**: the BTB removes 75% of flushes (**29% fewer cycles**). The 9
  remaining flushes are 5 first-time misses (branches not yet in the BTB) and
  4 loop exits.
- **`bias`**: a BTB alone predicts "taken" on every hit, so it mispredicts the
  rarely-taken branch 3 times in 4. The 2-bit counters learn that it is usually
  not taken: flushes drop from 15 to 7 (**14% fewer cycles** than the BTB alone).
- **`full`**: every branch runs only once, so no predictor can learn anything.
  It is included as a correctness check, not a performance benchmark.

## Architecture

```
        +-------+        +--------+        +---------+        +--------+        +------------+
  PC -> | FETCH | IF/ID  | DECODE | ID/EX  | EXECUTE | EX/MEM | MEMORY | MEM/WB | WRITE-BACK |
        +-------+   ||   +--------+   ||   +---------+   ||   +--------+   ||   +------------+
            ^       ||        ^       ||     |    ^      ||       |        ||         |
            |                 |              |    |               |                   |
           BTB          load-use stall       |    +--- forwarding (MEM, WB) ----------+
         lookup                              |
            ^                                v
            +------ BTB update, mispredict redirect + flush
```

| Stage | Work |
|-------|------|
| **FETCH** | Instruction memory read; BTB lookup chooses the next PC (predicted target or PC+4) |
| **DECODE** | Control unit, register file read, immediate generation, load-use hazard detection |
| **EXECUTE** | ALU, branch resolution, jump target, mispredict detection, BTB update |
| **MEMORY** | Load/store byte-lane decoding, data memory access, load sign/zero extension |
| **WRITE-BACK** | Write-back mux (ALU / load / PC+4 / LUI-AUIPC) into the register file |

Signal names carry the stage they belong to: no suffix (fetch/decode), `_d`
(IF/ID), `_e` (ID/EX), `_m` (EX/MEM), `_w` (MEM/WB).

### Hazards

- **Data hazards**: results are forwarded to EXECUTE from the MEMORY and
  WRITE-BACK stages, so back-to-back dependent instructions need no stalls.
  The register file bypasses its write port to its read ports, so DECODE reads a
  value being written back in the same cycle. Writes to `x0` are never forwarded.
- **Load-use**: a load followed by an instruction that uses its result stalls
  for one cycle (PC and IF/ID hold, a bubble goes into ID/EX), then forwarding
  supplies the loaded value.
- **Control hazards**: branches and jumps resolve in EXECUTE. On a mispredict,
  the two younger instructions in IF/ID and ID/EX are flushed and the PC is
  redirected: a **2-cycle penalty**.

### Branch predictor

A direct-mapped BTB (`src/btb.sv`), looked up in FETCH with the current PC and
updated in EXECUTE once the branch resolves.

```
  PC:  | tag [31:6] | index [5:2] | 00 |

  Entry (x16):  valid | tag (26 b) | target (32 b) | counter (2 b)
```

- **Lookup**: predict taken when the entry is valid, its tag matches the PC,
  and its counter is in a taken state (`1x`). The predicted target comes from
  the entry.
- **Counter**: `00` strongly not-taken, `01` weakly not-taken, `10` weakly
  taken, `11` strongly taken. Saturates at both ends, so one unusual outcome
  does not flip the prediction.
- **Update policy**:

  | Outcome | Entry in BTB | Action |
  |---------|--------------|--------|
  | taken | no | allocate: tag, target, counter = `10` |
  | taken | yes | refresh target, count up |
  | not taken | yes | count down |
  | not taken | no | nothing (never-taken branches use no entries) |

- **Mispredict detection** (EXECUTE) checks both the direction and the target, so
  a JALR whose target changed is also caught and corrected.

The prediction travels down the pipeline with its instruction (`pred_taken_d/_e`,
`pred_target_d/_e`), and EXECUTE compares it with the actual outcome.

## ISA support

RV32I base integer instructions:

- **ALU**: `add sub and or xor sll srl sra slt sltu` and their immediate forms
- **Loads/stores**: `lb lh lw lbu lhu sb sh sw` (a misaligned load does not write its register)
- **Branches**: `beq bne blt bge bltu bgeu`
- **Jumps**: `jal jalr`
- **Upper immediates**: `lui auipc`

Not implemented: `fence`, `ecall`, `ebreak`, CSRs.

## Repository layout

```
src/
  cpu.sv                  top level: pipeline, hazards, forwarding, branch handling
  btb.sv                  branch target buffer with 2-bit counters
  control.sv              main decoder + ALU decoder
  alu.sv                  ALU
  regfile.sv              32 x 32-bit register file
  signext.sv              immediate generator (I/S/B/J/U)
  load_store_decoder.sv   byte enables and store-data alignment
  reader.sv               load data extraction and sign/zero extension
  memory.sv               128-word memory (instruction and data), loaded from .hex
  riscv_pkg.sv            opcode / funct3 / ALU encodings
tb/
  cpu/    31 directed tests, one file per pipeline-construction step:
          IF/ID, ID/EX, EX/MEM, MEM/WB registers, forwarding, load-use stall,
          branch/jump flushing
  full/   full test program (back-to-back dependencies, loads, branches, jumps);
          final state compared against a single-cycle reference CPU
  loop/   branch predictor benchmark: nested loop with a function call
  bias/   branch predictor benchmark: branch taken 1 time in 4
```

## Running the tests

Requires [Verilator](https://www.veripool.org/verilator/) 5.x, Python 3 and
[cocotb](https://www.cocotb.org/) 2.0.

```sh
cd tb/loop     # or tb/cpu, tb/full, tb/bias
make           # build and run; prints cycle count and branch statistics
make waves     # open dump.vcd in GTKWave
```

The `loop` and `bias` programs are generated by `make_program.py` in their
directories (`python3 make_program.py` rewrites `test_imemory.hex`).

## Roadmap

- [ ] Run the official [riscv-tests](https://github.com/riscv-software-src/riscv-tests) RV32I suite
- [ ] Logic synthesis with Yosys: area and critical path
- [ ] RTL-to-GDSII on SkyWater Sky130 with OpenLane
