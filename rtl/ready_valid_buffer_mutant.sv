// SPDX-License-Identifier: MIT
// Deliberately incorrect teaching mutant: it accepts input while its only slot
// is stalled, so queued data can be overwritten. Never use as an implementation.
module ready_valid_buffer_mutant #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             in_valid,
    output logic             in_ready,
    input  logic [WIDTH-1:0] in_data,
    output logic             out_valid,
    input  logic             out_ready,
    output logic [WIDTH-1:0] out_data
);
    logic             full_q;
    logic [WIDTH-1:0] data_q;

    assign in_ready = 1'b1; // BUG: ignores a full, blocked output slot.
    assign out_valid = full_q;
    assign out_data  = data_q;

    always_ff @(posedge clk) begin
        if (rst) begin
            full_q <= 1'b0;
            data_q <= '0;
        end else begin
            full_q <= in_valid;
            if (in_valid)
                data_q <= in_data;
        end
    end
endmodule
