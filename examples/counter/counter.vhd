library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity counter is
    generic (
        WIDTH : integer := 4
    );
    port (
        clk   : in  std_logic;
        rst   : in  std_logic;
        count : out std_logic_vector(WIDTH - 1 downto 0)
    );
end entity counter;

architecture rtl of counter is
    signal value : unsigned(WIDTH - 1 downto 0) := (others => '0');
begin
    process (clk, rst)
    begin
        if rst = '1' then
            value <= (others => '0');
        elsif rising_edge(clk) then
            value <= value + 1;
        end if;
    end process;

    count <= std_logic_vector(value);
end architecture rtl;
