
-- Icarus Verilog VHDL Code Generator 11.0 (stable) (v11_0)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module grace_shifter (grace_shifter.sv:1)
--   BitWidth = 32
--   ShiftWidth = 5
entity grace_shifter is
  port (
    En : in std_logic;
    Left : in std_logic;
    RotateEnable : in std_logic;
    ShAmount : in unsigned(4 downto 0);
    dIN : in unsigned(31 downto 0);
    dOUT : out unsigned(31 downto 0)
  );
end entity; 
