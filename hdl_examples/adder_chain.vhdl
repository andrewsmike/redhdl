-- This VHDL was converted from Verilog using the
-- Icarus Verilog VHDL Code Generator 11.0 (stable) (v11_0)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module adder_chain (adder_chain.sv:1)
--   bit_width = 8
entity adder_chain is
  port (
    a : in unsigned(7 downto 0);
    b : in unsigned(7 downto 0);
    c : in unsigned(7 downto 0);
    sum : out unsigned(7 downto 0)
  );
end entity; 

-- Generated from Verilog module adder_chain (adder_chain.sv:1)
--   bit_width = 8
architecture from_verilog of adder_chain is
  signal partial_result : unsigned(7 downto 0);  -- Declared at adder_chain.sv:9
  
  component adder_stub is
    port (
      a : in unsigned(7 downto 0);
      b : in unsigned(7 downto 0);
      carry_in : in std_logic;
      carry_out : out std_logic;
      sum : out unsigned(7 downto 0)
    );
  end component;
  signal sum_Readable : unsigned(7 downto 0);  -- Needed to connect outputs
begin
  
  -- Generated from instantiation at adder_chain.sv:11
  first_adder: adder_stub
    port map (
      a => a,
      b => b,
      carry_in => '0',
      sum => partial_result
    );
  sum <= sum_Readable;
  
  -- Generated from instantiation at adder_chain.sv:12
  second: adder_stub
    port map (
      a => partial_result,
      b => c,
      carry_in => '0',
      sum => sum_Readable
    );
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module adder_stub (adder_stub.sv:1)
--   bit_width = 8
entity adder_stub is
  port (
    a : in unsigned(7 downto 0);
    b : in unsigned(7 downto 0);
    carry_in : in std_logic;
    carry_out : out std_logic;
    sum : out unsigned(7 downto 0)
  );
end entity; 

-- Generated from Verilog module adder_stub (adder_stub.sv:1)
--   bit_width = 8
architecture from_verilog of adder_stub is
  signal tmp_ivl_11 : std_logic;  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_12 : unsigned(8 downto 0);  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_14 : unsigned(8 downto 0);  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_17 : std_logic;  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_3 : std_logic;  -- Temporary created at adder_stub.sv:11
  signal tmp_ivl_4 : unsigned(8 downto 0);  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_7 : std_logic;  -- Temporary created at adder_stub.sv:15
  signal tmp_ivl_8 : unsigned(8 downto 0);  -- Temporary created at adder_stub.sv:15
  signal result : unsigned(8 downto 0);  -- Declared at adder_stub.sv:15
  signal spread_carry_in : unsigned(7 downto 0);  -- Declared at adder_stub.sv:10
  signal LPM_d0_ivl_9 : unsigned(7 downto 0);
  signal LPM_q_ivl_22 : std_logic;
  signal LPM_q_ivl_20 : unsigned(7 downto 0);
begin
  tmp_ivl_3 <= carry_in;
  spread_carry_in(0) <= tmp_ivl_3;
  tmp_ivl_4 <= tmp_ivl_7 & a;
  tmp_ivl_8 <= tmp_ivl_11 & b;
  tmp_ivl_12 <= tmp_ivl_4 + tmp_ivl_8;
  tmp_ivl_14 <= tmp_ivl_17 & spread_carry_in;
  result <= tmp_ivl_12 + tmp_ivl_14;
  sum <= result(0 + 7 downto 0);
  carry_out <= result(8);
  tmp_ivl_11 <= '0';
  tmp_ivl_17 <= '0';
  tmp_ivl_7 <= '0';
end architecture;

