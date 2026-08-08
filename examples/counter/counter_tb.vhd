library ieee;
use ieee.std_logic_1164.all;

entity counter_tb is
end entity counter_tb;

architecture sim of counter_tb is
    constant WIDTH : integer := 4;

    signal clk   : std_logic := '0';
    signal rst   : std_logic := '1';
    signal count : std_logic_vector(WIDTH - 1 downto 0);
begin
    dut : entity work.counter
        generic map (
            WIDTH => WIDTH
        )
        port map (
            clk   => clk,
            rst   => rst,
            count => count
        );

    clk_gen : process
    begin
        while now < 200 ns loop
            clk <= not clk;
            wait for 5 ns;
        end loop;
        wait;
    end process;

    stim : process
    begin
        wait for 12 ns;
        rst <= '0';
        wait;
    end process;
end architecture sim;
