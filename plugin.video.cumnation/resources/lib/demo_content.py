# -*- coding: utf-8 -*-
"""Shared sample catalogue: legally shareable CC-licensed Blender movies.

Used by both ``mock_server.py`` (a live reference backend you run yourself)
and ``tools/build_static_demo.py`` (a pre-baked, serverless version of the
same catalogue, published for free via GitHub Pages). Keeping the data in
one place keeps both in sync.
"""

# Public-domain / CC-licensed sample streams from Blender open movies.
_STREAM = 'https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4'
_SINTEL = 'https://download.blender.org/durian/movies/Sintel.2010.720p.mkv'
_BBB_1080P = ('https://download.blender.org/demo/movies/BBB/'
              'bbb_sunflower_1080p_30fps_normal.mp4')

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
         'preview': 'https://peach.blender.org/wp-content/uploads/bbb-splash.png',
         'plot': 'A large rabbit deals with three bullying rodents.',
         'duration': 596, 'date': '10.04.2008', 'rating': 8.1,
         'tags': ['animation', 'comedy']},
        {'id': 'sintel', 'title': 'Sintel', 'url': _SINTEL,
         'thumb': 'https://durian.blender.org/wp-content/uploads/2010/06/05.1c.jpg',
         'preview': 'https://durian.blender.org/wp-content/uploads/2010/06/05.1c.jpg',
         'plot': 'A girl named Sintel hunts a baby dragon across a snowy '
                 'wasteland.',
         'duration': 888, 'date': '27.09.2010', 'rating': 8.5,
         'tags': ['animation', 'fantasy']},
    ],
}
VIDEOS['recent'] = list(reversed(VIDEOS['featured']))


def find_video(video_id):
    for items in VIDEOS.values():
        for video in items:
            if video['id'] == video_id:
                return video
    return None


def resolve_payload(video_id):
    """The /resolve response body for ``video_id`` (empty streams if unknown)."""
    video = find_video(video_id)
    if not video:
        return {'streams': []}
    if video['id'] == 'bbb':
        # Demonstrate the multi-quality shape + the quality picker.
        return {'streams': [
            {'url': _BBB_1080P, 'quality': 1080, 'label': '1080p'},
            {'url': _STREAM, 'quality': 240, 'label': '240p'},
        ]}
    # Single progressive stream (older/simple shape still works).
    return {'stream': video['url'], 'headers': {}}
