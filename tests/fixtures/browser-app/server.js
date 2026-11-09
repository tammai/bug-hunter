// A notes app for bug-hunter's browser-mode acceptance run. Planted defect: the page's Save
// button stays enabled while its request is in flight, and the server takes every POST, so a
// double click saves the note twice.
const fs = require('fs');
const http = require('http');
const path = require('path');

const notes = [];
const page = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');

// A small router, so the routes read as they would in any web framework.
const app = {
  routes: [],
  get(route, handler) { this.routes.push(['GET', route, handler]); },
  post(route, handler) { this.routes.push(['POST', route, handler]); },
};

function send(res, status, type, body) {
  res.writeHead(status, {'Content-Type': type, 'Content-Length': Buffer.byteLength(body)});
  res.end(body);
}

app.get('/', (req, res) => send(res, 200, 'text/html', page));

app.get('/api/notes', (req, res) => send(res, 200, 'application/json', JSON.stringify(notes)));

app.post('/api/notes', (req, res) => {
  let body = '';
  req.on('data', (chunk) => { body += chunk; });
  req.on('end', () => {
    let text = '';
    try { text = String(JSON.parse(body).text || ''); } catch { /* an empty note */ }
    if (!text.trim()) return send(res, 400, 'application/json', '{"error":"text is required"}');
    notes.push({id: notes.length + 1, text});
    return send(res, 201, 'application/json', JSON.stringify(notes[notes.length - 1]));
  });
});

const server = http.createServer((req, res) => {
  const route = app.routes.find(([method, url]) => method === req.method && url === req.url);
  if (route) return route[2](req, res);
  return send(res, 404, 'application/json', '{"error":"not found"}');
});

server.listen(Number(process.env.PORT || 0), '127.0.0.1', () => {
  // The listening line is how a test or a run learns the port.
  console.log(`listening on http://127.0.0.1:${server.address().port}`);
});
