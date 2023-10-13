import gi

gi.require_version('Gtk', '4.0')
gi.require_version('GstAudio', '1.0')

from gi.repository import Adw, Gtk, GLib, Gio, GObject, GstAudio
from .monitor import ProgressMonitor


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/player_controls.ui'
)
class RecordBoxPlayerControls(Gtk.Box):
    __gtype_name__ = 'RecordBoxPlayerControls'
    play_pause = Gtk.Template.Child()
    skip_forward = Gtk.Template.Child()
    skip_backward = Gtk.Template.Child()

    stop = Gtk.Template.Child()
    loop = Gtk.Template.Child()

    playing_song = Gtk.Template.Child()
    playing_artist = Gtk.Template.Child()

    progress = Gtk.Template.Child()
    start_label = Gtk.Template.Child()
    end_label = Gtk.Template.Child()

    volume_toggle = Gtk.Template.Child()
    volume_slider = Gtk.Template.Child()

    _muted = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume_slider.set_range(0, 1)
        self._setup_actions()

    play_toggle = GObject.Signal(return_type=GObject.TYPE_NONE)

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_skip_forward(self):
        self.play_pause.set_icon_name('media-playback-pause-symbolic')

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_skip_backward(self):
        self.play_pause.set_icon_name('media-playback-pause-symbolic')

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_stop(self):
        self.play_pause.set_icon_name('media-playback-start-symbolic')

    muted = GObject.Property(type=bool, default=False)

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

    def attach_to_player(self, player):
        self._monitor = ProgressMonitor(
            player, self.progress, self.start_label, self.end_label
        )
        self.progress.connect('change-value', self._monitor.seek_event)
        player.bind_property(
            'volume', self, 'volume', GObject.BindingFlags.BIDIRECTIONAL
        )
        player.bind_property(
            'muted', self, 'muted', GObject.BindingFlags.BIDIRECTIONAL
        )

    def activate(self, playing=True):
        self._monitor.start_thread()
        self.progress.set_sensitive(True)
        if playing:
            self.play_pause.set_icon_name('media-playback-pause-symbolic')
        else:
            self.play_pause.set_icon_name('media-playback-start-symbolic')

    def deactivate(self):
        self._monitor.stop_thread()
        self.play_pause.set_icon_name('media-playback-start-symbolic')
        self.progress.set_sensitive(False)
        self.progress.set_value(0)

    def set_current_track(self, current_track):
        if current_track:
            self.playing_song.set_markup(
                f'<span size="large">{GLib.markup_escape_text(current_track.title)}</span>'
            )
            artists = map(
                GLib.markup_escape_text,
                [current_track.albumartist] + current_track.artists,
            )
            self.playing_artist.set_markup(
                f'<span size="small">{", ".join(artists)}</span>'
            )
            self.end_label.set_text(current_track.length_str())
        else:
            self.playing_song.set_text('')
            self.playing_artist.set_text('')
            self.end_label.set_text('0:00')

    def _setup_actions(self):
        self.play_pause.connect('clicked', lambda *_: self.emit('play_toggle'))
        self.stop.connect('clicked', lambda *_: self.emit('play_stop'))
        self.skip_forward.connect(
            'clicked', lambda *_: self.emit('play_skip_forward')
        )
        self.skip_backward.connect(
            'clicked', lambda *_: self.emit('play_skip_backward')
        )
        self.volume_toggle.connect('clicked', self._toggle_mute)
        self.volume_slider.connect('change-value', self._volume_changed)

    def _toggle_mute(self, _):
        self.set_property('muted', not self.muted)
        self._update_volume_icon()

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
