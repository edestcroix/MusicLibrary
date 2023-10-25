import os
import time
import urllib
import urllib.parse
from enum import Enum

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject, Gio


Gst.init(None)


class LoopMode(Enum):
    NONE = 0
    SINGLE = 1
    ALL = 2


class Player(GObject.GObject):
    volume = GObject.Property(type=float, default=1.0)
    muted = GObject.Property(type=bool, default=False)

    stream_start = GObject.Signal()
    seeked = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    player_error = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    # current_track property should not be setable
    current_track = GObject.Property(
        type=GObject.TYPE_PYOBJECT, default=None, setter=None
    )

    loop = GObject.Property(type=GObject.TYPE_PYOBJECT)

    single_repeated = False

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
        self._seeking = False

        self.state = 'stopped'
        self.loop = LoopMode.NONE

    @GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    def state_changed(self, state):
        self.state = state

    def play(self):
        self.setup(Gst.State.PLAYING)

    def ready(self):
        self.setup(Gst.State.PAUSED)

    def setup(self, initial_state):
        url = self._prepare_url(self._play_queue.get_current_track())
        self._player.set_state(Gst.State.NULL)
        time.sleep(0.1)
        self._player.set_property('uri', url)
        self._player.set_state(initial_state)
        if initial_state == Gst.State.PLAYING:
            self.emit('state_changed', 'playing')
        elif initial_state == Gst.State.PAUSED:
            self.emit('state_changed', 'paused')

    def toggle(self):
        match self._player.get_state(1 * Gst.SECOND)[1]:
            case Gst.State.PLAYING:
                self._player.set_state(Gst.State.PAUSED)
                self.emit('state_changed', 'paused')
            case Gst.State.PAUSED:
                self._player.set_state(Gst.State.PLAYING)
                self.emit('state_changed', 'playing')
            case Gst.State.NULL:
                if self.current_track:
                    self.play()

    def toggle_mute(self):
        mute_state = self._player.get_property('mute')
        self._player.set_property('mute', not mute_state)

    def stop(self):
        self._player.set_state(Gst.State.NULL)
        self.emit('state_changed', 'stopped')

    def exit(self):
        self.current_track = None
        self._player.set_state(Gst.State.NULL)
        self.emit('state_changed', 'stopped')

    def go_next(self):
        if self._play_queue.next():
            self.play()
        elif self.loop == LoopMode.ALL:
            self._play_queue.restart()
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
        self.emit('seeked', position)

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
        if self.loop == LoopMode.SINGLE and not self.single_repeated:
            self.single_repeated = True
            self._player.set_property(
                'uri', self._prepare_url(self._play_queue.get_current_track())
            )
        elif next_track := self._play_queue.get_next_track():
            self.single_repeated = False
            self._player.set_property('uri', self._prepare_url(next_track))
        elif self.loop == LoopMode.ALL:
            self._play_queue.restart()
            self._player.set_property(
                'uri', self._prepare_url(self._play_queue.get_current_track())
            )

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
            self.exit()
        elif t == Gst.MessageType.ASYNC_DONE and self._seeking:
            self._seeking = False
        elif message.type == Gst.MessageType.STREAM_START:
            self.current_track = self._play_queue.get_current_track()
            self.emit('stream_start')
        elif t == Gst.MessageType.ERROR:
            self._player.set_state(Gst.State.NULL)
            err, _ = message.parse_error()
            self.player_error.emit(err)
