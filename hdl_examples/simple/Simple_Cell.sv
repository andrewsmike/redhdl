module Simple_Cell (
	input  A,
	input  B,
	output C
);
	wire L = A ^ B;
        assign C = L & A;

endmodule : Simple_Cell