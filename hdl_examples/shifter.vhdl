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
  signal tmp_ivl_10 : unsigned(7 downto 0);  -- Temporary created at test.sv:11
  signal dIN : unsigned(7 downto 0);  -- Declared at test.sv:5
  signal dOUT : unsigned(7 downto 0);  -- Declared at test.sv:7
  signal dOUT_two : unsigned(7 downto 0);  -- Declared at test.sv:11
  
  component shifter is
    port (
      En : in std_logic;
      Left : in std_logic;
      RotateEnable : in std_logic;
      ShAmount : in unsigned(2 downto 0);
      dIN : in unsigned(7 downto 0);
      dOUT : out unsigned(7 downto 0)
    );
  end component;
begin
  dOUT_two <= dOUT + tmp_ivl_10;
  
  -- Generated from instantiation at test.sv:10
  sh: shifter
    port map (
      En => En,
      Left => Left,
      RotateEnable => RotateEnable,
      ShAmount => ShAmount,
      dIN => dIN,
      dOUT => dOUT
    );
  En <= '1';
  Left <= '1';
  RotateEnable <= '1';
  ShAmount <= "010";
  tmp_ivl_10 <= X"02";
  dIN <= X"16";
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module shifter (shifter.sv:1)
--   BitWidth = 8
--   ShiftWidth = 3
entity shifter is
  port (
    En : in std_logic;
    Left : in std_logic;
    RotateEnable : in std_logic;
    ShAmount : in unsigned(2 downto 0);
    dIN : in unsigned(7 downto 0);
    dOUT : out unsigned(7 downto 0)
  );
end entity; 

-- Generated from Verilog module shifter (shifter.sv:1)
--   BitWidth = 8
--   ShiftWidth = 3
architecture from_verilog of shifter is
  signal FullShifted : unsigned(15 downto 0);  -- Declared at shifter.sv:36
  signal ReversedShifted : unsigned(7 downto 0);  -- Declared at shifter.sv:39
  signal ReverseddIN : unsigned(7 downto 0);  -- Declared at shifter.sv:17
  signal ShiftInput : unsigned(15 downto 0);  -- Declared at shifter.sv:24
  signal Shifted : unsigned(7 downto 0);  -- Declared at shifter.sv:37
  signal Zero : unsigned(7 downto 0);  -- Declared at shifter.sv:25
  signal out_sig : unsigned(7 downto 0);  -- Declared at shifter.sv:46
  signal tmp_ivl_0_i0 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i1 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i2 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i3 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i4 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i5 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i6 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i7 : std_logic;  -- Temporary created at shifter.sv:42
  signal tmp_ivl_0_i0_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i1_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i2_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i3_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i4_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i5_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i6_1 : std_logic;  -- Temporary created at shifter.sv:20
  signal tmp_ivl_0_i7_1 : std_logic;  -- Temporary created at shifter.sv:20
begin
  dOUT <= out_sig;
  tmp_ivl_0_i0_1 <= dIN(7);
  tmp_ivl_0_i1_1 <= dIN(6);
  tmp_ivl_0_i2_1 <= dIN(5);
  tmp_ivl_0_i3_1 <= dIN(4);
  tmp_ivl_0_i4_1 <= dIN(3);
  tmp_ivl_0_i5_1 <= dIN(2);
  tmp_ivl_0_i6_1 <= dIN(1);
  tmp_ivl_0_i7_1 <= dIN(0);
  tmp_ivl_0_i0 <= Shifted(7);
  tmp_ivl_0_i1 <= Shifted(6);
  tmp_ivl_0_i2 <= Shifted(5);
  tmp_ivl_0_i3 <= Shifted(4);
  tmp_ivl_0_i4 <= Shifted(3);
  tmp_ivl_0_i5 <= Shifted(2);
  tmp_ivl_0_i6 <= Shifted(1);
  tmp_ivl_0_i7 <= Shifted(0);
  FullShifted <= ShiftInput sll To_Integer(ShAmount);
  Shifted <= FullShifted(8 + 7 downto 8);
  ReverseddIN <= tmp_ivl_0_i7_1 & tmp_ivl_0_i6_1 & tmp_ivl_0_i5_1 & tmp_ivl_0_i4_1 & tmp_ivl_0_i3_1 & tmp_ivl_0_i2_1 & tmp_ivl_0_i1_1 & tmp_ivl_0_i0_1;
  ReversedShifted <= tmp_ivl_0_i7 & tmp_ivl_0_i6 & tmp_ivl_0_i5 & tmp_ivl_0_i4 & tmp_ivl_0_i3 & tmp_ivl_0_i2 & tmp_ivl_0_i1 & tmp_ivl_0_i0;
  Zero <= X"00";
  
  -- Generated from always process in shifter (shifter.sv:26)
  process (Left, RotateEnable, ReverseddIN, Zero, dIN) is
    variable Verilog_Case_Ex : unsigned(1 downto 0);
  begin
    Verilog_Case_Ex := Left & RotateEnable;
    case Verilog_Case_Ex is
      when "00" =>
        ShiftInput <= ReverseddIN & Zero;
      when "01" =>
        ShiftInput <= ReverseddIN & ReverseddIN;
      when "10" =>
        ShiftInput <= dIN & Zero;
      when others =>
        ShiftInput <= dIN & dIN;
    end case;
  end process;
  
  -- Generated from always process in shifter (shifter.sv:47)
  process (En, Left, dIN, Shifted, ReversedShifted) is
    variable Verilog_Case_Ex : unsigned(1 downto 0);
  begin
    Verilog_Case_Ex := En & Left;
    case Verilog_Case_Ex is
      when "00" =>
        out_sig <= dIN;
      when "01" =>
        out_sig <= dIN;
      when "11" =>
        out_sig <= Shifted;
      when others =>
        out_sig <= ReversedShifted;
    end case;
  end process;
end architecture;

