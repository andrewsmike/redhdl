module main;
   wire En = 1;
   wire Left = 1;
   wire RotateEnable = 1;
   wire [8-1:0] dIN = 8'b00010110;
   wire [3-1:0] ShAmount = 2;
   wire [8-1:0] dOUT;


   shifter #(8) sh (.*);
   wire [8-1:0] dOUT_two = dOUT + 2;
   /*
  initial begin
    #1;
    $display("%b", dOUT);
  end*/
endmodule : main
