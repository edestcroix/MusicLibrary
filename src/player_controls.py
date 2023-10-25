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

    play_toggle = GObject.Signal()
    play_skip_forward = GObject.Signal()
    play_skip_backward = GObject.Signal()
    play_stop = GObject.Signal()
    exit = GObject.Signal()

    stop_button = Gtk.Template.Child()

    muted = GObject.Property(type=bool, default=False)
    loop_mode = GObject.Property(type=GObject.TYPE_PYOBJECT)

    _stop_exits = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume_slider.set_range(0, 1)
        self.progress.set_increments(1, 5)

        self.loop.connect('clicked', self._cycle_loop_mode)

        self.connect('notify::loop-mode', self._on_loop_mode_changed)
        self.loop_mode = LoopMode.NONE

    # Create a GObject property for the volume so it can be bidirectionally
    # bound to the player's volume property.
    @GObject.Property(type=float, default=1.0)
    def volume(self):
        value = self.volume_slider.get_value()
        return GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.CUBIC,
            GstAudio.StreamVolumeFormat.LINEAR,
            value,
        )

    @volume.setter
    def set_volume(self, value):
        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.LINEAR,
            GstAudio.StreamVolumeFormat.CUBIC,
            value,
        )
        GLib.idle_add(self.volume_slider.set_value, value)
        self._update_volume_icon()

    @GObject.Property(type=bool, default=False)
    def stop_exits(self):
        return self._stop_exits

    @stop_exits.setter
    def set_stop_exits(self, value):
        self._stop_exits = value
        if value:
            self.stop_button.set_icon_name('application-exit-symbolic')
        else:
            self.stop_button.set_icon_name('media-playback-stop-symbolic')

    def attach_to_player(self, player):
        self._monitor = ProgressMonitor(
            player, self.progress, self.start_label, self.end_label
        )
        player.bind_property(
            'volume', self, 'volume', GObject.BindingFlags.BIDIRECTIONAL
        )
        player.bind_property(
            'muted', self, 'muted', GObject.BindingFlags.BIDIRECTIONAL
        )

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
        self.set_property('stop_exits', True)

    def set_current_track(self, track):
        if track:
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
        if self.stop_exits:
            self.emit('exit')
        else:
            self.emit('play_stop')

    @Gtk.Template.Callback()
    def _play_pause(self, _):
        self.emit('play_toggle')

    @Gtk.Template.Callback()
    def _skip_forward(self, _):
        self.emit('play_skip_forward')

    @Gtk.Template.Callback()
    def _skip_backward(self, _):
        self.emit('play_skip_backward')

    @Gtk.Template.Callback()
    def _toggle_mute(self, _):
        self.set_property('muted', not self.muted)
        self._update_volume_icon()

    def _cycle_loop_mode(self, loop):
        self.loop_mode = LoopMode((self.loop_mode.value + 1) % 3)

    @Gtk.Template.Callback()
    def _volume_changed(self, _, __, value):
        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.CUBIC,
            GstAudio.StreamVolumeFormat.LINEAR,
            value,
        )
        self.set_property('volume', value)

    def _update_volume_icon(self):
        if self.muted:
            self.volume_toggle.set_icon_name('audio-volume-muted-symbolic')
        elif self.volume_slider.get_value() < 0.3:
            self.volume_toggle.set_icon_name('audio-volume-low-symbolic')
        elif self.volume_slider.get_value() < 0.7:
            self.volume_toggle.set_icon_name('audio-volume-medium-symbolic')
        else:
            self.volume_toggle.set_icon_name('audio-volume-high-symbolic')

    def _on_loop_mode_changed(self, _, loop):
        loop = self.loop_mode
        if loop == LoopMode.NONE:
            self.loop.set_icon_name('media-playlist-consecutive-symbolic')
        elif loop == LoopMode.ALL:
            self.loop.set_icon_name('media-playlist-repeat-symbolic')
        elif loop == LoopMode.SINGLE:
            self.loop.set_icon_name('media-playlist-repeat-song-symbolic')
