# -*- coding: utf-8 -*-
"""Player monitor used to capture resume points.

Kodi's xbmc.Player fires callbacks on its own thread. We poll the current
time while our stream is playing and persist the final position when it stops
or ends, so the item can resume next time.
"""
import xbmc

from . import resume
from . import kodiutils
from . import trakt


class ResumePlayer(xbmc.Player):
    def __init__(self, video_id, video=None):
        super(ResumePlayer, self).__init__()
        self.video_id = video_id
        self.video = video
        self._last_position = 0.0
        self._total = 0.0
        self._stopped = False
        self._ended = False

    def run(self):
        """Block until playback ends, sampling position roughly once a second."""
        monitor = xbmc.Monitor()
        # Wait for playback to actually start (max ~30s).
        waited = 0
        while not self.isPlayingVideo() and waited < 30 and not monitor.abortRequested():
            if monitor.waitForAbort(0.5):
                return
            waited += 0.5

        while self.isPlayingVideo() and not self._stopped:
            try:
                self._last_position = self.getTime()
                self._total = self.getTotalTime()
            except RuntimeError:
                break
            if monitor.waitForAbort(1.0):
                break

        self._persist()

    @property
    def ended(self):
        """Whether playback ran to completion, as opposed to being stopped early."""
        return self._ended

    def _persist(self):
        if self._last_position > 0:
            if resume.enabled():
                resume.set(self.video_id, self._last_position, self._total)
                kodiutils.log('Saved resume point {0:.0f}s for {1}'.format(
                    self._last_position, self.video_id))
            if trakt.enabled() and self.video:
                if self._last_position >= self._total * 0.95:
                    trakt.scrobble_complete(self.video)
                else:
                    trakt.scrobble_stop(self.video, self._last_position)

    def onPlayBackStopped(self):
        self._stopped = True

    def onPlayBackEnded(self):
        self._stopped = True
        self._ended = True
