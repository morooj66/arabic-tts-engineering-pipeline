# Engineering Case Study — Gated Arabic TTS for a Two-Voice Dictionary

This case study describes the private production project that this repository re-implements in miniature. Every claim below comes from the project's own code, tests, experiment reports and decision logs. Where the record is thin, the text says so. Dictionary content, recordings, reviewer data, storage locations and internal names are deliberately absent.

**Reading guide.** *Production* = the system that produced the delivered audio. *Experimental* = tried, documented, not part of the final system. *This repository* = a synthetic, offline re-implementation of the patterns (see [PUBLIC_REIMPLEMENTATION.md](PUBLIC_REIMPLEMENTATION.md)).

## 1. Problem & Context

A dictionary needed spoken Arabic pronunciations for a few hundred fully diacritized entries, each in **two voices** (male and female), delivered to a review platform. Constraints that shaped everything:

- A headword is read **in isolation**, so the end of the word matters most: no audible tanween, no extra final short vowel, no wrongly voiced ta marbuta, no changed letters.
- The TTS output is **non-deterministic** at identical settings, so one good take proves little.
- Humans can listen to hundreds of clips, but not endlessly, and not consistently (see §7).
- A word is useful only if **both** voices are valid.

## 2. Initial Approach

The first deliverable was an **n8n workflow** (27 nodes: spreadsheet read in bounded chunks → Gemini `generateContent` per voice → WAV decode → S3 upload → spreadsheet write-back) using the model `gemini-2.5-flash-preview-tts`. It was designed for scale (bounded memory, two nested loops, retry per call) and never tuned for audio quality; its own documentation lists its trade-offs, e.g. no per-voice partial retry (a male success next to a female failure retries both). It contained no evaluation step and no per-word text policy.

*Record gap:* the n8n-era documents reference two voice pairs (a canonical prompt naming Charon/Kore, and a provisional configuration naming other candidates), and the audio produced then carries no per-file model/voice provenance. This study therefore does not assert which voices the n8n audio used.

## 3. Model Experimentation

What the record supports — all within one provider family (Gemini TTS):

| Experiment | Question | Evidence | Outcome |
|---|---|---|---|
| Model generation | Keep the n8n-era `gemini-2.5-flash-preview-tts` or use `gemini-3.8-flash-tts`? | All Python-era female recordings use `gemini-3.8-flash-tts`; the owner explicitly confirmed staying on it | `gemini-3.8-flash-tts` for production |
| Male voice prompt tuning (catalog voice "Ludo") | Can prompt text fix delivery/endings? | Three consecutive prompt experiments (presence, unhurried delivery, copying the female voice's pronunciation sentences) did not beat the incumbent prompt; fewer final vowels came with faster speech and two wrong letters in one | Prompt tuning closed: *take-to-take variance exceeded prompt effects* |
| Male voice choice | Is a native-Arabic library voice better? | 3-clip isolated test of a voice-library MSA voice; adopted, then replaced | Superseded |
| Male voice = **Charon** | Can a different provider voice keep every other setting identical? | Profile identical to the previous male profile except the voice; 3-word test, listened and approved | **Final male voice**  |
| Female voice | Is Kore stable enough to freeze? | Stability test of temperature 0.3 and a seed: the endpoint accepted both, the same seed did *not* reproduce audio, no arm was clearly more stable (35 takes, ≈ US$0.01) | Kore frozen unchanged; seed/temperature rejected as controls |
| Phoneme alignment (wav2vec2) | Can forced alignment help evaluation? | No benefit shown on independent data | Excluded from every evaluation path by decision |

Not claimed: any cross-provider TTS benchmark. The original notebook lists two further Gemini TTS models as options; no evaluation of them is recorded.

## 4. Engineering Challenges

Each challenge is written as problem → discovery → options → decision → implementation → verification → remaining limits.

### 4.1 Audible tanween and leaked final vowels
- **Problem.** Words written without final tanween were still read with it, or with a final short vowel.
- **Discovered.** By ear, then measured: on the first 100 words, a judge-corroborated final-vowel rate of 16/100 for one voice versus 10/100 for the other on the same words.
- **Options tried.** Negative instructions in the style prompt (did not suppress it); dropping the final vowel mark; **sukun on the last letter** (blind listening on 9 words: original text had a final vowel in 9/9; sukun removed it in 3/3 of the long-vowel words and was preferred 3/3; a second round preferred sukun in 6 of 9, verbatim in 3).
- **Decision.** Treat it as an *input* problem: a pausal (waqf) text policy for the male voice that changes only the end of the word; verbatim text for the female voice, whose approved recordings were produced that way.
- **Implemented.** A pure text function plus a letters-preserved check; per-word overrides that apply only to one entry and one voice (see `pausal.py`).
- **Verified.** Unit tests on the policy; batch-level check that only marks (plus one allow-listed letter swap) differ from the dictionary text.
- **Remaining.** The listening evidence is small (one listener, one generation per cell). The model is stochastic, so the policy lowers the rate; the gate and humans still catch the rest.

### 4.2 Trusting an automated judge
- **Problem.** Audio quality cannot be asserted by file checks alone.
- **Discovered.** A canary showed that 3 of 4 identical recordings rejected in one session were rated good in a later blind session — human labels are noisy.
- **Decision.** A two-pass multimodal judge (pass A: transcribe and name the final sound; pass B: yes/no questions) whose output is **evidence only**. Judge calls see the audio only (metadata stripped), never the text, ids or earlier labels.
- **Implemented.** A rule-based gate over the judge's answers: hard faults block, weighted soft risks accumulate, a take passes if its score stays under a small frozen threshold. The threshold was chosen from a *development* sweep (the highest-recall setting that rejected only a limited share of owner-accepted dev clips) and frozen before any hold-out test. Measurement code refuses sets that overlap development data.
- **Verified.** Where the owner rated clips the judge flagged for a final vowel, the ratings agreed 5/5; this is small, and it is why the judge stays advisory.
- **Remaining.** Pass-through is *not* approval; speed, exaggerated shadda and some letter issues are not machine-detectable.

### 4.3 A safety rule that stopped legitimate work
- **Problem.** A repeated-error guard halted production whenever a rule tripped.
- **Discovered.** It correctly stopped on a real audible-tanween case, then kept holding production pending decisions while isolated clips accumulated for later human review.
- **Decision.** *Completion Mode*: quality rules (S1–S4) become advisories printed after every batch; only technical, budget or data-integrity problems stop a run. `GUARD_MODE=strict` restores the old behaviour.
- **Verified.** Unit tests for both modes (advisory never stops on quality; technical error stops in both).
- **Remaining.** Detection and isolation are unchanged, so review load moves to the end of the run.

### 4.4 Protecting approved recordings
- **Problem.** New takes must never silently replace what a human accepted.
- **Implemented.** Registry and approved WAVs are checked byte-identical around each live stage; a database UNIQUE constraint allows one generation attempt per (entry, voice); judge calls, decisions and events are append-only (database triggers); decisions bind to the recording's SHA-256, so a decision about one take never carries to another; uploads were conditional (no overwrite).
- **Verified.** Fingerprint checks before delivery: for the final workbook, every approved-registry recording is delivered as-is except documented, owner-decided cases.

### 4.5 Delivering what was actually verified
- **Problem.** Links can be live yet point to the wrong audio.
- **Discovered.** A consistency check found blank links in one delivery sheet and a few rows that pointed to later, unreviewed takes instead of approved ones.
- **Implemented.** A 24-check verifier: template identity, key uniqueness, URL form, local file validity, **size, ETag/MD5 and SHA-256 of live objects equal the selected local recording**.
- **Remaining.** The importer's behaviour for pre-existing keys is unconfirmed; the file is intended for a new, independent project.

### 4.6 Putting files into object storage safely
- **Problem.** The first workflow uploaded files automatically as they were generated; for reviewed and approved audio, an automatic or overwriting upload could replace something a person had accepted.
- **Options.** Keep the upload inside generation (n8n style); or separate it from generation and make it an authorized step.
- **Decision.** In the Python era, generation never uploads. A separate tool is dry-run by default, needs an explicit flag plus a confirmation phrase derived from the manifest, writes with conditional puts (no overwrite) and a SHA-256 checksum, uploads one canary first, and stops at the first failure.
- **Verification.** After each object: size and ETag/MD5 from `HEAD`, then an anonymous read whose SHA-256 must match the local file; the import workbook was later checked row by row against the live objects.
- **Remaining.** No automatic upload retry; a batch is resumed deliberately. The upload tool for the final delivery batch was a one-off with a progress log.

## 5. Key Technical Decisions

| Decision | Reason (from the record) |
|---|---|
| Python orchestrator with SQLite state | Resume, UNIQUE keys, triggers, pinned configs and tests were not expressible in the n8n graph |
| Pin every config by hash; mismatch stops the run | Reproducibility; "nothing changes them automatically" |
| Fix text policy, not prompt | Prompt experiments lost to take-to-take variance |
| Judge = evidence; human = approval | Judge false-pass rate unproven; human labels noisy too |
| Isolate, never delete; no automatic retry — retakes are planned and authorized within a class ceiling | Auditability; bounded cost (retry policy: at most 3 attempts per key, fewer for some fault classes) |
| Two-voice delivery rule | A word with one voice is not shippable |
| Verify by content identity | URLs can be right while content is wrong |

## 6. Architecture Evolution

n8n workflow (chunked read → TTS → upload → sheet) → Python pipeline with stages (generation → technical QA → pronunciation judge → decision → human review) → text policies and per-word exceptions → gate and guard → completion mode → append-only review store → delivery verification. Diagram and rationale: [ARCHITECTURE.md](ARCHITECTURE.md).

## 7. Quality Assurance Strategy

Layers, each separable: (L0/L1) technical and acoustic checks → judge passes A/B → rule-based gate → human review. Offline unit tests cover the policy, gate, guard, state and delivery rules. Development and independent data are kept apart.

## 8. Human-in-the-Loop Design

Reviewers listen blind to the verdict where policy requires it, record one decision per recording (accept / recorrect / regenerate / linguistic review), and a later decision supersedes by reference. Approved recordings are the only ones counted as *human accepted*. Others delivered by completion are labelled *automatically ready (not human-reviewed)*.

## 9. Failure Handling & Recovery

- Each stage resumes; recorded work is never requested again; a WAV whose metadata was lost is adopted; temp files never become final names.
- Live runs need a recorded authorization, an explicit flag and an exact confirmation phrase; otherwise every command is a dry run.
- Failures are classified (technical, letter, ending vowel, shadda/madd, stop strength, extra sound, delivery) and routed: a retake may be proposed while the class ceiling allows (a person plans and authorizes it), otherwise the word is parked for a human. There is no automatic API retry: a single attempt per key, aborting after repeated failures, on authentication/rate-limit errors or at the cost cap.
- A hard budget cap and a `STOP` file stop a stage safely.

## 10. Results & Validation

Production figures belong to the originating organization and are not published here. What the project established, descriptively:

- **Complete delivery.** Every delivered word carried a valid recording in both voices; words that could not be completed were held back rather than shipped with one voice.
- **Separate counters.** The delivery sheets distinguished human-accepted recordings, automatically-ready recordings that no person had reviewed, earlier approved recordings reused as-is, and earlier-phase recordings carried over unreviewed.
- **Verified delivery.** The final import file passed a multi-check verifier (template identity, key uniqueness, URL form, and size / ETag-MD5 / SHA-256 equality between each live object and the selected local recording).
- **Cost and effort stayed small** for a project of this size, because batches were bounded, capped and resumable.

**Production completion is not human approval.** Delivered recordings include some that only passed automated checks.

Results of this repository's own **synthetic** tests and demo (not production data): 34 Python and 9 JavaScript offline tests pass; the two-voice demo yields 6 complete and 6 incomplete words out of 12 synthetic entries, with injected faults producing isolated and rejected slots.

## 11. Engineering Contribution & Lessons Learned

**Contribution.** System design (stage separation, invariants), the experiments and blind listening reviews, the decisions to freeze the model, voices and text policy, the stop/continue policy (including completion mode), the protection rules for approved recordings, and the verification of delivery files.

**Lessons.**

1. Separate producing from trusting.
2. Measure the evaluator, and the humans, before trusting either.
3. Fix the input policy before tuning the model.
4. A stop rule that blocks legitimate work is a defect; keep the signal, drop the stop.
5. Never delete; isolate and record why.
6. Verify by identity, not by address.
7. Keep development data and independent data apart.

## 12. Limitations & Next Steps

- Single provider family; no cross-provider benchmark is recorded.
- Listening evidence is small and mostly single-listener; the judge was developed on a small dev set.
- Some delivered recordings were not human-reviewed; a few rejected ones still need correction, and some entries lack a valid pair.
- Next: repeat-rating to measure human reliability, an independent frozen test set for judge comparison, self-contained test fixtures (some production tests depend on live inventory), and confirming platform import behaviour.
