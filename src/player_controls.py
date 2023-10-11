from gi.repository import Adw, Gtk, GLib, Gst, Gio, GObject
from .monitor import ProgressMonitor

import gi

gi.require_version('Gtk', '4.0')


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_actions()

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_skip_forward(self):
        self.play_pause.set_icon_name('media-playback-pause-symbolic')

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_skip_backward(self):
        self.play_pause.set_icon_name('media-playback-pause-symbolic')

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_toggle(self):
        pass

    @GObject.Signal(return_type=GObject.TYPE_NONE)
    def play_stop(self):
        self.play_pause.set_icon_name('media-playback-start-symbolic')

    def attach_to_player(self, player):
        self._monitor = ProgressMonitor(
            player, self.progress, self.start_label, self.end_label
        )
        self.progress.connect('change-value', self._monitor.seek_event)

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
        self._playing = False
        self.progress.set_value(0)

    def set_current_track(self, current_track):
        if current_track:
            self.playing_song.set_markup(
                f'<span size="large">{GLib.markup_escape_text(current_track.title)}</span>'
            )
            artists = map(GLib.markup_escape_text, current_track.artists)
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
