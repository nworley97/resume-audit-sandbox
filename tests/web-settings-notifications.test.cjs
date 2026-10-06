const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the actual header script with browser dependencies replaced by fakes.
// Template values only supply routes/account identifiers; their values are immaterial here.
const template = fs.readFileSync(require('node:path').join(__dirname, '../templates/partials/header.html'), 'utf8');
const script = template.split('<script>')[1].split('</script>')[0]
  .replace(/\{\{[\s\S]*?\}\}/g, '"test"').replace(/\{%[\s\S]*?%\}/g, '');
const settle = () => new Promise(resolve => setImmediate(resolve));

function dashboard() {
  const storage = new Map(), requests = [];
  const window = {
    dashboardSettings: {user_id: 1, preferences: {site_alerts: true, site_badge: true}},
    addEventListener() {},
  };
  let poll;
  vm.runInNewContext(script, {
    window,
    document: {getElementById: () => null, addEventListener() {}},
    localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)},
    fetch: () => new Promise(resolve => requests.push(rows => resolve({ok: true, json: async () => rows}))),
    setInterval: callback => { poll = callback; },
  });
  return {window, storage, requests, poll: () => poll()};
}

test('disabling alerts during a pending fetch does not consume unseen notifications', async () => {
  const app = dashboard();
  const rows = [{id: 'app_1', title: 'New application', subtitle: 'Example candidate', created_at: '2026-10-06T12:00:00'}];
  app.window.dashboardSettings.preferences.site_alerts = false;
  app.requests.shift()(rows);
  await settle();
  app.window.dashboardSettings.preferences.site_alerts = true;
  const pending = app.poll();
  app.requests.shift()(rows);
  await pending;
  const timeline = JSON.parse(app.storage.get('altera-notifs-v2-1-test') || '[]');
  assert.equal(timeline.length, 1, 'The notification must still appear after alerts are enabled again');
});
