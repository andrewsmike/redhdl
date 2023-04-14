entity Simple_Row is
  port (
    A : in std_logic;
    B : in unsigned(1 downto 0);
    C : out std_logic;
    D : out unsigned(1 downto 0)
  );
end entity;

architecture from_verilog of Simple_Row is
  signal L : unsigned(2 downto 0);  -- Declared at Simple_Row.sv:9
  signal M : unsigned(1 downto 0);  -- Declared at Simple_Row.sv:12
  signal tmp_ivl_13 : std_logic;  -- Temporary created at Simple_Row.sv:11
  signal tmp_ivl_15 : std_logic;  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_17 : std_logic;  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_18 : unsigned(31 downto 0);  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_21 : unsigned(30 downto 0);  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_22 : unsigned(31 downto 0);  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_24 : std_logic;  -- Temporary created at Simple_Row.sv:26
  signal tmp_ivl_31 : std_logic;  -- Temporary created at Simple_Row.sv:27
  signal tmp_ivl_35 : std_logic;  -- Temporary created at 
  signal tmp_ivl_9 : std_logic;  -- Temporary created at Simple_Row.sv:10
  signal LPM_q_ivl_0 : std_logic;
  signal LPM_q_ivl_3 : std_logic;
  signal LPM_d0_ivl_32 : std_logic;
  signal LPM_d1_ivl_32 : std_logic;

  component Simple_Cell is
    port (
      A : in std_logic;
      B : in std_logic;
      C : out std_logic
    );
  end component;
begin
  tmp_ivl_9 <= A;
  C <= tmp_ivl_15 and tmp_ivl_24;
  tmp_ivl_31 <= C;
  LPM_q_ivl_0 <= L(0);
  LPM_q_ivl_3 <= L(1);
  tmp_ivl_13 <= B(1);
  tmp_ivl_15 <= M(1);
  tmp_ivl_17 <= M(0);
  tmp_ivl_18 <= tmp_ivl_21 & tmp_ivl_17;
  tmp_ivl_24 <= '1' when tmp_ivl_18 = tmp_ivl_22 else '0';
  D(0) <= tmp_ivl_31;
  M <= LPM_d1_ivl_32 & LPM_d0_ivl_32;
  L <= tmp_ivl_35 & tmp_ivl_13 & tmp_ivl_9;
  
  -- Generated from instantiation at Simple_Row.sv:17
  SimpleCell_i0: Simple_Cell
    port map (
      A => LPM_q_ivl_0,
      B => A,
      C => LPM_d0_ivl_32
    );
  
  -- Generated from instantiation at Simple_Row.sv:17
  SimpleCell_i1: Simple_Cell
    port map (
      A => LPM_q_ivl_3,
      B => A,
      C => LPM_d1_ivl_32
    );
  tmp_ivl_21 <= "0000000000000000000000000000000";
  tmp_ivl_22 <= X"00000000";
  tmp_ivl_35 <= 'Z';
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- Generated from Verilog module Simple_Cell (Simple_Cell.sv:1)
entity Simple_Cell is
  port (
    A : in std_logic;
    B : in std_logic;
    C : out std_logic
  );
end entity; 

-- Generated from Verilog module Simple_Cell (Simple_Cell.sv:1)
architecture from_verilog of Simple_Cell is
  signal L : std_logic;  -- Declared at Simple_Cell.sv:6
begin
  L <= A xor B;
  C <= L and A;
end architecture;

