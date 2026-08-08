-- OSVVM-based testbench for the combinational adder example.
-- Requires a precompiled OSVVM library (Settings → OSVVM lib path → -P).

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

library osvvm;
context osvvm.OsvvmContext;

entity adder_tb is
end entity adder_tb;

architecture Test of adder_tb is
    constant WIDTH : integer := 4;

    signal a   : std_logic_vector(WIDTH - 1 downto 0) := (others => '0');
    signal b   : std_logic_vector(WIDTH - 1 downto 0) := (others => '0');
    signal sum : std_logic_vector(WIDTH downto 0);
begin
    ------------------------------------------------------------
    -- Device under test
    ------------------------------------------------------------
    Dut : entity work.adder
        generic map (
            WIDTH => WIDTH
        )
        port map (
            a   => a,
            b   => b,
            sum => sum
        );

    ------------------------------------------------------------
    -- Test process (OSVVM AlertLog / AffirmIfEqual)
    ------------------------------------------------------------
    TestProc : process
        variable RV              : RandomPType;
        variable expected_bits   : std_logic_vector(WIDTH downto 0);
        variable expected_signed : integer;
        variable received_signed : integer;

        procedure check_sum(constant a_val : in natural; constant b_val : in natural) is
        begin
            a <= std_logic_vector(to_unsigned(a_val, WIDTH));
            b <= std_logic_vector(to_unsigned(b_val, WIDTH));
            wait for 1 ns;
            -- Compare as signed integers so OSVVM logs Received as signed decimal
            -- (std_logic_vector AffirmIfEqual would print hex).
            expected_bits   := std_logic_vector(to_unsigned(a_val + b_val, WIDTH + 1));
            expected_signed := to_integer(signed(expected_bits));
            received_signed := to_integer(signed(sum));
            AffirmIfEqual(received_signed, expected_signed,
                "adder check: " & to_string(a_val) & " + " & to_string(b_val));
        end procedure check_sum;
    begin
        SetAlertLogName("adder_tb");
        SetLogEnable(PASSED, TRUE);
        TranscriptOpen;
        SetTranscriptMirror(TRUE);

        Log("Test-Start", ALWAYS);

        -- Directed corner cases
        check_sum(0, 0);
        check_sum(1, 2);
        check_sum(7, 8);     -- 15
        check_sum(15, 1);    -- carry out → 16 ("10000")
        check_sum(15, 15);   -- max + max → 30

        -- A few random vectors
        RV.InitSeed(RV'instance_name);
        for i in 1 to 8 loop
            check_sum(RV.RandInt(0, 15), RV.RandInt(0, 15));
        end loop;

        Log("Test-Stop", ALWAYS);
        TranscriptClose;
        EndOfTestReports;
        std.env.stop;
        wait;
    end process TestProc;
end architecture Test;
