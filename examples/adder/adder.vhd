library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity adder is
    generic (
        WIDTH : integer := 4
    );
    port (
        a   : in  std_logic_vector(WIDTH - 1 downto 0);
        b   : in  std_logic_vector(WIDTH - 1 downto 0);
        sum : out std_logic_vector(WIDTH downto 0)  -- WIDTH+1 bits (includes carry)
    );
end entity adder;

architecture rtl of adder is
begin
    sum <= std_logic_vector(
        resize(unsigned(a), WIDTH + 1) + resize(unsigned(b), WIDTH + 1)
    );
end architecture rtl;
