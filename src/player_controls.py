import gi

gi.require_version('Gtk', '4.0')
gi.require_version('GstAudio', '1.0')

from gi.repository import Adw, Gtk, GLib, GObject, GstAudio
from .monitor import ProgressMonitor
from .player import LoopMode


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/player_controls.ui'
)
class RecordBoxPlayerControls(Gtk.Box):
    __gtype_name__ = 'RecordBoxPlayerControls'
    play_pause = Gtk.Template.Child()

    playing_song = Gtk.Template.Child()
    playing_artist = Gtk.Template.Child()

    loop = Gtk.Template.Child()

    progress = Gtk.Template.Child()
    start_label = Gtk.Template.Child()
    end_label = Gtk.Template.Child()

    volume_toggle = Gtk.Template.Child()
    volume_slider = Gtk.Template.Child()

    stop_button = Gtk.Template.Child()

    muted = GObject.Property(type=bool, default=False)
    stop_exits = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume_slider.set_range(0, 1)
        self.progress.set_increments(1, 5)

        self.loop.connect('clicked', self._cycle_loop_mode)
        self.connect('notify::stop_exits', lambda *_: self._update_stop)

    def attach_to_player(self, player):
        self._player = player
        self._monitor = ProgressMonitor(
            player, self.progress, self.start_label, self.end_label
        )
        self._player.connect(
            'notify::muted', lambda *_: self._update_volume_icon
        )
        self._player.connect('notify::volume', self._update_volume)
        self._player.connect('notify::loop', self._update_loop_icon)
        self._player.connect('state-changed', self._update_state)
        self._player.connect('stream-start', self.set_current_track)

    def activate(self, playing=True):
        self._monitor.start()
        if playing:
            self.play_pause.set_icon_name('media-playback-pause-symbolic')
            self.progress.set_sensitive(True)
        else:
            self.play_pause.set_icon_name('media-playback-start-symbolic')

    def deactivate(self):
        self.play_pause.set_icon_name('media-playback-start-symbolic')
        self.progress.set_sensitive(False)
        self.set_property('stop-exits', True)

    def set_current_track(self, *_):
        if track := self._player.current_track:
            self.playing_song.set_markup(
                f'<span size="large">{track.title}</span>'
            )
            artists = (
                f'{track.albumartist}, {track.artists}'
                if track.artists
                else track.albumartist
            )
            self.playing_artist.set_markup(
                f'<span size="small">{GLib.markup_escape_text(artists)}</span>'
            )
            self.end_label.set_text(track.length)
        else:
            self.playing_song.set_text('')
            self.playing_artist.set_text('')
            self.end_label.set_text('0:00')

    @Gtk.Template.Callback()
    def _stop(self, _):
        self._player.exit() if self.stop_exits else self._player.stop()

    @Gtk.Template.Callback()
    def _play_pause(self, _):
        self._player.toggle()

    @Gtk.Template.Callback()
    def _skip_forward(self, _):
        self._player.go_next()

    @Gtk.Template.Callback()
    def _skip_backward(self, _):
        self._player.go_previous()

    @Gtk.Template.Callback()
    def _toggle_mute(self, _):
        self._player.set_property('muted', not self._player.muted)

    @Gtk.Template.Callback()
    def _volume_changed(self, _, __, value):
        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.CUBIC,
            GstAudio.StreamVolumeFormat.LINEAR,
            value,
        )
        self._player.set_property('volume', value)

    def _update_state(self, _, state: str):
        match state:
            case 'playing':
                self._update_stop(False)
                self.activate(playing=True)
            case 'paused':
                self._update_stop(False)
                self.activate(playing=False)
            case 'stopped':
                self._update_stop(True)
                self.deactivate()

    def _cycle_loop_mode(self, _):
        self._player.loop = LoopMode((self._player.loop.value + 1) % 3)

    def _update_stop(self, state):
        self.stop_exits = state
        if self.stop_exits:
            self.stop_button.set_icon_name('application-exit-symbolic')
        else:
            self.stop_button.set_icon_name('media-playback-stop-symbolic')

    def _update_volume(self, *_):
        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.LINEAR,
            GstAudio.StreamVolumeFormat.CUBIC,
            self._player.volume,
        )
        GLib.idle_add(self.volume_slider.set_value, value)
        GLib.idle_add(self._update_volume_icon)

    def _update_volume_icon(self):
        if self._player.muted:
            self.volume_toggle.set_icon_name('audio-volume-muted-symbolic')
            return
        elif self.volume_slider.get_value() < 0.3:
            self.volume_toggle.set_icon_name('audio-volume-low-symbolic')
        elif self.volume_slider.get_value() < 0.7:
            self.volume_toggle.set_icon_name('audio-volume-medium-symbolic')
        else:
            self.volume_toggle.set_icon_name('audio-volume-high-symbolic')

    def _update_loop_icon(self, *_):
        match self._player.loop:
            case LoopMode.NONE:
                self.loop.set_icon_name('media-playlist-consecutive-symbolic')
            case LoopMode.ALL:
                self.loop.set_icon_name('media-playlist-repeat-symbolic')
            case LoopMode.SINGLE:
                self.loop.set_icon_name('media-playlist-repeat-song-symbolic')
