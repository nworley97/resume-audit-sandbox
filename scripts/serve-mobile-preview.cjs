// Local preview only: serve the same template and assets as the Flask blueprint.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const routes = new Map([
  ['/static/js/mobile-preview-data.js', ['static/js/mobile-preview-data.js', 'text/javascript']],
  ['/mobile-demo/preview-61d7c4a9f2e8', ['templates/mobile_demo.html', 'text/html']],
  ['/static/css/mobile-preview.css', ['static/css/mobile-preview.css', 'text/css']],
  ['/static/js/mobile-preview.js', ['static/js/mobile-preview.js', 'text/javascript']],
]);
http.createServer((req, res) => {
  const entry = routes.get(new URL(req.url, 'http://localhost').pathname);
  if (!entry) { res.writeHead(404); res.end('Not found'); return; }
  res.writeHead(200, {'Content-Type': entry[1] + '; charset=utf-8', 'Cache-Control':'no-store', 'X-Robots-Tag':'noindex, nofollow, noarchive'});
  fs.createReadStream(path.join(root, entry[0])).pipe(res);
}).listen(5057, '127.0.0.1', () => console.log('Preview: http://127.0.0.1:5057/mobile-demo/preview-61d7c4a9f2e8'));
