"""Spike only: what does input() do in a script launched this way?"""

from anvil.tables import app_tables

try:
    answer = input("password? ")
    outcome = "input returned " + repr(answer)[:40]
except BaseException as exc:
    outcome = "input raised " + type(exc).__name__ + ": " + str(exc)[:150]
print("PROMPT-PROBE", outcome)
app_tables.spike_row.add_row(name="prompt", n=0)
