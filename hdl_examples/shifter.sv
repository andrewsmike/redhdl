module shifter #(
    parameter int BitWidth = 32
) (
    input En,  // Enable the shifter
    input Left,  // If 1, shift left; if 0, shift right
    input RotateEnable,  // If 1, rotate while shifting;
    //     If 0, do not rotate while shifting

    input  [  BitWidth-1:0] dIN,  // Data In
    input  [ShiftWidth-1:0] ShAmount,
    output [  BitWidth-1:0] dOUT
);

  localparam int ShiftWidth = $clog2(BitWidth);
  genvar i;

  wire [BitWidth-1:0] ReverseddIN;
  generate
    for (i = 0; i < BitWidth; i = i + 1) begin : gen_ReverseddIN
      assign ReverseddIN[i] = dIN[BitWidth-i-1];
    end
  endgenerate

  logic [2*BitWidth-1:0] ShiftInput;
  wire [BitWidth-1:0] Zero = {BitWidth{1'b0}};
  always_comb
    case ({
      Left, RotateEnable
    })
      2'b00:   ShiftInput = {ReverseddIN, Zero};
      2'b01:   ShiftInput = {ReverseddIN, ReverseddIN};
      2'b10:   ShiftInput = {dIN, Zero};
      default: ShiftInput = {dIN, dIN};
    endcase

  wire [2*BitWidth-1:0] FullShifted = ShiftInput << ShAmount;
  wire [BitWidth-1:0] Shifted = FullShifted[2*BitWidth-1:BitWidth];

  wire [BitWidth-1:0] ReversedShifted;
  generate
    for (i = 0; i < BitWidth; i = i + 1) begin : gen_ReversedShifted
      assign ReversedShifted[i] = Shifted[BitWidth-i-1];
    end
  endgenerate

  logic [BitWidth-1:0] out;
  always_comb
    case ({
      En, Left
    })
      2'b00,
      2'b01   : out = dIN;
      2'b11   : out = Shifted;
      default : out = ReversedShifted;
    endcase
  assign dOUT = out;
endmodule : shifter
