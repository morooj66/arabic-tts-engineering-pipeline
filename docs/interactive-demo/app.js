(function () {
  const E = window.PipelineEngine, $ = (id) => document.getElementById(id), D = 'https://github.com/morooj66/arabic-tts-engineering-pipeline/blob/main/docs/';
  const STAGES = [
    { id: 'input', name: 'Arabic Input', sub: 'diacritized text', does: 'Reads an entry (id + fully diacritized text) and refuses input that cannot be spoken reliably.', decisions: ['Undiacritized Arabic is routed to linguistic review instead of being guessed.', 'Stable identifiers make every later step idempotent and resumable.'], link: 'ARCHITECTURE.md' },
    { id: 'policy', name: 'Text Policy', sub: 'pausal · exceptions', does: 'Decides what text is sent to the TTS: pausal (waqf) form for one voice, verbatim for the other, plus narrow per-word overrides.', decisions: ['The end of a headword is where TTS fails (tanween, leaked vowels), so the fix lives in the input policy, not the prompt.', 'A letters-preserved check blocks any change except marks and one allow-listed swap; blocked text is never sent.'], link: 'CASE_STUDY.md' },
    { id: 'tts', name: 'TTS Generation', sub: 'pinned config', does: 'Requests one recording per (entry, voice) with a pinned, hash-checked configuration.', decisions: ['A unique attempt per key plus a bounded retake ceiling keeps cost predictable.', 'Output is non-deterministic, so one good take proves little; seeds/temperature did not help.'], link: 'ARCHITECTURE.md' },
    { id: 'validation', name: 'Audio Validation', sub: 'L0 / L1', does: 'Checks container, format, duration, energy and clipping before any judge call is spent.', decisions: ['Cheap, deterministic checks first; failures are classified and retried within bounds.', 'Technical validity says nothing about pronunciation.'], link: 'QUALITY_ASSURANCE.md' },
    { id: 'evaluation', name: 'Automated Evaluation', sub: 'judge A/B → gate', does: 'A two-pass judge reports what it heard and answers targeted yes/no questions; a rule-based gate turns that into PASS_GATE or HOLD.', decisions: ['The judge sees audio only and is evidence, never approval.', 'Hard faults block; soft risks add weighted points; the threshold was frozen from development data.', 'HOLD means isolated: kept, never deleted, never retried automatically.'], link: 'CASE_STUDY.md' },
    { id: 'review', name: 'Human Review', sub: 'append-only', does: 'People listen and decide per recording; a later decision supersedes by reference.', decisions: ['Decisions are bound to the recording\'s SHA-256, so they never transfer to a new take.', 'A human decision overrides the gate in both directions.'], link: 'CASE_STUDY.md' },
    { id: 'delivery', name: 'Delivery', sub: 'two-voice rule', does: 'Ships a word only when both voices are valid, keeps human-accepted and auto-ready counters apart, exports the import file and verifies it.', decisions: ['Production completion is not human approval.', 'Verify by content identity (size, hash), not by URL.'], link: 'ARCHITECTURE.md' }
  ];
  const rail = $('rail'), stage = $('stage'); let sel = 0;
  STAGES.forEach((s, i) => { const b = document.createElement('button'); b.setAttribute('aria-pressed', 'false'); b.innerHTML = (i + 1) + '. ' + s.name + '<small>' + s.sub + '</small>'; b.onclick = () => showStage(i); rail.appendChild(b); });
  function showStage(i) {
    sel = i; [...rail.children].forEach((b, j) => b.setAttribute('aria-pressed', String(j === i))); const s = STAGES[i];
    stage.innerHTML = '<h2>' + (i + 1) + '. ' + s.name + '</h2><p>' + s.does + '</p><b>Engineering decisions</b><ul>' + s.decisions.map((d) => '<li>' + d + '</li>').join('') + '</ul><a href="' + D + s.link + '">Read more →</a>';
    highlight(s.id);
  }
  const sc = $('sc'); E.SCENARIOS.forEach((s) => { const o = document.createElement('option'); o.value = s.id; o.textContent = s.title; sc.appendChild(o); });
  let sim = null, shown = 0, flat = [];
  function load() {
    const s = E.SCENARIOS.find((x) => x.id === sc.value); sim = E.simulate(s); $('blurb').textContent = s.blurb; $('lemma').textContent = s.lemma;
    flat = []; sim.voices.forEach((v, vi) => v.steps.forEach((st) => flat.push({ vi, st }))); shown = 0; render();
  }
  function render() {
    ['va', 'vb'].forEach((id, vi) => {
      const el = $(id); el.innerHTML = '';
      flat.slice(0, shown).filter((x) => x.vi === vi).forEach((x) => { const d = document.createElement('div'); d.className = 'step ' + x.st.status; d.innerHTML = '<b></b><span></span>'; d.firstChild.textContent = x.st.stage; d.lastChild.textContent = x.st.detail; el.appendChild(d); });
      if (shown >= flat.length) { const t = document.createElement('div'); t.innerHTML = 'Final slot: <span class="tag t-' + sim.voices[vi].category + '">' + sim.voices[vi].category + '</span>'; el.appendChild(t); }
    });
    const done = shown >= flat.length, out = $('outcome'); out.textContent = done ? sim.summary : ''; out.className = 'result ' + (done ? (sim.delivered ? 'good' : 'bad') : '');
    $('next').disabled = done;
    const last = flat[Math.max(0, shown - 1)]; if (last && shown) highlight(last.st.stage);
  }
  function highlight(id) { const i = STAGES.findIndex((s) => s.id === id); if (i >= 0) [...rail.children].forEach((b, j) => { b.style.outline = j === i ? '2px dashed var(--acc)' : 'none'; }); }
  $('next').onclick = () => { shown = Math.min(flat.length, shown + 1); render(); };
  $('all').onclick = () => { shown = flat.length; render(); };
  $('reset').onclick = () => { shown = 0; render(); };
  sc.onchange = load; showStage(0); load();
})();
