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

from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi
import threading
from .album_view import MusicLibraryAlbumView
from .musicdb import Album, MusicDB
from .musicrow import MusicRow
from .library_list import MusicLibraryList
from .play_queue import PlayQueue
from .player import Player

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/window.ui')
class MusicLibraryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MusicLibraryWindow'

    # The two Adw.NavigationSplitViews, first one
    # contains inner_view and the track view page

    breakpoint1 = Gtk.Template.Child()
    breakpoint2 = Gtk.Template.Child()
    breakpoint3 = Gtk.Template.Child()

    outer_split = Gtk.Template.Child()

    lists_toggle = Gtk.Template.Child()
    artist_return = Gtk.Template.Child()
    album_return = Gtk.Template.Child()
    # inner_view contains the artist and album lists.
    inner_split = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()

    artist_list = Gtk.Template.Child()
    album_list = Gtk.Template.Child()
    album_list_page = Gtk.Template.Child()

    album_overview_page = Gtk.Template.Child()
    album_overview = Gtk.Template.Child()

    queue_toggle = Gtk.Template.Child()
    queue_panel_split_view = Gtk.Template.Child()
    queue_add = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    play = Gtk.Template.Child()
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # update_music_library()
        self.db = MusicDB()

        self.__setup_actions()
        # TODO: On start, finish init without refresing lists
        # so the window will display, have main.py start refresing
        # after the window displays, make refresh_lists() add a
        # loading screen while running.
        self.refresh_lists()

        self.player = Player(self.play_queue)

    def __setup_actions(self):
        self.artist_list.connect('row-activated', self.select_artist)
        self.album_list.connect('row-activated', self.select_album)
        self.album_list.filter_all()
        self.artist_list.filter_all()

        self.queue_toggle.connect('clicked', self.toggle_album_info)

        self.artist_return.connect(
            'clicked',
            lambda _: self.inner_split.set_show_content('album_view'),
        )

        self.album_return.connect(
            'clicked', lambda _: self.outer_split.set_show_sidebar(False)
        )

        self.lists_toggle.connect(
            'clicked',
            lambda _: self.outer_split.set_show_sidebar(
                not self.outer_split.get_show_sidebar()
            ),
        )

        self.queue_add.connect('clicked', self.enqueue_album)

        self.play.connect('clicked', self.play_album)

        self.__connect_breakpoint(self.breakpoint1)
        self.__connect_breakpoint(self.breakpoint2)
        self.__connect_breakpoint(self.breakpoint3)

    def __connect_breakpoint(self, breakpoint):
        breakpoint.connect('apply', self.album_overview.apply_breakpoint)
        breakpoint.connect('unapply', self.album_overview.unset_breakpoint)

    def play_album(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.clear()
            self.play_queue.add_album(album)
            self.player.play()

    def enqueue_album(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)

    def toggle_album_info(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    def sync_library(self, _):
        self.thread = threading.Thread(target=self.update_db)
        self.thread.daemon = True
        self.create_toast('Syncronizing music database...', 3)
        self.thread.start()

    def update_db(self):
        db = MusicDB()
        db.parse_library()
        self.create_toast('Done!', 2)
        GLib.MainContext.default().invoke_full(1, self.refresh_lists)

    def create_toast(self, title, timeout):
        toast = Adw.Toast()
        toast.set_title(title)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def refresh_lists(self):
        # Clear the lists
        self.artist_list.remove_all()
        self.album_list.remove_all()

        print('Populating lists')

        for artist in self.db.get_artists():
            self.artist_list.append(*artist.to_row())
        for album in self.db.get_albums():
            self.album_list.append(*album.to_row())
            self.album_list.sort()

    def select_album(self, _, clicked_row):
        album = self.db.get_album(clicked_row.raw_title)

        self.album_overview_page.set_title(album.name)
        tracks = self.db.get_tracks(album.name)
        album.set_tracks(tracks)
        self.album_overview.update_album(album)
        self.outer_split.set_show_sidebar(
            self.outer_split.get_collapsed() == False
        )

    def select_artist(self, _, clicked_row):
        if clicked_row:
            self.album_list.filter_on_key(clicked_row.raw_title)
            self.album_list_page.set_title(clicked_row.raw_title)
            self.inner_split.set_show_content('album_view')

    def seconds_to_time(self, seconds):
        return f'{int(seconds // 3600):02}:{int(seconds // 60 % 60):02}:{int(seconds % 60):02}'
