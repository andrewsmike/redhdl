module Or #(
	parameter BitWidth = 8
)(
	input [BitWidth - 1: 0] A,
	input [BitWidth - 1: 0] B,
	output [BitWidth - 1: 0] C
);
	wire [BitWidth - 1 : 0] NotAOut;
	wire [BitWidth - 1 : 0] NotBOut;
	wire [BitWidth - 1 : 0] AndOut;

   	Bitwise_Not_H8b NotA (
		.In (A),
		.Out (NotAOut)
	);
   	Bitwise_Not_H8b NotB (
		.In (B),
		.Out (NotBOut)
	);
   	Bitwise_And_H8b And (
		.A (NotAOut),
		.B (NotBOut),
		.Out (AndOut)
	);
   	Bitwise_Not_H8b NotOut (
		.In (AndOut),
		.Out (C)
	);

endmodule : Or
