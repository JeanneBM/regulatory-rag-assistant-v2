// Exercise the real UI module without browser or network dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.hidden = false; this.disabled = false; this.value = ''; }
  replaceChildren(...nodes) { this.children = nodes; }
  append(...nodes) { this.children.push(...nodes); }
}

const ids = Object.fromEntries(['question', 'act', 'submit', 'claims', 'evidence',
  'rejected', 'evidence-box', 'rejected-box', 'status'].map(id => [id, new Element()]));
const context = vm.createContext({
  document: { getElementById: id => ids[id], createElement: () => new Element(), addEventListener() {} },
  fetch: async () => { throw new Error('Network failure'); },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/regrag/static/app.js'), 'utf8'), context);

for (const url of [
  'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689',
  'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf#page=10',
  'https://ec.europa.eu/newsroom/dae/redirection/document/118120#page=4',
]) {
  context.testUrl = url;
  const node = vm.runInContext('link(testUrl, "Source")', context);
  assert.equal(node.href, url);
  assert.equal(node.rel, 'noopener noreferrer');
}
for (const url of ['javascript:alert(1)', 'https://ec.europa.eu.attacker.test/newsroom/dae/redirection/document/1',
  'https://ec.europa.eu/unreviewed-path', 'https://nvlpubs.nist.gov.attacker.test/x']) {
  context.testUrl = url;
  assert.equal(vm.runInContext('link(testUrl, "Source")', context).href, undefined);
}

(async () => {
  ids.question.value = 'What does DORA say?';
  for (const id of ['claims', 'evidence', 'rejected']) ids[id].append('previous response');
  await vm.runInContext('ask({preventDefault(){}})', context);
  for (const id of ['claims', 'evidence', 'rejected']) assert.equal(ids[id].children.length, 0);
  assert.equal(ids['evidence-box'].hidden, true);
  assert.equal(ids['rejected-box'].hidden, true);
  assert.equal(ids.submit.disabled, false);
  assert.match(ids.status.children[0].textContent, /Network failure/);
  console.log('PASS: official citation links, hostile URL rejection and stale-evidence cleanup');
})();
