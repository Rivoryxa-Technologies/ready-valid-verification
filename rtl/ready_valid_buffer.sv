// SPDX-License-Identifier: MIT
// One-entry ready/valid elastic buffer.
module ready_valid_buffer #(
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

    assign in_ready = !full_q || out_ready;
    assign out_valid = full_q;
    assign out_data  = data_q;

    always_ff @(posedge clk) begin
        if (rst) begin
            full_q <= 1'b0;
            data_q <= '0;
        end else if (in_ready) begin
            full_q <= in_valid;
            if (in_valid)
                data_q <= in_data;
        end
    end
endmodule
