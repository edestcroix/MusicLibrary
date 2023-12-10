from gi.repository import Adw, Gtk, GLib, GObject, Gio
from enum import Enum
from .items import AlbumItem, ArtistItem, TrackItem


class ArtistSort(Enum):
    NAME_ASC = 'name-ascending'
    NAME_DESC = 'name-descending'


class AlbumSort(Enum):
    NAME_ASC = 'name-ascending'
    NAME_DESC = 'name-descending'
    DATE_ASC = 'date-ascending'
    DATE_DESC = 'date-descending'


class LibraryList(Gtk.ListView):
    """Base class for artist and album lists, since they're almost identical other than
    the album list needing a filter model."""

    __gtype_name__ = 'RecordBoxLibraryList'

    sort = GObject.Property(type=str)

    # Emits whenever the selection model's selection changes, if a row is selected.
    selection_changed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    # Navigating lists with the arrow keys changes the selection, so other widgets
    # can't use the selection_changed signal to know when to hide sidebar widgets, for example.
    # Instead, this signal is used, which only emits when a row is clicked on or activated.
    selection_confirmed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    model: Gio.ListStore
    template: str

    def __init__(self, click_activates: bool = True):
        super().__init__()

        self._setup_model()
        self.set_tab_behavior(Gtk.ListTabBehavior.ITEM)
        self.set_factory(
            Gtk.BuilderListItemFactory.new_from_resource(
                Gtk.BuilderCScope(), self.template
            )
        )
        self.connect('notify::sort', lambda *_: self._update_sort())

        self.connect(
            'activate', lambda *_: self.selection_confirmed.emit(True)
        )

        click = Gtk.GestureClick.new()
        click.connect(
            'released',
            lambda *_: self.selection_confirmed.emit(click_activates),
        )
        self.add_controller(click)

    def append(self, item: GObject.Object):
        self.model.append(item)

    def populate(self, items: list[GObject.Object]):
        self.model.remove_all()
        self.model.splice(0, 0, items)
        self._update_sort()
        self.scroll_to(0, Gtk.ListScrollFlags.FOCUS)

    def unselect_all(self):
        # for some reason unselect_all() doesn't work on a SingleSelection
        self.selection_model.unselect_item(self.selection_model.get_selected())

    def remove_all(self):
        self.model.remove_all()

    def get_row_at_index(self, index: int) -> GObject.Object:
        return self.model[index]

    def select_index(self, index: int):
        self.selection_model.select_item(index, True)

    def _setup_model(self):
        self.selection_model = Gtk.SingleSelection.new(self.model)
        self.selection_model.set_can_unselect(True)
        self.selection_model.set_autoselect(False)
        self.selection_model.connect('selection_changed', self._item_selected)
        self.set_model(self.selection_model)

    def _item_selected(self, *_):
        if selected := self.selection_model.get_selected_item():
            self.selection_changed.emit(selected)

    def _update_sort(self):
        pass


class ArtistList(LibraryList):
    __gtype_name__ = 'RecordBoxArtistList'

    model = Gio.ListStore.new(ArtistItem)
    template = '/com/github/edestcroix/RecordBox/lists/artist_row.ui'

    def _update_sort(self):
        match ArtistSort(self.sort):
            case ArtistSort.NAME_ASC:
                self.model.sort(lambda a, b: a.sort < b.sort)
            case ArtistSort.NAME_DESC:
                self.model.sort(lambda a, b: a.sort > b.sort)


class AlbumList(LibraryList):
    __gtype_name__ = 'RecordBoxAlbumList'

    model = Gio.ListStore.new(AlbumItem)
    template = '/com/github/edestcroix/RecordBox/lists/album_row.ui'

    def __init__(self):

        # In the case of the AlbumList the click shouldn't count as an acvtivation,
        # because playback will start when activation is true.
        super().__init__(click_activates=False)

    def get_row_at_index(self, index: int):
        return self.filter_model[index]

    def filter_all(self):
        self.filter_model.set_filter(None)

    def filter_on_artist(self, artist: str):
        self.filter_model.set_filter(
            Gtk.CustomFilter.new(lambda r: artist in r.artists)
        )
        self._item_selected()

    def find_album_by_track(self, track: TrackItem) -> AlbumItem | None:
        return next((row for row in self.model if track in row.tracks), None)

    def _setup_model(self):
        self.filter_model = Gtk.FilterListModel.new(self.model, None)
        self.selection_model = Gtk.SingleSelection.new(self.filter_model)
        self.selection_model.set_can_unselect(True)
        self.selection_model.set_autoselect(False)
        self.selection_model.connect(
            'selection_changed', lambda *_: self._item_selected()
        )
        self.set_model(self.selection_model)

    def _update_sort(self):
        match AlbumSort(self.sort):
            case AlbumSort.NAME_ASC:
                self.model.sort(lambda a, b: a.name < b.name)
            case AlbumSort.NAME_DESC:
                self.model.sort(lambda a, b: a.name > b.name)
            case AlbumSort.DATE_ASC:
                self.model.sort(lambda a, b: a.date > b.date)
            case AlbumSort.DATE_DESC:
                self.model.sort(lambda a, b: a.date < b.date)
