# Pipeline artifacts and gates

| Stage | Durable artifact | Gate |
|---|---|---|
| inventory | `source-inventory.txt` | every listed source exists and probes |
| structure | `transcript.txt`, `cuts.txt` | EDL rows parse, do not overlap, and fit target duration |
| cutting | `segments/*`, `concat-list.txt` | one segment per EDL row, list order equals EDL order |
| assembly | `assembled/rough-cut.mp4` | output probes with expected streams and duration |
| overlays | `assembled/remotion-output.mp4` | required only when programmatic graphics were requested |
| generation | `assets/*` | provider/cost authorized before calls; every referenced asset exists |

For generation gaps: first cut around the gap and rerun the EDL. Voiceover, music, or b-roll are externally billed mutations and require explicit authorization. Do not embed API keys or assume a voice ID.

Handoff notes should point to sources, EDL, chosen output, generated assets, duration, and only the subjective tasks that actually remain.
