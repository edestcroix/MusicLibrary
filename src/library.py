from gi.repository import Adw, Gtk, GLib, Gio, GObject
import gi
import threading

from .parser import MusicParser
from .musicdb import MusicDB
from .items import AlbumItem, ArtistItem
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

    collapsed = GObject.Property(type=bool, default=False)
    parent_collapsed = GObject.Property(type=bool, default=False)

    show_all_artists = GObject.Property(type=bool, default=False)

    filter_all_albums = GObject.Property(type=bool, default=False)

    artist_sort = GObject.Property(type=str, default='name-descending')
    album_sort = GObject.Property(type=str, default='name-descending')

    close = GObject.Signal()
    album_selected = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    album_activated = GObject.Signal()

    def __init__(self):
        super().__init__()

        self.parser = MusicParser()

        self.parser.bind_property(
            'progress',
            self.progress_bar,
            'fraction',
            GObject.BindingFlags.DEFAULT,
        )
        self.connect(
            'notify::show-all-artists', lambda *_: self.refresh_lists()
        )

    def sync_library(self, _):
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

    def refresh_lists(self):
        db = MusicDB()
        self.artist_list.populate(db.get_artists(self.show_all_artists))
        self.album_list.populate(db.get_albums())
        db.close()

    def filter_all(self, *_):
        self.album_list.filter_all()
        self.artist_list.unselect_all()
        self.album_list_page.set_title('Albums')
        self.set_property('filter-all-albums', True)

    def find_album(self, album_name):
        return self.album_list.find_album(album_name)

    def select_album(self, album: AlbumItem):
        self.album_list.filter_on_artist(album.artists[0])
        self.album_list_page.set_title(album.artists[0])

        self.album_return.set_sensitive(True)

        self.inner_split.set_show_content('album_view')

        self.album_list.unselect_all()
        self.artist_list.unselect_all()

        self._select_row_with_title(self.artist_list, album.artists[0])
        self._select_row_with_title(self.album_list, album.raw_name)

    @Gtk.Template.Callback()
    def _album_selected(self, _, album: AlbumItem):
        self.emit('album-selected', album)
        self.set_property('filter-all-albums', False)

    @Gtk.Template.Callback()
    def select_artist(self, _, selected: ArtistItem):
        self.album_list.filter_on_artist(selected.raw_name)
        self.album_list_page.set_title(selected.raw_name)
        self.inner_split.set_show_content('album_view')

    @Gtk.Template.Callback()
    def _on_artist_return(self, _):
        self.inner_split.set_show_content('album_view')

    @Gtk.Template.Callback()
    def _on_album_return(self, _):
        self.emit('close')

    @Gtk.Template.Callback()
    def _on_album_activated(self, *_):
        self.emit('album-activated')

    def _select_row_with_title(
        self, row_list: AlbumList | ArtistList, title: str
    ):
        i = 0
        cur = row_list.get_row_at_index(i)
        while cur and cur.raw_name != title:
            i += 1
            cur = row_list.get_row_at_index(i)
        if cur:
            row_list.scroll_to(i, Gtk.ListScrollFlags.SELECT)
