/* Fictional public-preview fixtures. Never populate this file with applicant PII. */
(function (root, factory) {
  const data = factory();
  if (typeof module === 'object' && module.exports) module.exports = data;
  else root.MobilePreviewData = data;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function averageClaim(responses) {
    const scores = responses.map(response => response.score)
      .filter(score => typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 5);
    return scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length * 100) / 100 : null;
  }
  // Same threshold as ios_api.py:_is_diamond.
  function isDiamond(candidate) {
    const claim = averageClaim(candidate.responses);
    return candidate.fit >= 4 && claim !== null && claim >= 4;
  }
  function diamondsFor(candidates, role = null, excluded = []) {
    return candidates.map((candidate, index) => ({...candidate, index}))
      .filter(candidate => isDiamond(candidate) && (!role || candidate.role === role) && !excluded.includes(candidate.index))
      .sort((a, b) => b.fit - a.fit || b.claim - a.claim);
  }
  const associate = 'Software Development Associate';
  const sales = 'Sales Development Representative (SDR) Intern';
  const fixtures = [
    ['June Gu', 'Software Development Engineer', 5, [4.0, 4.2, 4.4]],
    ['Victor Chhun', 'Software Development Engineer', 5, [3.8, 4.0, 4.2]],
    ['Manthan', associate, 5, [3.6, 3.8, 4.0]],
    ['Ketaki Kulkarni', associate, 5, [4.0, 4.2, 4.4]],
    ['Abhishek Raj', associate, 4.8, [4.2, 4.4, 4.6]],
    ['Yafei Zhang', sales, 4.2, [3.9, 4.1, 4.3]],
    ['Gunnar Gumilang', sales, 4, [3.8, 4.0, 4.2]],
    ['Anastasia Skrypnychenko', sales, 4, [3.7, 3.9, 4.1]],
    ['Gavin Best', sales, 4, [3.6, 3.8, 4.0]],
    ['HaoYu Chou', sales, 4, [3.8, 4.0, 4.2]],
  ];
  const prompts = [
    'Describe a project where you solved a difficult problem.',
    'How did you validate your approach and measure the result?',
    'Tell us how you collaborated with your team.',
  ];
  const answers = [
    'I broke the problem into smaller steps, reviewed the requirements, and tested a working solution with the team.',
    'I established a baseline, checked the result against the requirements, and monitored the outcome after release.',
    'I shared progress early, asked for feedback, and documented the decisions so the team could move forward together.',
  ];
  const candidates = fixtures.map(([name, role, fit, scores]) => ({
    name, role, fit,
    email: name.toLowerCase().replaceAll(' ', '.') + '@example.com',
    responses: scores.map((score, index) => ({question: prompts[index], answer: answers[index], score})),
    get claim() { return averageClaim(this.responses); },
    get diamond() { return isDiamond(this); },
  }));
  return {candidates, averageClaim, isDiamond, diamondsFor};
});
