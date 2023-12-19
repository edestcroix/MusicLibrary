import gi

gi.require_version('Gtk', '4.0')
gi.require_version('GstAudio', '1.0')

from gi.repository import Gtk, GLib, GObject, GstAudio
from .items import TrackItem
from .player import Player


TIME_DIVISOR = 1000000000


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/player_controls.ui'
)
class RecordBoxPlayerControls(Gtk.Box):
    """Player control widget, responsible for displaying and controlling player state.
    Binds to a Player instance and updates itself based on the player's state, relays
    control signals to the player, and displays information about the currently playing track"""

    __gtype_name__ = 'RecordBoxPlayerControls'
    playback_toggle = Gtk.Template.Child()

    progress_bar = Gtk.Template.Child()

    volume_toggle = Gtk.Template.Child()
    volume_slider = Gtk.Template.Child()

    playing_track = GObject.Property(type=str, default='')
    playing_track_info = GObject.Property(type=str, default='')

    progress_text = GObject.Property(type=str, default='-:--')
    duration_text = GObject.Property(type=str, default='-:--')

    active = GObject.Property(type=bool, default=False)

    def attach_to_player(self, player: Player):
        self._player = player
        self._player.connect(
            'notify::muted', lambda *_: self._update_volume_icon
        )
        self._player.connect('notify::volume', self._update_volume)
        self._player.connect('state-changed', self._update_state)
        self._player.connect('stream-start', self.set_current_track)
        self._player.connect('eos', self.set_current_track)

        self._player.bind_property(
            'position',
            self.progress_bar.get_adjustment(),
            'value',
            GObject.BindingFlags.BIDIRECTIONAL,
        )
        self._player.connect('notify::position', self._update_progress)
        self._player.connect('notify::duration', self._update_duration)

    def set_current_track(self, *_):
        if track := self._player.current_track:
            self._set_song_info(track)
        else:
            self.playing_track = ''
            self.playing_track_info = ''

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
        self._update_volume_icon(self._player.toggle_mute())

    @Gtk.Template.Callback()
    def _volume_changed(self, _, __, value: float):
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
                self._set_play_icon(True)
                self.active = True
            case 'paused':
                self._set_play_icon(False)
            case 'stopped':
                self._set_play_icon(False)
                self.active = False
                self.progress_text = '-:--'
                self.duration_text = '-:--'

    def _update_progress(self, *_):
        self.progress_text = self._format_time(self._player.position)

    def _update_duration(self, *_):
        if self._player.duration < 0:
            # if the duration is unknown, try again in 100ms (player was probably still buffering)
            GLib.timeout_add(100, self._update_duration)
            return

        self.duration_text = self._format_time(self._player.duration)
        self.progress_bar.set_range(0, self._player.duration)

    def _set_song_info(self, track: TrackItem):
        artists = (
            f'{track.albumartist}, {track.artists}'
            if track.artists
            else track.albumartist
        )
        self.playing_track = f"""<span weight="bold">{track.title}</span> - {GLib.markup_escape_text(artists)}"""
        album = GLib.markup_escape_text(track.album)
        self.playing_track_info = f'Track <span weight="bold">{track.track:02}</span> on <span weight="bold">{album}</span>'
        if track.discsubtitle:
            self.playing_track_info += f' ({track.discsubtitle})'
        elif track.discnumber:
            self.playing_track_info += f' (Disc {track.discnumber})'

    def _update_volume(self, *_):
        value = GstAudio.StreamVolume.convert_volume(
            GstAudio.StreamVolumeFormat.LINEAR,
            GstAudio.StreamVolumeFormat.CUBIC,
            self._player.volume,
        )
        GLib.idle_add(self.volume_slider.set_value, value)
        GLib.idle_add(self._update_volume_icon)

    def _set_play_icon(self, playing: bool):
        if playing:
            self.playback_toggle.set_icon_name('media-playback-pause-symbolic')
        else:
            self.playback_toggle.set_icon_name('media-playback-start-symbolic')

    def _update_volume_icon(self, muted: bool = False):
        """Updates the volume icon based on the current volume, optionally
        takes a 'muted' argument to manually set the icon to muted, because the
        player's muted property doesn't update when paused"""
        if self._player.muted or muted:
            self.volume_toggle.set_icon_name('audio-volume-muted-symbolic')
            return
        elif self.volume_slider.get_value() < 0.3:
            self.volume_toggle.set_icon_name('audio-volume-low-symbolic')
        elif self.volume_slider.get_value() < 0.7:
            self.volume_toggle.set_icon_name('audio-volume-medium-symbolic')
        else:
            self.volume_toggle.set_icon_name('audio-volume-high-symbolic')

    def _format_time(self, time: int):
        time //= TIME_DIVISOR
        return f'{int(time // 60)}:{int(time % 60):0>2}'
