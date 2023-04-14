module Simple_Row #(
	parameter BitWidth = 2
)(
	input A,
	input [BitWidth-1:0] B,
	output C,
	output [BitWidth-1:0] D
);
	wire [BitWidth:0] L;
	assign L[0] = A;
	assign L[1] = B[1];
	wire [BitWidth-1:0] M;

	generate
		genvar i;
		for(i = 0; i < BitWidth; i = i + 1) begin : RowOfCells
			Simple_Cell SimpleCell (
				.A (L[i]),
				.B (A),
				.C (M[i])
			);
		end
	endgenerate

	assign C = M[BitWidth - 1] & (M[0] == 1);
	assign D[0] = C;

endmodule : Simple_Row


