(function () {
  const E = window.PipelineEngine, $ = (id) => document.getElementById(id);
  const ST = ['input', 'policy', 'tts', 'validation', 'j1', 'gate', 'review', 'delivery'];
  const LABEL = { pending: 'Pending', running: 'Running', passed: 'Passed', failed: 'Failed', manual: 'Manual Review' };
  const STAGES = {
    input: { name: 'Arabic Input', mode: 'auto', prod: 'Reads fully diacritized entries; undiacritized text is excluded.', sim: 'A synthetic word, always valid.', why: ['Stable ids make every later step resumable.'] },
    policy: { name: 'Text Policy', mode: 'auto', prod: 'Waqf (male) or verbatim (female) text, per-word exceptions, inner-letter check.', sim: 'A scenario can force a letter change, which blocks the request.', why: ['Fix the input policy, not the prompt.', 'Blocked text is never sent.'] },
    tts: { name: 'TTS Generation', mode: 'auto', prod: 'Gemini TTS, one attempt per key. No automatic API retry.', sim: 'A synthetic tone. The retake shown is a shortcut: in production a person plans and authorizes it.', why: ['Output is non-deterministic: one good take proves little.'] },
    validation: { name: 'L0/L1 Validation', mode: 'auto', prod: 'L0 file and format check, L1 acoustic flags.', sim: 'Pass or fail is set by the scenario.', why: ['Cheap deterministic checks before any judge call.'] },
    j1: { name: 'J1 Evaluation', mode: 'auto', prod: 'Two-pass judge on audio only. Evidence, not approval.', sim: 'Faults are injected by the scenario. No model is called.', why: ['The judge never approves.'] },
    gate: { name: 'Quality Gate', mode: 'auto', prod: 'Hard faults block, soft risks add points: PASS_GATE or HOLD. Best take is selected; isolation is a report classification, not a deletion or move.', sim: 'Same rules as the reference gate (score ≤ 2).', why: ['PASS_GATE is not human approval.', 'Nothing is deleted.'] },
    review: { name: 'Human Review', mode: 'manual', prod: 'A person decides per recording; acceptance happens outside the run.', sim: 'The scenario supplies accept, reject or no decision.', why: ['A human decision overrides the gate.'] },
    delivery: { name: 'Delivery', mode: 'manual', prod: 'Two valid voices per word. Files are built and verified by scripts a person runs; upload is a separate authorized tool.', sim: 'Pair complete or not. Upload is not simulated.', why: ['Delivered is not the same as approved.'] }
  };
  const V = ['voice_a', 'voice_b'], VN = ['M', 'F'], VNAME = ['Male', 'Female'];
  let sim = null, events = [], pos = 0, timer = null, sel = 'gate';

  function build() {
    const sc = E.SCENARIOS.find((x) => x.id === $('sc').value); sim = E.simulate(sc); $('word').innerHTML = sc.lemma + '<small>synthetic word</small>';
    const per = sim.voices.map((v, i) => [{ vi: i, s: { stage: 'input', status: 'ok' } }].concat(v.steps.map((s) => ({ vi: i, s }))));
    events = []; for (let k = 0; k < Math.max(per[0].length, per[1].length); k++) per.forEach((p) => { if (p[k]) events.push(p[k]); });
    events.push({ vi: -1, s: { stage: 'delivery', status: sim.delivered ? 'ok' : 'fail', detail: '' } });
    pos = 0; render();
  }
  function stateAt(n) {
    const st = V.map(() => Object.fromEntries(ST.map((k) => [k, 'pending']))), info = V.map(() => ({ attempts: 0, gate: null, retry: false, isolated: false })); let delivery = 'pending';
    for (let i = 0; i < n; i++) {
      const { vi, s } = events[i]; if (vi < 0) { delivery = s.status === 'ok' ? 'passed' : 'failed'; continue; }
      const m = st[vi], f = info[vi]; m.input = 'passed';
      if (s.stage === 'policy') m.policy = s.status === 'ok' ? 'passed' : 'failed';
      else if (s.stage === 'tts') { if (s.status === 'ok') { m.tts = 'passed'; f.attempts = s.attempt || f.attempts; } else { ['tts', 'validation', 'j1', 'gate'].forEach((k) => { m[k] = 'pending'; }); f.retry = true; } }
      else if (s.stage === 'validation') m.validation = s.status === 'ok' ? 'passed' : 'failed';
      else if (s.stage === 'evaluation') { if (s.gate) { m.j1 = 'passed'; m.gate = s.gate.status === 'PASS_GATE' ? 'passed' : 'failed'; f.gate = s.gate; } else { m.gate = 'failed'; f.isolated = true; } }
      else if (s.stage === 'review') m.review = s.status === 'ok' ? 'passed' : (s.status === 'fail' ? 'failed' : 'manual');
    }
    if (n >= events.length) { V.forEach((v, i) => { if (sim.voices[i].slot.recorded === false && st[i].review === 'pending') st[i].review = 'pending'; }); }
    const running = V.map(() => null); if (n < events.length) for (let j = n; j < events.length; j++) { const e = events[j]; if (e.vi >= 0 && running[e.vi] === null) running[e.vi] = e.s.stage === 'evaluation' ? 'j1' : e.s.stage; }
    running.forEach((r, i) => { if (r && st[i][r] === 'pending') st[i][r] = 'running'; });
    return { st, info, delivery, running };
  }
  function chip(label, state) { return '<div class="chip s-' + state + '">' + (label ? '<u>' + label + '</u>' : '') + '<i class="dot"></i>' + LABEL[state] + '</div>'; }
  function render() {
    const S = stateAt(pos), pipe = $('pipe'); pipe.innerHTML = '';
    ST.forEach((k) => {
      const d = STAGES[k], b = document.createElement('button'); b.className = 'node' + (d.mode === 'manual' ? ' manual' : ''); b.setAttribute('aria-pressed', String(sel === k));
      const body = k === 'delivery' ? chip('', S.delivery === 'pending' ? 'pending' : S.delivery) : chip('M', S.st[0][k]) + chip('F', S.st[1][k]);
      b.innerHTML = '<i>' + (d.mode === 'manual' ? 'MANUAL' : 'AUTO') + '</i><b>' + d.name + '</b>' + body; b.onclick = () => { sel = k; render(); }; pipe.appendChild(b);
    });
    side(S); log(); cards(S);
    const done = pos >= events.length; $('step').disabled = done || !!timer; $('run').disabled = done || !!timer;
    const vd = $('verdict'); vd.textContent = done ? sim.summary : ''; vd.className = 'verdict ' + (done ? (sim.delivered ? 'good' : 'bad') : '');
  }
  function side(S) {
    const d = STAGES[sel], m = S.st[0][sel] || S.delivery, el = $('side');
    const states = sel === 'delivery' ? chip('', S.delivery) : chip('Male', S.st[0][sel]).replace('chip ','chip w ') + chip('Female', S.st[1][sel]).replace('chip ','chip w ');
    el.innerHTML = '<h3>' + d.name + '</h3><span class="tag ' + (d.mode === 'manual' ? 'man' : 'auto') + '">' + (d.mode === 'manual' ? 'Manual' : 'Automatic') + '</span><div style="margin-top:8px">' + states + '</div>' +
      '<div class="kv"><b>Production</b>' + d.prod + '<b>In this simulation</b>' + d.sim + '<b>Decisions</b><ul>' + d.why.map((w) => '<li>' + w + '</li>').join('') + '</ul></div>';
  }
  const MSG = { input: { ok: 'Synthetic word loaded' }, policy: { ok: 'Policy applied', blocked: 'Blocked: a letter would change' }, tts: { ok: 'Synthetic tone', retry: 'Retake' }, validation: { ok: 'File checks passed', fail: 'File checks failed', failed: 'Attempts exhausted' }, evaluation: { ok: 'Judge + gate: PASS_GATE', hold: 'Judge + gate: HOLD', isolated: 'Isolated in report' }, review: { ok: 'Accepted by reviewer', fail: 'Rejected by reviewer', pending: 'Awaiting a reviewer', hold: 'Waits for a reviewer' } };
  function log() {
    const ol = $('log'); ol.innerHTML = '';
    if (!pos) { ol.innerHTML = '<li class="idle"><span class="empty">Run the pipeline or press Step.</span></li>'; return; }
    events.slice(0, pos).forEach((e) => {
      const li = document.createElement('li'), s = e.s, delivery = e.vi < 0, status = (s.status === 'ok' || s.status === 'pending' || s.status === 'hold' ? s.status : s.status);
      const cls = s.status === 'ok' ? 's-passed' : (['pending', 'hold'].includes(s.status) && s.stage === 'review' ? 's-manual' : (s.status === 'retry' ? 's-manual' : 's-failed'));
      const msg = delivery ? (s.status === 'ok' ? 'Pair complete: delivered' : 'Pair incomplete: not delivered') : ((MSG[s.stage] || {})[s.status] || s.status) + (s.attempt ? ' · attempt ' + s.attempt : '') + (s.gate ? ' · score ' + s.gate.score : '');
      li.innerHTML = '<span class="v">' + (delivery ? '' : VN[e.vi]) + '</span><span class="st ' + cls + '">' + (delivery ? 'Delivery' : STAGES[s.stage === 'evaluation' ? 'gate' : s.stage].name) + '</span><span>' + msg + (s.status === 'retry' ? '<span class="sim">simulation shortcut</span>' : '') + '</span>';
      ol.appendChild(li);
    }); ol.scrollTop = ol.scrollHeight;
  }
  function cards(S) {
    const done = pos >= events.length, c = $('cards'), cat = (i) => (done ? sim.voices[i].category : null);
    const two = (k) => chip('M', S.st[0][k]) + chip('F', S.st[1][k]);
    const gateTxt = (i) => (S.info[i].gate ? (S.info[i].gate.status + ' · ' + S.info[i].gate.score) : '—');
    const html = [
      ['Technical Validation', two('validation'), 'L0/L1 file checks'],
      ['Automated Evaluation', two('j1'), 'Evidence, not approval'],
      ['Quality Gate', '<div class="chip"><u>M</u>' + gateTxt(0) + '</div><div class="chip"><u>F</u>' + gateTxt(1) + '</div>', S.info.some((x) => x.isolated) ? 'Isolated = report label' : 'Max score 2'],
      ['Human Review', two('review'), 'Manual · outside the run'],
      ['Delivery Status', done ? '<div class="big ' + (sim.delivered ? 's-passed' : 's-failed') + '">' + (sim.delivered ? 'Delivered' : 'Not delivered') + '</div>' : chip('', 'pending'), done ? (cat(0) + ' / ' + cat(1)).replace(/_/g, ' ').toLowerCase() : 'Both voices must be valid']
    ];
    c.innerHTML = html.map((h) => '<div class="res"><h4>' + h[0] + '</h4>' + h[1] + '<div class="sub">' + h[2] + '</div></div>').join('');
  }
  function advance() { if (pos < events.length) { pos++; render(); } }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  E.SCENARIOS.forEach((s) => { const o = document.createElement('option'); o.value = s.id; o.textContent = s.title; $('sc').appendChild(o); });
  $('sc').onchange = () => { stop(); build(); };
  $('step').onclick = advance;
  $('run').onclick = () => { if (timer || pos >= events.length) return; render(); timer = setInterval(() => { advance(); if (pos >= events.length) { stop(); render(); } }, 650); render(); };
  $('reset').onclick = () => { stop(); pos = 0; render(); };
  build();
})();
