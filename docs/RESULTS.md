# Results

## Private project (descriptive)
The original project's counts, costs and timings belong to the originating organization and are not published. In summary, it delivered two-voice Arabic pronunciation audio for a few hundred diacritized entries; held back entries that lacked a valid pair; kept *human-accepted*, *automatically ready (unreviewed)*, *reused-approved* and *carried-over (unreviewed)* recordings in separate counters; and verified the final import file against the live objects by size, ETag/MD5 and SHA-256.

**Production completion is not human approval.** A recording that passed the automated gate was delivered as "automatically ready"; only a person's recorded decision makes it "human accepted".

## This repository (synthetic)
| Check | Result |
|---|---|
| Offline unit tests | 32 / 32 pass |
| Single-voice demo (`make demo`) | 4 synthetic entries → `READY_FOR_REVIEW`, 0 paid API calls |
| Two-voice demo (`make demo-two-voice`) | 12 synthetic entries → 6 complete pairs, 6 incomplete; 2 human-accepted, 16 auto-ready, 4 isolated, 2 rejected slots |

These numbers describe the **synthetic demo only**; they say nothing about speech quality or the production data.

## How to read them
- The gate and judge here are simulations driven by injected faults.
- A complete pair requires both voices to be valid (human-accepted or auto-ready); isolated and rejected slots never complete a pair.
