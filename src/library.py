from gi.repository import Adw, Gtk, GLib, Gio, GObject
import gi
import threading

from .parser import MusicParser
from .musicdb import MusicDB
from .items import AlbumItem, ArtistItem, TrackItem
from .library_lists import AlbumList, ArtistList

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/library.ui')
class MusicLibrary(Adw.Bin):
    __gtype_name__ = 'RecordBoxMusicLibrary'

    inner_split = Gtk.Template.Child()

    artist_return = Gtk.Template.Child()
    album_return = Gtk.Template.Child()

    artist_list = Gtk.Template.Child()
    album_list = Gtk.Template.Child()
    album_list_page = Gtk.Template.Child()

    progress_bar = Gtk.Template.Child()

    stack = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    directory_select = Gtk.Template.Child()
    start_button = Gtk.Template.Child()

    collapsed = GObject.Property(type=bool, default=False)
    parent_collapsed = GObject.Property(type=bool, default=False)

    show_all_artists = GObject.Property(type=bool, default=False)

    filter_all_albums = GObject.Property(type=bool, default=False)

    music_directory = GObject.Property(type=str, default='')

    artist_sort = GObject.Property(type=str, default='name-descending')
    album_sort = GObject.Property(type=str, default='name-descending')

    close = GObject.Signal()

    # Emits when the AlbumList's selection changes.
    album_changed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    # Emits when the library sidebar is not collapsed and when the AlbumList emits it's
    # selection_confirmed signal with the 'activated' parameter set to True.
    album_activated = GObject.Signal()

    # Emits when the library sidebar is collapsed and when the AlbumList emits it's
    # selection_confirmed signal, regardless of the 'activated' parameter.
    album_confirmed = GObject.Signal()

    def __init__(self):
        super().__init__()

        self.parser = MusicParser()

        self.bind_property(
            'music-directory',
            self.parser,
            'path',
            GObject.BindingFlags.DEFAULT,
        )

        self.parser.bind_property(
            'progress',
            self.progress_bar,
            'fraction',
            GObject.BindingFlags.DEFAULT,
        )
        self.connect(
            'notify::show-all-artists', lambda *_: self.refresh_lists()
        )
        self.artist_list.connect(
            'activate', lambda *_: self.album_list.grab_focus()
        )

    def present(self):
        if self.parser.path in ['', '-']:
            self.stack.set_visible_child_name('setup')
        else:
            self.stack.set_visible_child_name('library')

    @Gtk.Template.Callback()
    def sync_library(self, _, show_spinner: bool = True):
        if self.parser.path in ['', '-']:
            self.stack.set_visible_child_name('setup')
            return

        if show_spinner:
            self.stack.set_visible_child_name('sync')
            self.spinner.start()
        self.thread = threading.Thread(target=self.update_db)
        self.thread.daemon = True
        self.progress_bar.set_visible(True)
        self.thread.start()

    def update_db(self):
        db = MusicDB()
        self.parser.build(db)
        db.close()
        GLib.idle_add(self.refresh_lists)
        GLib.idle_add(self.progress_bar.set_visible, False)
        GLib.idle_add(self.spinner.stop)

    def refresh_lists(self):
        db = MusicDB()
        self.stack.set_visible_child_name('library')
        self.artist_list.populate(db.get_artists(self.show_all_artists))
        self.album_list.populate(db.get_albums())
        db.close()

    def filter_all(self, *_):
        self.album_list.filter_all()
        self.artist_list.unselect_all()
        self.album_list_page.set_title('Albums')
        self.set_property('filter-all-albums', True)

    def find_album_by_track(self, track: TrackItem):
        return self.album_list.find_album_by_track(track)

    def find_album(self, albumartist: str, title: str):
        return self.album_list.find_album(albumartist, title)

    def select_album(self, artist: str, album: AlbumItem):
        self.album_list.filter_on_artist(artist)
        self.album_list_page.set_title(artist)

        self.album_return.set_sensitive(True)

        self.inner_split.set_show_content('album_view')

        self.album_list.unselect_all()
        self.artist_list.unselect_all()

        self._select_row_with_title(self.artist_list, artist)
        self._select_row_with_title(self.album_list, album.title)

    @Gtk.Template.Callback()
    def _artist_selection_changed(self, _, selected: ArtistItem):
        self.album_list.filter_on_artist(selected.raw_name)
        self.album_list_page.set_title(f'Albums - {selected.raw_name}')
        self.filter_all_albums = False

    @Gtk.Template.Callback()
    def _artist_confirmed(self, *_):
        self.inner_split.set_show_content('album_view')

    @Gtk.Template.Callback()
    def _album_selection_changed(self, _, selected: AlbumItem):
        self.emit('album-changed', selected)
        self.set_property('filter-all-albums', False)

    @Gtk.Template.Callback()
    def _album_confirmed(self, _, activated: bool = False):
        """Callback for the AlbumList's selection_confirmed signal, emits a different
        signal depending on whether the library sidebar is collapsed or not.
        """
        if self.parent_collapsed:
            # When the sidebar is collapsed, the album_confirmed signal is emitted to indicate that
            # the user explicitly selected an album with a click rather than selecting it through keynav, so the library
            # is closed and the album view is opened.
            self.emit('album-confirmed')
        elif activated:
            # When the sidebar is not collapsed, the album_activated signal is emitted when the activated parameter is True.
            # This is so that playback can be started when the user presses enter or double clicks on an album while still allowing
            # clicks to change the selection without starting playback.
            self.emit('album-activated')

    @Gtk.Template.Callback()
    def _on_artist_return(self, _):
        self.inner_split.set_show_content('album_view')

    @Gtk.Template.Callback()
    def _on_album_return(self, _):
        self.emit('close')

    def _select_row_with_title(
        self, row_list: AlbumList | ArtistList, title: str
    ):
        if type(row_list) is AlbumList:
            row_list.scroll_to_row_with_title(title)
        else:
            row_list.scroll_to_row_with_name(title)

    @Gtk.Template.Callback()
    def _on_directory_select(self, _):

        file_chooser = Gtk.FileDialog()
        file_chooser.set_initial_folder(
            Gio.File.new_for_path(GLib.get_home_dir())
        )
        file_chooser.select_folder(callback=self._on_folder_selected)

    def _on_folder_selected(self, dialog, response):
        folder: Gio.LocalFile = dialog.select_folder_finish(response)

        self.music_directory = folder.get_path()
        self.directory_select.get_child().set_label(self.music_directory)
        self.start_button.set_sensitive(True)
