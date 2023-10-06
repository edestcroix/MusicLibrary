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

    def bind_settings(self, settings: Gio.Settings):
        self.settings = settings

        self.settings.bind(
            'clear-queue',
            self.clear_queue,
            'active',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.settings.bind(
            'background-playback',
            self.background_playback,
            'active',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.settings.bind(
            'expand-discs',
            self.expand_discs,
            'active',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.settings.bind(
            'artist-sort',
            self.artist_sort,
            'selected',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.settings.bind(
            'album-sort',
            self.album_sort,
            'selected',
            Gio.SettingsBindFlags.DEFAULT,
        )
