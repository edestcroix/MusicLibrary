import os
import time
import urllib
import urllib.parse

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject, Gio


Gst.init(None)


class Player(GObject.GObject):
    def __init__(self, play_queue, **kwargs):
        super().__init__(**kwargs)
        self._player = Gst.parse_launch(
            'playbin audio-sink="rgvolume album-mode=\\"true\\" ! autoaudiosink"'
        )
        self._player.connect('about-to-finish', self._on_about_to_finish)
        self._player.bind_property(
            'volume', self, 'volume', GObject.BindingFlags.BIDIRECTIONAL
        )
        self._player.bind_property(
            'mute', self, 'muted', GObject.BindingFlags.BIDIRECTIONAL
        )
        self.bus = self._player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self._on_message)
        self._play_queue = play_queue
        self.state = 'stopped'
        self._seeking = False

    volume = GObject.Property(type=float, default=1.0)
    muted = GObject.Property(type=bool, default=False)

    stream_start = GObject.Signal()

    player_error = GObject.Signal(
        arg_types=(GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)
    )

    @GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    def state_changed(self, state):
        self.state = state

    def play(self):
        url = self._prepare_url(self._play_queue.get_current_track())
        self._player.set_state(Gst.State.NULL)
        time.sleep(0.1)
        self._player.set_property('uri', url)
        self._player.set_state(Gst.State.PLAYING)
        self.emit('state_changed', 'playing')

    def ready(self):
        url = self._prepare_url(self._play_queue.get_current_track())
        self._player.set_state(Gst.State.NULL)
        time.sleep(0.1)
        self._player.set_property('uri', url)
        self._player.set_state(Gst.State.PAUSED)
        self.emit('state_changed', 'ready')

    def toggle(self):
        if self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PLAYING:
            self._player.set_state(Gst.State.PAUSED)
            self.emit('state_changed', 'paused')
            self.state = 'paused'
        elif self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PAUSED:
            self._player.set_state(Gst.State.PLAYING)
            self.emit('state_changed', 'playing')

    def toggle_mute(self):
        mute_state = self._player.get_property('mute')
        print(mute_state)
        self._player.set_property('mute', not mute_state)

    def stop(self):
        self._player.set_state(Gst.State.NULL)
        self.emit('state_changed', 'stopped')

    def go_next(self):
        if self._play_queue.next():
            self.play()

    def go_previous(self):
        if self._play_queue.previous():
            self.play()

    def get_progress(self):
        return self._player.query_position(Gst.Format.TIME)[1]

    def get_duration(self):
        return self._player.query_duration(Gst.Format.TIME)[1]

    def seek(self, position):
        duration = self._player.query_duration(Gst.Format.TIME)[1]
        if self._seeking or position > duration:
            return
        # set seeking to True. This will be turned False by the message handler
        # the next time it receives an ASYNC_DONE message and _seeking is True.
        # This way, scrolling the seekbar doesn't trigger overlapping seeks.
        self._seeking = True
        self._player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH, position
        )

    def jump_to_track(self, _):
        """Reloads the current track in the play queue, in response to the play
        queue jumping to a different track. Expectation is that the current track
        in the queue is no longer the same track that is playing"""

        self._player.set_state(Gst.State.NULL)
        self._player.set_property(
            'uri', self._prepare_url(self._play_queue.get_current_track())
        )
        self._player.set_state(Gst.State.PLAYING)

    def _on_about_to_finish(self, _):
        if next_track := self._play_queue.get_next_track():
            self._player.set_property('uri', self._prepare_url(next_track))

    def _prepare_url(self, track):
        path = os.path.realpath(track.path.strip())
        result = urllib.parse.ParseResult(
            scheme='file',
            path=path,
            netloc='',
            query='',
            fragment='',
            params='',
        )
        result = urllib.parse.urlunparse(result)
        return result

    def _on_message(self, _, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._player.set_state(Gst.State.NULL)
            self.emit('state_changed', 'stopped')
        elif t == Gst.MessageType.ASYNC_DONE and self._seeking:
            self._seeking = False
        elif message.type == Gst.MessageType.STREAM_START:
            self.emit('stream_start')
        elif t == Gst.MessageType.ERROR:
            self._player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
