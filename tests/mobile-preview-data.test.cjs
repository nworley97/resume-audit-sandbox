const test = require('node:test');
const assert = require('node:assert/strict');
const {candidates, averageClaim, isDiamond, diamondsFor} = require('../static/js/mobile-preview-data.js');

test('June header is calculated from her question scores', () => {
  const june = candidates.find(candidate => candidate.name === 'June Gu');
  assert.equal(june.claim, 4.2);
  june.responses[0].score = 1;
  assert.equal(june.claim, 3.2);
  assert.equal(june.diamond, false);
  june.responses[0].score = 4;
});
test('missing scores are unscored, while zero is a real score', () => {
  assert.equal(averageClaim([]), null);
  assert.equal(averageClaim([{score:null},{score:NaN},{score:'4.2'}]), null);
  assert.equal(averageClaim([{score:0},{score:4}]), 2);
  assert.equal(isDiamond({fit:5,responses:[]}), false);
});
test('diamond threshold matches the native API at the boundary', () => {
  assert.equal(isDiamond({fit:4,responses:[{score:4}]}), true);
  assert.equal(isDiamond({fit:3.9,responses:[{score:5}]}), false);
  assert.equal(isDiamond({fit:5,responses:[{score:3.9}]}), false);
});
test('role analytics includes qualifying candidates, excludes other roles and archived candidates', () => {
  const role = 'Software Development Associate';
  assert.deepEqual(diamondsFor(candidates, role).map(c => c.name), ['Ketaki Kulkarni','Abhishek Raj']);
  assert.deepEqual(diamondsFor(candidates, role, [3]).map(c => c.name), ['Abhishek Raj']);
  assert.equal(diamondsFor(candidates, 'Missing role').length, 0);
  assert.ok(diamondsFor(candidates).some(c => c.name === 'June Gu'));
});
test('every displayed aggregate agrees with its candidate responses', () => {
  for (const candidate of candidates) {
    const expected = candidate.responses.reduce((sum, response) => sum + response.score, 0) / candidate.responses.length;
    assert.equal(candidate.claim.toFixed(1), expected.toFixed(1));
    assert.ok(candidate.email.endsWith('.example'));
  }
});

test('anonymized emails use varied, non-deliverable domains', () => {
  assert.equal(new Set(candidates.map(c => c.email)).size, candidates.length);
  assert.ok(new Set(candidates.map(c => c.email.split('@')[1])).size >= 4);
});
