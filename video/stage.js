// The stage's own behaviour: no app logic, no data of its own. record.spec.ts calls
// window.stage.* with cues built from the take's capture (decision 0028).
;(() => {
  const $ = (id) => document.getElementById(id)
  const LAYERS = ['Browser', 'FastAPI', 'Agent loop', 'Model', 'Tools', 'Validators', 'Manual', 'SAP']
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

  function pipeline(active) {
    $('pipeline').innerHTML = LAYERS.map(
      (l, i) => `${i ? '<i>›</i>' : ''}<span class="${l === active ? 'on' : ''}">${esc(l)}</span>`,
    ).join('')
  }

  function loadApp() {
    return new Promise((resolve) => {
      const app = $('app')
      app.addEventListener('load', () => resolve(), { once: true })
      app.src = '/'
    })
  }

  function init({ banner, provider }) {
    $('banner').textContent = banner
    $('provider').textContent = provider
    pipeline(null)
  }

  /** One storyboard row: subtitle, layer, callouts (file:line + excerpt), payload JSON. */
  function show(cue) {
    $('subs').textContent = cue.subtitle || ''
    $('row-id').textContent = cue.id ? `row ${cue.id}` : ''
    if (cue.layer) pipeline(cue.layer)
    $('callouts').innerHTML = (cue.callouts || [])
      .slice(0, cue.payload ? 2 : 3)
      .map((c) => `<div class="callout"><div class="where">${esc(c.file)}:${c.line} · ${esc(c.symbol)}</div><pre>${esc(c.excerpt)}</pre></div>`)
      .join('')
    const box = $('payload')
    if (cue.payload) {
      box.classList.remove('empty')
      $('payload-label').textContent = cue.payload.label
      $('payload-note').textContent = cue.payload.note || ''
      $('payload-json').textContent = JSON.stringify(cue.payload.value, null, 2)
    } else {
      box.classList.add('empty')
    }
    if (cue.slide) slide(cue.slide, cue.slideData)
    else hideSlide()
  }

  const SLIDES = {
    title: () => `
      <h1>Create Design</h1>
      <p class="lead">How a question becomes an answer: one take of the real app, with the code and the data behind each step.</p>`,
    map: () => `
      <h2>Five pieces</h2>
      <div class="boxes">
        <div class="box"><b>Browser</b><span>React app: chat, form, cards. Sends JSON, reads an SSE stream.</span></div><div class="arrow">→</div>
        <div class="box"><b>FastAPI</b><span>The chat stream, and the confirm endpoint that the user's click calls.</span></div><div class="arrow">→</div>
        <div class="box hot"><b>Agent loop</b><span>Bounded tool loop. A model picks tools; it has no side effects.</span></div><div class="arrow">→</div>
        <div class="box"><b>Tools</b><span>Validators, manual search (SQLite FTS5), SapClient, the designs folder.</span></div><div class="arrow">→</div>
        <div class="box"><b>SAP + KiCad</b><span>Mock SAP (OData v2) issues numbers. kicad-cli exports the PDF.</span></div>
      </div>`,
    invariants: (d) => `
      <h2>The invariants</h2>
      <ol class="inv">${(d.invariants || []).map((t, i) => `<li class="${(d.hot || []).includes(i + 1) ? 'hot' : ''}">${esc(t)}</li>`).join('')}</ol>`,
    trace: (d) => `
      <h2>The trace of run ${esc(d.id)}</h2>
      <div class="counters">
        <div class="counter"><b>${esc(d.model_calls)}</b><span>model calls</span></div>
        <div class="counter"><b>${esc(d.tool_calls)}</b><span>tool calls</span></div>
        <div class="counter"><b>${esc(d.status)}</b><span>status</span></div>
        <div class="counter"><b>${esc(d.max_iterations)}</b><span>max iterations</span></div>
        <div class="counter"><b>${esc(d.provider)}</b><span>provider · ${esc(d.model)}</span></div>
      </div>
      <div class="steps">${(d.steps || []).map(esc).join('\n')}</div>`,
    compare: () => `
      <h2>What changes with a real model</h2>
      <table class="cmp">
        <tr><th></th><th>Demo (this video)</th><th>Ollama</th><th>Groq</th></tr>
        <tr><td>Who picks the tool</td><td>Rules in DemoClient</td><td>The model, native tools</td><td>The model, OpenAI-style tools</td></tr>
        <tr><td>Request</td><td>none</td><td>/api/chat, temperature 0, num_ctx 8192</td><td>OpenAI-compatible chat/completions</td></tr>
        <tr><td>Result</td><td>ChatTurn</td><td>ChatTurn (a call written as text is parsed)</td><td>ChatTurn</td></tr>
        <tr class="same"><td>Pre-retrieval, tools, validators, gate, trace, SSE, UI</td><td>identical</td><td>identical</td><td>identical</td></tr>
      </table>`,
    hook: () => `
      <h1>Create Design</h1>
      <p class="lead">An engineer describes a board in plain words. A real model guides; plain code checks every rule, SAP issues the number, and KiCad gets a project with the company title block filled in.</p>`,
    end: (d) => `
      <h1>The AI guides. The code decides.</h1>
      <p class="lead" style="margin-bottom:34px">And the engineer clicks. Every step is traced.</p>
      <p class="lead">${esc(d.repo || '')}</p>
      ${d.author ? `<p class="lead" style="margin-top:34px">${esc(d.author)}</p>` : ''}
      ${d.linkedin ? `<p class="lead">${esc(d.linkedin)}</p>` : ''}`,
    close: (d) => `
      <h1>The AI guides. The code decides.</h1>
      <p class="lead" style="margin-bottom:34px">And the user clicks.</p>
      <ol class="inv">${(d.invariants || []).map((t) => `<li class="hot">${esc(t)}</li>`).join('')}</ol>`,
  }

  function slide(name, data = {}) {
    $('slide-inner').innerHTML = SLIDES[name](data)
    $('slide').classList.add('on')
  }

  function hideSlide() {
    $('slide').classList.remove('on')
  }

  /** The app frame's text, without what the recorder masks: for the no-paths check. */
  function appText() {
    const doc = $('app').contentDocument
    if (!doc) return ''
    const clone = doc.body.cloneNode(true)
    clone.querySelectorAll('[data-video-masked]').forEach((n) => n.remove())
    return clone.innerText || clone.textContent || ''
  }

  window.stage = { init, loadApp, show, slide, hideSlide, appText }
})()
