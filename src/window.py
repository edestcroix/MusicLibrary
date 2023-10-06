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

from gi.repository import Adw, Gtk, GLib, Gio
import gi
import threading
from .musicdb import Album, MusicDB
from .musicrow import MusicRow
from .library_list import RecordBoxArtistList, RecordBoxAlbumList
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

    main_page = Gtk.Template.Child()
    main_view = Gtk.Template.Child()

    breakpoint1 = Gtk.Template.Child()
    breakpoint2 = Gtk.Template.Child()
    breakpoint3 = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs['application']

        self.db = MusicDB()

        status = Adw.StatusPage(title='Empty Library')
        status.set_description('Sync library to detect music')
        status.set_icon_name('emblem-synchronizing-symbolic')
        self.album_list.set_placeholder(status)

        self._setup_actions()
        self._bind_settings()
        self.refresh_lists()

    def _bind_settings(self):
        self.app.settings.bind(
            'artist-sort',
            self.artist_list,
            'sort',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.app.settings.bind(
            'album-sort',
            self.album_list,
            'sort',
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.app.settings.bind(
            'clear-queue',
            self.main_view,
            'clear_queue',
            Gio.SettingsBindFlags.DEFAULT,
        )

    def _setup_actions(self):
        self.artist_list.connect('row-activated', self.select_artist)
        self.album_list.connect('row-activated', self.select_album)
        self.album_list.filter_all()

        self.artist_return.connect(
            'clicked',
            lambda _: self.inner_split.set_show_content('album_view'),
        )

        self.album_return.connect(
            'clicked', lambda _: self.outer_split.set_show_sidebar(False)
        )

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

        # Connect breakpoint signals to functions so that the breakpoint signal can be propagated to child widgets.
        self._connect_breakpoint(self.breakpoint1, 1)
        self._connect_breakpoint(self.breakpoint2, 2)
        self._connect_breakpoint(self.breakpoint3, 3)

    def toggle_album_info(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    def sync_library(self, _):
        self.thread = threading.Thread(target=self.update_db)
        self.thread.daemon = True
        self.main_view.send_toast('Syncronizing music database...', 3)
        self.thread.start()

    def update_db(self):
        db = MusicDB()
        db.sync_library()
        self.main_view.send_toast('Done!', 2)
        GLib.MainContext.default().invoke_full(1, self.refresh_lists)

    def refresh_lists(self):
        # Clear the lists
        self.artist_list.remove_all()
        self.album_list.remove_all()

        print('Populating lists')

        for artist in self.db.get_artists():
            self.artist_list.append(artist)
        for album in self.db.get_albums():
            self.album_list.append(album)

    def select_album(self, _, clicked_row):
        album = self.db.get_album(clicked_row.raw_title)

        self.main_page.set_title(album.name)
        tracks = self.db.get_tracks(album)
        album.set_tracks(tracks)
        self.main_view.update_album(album)
        self.outer_split.set_show_sidebar(
            self.outer_split.get_collapsed() == False
        )

    def select_artist(self, _, clicked_row):
        if clicked_row:
            self.album_list.filter_on_key(clicked_row.raw_title)
            self.album_list_page.set_title(clicked_row.raw_title)
            self.inner_split.set_show_content('album_view')

    def _connect_breakpoint(self, breakpoint, num):
        breakpoint.connect('apply', self.main_view.set_breakpoint, num)
        breakpoint.connect('unapply', self.main_view.unset_breakpoint, num)
