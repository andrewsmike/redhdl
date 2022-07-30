module adder_chain #(
    parameter int bit_width = 8
) (
    input [bit_width - 1:0] a,
    input [bit_width - 1:0] b,
    input [bit_width - 1:0] c,
    output [bit_width - 1:0] sum
);
   wire [bit_width-1:0] partial_result;

   adder_stub #(.bit_width(bit_width)) first_adder(.a(a), .b(b), .carry_in('0), .sum(partial_result));
   adder_stub #(.bit_width(bit_width)) second(.a(partial_result), .b(c), .carry_in('0), .sum(sum));

endmodule : adder_chain
