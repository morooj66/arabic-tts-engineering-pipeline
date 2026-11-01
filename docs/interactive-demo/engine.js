/* Synthetic pipeline rules. A JavaScript port of the rules in src/arabic_tts_pipeline (pausal policy check, simulated judge, gate, delivery rules).
   Nothing here calls a model, plays audio or uses the network: it is a deterministic simulation over synthetic scenarios. */
(function (root, factory) { if (typeof module === 'object' && module.exports) module.exports = factory(); else root.PipelineEngine = factory(); })(this, function () {
  const WEIGHTS = { final_short_vowel_heard: 2, final_vowel_both_passes: 1, extra_sounds: 2, b_final_breath: 1, ab_conflict: 1, letter_mismatch_minor: 1 };
  const MAX_SCORE = 2, MAX_ATTEMPTS = 2, FAULTS = ['tanween', 'final_vowel', 'letters', 'extra_sound', 'ab_conflict', 'breath'];
  const VALID = ['HUMAN_ACCEPTED', 'AUTO_READY'];

  function evidence(faults, endsLong) {
    const has = (f) => faults.includes(f);
    let final = endsLong ? 'long_vowel' : 'consonant';
    if (has('tanween')) final = 'nasal_tanween';
    if (has('final_vowel')) final = 'short_vowel';
    if (has('breath')) final = 'breath_or_h';
    const a = { final, extra: has('extra_sound'), lettersDiffer: has('letters') && !has('tanween'), minor: has('letters') && has('tanween') };
    const b = { finalVowel: ['short_vowel', 'nasal_tanween'].includes(final) || has('ab_conflict'), breath: final === 'breath_or_h' };
    return { a, b };
  }

  function gate(faults, opts) {
    opts = opts || {}; const endsLong = !!opts.endsLong, hard = [], soft = [];
    if (opts.technicalOk === false) hard.push('TECHNICAL_FAIL');
    const { a, b } = evidence(faults, endsLong);
    if (a.final === 'nasal_tanween') hard.push('AUDIBLE_TANWEEN');
    if (a.lettersDiffer) hard.push('LETTERS_DIFFER'); else if (a.minor) soft.push('letter_mismatch_minor');
    if (a.final === 'short_vowel' && !endsLong) soft.push('final_short_vowel_heard');
    if (a.final === 'short_vowel' && b.finalVowel && !endsLong) soft.push('final_vowel_both_passes');
    if (a.extra) soft.push('extra_sounds');
    if (b.breath && a.final !== 'breath_or_h') soft.push('b_final_breath');
    if (a.final !== 'short_vowel' && a.final !== 'nasal_tanween' && b.finalVowel) soft.push('ab_conflict');
    const score = soft.reduce((s, k) => s + WEIGHTS[k], 0);
    return { status: !hard.length && score <= MAX_SCORE ? 'PASS_GATE' : 'HOLD', hard, soft, score };
  }

  function categorize(slot, decision) {
    if (slot.blocked) return 'BLOCKED';
    if (!slot.recorded) return 'NO_RECORDING';
    if (['reject', 'recorrect', 'regenerate', 'linguistic_review'].includes(decision)) return 'REJECTED';
    if (decision === 'accept') return 'HUMAN_ACCEPTED';
    return slot.gate === 'PASS_GATE' ? 'AUTO_READY' : 'ISOLATED';
  }

  const POLICY = { voice_a: 'waqf (end of word only)', voice_b: 'verbatim' };

  function simulateVoice(voice, cfg) {
    const steps = [], add = (stage, status, detail) => steps.push({ stage, status, detail });
    add('policy', 'ok', 'Policy: ' + POLICY[voice] + '. Dictionary text is never changed; only marks may differ.');
    if (cfg.letterChange) {
      add('policy', 'blocked', 'Letters-preserved check failed: the prepared text would change a letter. The text is blocked and never sent to the provider.');
      return { voice, steps, slot: { blocked: true, recorded: false }, category: categorize({ blocked: true }, null) };
    }
    const attempts = cfg.attempts || [{ faults: [] }]; let slot = { blocked: false, recorded: false, gate: null };
    for (let n = 1; n <= MAX_ATTEMPTS; n++) {
      const at = attempts[Math.min(n - 1, attempts.length - 1)];
      add('tts', 'ok', 'Attempt ' + n + ': synthetic tone generated (no model is called).');
      const technicalOk = at.technicalOk !== false;
      if (!technicalOk) {
        add('validation', 'fail', 'Attempt ' + n + ': technical check failed (L0 / format).');
        if (n < MAX_ATTEMPTS) { add('tts', 'retry', 'Retryable failure: bounded retry.'); continue; }
        add('validation', 'failed', 'Attempts exhausted: FAILED, nothing recorded.'); break;
      }
      add('validation', 'ok', 'Attempt ' + n + ': technical check passed.');
      const g = gate(at.faults || [], { endsLong: false });
      const why = g.hard.concat(g.soft).join(', ') || 'no findings';
      if (g.status === 'PASS_GATE') {
        add('evaluation', 'ok', 'Judge A/B + gate: PASS_GATE (score ' + g.score + ', ' + why + '). Evidence, not approval.');
        slot = { blocked: false, recorded: true, gate: 'PASS_GATE' }; break;
      }
      add('evaluation', 'hold', 'Judge A/B + gate: HOLD (' + why + '; score ' + g.score + ').');
      slot = { blocked: false, recorded: true, gate: 'HOLD' };
      if (n < MAX_ATTEMPTS) add('tts', 'retry', 'Bounded retake allowed.'); else add('evaluation', 'isolated', 'No passing take: the recording is ISOLATED (kept, never deleted, not retried automatically).');
    }
    const category = categorize(slot, cfg.review || null);
    if (slot.recorded) {
      if (cfg.review) add('review', cfg.review === 'accept' ? 'ok' : 'fail', 'Human decision: ' + cfg.review + '. A human decision overrides the gate and is bound to this recording\'s hash.');
      else add('review', slot.gate === 'PASS_GATE' ? 'pending' : 'hold', slot.gate === 'PASS_GATE' ? 'No human decision yet: stays AUTO_READY (valid, NOT approved).' : 'Isolated recordings wait for a human; they never complete a pair on their own.');
    }
    return { voice, steps, slot, category };
  }

  function simulate(scenario) {
    const voices = ['voice_a', 'voice_b'].map((v) => simulateVoice(v, scenario[v] || {}));
    const ok = voices.every((v) => VALID.includes(v.category));
    const human = voices.filter((v) => v.category === 'HUMAN_ACCEPTED').length;
    return { voices, delivered: ok, humanAccepted: human,
      summary: ok ? 'Pair complete: delivered (' + human + ' of 2 recordings human-accepted, ' + (2 - human) + ' auto-ready).' : 'Pair incomplete: the word is NOT delivered. A blocked, isolated, rejected or missing slot never completes a pair.' };
  }

  const SCENARIOS = [
    { id: 'ready', title: 'Clean word, ready for delivery', lemma: 'سَحَابَةٌ', blurb: 'Both voices pass the gate on the first attempt; the reviewer accepts one.', voice_a: { attempts: [{ faults: [] }], review: 'accept' }, voice_b: { attempts: [{ faults: [] }] } },
    { id: 'retry', title: 'Gate fails, retake passes', lemma: 'نَهْرٌ', blurb: 'An audible tanween is a hard fault; one bounded retake passes.', voice_a: { attempts: [{ faults: ['tanween'] }, { faults: [] }] }, voice_b: { attempts: [{ faults: [] }] } },
    { id: 'isolated', title: 'Quality failure → isolation', lemma: 'غَابَةٌ', blurb: 'Every take of one voice has a leaked final vowel: the recording is isolated and the pair is incomplete.', voice_a: { attempts: [{ faults: [] }] }, voice_b: { attempts: [{ faults: ['final_vowel'] }] } },
    { id: 'awaiting', title: 'Awaiting the reviewer', lemma: 'جَبَلٌ', blurb: 'Both pass automatically; no one has decided. Delivered as auto-ready, not as approved.', voice_a: { attempts: [{ faults: [] }] }, voice_b: { attempts: [{ faults: ['extra_sound'] }] } },
    { id: 'rejected', title: 'Reviewer rejects a take', lemma: 'بَحْرٌ', blurb: 'A passing take is rejected by a human; the human decision wins and the pair is incomplete.', voice_a: { attempts: [{ faults: [] }], review: 'accept' }, voice_b: { attempts: [{ faults: [] }], review: 'reject' } },
    { id: 'technical', title: 'Technical failure', lemma: 'قَلَمٌ', blurb: 'The audio fails the technical check twice: FAILED, nothing recorded for that voice.', voice_a: { attempts: [{ faults: [] }] }, voice_b: { attempts: [{ technicalOk: false }] } },
    { id: 'blocked', title: 'Text policy blocks the request', lemma: 'شَمْسٌ', blurb: 'A prepared text that would change a letter is blocked before any generation.', voice_a: { attempts: [{ faults: [] }] }, voice_b: { letterChange: true } }
  ];

  return { WEIGHTS, MAX_SCORE, MAX_ATTEMPTS, FAULTS, gate, evidence, categorize, simulate, simulateVoice, SCENARIOS };
});
