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
    """Player control widget, responsible for displaying and controlling player state.
    Binds to a Player instance and updates itself based on the player's state, relays
    control signals to the player, and displays information about the currently playing track"""

    __gtype_name__ = 'RecordBoxPlayerControls'
    playback_toggle = Gtk.Template.Child()

    playing_song = Gtk.Template.Child()
    song_info = Gtk.Template.Child()

    progress = Gtk.Template.Child()
    start_label = Gtk.Template.Child()
    end_label = Gtk.Template.Child()

    volume_toggle = Gtk.Template.Child()
    volume_slider = Gtk.Template.Child()
    muted = GObject.Property(type=bool, default=False)

    def __init__(self):
        super().__init__()
        self.volume_slider.set_range(0, 1)
        self.volume_slider.set_increments(0.1, 0.1)
        self.progress.set_increments(1, 5)

    def attach_to_player(self, player):
        self._player = player
        self._monitor = ProgressMonitor(
            player, self.progress, self.start_label, self.end_label
        )
        self._player.connect(
            'notify::muted', lambda *_: self._update_volume_icon
        )
        self._player.connect('notify::volume', self._update_volume)
        self._player.connect('state-changed', self._update_state)
        self._player.connect('stream-start', self.set_current_track)
        self._player.connect('eos', self.set_current_track)
        self._update_volume_icon()

    def activate(self, playing=True):
        self._monitor.start()
        if playing:
            self.playback_toggle.set_icon_name('media-playback-pause-symbolic')
            self.progress.set_sensitive(True)
        else:
            self.playback_toggle.set_icon_name('media-playback-start-symbolic')

    def deactivate(self):
        self.playback_toggle.set_icon_name('media-playback-start-symbolic')
        self.progress.set_sensitive(False)

    def set_current_track(self, *_):
        if track := self._player.current_track:
            self._set_song_info(track)
        else:
            self.playing_song.set_text('')
            self.playing_artist.set_text('')
            self.end_label.set_text('0:00')

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
        if value < 0:
            return

        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.CUBIC,
            GstAudio.StreamVolumeFormat.LINEAR,
            value,
        )
        self._player.set_property('volume', value)

    def _update_state(self, _, state: str):
        match state:
            case 'playing':
                self.activate(playing=True)
            case 'paused':
                self.activate(playing=False)
            case 'stopped':
                self.deactivate()

    def _set_song_info(self, track):
        artists = (
            f'{track.albumartist}, {track.artists}'
            if track.artists
            else track.albumartist
        )
        self.playing_song.set_markup(
            f'<span size="large" weight="bold">{track.title}</span> - <span size="large">{GLib.markup_escape_text(artists)}</span>'
        )
        info = f'Track <span weight="bold">{track.track:02}</span> on <span weight="bold">{track.album}</span>'
        if track.discsubtitle:
            info += f' ({track.discsubtitle})'
        elif track.discnumber:
            info += f' (Disc {track.discnumber})'
        self.song_info.set_markup(info)
        self.end_label.set_text(track.length)

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
