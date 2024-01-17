import os
import time
import urllib
import urllib.parse
from enum import auto, StrEnum
from .items import TrackItem


import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject, Gio

Gst.init(None)

TIMEOUT = 100   # ms
SEEK_THRESHOLD = 1000000000   # 1s


class LoopMode(StrEnum):
    NONE = auto()
    TRACK = auto()
    PLAYLIST = auto()


class PlayerState(StrEnum):
    STOPPED = auto()
    PAUSED = auto()
    PLAYING = auto()


class Player(GObject.GObject):
    __gtype_name__ = 'RecordBoxPlayer'
    """The player class handles playback control and manages the GStreamer
    pipeline. Must be connected to a play queue to function."""

    state = GObject.Property(type=str, default=PlayerState.STOPPED)

    position = GObject.Property(type=float, default=0.0)
    duration = GObject.Property(type=float, default=0.0)

    current_track = GObject.Property(
        type=GObject.TYPE_PYOBJECT, default=None, setter=None
    )

    volume = GObject.Property(type=float, default=1.0)
    muted = GObject.Property(type=bool, default=False)

    loop = GObject.Property(type=str, default=LoopMode.NONE)
    stop_after_current = GObject.Property(type=bool, default=False)

    rg_mode = GObject.Property(type=str, default='album')
    rg_enabled = GObject.Property(type=bool, default=False)
    rg_preamp = GObject.Property(type=float, default=0.0)
    rg_fallback = GObject.Property(type=float, default=0.0)

    eos = GObject.Signal()
    stream_start = GObject.Signal()
    seeked = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    player_error = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    single_repeated = False

    _monitoring = False
    _seeking = False
    _stop_next = False

    def __init__(self):
        super().__init__()

        self._rg_bin, self._rg_volume = self._setup_replaygain()
        self._rg_volume.bind_property(
            'pre-amp', self, 'rg_preamp', GObject.BindingFlags.BIDIRECTIONAL
        )
        self._rg_volume.bind_property(
            'fallback-gain',
            self,
            'rg_fallback',
            GObject.BindingFlags.BIDIRECTIONAL,
        )

        self._player = Gst.ElementFactory.make('playbin')
        self._default_sink = Gst.ElementFactory.make('autoaudiosink')
        self._player.set_property('audio-sink', self._default_sink)

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

        self.connect('notify::rg-mode', self._on_rg_mode_changed)
        self.connect('notify::rg-enabled', self._on_rg_enabled_changed)

        self._state_restored = False

    def attach_to_play_queue(self, play_queue):
        self._play_queue = play_queue
        self._play_queue.connect(
            'jump-to-track',
            self.jump_to_track,
        )

    @GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    def state_changed(self, state):
        self.state = state
        if state == PlayerState.PLAYING and not self._monitoring:
            self._monitoring = True
            GLib.timeout_add(TIMEOUT, self._update_position)

    def play(self):
        self.setup(Gst.State.PLAYING)

    def ready(self):
        self.setup(Gst.State.PAUSED)

    def resume(self, position: int):
        self._state_restored = True
        self.current_track = self._play_queue.get_current_track()
        self.setup(Gst.State.PAUSED, position)
        GLib.timeout_add(300, self._update_position)

    def setup(self, initial_state: Gst.State, position=0):
        url = self._prepare_url(self._play_queue.get_current_track())
        self._player.set_state(Gst.State.NULL)
        time.sleep(0.1)
        self._player.set_property('uri', url)
        self._player.set_state(initial_state)
        self.position = position
        if initial_state == Gst.State.PLAYING:
            self.emit('state_changed', PlayerState.PLAYING)
        elif initial_state == Gst.State.PAUSED:
            self.emit('state_changed', PlayerState.PAUSED)

    def toggle(self):
        match self._player.get_state(1 * Gst.SECOND)[1]:
            case Gst.State.PLAYING:
                self._player.set_state(Gst.State.PAUSED)
                self.emit('state_changed', PlayerState.PAUSED)
            case Gst.State.PAUSED:
                self._player.set_state(Gst.State.PLAYING)
                self.emit('state_changed', PlayerState.PLAYING)
            case Gst.State.NULL:
                if self.current_track:
                    self.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted

    def stop(self):
        self._player.set_state(Gst.State.NULL)
        self.position, self.duration = 0, 0
        self.stop_after_current, self._stop_next = False, False
        self.emit('state_changed', PlayerState.STOPPED)

    def exit(self):
        self.current_track = None
        self.stop()

    def go_next(self):
        if self._play_queue.next():
            self.play()
        elif self.loop == LoopMode.PLAYLIST:
            self._play_queue.restart()
            self.play()

    def go_previous(self):
        if self._play_queue.previous():
            self.play()

    def jump_to_track(self, _):
        """Reloads the current track in the play queue, in response to the play
        queue jumping to a different track. Expectation is that the current track
        in the queue is no longer the same track that is playing."""

        self._player.set_state(Gst.State.NULL)
        self._player.set_property(
            'uri', self._prepare_url(self._play_queue.get_current_track())
        )
        self._player.set_state(Gst.State.PLAYING)
        self.emit('state-changed', PlayerState.PLAYING)

    def export_state(self):
        """Export the currently playing track and the position in the track."""
        return {
            'track': self.current_track,
            'position': self.position,
        }

    def _setup_replaygain(self) -> tuple[Gst.Bin, Gst.Element]:
        rg_bin = Gst.Bin.new('rg')
        rg_volume = Gst.ElementFactory.make('rgvolume', 'rg_volume')
        rg_bin.add(rg_volume)
        pad = rg_volume.get_static_pad('sink')
        ghost_pad = Gst.GhostPad.new('sink', pad)
        ghost_pad.set_active(True)
        rg_bin.add_pad(ghost_pad)

        output = Gst.ElementFactory.make('autoaudiosink', 'rg_output')
        rg_bin.add(output)
        rg_volume.link(output)

        return rg_bin, rg_volume

    def _on_rg_mode_changed(self, *_):
        self._rg_volume.set_property(
            'album-mode',
            self.rg_mode == 'album',
        )

    def _on_rg_enabled_changed(self, *_):
        self._player.set_property(
            'audio-sink',
            self._rg_bin if self.rg_enabled else self._default_sink,
        )

    def _on_about_to_finish(self, _):
        if self.stop_after_current:
            self._stop_next = True

        if self.loop == LoopMode.TRACK and not self.single_repeated:
            self.single_repeated = True
            self._player.set_property(
                'uri', self._prepare_url(self._play_queue.get_current_track())
            )
        elif next_track := self._play_queue.get_next_track():
            self.single_repeated = False
            self._player.set_property('uri', self._prepare_url(next_track))
        elif self.loop == LoopMode.PLAYLIST:
            self._play_queue.restart()
            self._player.set_property(
                'uri', self._prepare_url(self._play_queue.get_current_track())
            )

    def _prepare_url(self, track: TrackItem):
        path = os.path.realpath(track.path.strip())
        # escape characters that need to be escaped in a file URI
        path = urllib.parse.quote(path)
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

    def _update_position(self):
        """Updates the position property of the player. Should be called
        periodically while the player is playing or paused. (Position is not
        a property that can be bound to, it must be updated manually.)"""
        if self.state == PlayerState.STOPPED:
            self._monitoring = False
            return False
        new_position = self._player.query_position(Gst.Format.TIME)[1]
        # if the position has changed by more than SEEK_THRESHOLD, seek to the new position
        # (the postion property was changed externally, and the player needs to update to match)
        if abs(self.position - new_position) >= SEEK_THRESHOLD:
            self._seek(self.position)
        else:
            self.position = new_position
        return True

    def _seek(self, position: int):
        duration = self._player.query_duration(Gst.Format.TIME)[1]
        if self._seeking or position > duration:
            return
        # set seeking to True. This will be turned False by the message handler
        # the next time it receives an ASYNC_DONE message and _seeking is True.
        # This way, scrolling the seekbar doesn't trigger overlapping seeks.
        # (Which I think can happen)
        self._seeking = True
        self.position = position
        self._player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH, position
        )
        self.emit('seeked', position)

    def _on_message(self, _, message: Gst.Message):
        match message.type:
            case Gst.MessageType.EOS:
                self.stop()
                if not self._play_queue.empty and not self.stop_after_current:
                    self._play_queue.restart()
                    self.current_track = self._play_queue.get_current_track()
                self.stop_after_current = False
                self.emit('eos')
            case Gst.MessageType.STREAM_START:
                self._on_stream_start()
            case Gst.MessageType.ASYNC_DONE if self._seeking:
                self._seeking = False
            case Gst.MessageType.ERROR:
                self._player.set_state(Gst.State.NULL)
                err, _ = message.parse_error()
                self.player_error.emit(err)

    def _on_stream_start(self):
        self.current_track = self._play_queue.get_current_track()
        # set position to 0 here, otherwise it will still be the last position of the
        # previous track the next time _update_position is called, triggering a seek
        # (Unless _state_restored is True, where the position was set manually when the app
        # started while it restored from a previous session, then just disable _state_restored)
        if not self._state_restored:
            self.position = 0
        else:
            self._state_restored = False

        self.duration = self._player.query_duration(Gst.Format.TIME)[1]
        # always emit stream_start, even if we're going to stop immediately
        # because the UI uses it as the signal to update the current track info
        self.emit('stream_start')
        if self._stop_next:
            self.stop()
