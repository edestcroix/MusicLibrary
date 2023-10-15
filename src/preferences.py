from gi.repository import Adw, Gtk, GLib, Gio
import gi

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/preferences.ui')
class RecordBoxPreferencesWindow(Adw.PreferencesWindow):
    __gtype_name__ = 'RecordBoxPreferencesWindow'

    clear_queue = Gtk.Template.Child()
    background_playback = Gtk.Template.Child()
    expand_discs = Gtk.Template.Child()
    artist_sort = Gtk.Template.Child()
    album_sort = Gtk.Template.Child()
    confirm_play = Gtk.Template.Child()
    show_all_artists = Gtk.Template.Child()
    restore_window_state = Gtk.Template.Child()

    def bind_settings(self, settings: Gio.Settings):
        self.settings = settings

        self._bind('clear-queue', self.clear_queue, 'active')

        self._bind('background-playback', self.background_playback, 'active')

        self._bind('expand-discs', self.expand_discs, 'active')

        self._bind('artist-sort', self.artist_sort, 'selected')

        self._bind('album-sort', self.album_sort, 'selected')

        self._bind('confirm-play', self.confirm_play, 'active')

        self._bind('show-all-artists', self.show_all_artists, 'active')

        self._bind('restore-window-state', self.restore_window_state, 'active')

    def _bind(self, key, obj, prop):
        self.settings.bind(key, obj, prop, Gio.SettingsBindFlags.DEFAULT)
