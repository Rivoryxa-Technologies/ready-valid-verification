// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb #(
    parameter int WIDTH = 8,
    parameter int RANDOM_CYCLES = 400
);
    logic clk = 0;
    logic rst, in_valid, in_ready, out_valid, out_ready;
    logic [WIDTH-1:0] in_data, out_data;
    logic [WIDTH-1:0] expected[$];
    logic [WIDTH-1:0] held_data;
    logic held_valid, last_take_in, last_take_out;
    integer configured_seed, random_state, cycle, accepted, emitted;
    integer source_value;

`ifdef MUTANT
    ready_valid_buffer_mutant #(.WIDTH(WIDTH)) dut (.*);
`else
    ready_valid_buffer #(.WIDTH(WIDTH)) dut (.*);
`endif

    always #5 clk = ~clk;

    task automatic fail(input string marker, input string detail);
        $display("%s: %s", marker, detail);
        $fatal(1, "%s", marker);
    endtask

    // Sample transfers immediately before the active edge, then check the
    // registered result immediately after it.
    task automatic step;
        logic take_in, take_out;
        logic [WIDTH-1:0] old_out;
        begin
            @(negedge clk);
            take_in = in_valid && in_ready;
            take_out = out_valid && out_ready;
            old_out = out_data;
            if (rst) begin
                take_in = 0;
                take_out = 0;
                expected.delete();
                held_valid = 0;
                accepted = 0;
                emitted = 0;
            end
            if (held_valid && (out_valid !== 1'b1 || out_data !== held_data))
                fail("FAIL_STABILITY_OR_ORDER", "out_valid or out_data changed while stalled");
            if (take_out) begin
                if (expected.size() == 0)
                    fail("FAIL_STABILITY_OR_ORDER", "output transfer with empty scoreboard");
                if (out_data !== expected[0])
                    fail("FAIL_STABILITY_OR_ORDER", "output did not match scoreboard head");
                expected.pop_front();
                emitted = emitted + 1;
            end
            if (take_in) begin
                expected.push_back(in_data);
                accepted = accepted + 1;
            end
            if (!rst) begin
                held_valid = out_valid && !out_ready;
                held_data = old_out;
            end
            last_take_in = take_in;
            last_take_out = take_out;
            @(posedge clk); #1;
            if (rst && out_valid !== 1'b0)
                fail("FAIL_RESET_CONTRACT", "out_valid asserted during reset");
        end
    endtask

    initial begin
        if (!$value$plusargs("SEED=%d", configured_seed)) configured_seed = 1;
        random_state = configured_seed;
        accepted = 0; emitted = 0; held_valid = 0; last_take_in = 0; last_take_out = 0;
        rst = 1; in_valid = 0; in_data = '0; out_ready = 0;
        repeat (3) step();
        rst = 0;

        // Reset while occupied must discard the buffered item.
        in_valid = 1; in_data = WIDTH'('h5a); out_ready = 0; step();
        in_valid = 0; rst = 1; step();
        rst = 0; step();
        if (out_valid) fail("FAIL_RESET_CONTRACT", "buffered item survived reset");

        // Directed backpressure: three legal inputs expose an implementation
        // that falsely advertises readiness while the first word is blocked.
        in_valid = 1; in_data = WIDTH'(1); out_ready = 0; step();
        if (!out_valid || out_data !== WIDTH'(1))
            fail("FAIL_BASIC", "first word was not buffered");
        repeat (2) begin
            if (in_ready) in_data = in_data + 1'b1;
            step();
        end
        out_ready = 1; step();

        // Four consecutive simultaneous transfers demonstrate no bubbles once
        // the buffer is occupied. The final step drains the last accepted word.
        for (cycle = 2; cycle <= 5; cycle = cycle + 1) begin
            if (!last_take_in)
                fail("FAIL_THROUGHPUT", "expected previous input handshake");
            in_data = WIDTH'(cycle);
            in_valid = 1;
            out_ready = 1;
            step();
            if (!last_take_in || !last_take_out)
                fail("FAIL_THROUGHPUT", "simultaneous transfer was not sustained");
        end
        in_valid = 0; step();

        // Random producer and consumer. The producer changes its item only
        // after a handshake, as required by ready/valid.
        source_value = 17;
        for (cycle = 0; cycle < RANDOM_CYCLES; cycle = cycle + 1) begin
            out_ready = ($urandom(random_state) % 100) < 61;
            if (!in_valid || last_take_in) begin
                in_valid = (($urandom(random_state) % 100) < 73);
                if (in_valid) begin
                    in_data = WIDTH'(source_value);
                    source_value = source_value + 1;
                end
            end
            step();
        end

        // Do not withdraw a final blocked source item; first let it handshake.
        out_ready = 1;
        while (in_valid && !last_take_in) step();
        in_valid = 0;
        while (expected.size() != 0) step();
        step();
        if (out_valid) fail("FAIL_DRAIN", "out_valid remained set after drain");
        if (accepted == 0 || emitted != accepted)
            fail("FAIL_COUNTS", "accepted/emitted counts disagree");
        $display("PASS seed=%0d width=%0d accepted=%0d emitted=%0d", configured_seed, WIDTH, accepted, emitted);
        $finish;
    end
endmodule
