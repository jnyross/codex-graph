# Goal

I have a fixed shortlist of 24 candidate European city-break destinations for
a long weekend with two adults and two primary-school-age children,
travelling from Birmingham in early June. I want each candidate screened
independently against four hard gates, and nothing else decided for me.

Hard gates (a candidate is killed only when a gate clearly fails):

1. Realistic family door-to-door travel over 8 hours — kill.
2. Typical daytime highs for the trip window routinely at or above 33°C — kill.
3. No credible signal of family-capable accommodation (family rooms,
   interconnecting rooms, or 2-bed apartments) — kill.
4. A major closure or event that removes the core attraction for the whole
   period — kill.

Rules I care about:

- One screener per candidate. Each screener looks at exactly one destination
  and returns PASS or KILL with a reason and the gate that failed. Screeners
  must verify with current web sources, not answer from memory.
- Uncertain means PASS. Soft concerns (mild heat, budget airports, taste) are
  noted, never fatal.
- If a screener fails to run or returns garbage, keep the candidate in the
  pool and record why — a broken screener must not silently kill a
  destination. That decision belongs to the coordinator, not to any screener.
- Output: the surviving pool and a complete kill log with per-candidate
  reasons. Do not rank survivors; deep research is a later, separate job.

The 24 candidates are an evenly mixed list of coastal, city, and lake
destinations across Northern and Southern Europe; treat the list as fixed
input data supplied with the run.
