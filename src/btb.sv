module btb #(parameter ENTRIES = 16)(
    input clk,
    input rst_n,
    input [31:0] lookup_pc,
    input update_en,
    input [31:0] update_pc,
    input update_taken,
    input [31:0] update_target,
    output hit,
    output hit_taken,
    output [31:0] hit_target
);

localparam IDX_BITS = $clog2(ENTRIES);
logic [IDX_BITS-1:0] lookup_idx, update_idx;
logic [25:0]         lookup_tag, update_tag;

logic                valid   [ENTRIES];
logic [25:0]         tag     [ENTRIES];
logic [31:0]         target  [ENTRIES];
logic [1:0]          counter [ENTRIES];

assign lookup_idx = lookup_pc[IDX_BITS+1:2];
assign lookup_tag = lookup_pc[31:6];
assign update_idx = update_pc[IDX_BITS+1:2];
assign update_tag = update_pc[31:6];

assign hit        = valid[lookup_idx] && (tag[lookup_idx] == lookup_tag);
assign hit_target = target[lookup_idx];
assign hit_taken  = counter[lookup_idx][1];

logic update_hit;
assign update_hit = valid[update_idx] && (tag[update_idx] == update_tag);

always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 0; i < ENTRIES; i++)
            valid[i] <= 1'b0;
    end
    else if (update_en) begin
        if (update_taken) begin
            if (!update_hit) begin
                valid[update_idx]   <= 1'b1;
                tag[update_idx]     <= update_tag;
                target[update_idx]  <= update_target;
                counter[update_idx] <= 2'b10;
            end
            else begin
                target[update_idx] <= update_target;
                if (counter[update_idx] != 2'b11)
                    counter[update_idx] <= counter[update_idx] + 2'b01;
            end
        end
        else if (update_hit) begin
            if (counter[update_idx] != 2'b00)
                counter[update_idx] <= counter[update_idx] - 2'b01;
        end
    end
end

endmodule
