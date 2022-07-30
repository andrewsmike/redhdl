-- This VHDL was converted from Verilog using the
-- Icarus Verilog VHDL Code Generator 11.0 (stable) (v11_0)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module main (test.sv:1)
entity main is
end entity; 

-- Generated from Verilog module main (test.sv:1)
architecture from_verilog of main is
  signal En : std_logic;  -- Declared at test.sv:2
  signal Left : std_logic;  -- Declared at test.sv:3
  signal RotateEnable : std_logic;  -- Declared at test.sv:4
  signal ShAmount : unsigned(2 downto 0);  -- Declared at test.sv:6
  signal dIN : unsigned(7 downto 0);  -- Declared at test.sv:5
begin
  En <= '1';
  Left <= '1';
  RotateEnable <= '1';
  ShAmount <= "010";
  dIN <= X"16";
end architecture;

