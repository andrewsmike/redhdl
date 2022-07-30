module adder_stub #(
    parameter int bit_width = 8
) (
    input [bit_width - 1:0] a,
    input [bit_width - 1:0] b,
    input carry_in,
    output [bit_width - 1:0] sum,
    output carry_out
);
   wire [bit_width - 1:0] spread_carry_in;
   assign spread_carry_in[0] = carry_in;

   wire [bit_width:0] result = a + b + spread_carry_in;
   assign sum = result[bit_width-1:0];
   assign carry_out = result[bit_width];

endmodule : adder_stub
   
