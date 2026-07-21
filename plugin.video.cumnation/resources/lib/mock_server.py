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

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs
except ImportError:  # pragma: no cover - Python 2 fallback
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from urlparse import urlparse, parse_qs

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


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        path = parsed.path.strip('/')

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
