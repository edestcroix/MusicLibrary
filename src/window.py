# window.py
#
# Copyright 2023 Emmett de St. Croix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib, Gio, GObject
import gi
import threading
from .library import RecordBoxArtistList, RecordBoxAlbumList
from .musicdb import MusicDB
from .parser import MusicParser
from .play_queue import PlayQueue
from .player import Player
from .main_view import MainView

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/window.ui')
class RecordBoxWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'RecordBoxWindow'

    # outer_split is the AdwOverlaySplitView with the artist/album lists as it's sidebar
    outer_split = Gtk.Template.Child()
    # inner_split is the AdwNavigationSplitView that contains the artist and album lists
    inner_split = Gtk.Template.Child()

    artist_return = Gtk.Template.Child()
    album_return = Gtk.Template.Child()

    artist_list = Gtk.Template.Child()
    album_list = Gtk.Template.Child()
    album_list_page = Gtk.Template.Child()

    progress_bar1 = Gtk.Template.Child()
    progress_bar2 = Gtk.Template.Child()

    main_page = Gtk.Template.Child()
    main_view = Gtk.Template.Child()

    breakpoint1 = Gtk.Template.Child()
    breakpoint2 = Gtk.Template.Child()
    breakpoint3 = Gtk.Template.Child()

    filter_all = Gtk.Template.Child()

    _show_all_artists = False

    @GObject.Property(type=bool, default=False)
    def show_all_artists(self):
        return self._show_all_artists

    @show_all_artists.setter
    def set_show_all_artists(self, value):
        self._show_all_artists = value
        self.refresh_lists()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs.get('application', None)

        self.db = MusicDB()
        self.parser = MusicParser()

        self.selected_artist = None

        if self.app.settings.get_boolean('restore-window-state'):
            self._bind_state()
        self._bind_settings()
        self._setup_actions()

        if self.app.settings.get_boolean('sync-on-startup'):
            self.sync_library(None)

    def _bind_state(self):
        self._bind('width', self, 'default-width')
        self._bind('height', self, 'default-height')
        self._bind('is-maximized', self, 'maximized')
        self._bind('is-fullscreen', self, 'fullscreened')

    def _bind_settings(self):
        self._bind('artist-sort', self.artist_list, 'sort')
        self._bind('album-sort', self.album_list, 'sort')
        self._bind('clear-queue', self.main_view, 'clear_queue')
        self._bind(
            'expand-discs', self.main_view.album_overview, 'expand_discs'
        )

        self._bind('confirm-play', self.main_view, 'confirm_play')

        # binding this refreshes the lists on initial startup, so it doesn't have to be done on init.
        self._bind('show-all-artists', self, 'show_all_artists')

    def _bind(self, key, obj, property):
        self.app.settings.bind(
            key, obj, property, Gio.SettingsBindFlags.DEFAULT
        )

    def _setup_actions(self):
        self.main_view.lists_toggle.connect(
            'clicked',
            lambda _: self.outer_split.set_show_sidebar(
                not self.outer_split.get_show_sidebar()
            ),
        )

        self.main_view.player.connect(
            'state-changed',
            lambda _, state: self.set_hide_on_close(
                self.app.settings.get_boolean('background-playback')
                and state in ['playing', 'paused']
            ),
        )

        self.parser.bind_property(
            'progress',
            self.progress_bar1,
            'fraction',
            GObject.BindingFlags.DEFAULT,
        )
        self.parser.bind_property(
            'progress',
            self.progress_bar2,
            'fraction',
            GObject.BindingFlags.DEFAULT,
        )

        # Connect breakpoint signals to functions so that the breakpoint signal can be propagated to child widgets.
        self._connect_breakpoint(self.breakpoint1, 1)
        self._connect_breakpoint(self.breakpoint2, 2)
        self._connect_breakpoint(self.breakpoint3, 3)

    def sync_library(self, _):
        self.thread = threading.Thread(target=self.update_db)
        self.thread.daemon = True
        self.progress_bar1.set_visible(True)
        self.progress_bar2.set_visible(True)
        self.thread.start()

    def update_db(self):
        db = MusicDB()
        self.parser.build(db)
        GLib.idle_add(self.refresh_lists)
        GLib.idle_add(self.progress_bar1.set_visible, False)
        GLib.idle_add(self.progress_bar2.set_visible, False)

    def refresh_lists(self):
        self.artist_list.remove_all()
        self.album_list.remove_all()

        print('Populating lists')

        for artist in self.db.get_artists(self._show_all_artists):
            self.artist_list.append(artist)
        for album in self.db.get_albums():
            self.album_list.append(album)

    @Gtk.Template.Callback()
    def select_album(self, _, clicked_row):
        album = self.db.get_album(clicked_row.raw_title)

        self.main_page.set_title(album.name)
        tracks = self.db.get_tracks(album)
        album.set_tracks(tracks)
        self.main_view.update_album(album, self.selected_artist)
        self.outer_split.set_show_sidebar(
            self.outer_split.get_collapsed() == False
        )

    @Gtk.Template.Callback()
    def select_artist(self, _, clicked_row):
        self.selected_artist = clicked_row.raw_title
        if clicked_row:
            self.album_list.filter_on_key(clicked_row.raw_title)
            self.album_list_page.set_title(clicked_row.raw_title)
            self.inner_split.set_show_content('album_view')
            self.filter_all.set_sensitive(True)

    @Gtk.Template.Callback()
    def _on_artist_return(self, _):
        self.inner_split.set_show_content('album_view')

    @Gtk.Template.Callback()
    def _on_album_return(self, _):
        self.outer_split.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def _on_filter_all(self, _):
        self.album_list.filter_all()
        self.filter_all.set_sensitive(False)
        self.album_list_page.set_title('Artists')
        self.artist_list.unselect_all()

    @Gtk.Template.Callback()
    def _on_album_changed(self, _, album):
        self.album_list.filter_on_key(album.artists[0])
        self.album_list_page.set_title(album.artists[0])
        self.main_page.set_title(album.name)
        self.inner_split.set_show_content('album_view')
        self.album_return.set_sensitive(True)

        self.selected_artist = album.artists[0]

        self.album_list.unselect_all()
        self.artist_list.unselect_all()

        self._select_row_with_title(self.album_list, album.name)
        self._select_row_with_title(self.artist_list, album.artists[0])

    def _select_row_with_title(self, row_list, title):
        i = 0
        cur = row_list.get_row_at_index(i)
        while cur and cur.raw_title != title:
            i += 1
            cur = row_list.get_row_at_index(i)
        if cur:
            self.artist_list.select_row(cur)

    def _connect_breakpoint(self, breakpoint, num):
        breakpoint.connect('apply', self.main_view.set_breakpoint, num)
        breakpoint.connect('unapply', self.main_view.unset_breakpoint, num)
