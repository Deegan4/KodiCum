# -*- coding: utf-8 -*-
"""A tiny reference backend for the Cumnation add-on.

This is NOT loaded by Kodi. It is a standalone example that implements the
JSON API contract the add-on expects, so you can point the add-on at a real
endpoint and see it work end to end without writing a backend first.

Run it with plain CPython (no Kodi needed):

    python3 resources/lib/mock_server.py 8080

Then set the add-on's "Base API URL" setting to:

    http://<this-machine-ip>:8080

It serves Blender Foundation open movies (Creative Commons licensed) so the
playback path is exercised with legally shareable content.
"""
import json
import sys
import time
from collections import deque

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs
except ImportError:  # pragma: no cover - Python 2 fallback
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from urlparse import urlparse, parse_qs

START_TIME = time.time()
RECENT_REQUESTS = deque(maxlen=20)  # most-recent-first, for the dashboard

# Public-domain / CC-licensed sample streams from Blender open movies.
_STREAM = 'https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4'
_SINTEL = 'https://download.blender.org/durian/movies/Sintel.2010.720p.mkv'

CATEGORIES = [
    {'id': 'featured', 'name': 'Featured', 'count': 2,
     'plot': 'Hand-picked highlights'},
    {'id': 'recent', 'name': 'Recently Added', 'count': 2,
     'plot': 'The newest additions'},
]

VIDEOS = {
    'featured': [
        {'id': 'bbb', 'title': 'Big Buck Bunny', 'url': _STREAM,
         'thumb': 'https://peach.blender.org/wp-content/uploads/bbb-splash.png',
         'plot': 'A large rabbit deals with three bullying rodents.',
         'duration': 596, 'date': '10.04.2008', 'rating': 8.1,
         'tags': ['animation', 'comedy']},
        {'id': 'sintel', 'title': 'Sintel', 'url': _SINTEL,
         'thumb': 'https://durian.blender.org/wp-content/uploads/2010/06/05.1c.jpg',
         'plot': 'A girl searches for a baby dragon she befriended.',
         'duration': 888, 'date': '27.09.2010', 'rating': 8.5,
         'tags': ['animation', 'fantasy']},
    ],
}
VIDEOS['recent'] = list(reversed(VIDEOS['featured']))


def _find(video_id):
    for items in VIDEOS.values():
        for video in items:
            if video['id'] == video_id:
                return video
    return None


def _status_payload():
    return {
        'status': 'up',
        'uptime_seconds': int(time.time() - START_TIME),
        'categories': len(CATEGORIES),
        'videos': sum(len(items) for items in VIDEOS.values()),
        'recent_requests': list(RECENT_REQUESTS),
    }


def _dashboard_html():
    return """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cumnation backend</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0;
         padding: 1.25rem; background: #0b0f14; color: #e6edf3; }
  h1 { font-size: 1.1rem; margin: 0 0 1rem; }
  .dot { display: inline-block; width: 0.6rem; height: 0.6rem;
         border-radius: 50%; background: #3fb950; margin-right: 0.4rem; }
  .dot.down { background: #f85149; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px;
          padding: 0.9rem 1rem; margin-bottom: 0.9rem; }
  .row { display: flex; justify-content: space-between; padding: 0.25rem 0;
         font-size: 0.95rem; border-bottom: 1px solid #21262d; }
  .row:last-child { border-bottom: none; }
  .row span:first-child { color: #8b949e; }
  a { color: #58a6ff; text-decoration: none; }
  ul { padding-left: 1.1rem; margin: 0.3rem 0; }
  li { font-size: 0.9rem; margin: 0.2rem 0; }
  #reqs div { font-size: 0.82rem; color: #8b949e; padding: 0.15rem 0; }
  #reqs b { color: #e6edf3; }
</style>
</head><body>
<h1><span id="dot" class="dot"></span>Cumnation mock backend</h1>
<div class="card">
  <div class="row"><span>Status</span><span id="status">checking...</span></div>
  <div class="row"><span>Uptime</span><span id="uptime">-</span></div>
  <div class="row"><span>Categories</span><span id="categories">-</span></div>
  <div class="row"><span>Videos</span><span id="videos">-</span></div>
</div>
<div class="card">
  <b>Try it</b>
  <ul>
    <li><a href="/categories">/categories</a></li>
    <li><a href="/list?category=featured&page=1">/list?category=featured</a></li>
    <li><a href="/search?q=bunny">/search?q=bunny</a></li>
    <li><a href="/resolve?id=bbb">/resolve?id=bbb</a></li>
  </ul>
</div>
<div class="card">
  <b>Recent requests</b>
  <div id="reqs"></div>
</div>
<script>
function fmt(s) {
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h + 'h ' + m + 'm ' + sec + 's';
}
function refresh() {
  fetch('/status').then(function (r) { return r.json(); }).then(function (d) {
    document.getElementById('dot').className = 'dot';
    document.getElementById('status').textContent = 'up';
    document.getElementById('uptime').textContent = fmt(d.uptime_seconds);
    document.getElementById('categories').textContent = d.categories;
    document.getElementById('videos').textContent = d.videos;
    var reqs = document.getElementById('reqs');
    reqs.innerHTML = d.recent_requests.length ? '' : '<div>none yet</div>';
    d.recent_requests.forEach(function (r) {
      var line = document.createElement('div');
      line.innerHTML = '<b>' + r.time + '</b> &nbsp;' + r.path;
      reqs.appendChild(line);
    });
  }).catch(function () {
    document.getElementById('dot').className = 'dot down';
    document.getElementById('status').textContent = 'unreachable';
  });
}
refresh();
setInterval(refresh, 3000);
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        path = parsed.path.strip('/')

        # Dashboard and its polling endpoint are excluded from the request
        # log below, or the log would fill with nothing but its own polls.
        if path in ('', 'dashboard'):
            self._send_html(_dashboard_html())
            return
        if path == 'status':
            self._send(_status_payload())
            return

        RECENT_REQUESTS.appendleft(
            {'time': time.strftime('%H:%M:%S'), 'path': self.path})

        if path == 'categories':
            self._send({'categories': CATEGORIES})
        elif path == 'list':
            items = VIDEOS.get(query.get('category', ''), [])
            self._send({'videos': items, 'page': int(query.get('page', 1)),
                        'has_next': False})
        elif path == 'search':
            term = query.get('q', '').lower()
            hits = [v for items in VIDEOS.values() for v in items
                    if term in v['title'].lower()]
            self._send({'videos': hits, 'page': 1, 'has_next': False})
        elif path == 'resolve':
            video = _find(query.get('id', ''))
            if not video:
                self._send({'streams': []})
            elif video['id'] == 'bbb':
                # Demonstrate the multi-quality shape + the quality picker.
                self._send({'streams': [
                    {'url': 'https://download.blender.org/demo/movies/BBB/'
                            'bbb_sunflower_1080p_30fps_normal.mp4',
                     'quality': 1080, 'label': '1080p'},
                    {'url': _STREAM, 'quality': 240, 'label': '240p'},
                ]})
            else:
                # Single progressive stream (older/simple shape still works).
                self._send({'stream': video['url'], 'headers': {}})
        else:
            self._send({'error': 'not found'})

    def log_message(self, *args):
        pass  # keep stdout quiet


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('0.0.0.0', port), Handler)
    print('Cumnation mock backend on http://0.0.0.0:{0}'.format(port))
    print('Set the add-on Base API URL to http://<ip>:{0}'.format(port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == '__main__':
    main()
