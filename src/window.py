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
from .musicdb import Album, MusicDB
from .musicrow import MusicRow
from .library_list import MusicLibraryList

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/window.ui')
class MusicLibraryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MusicLibraryWindow'

    # The two Adw.NavigationSplitViews, first one
    # contains inner_view and the track view page

    # TODO: These id's need to be more descriptive to tell them apart easier.
    outer_view = Gtk.Template.Child()
    # inner_view contains the artist and album lists.
    inner_view = Gtk.Template.Child()

    artist_box = Gtk.Template.Child()
    album_box = Gtk.Template.Child()

    album_view = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()

    album_page = Gtk.Template.Child()
    view_page = Gtk.Template.Child()

    album_info_toggle = Gtk.Template.Child()
    split_view = Gtk.Template.Child()

    # info_list = Gtk.Template.Child()

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

    def __setup_actions(self):
        self.artist_box.connect('row-activated', self.select_artist)
        self.album_box.connect('row-activated', self.select_album)
        self.album_box.filter_all()
        self.artist_box.filter_all()

        self.album_info_toggle.connect('clicked', self.toggle_album_info)

    def toggle_album_info(self, _):
        self.split_view.set_show_sidebar(
            not self.split_view.get_show_sidebar()
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
        self.artist_box.remove_all()
        self.album_box.remove_all()

        print('Populating lists')

        for artist in self.db.get_artists():
            self.artist_box.append(*self.format_artist(artist))
        for album in self.db.get_albums():
            self.album_box.append(*album.to_row())

    def select_album(self, _, clicked_row):
        self.outer_view.set_show_content('track_view')
        album = self.db.get_album(clicked_row.raw_title)
        self.album_view.update_cover(album.cover)
        self.album_view.clear_all()
        self.view_page.set_title(album.name)

        tracks = self.db.get_tracks(album.name)
        self.album_view.update_tracks(tracks)

    def select_artist(self, _, clicked_row):
        if clicked_row:
            self.album_box.filter_on_key(clicked_row.raw_title)
            self.album_page.set_title(clicked_row.raw_title)
        self.inner_view.set_show_content('album_view')

    def seconds_to_time(self, seconds):
        return f'{int(seconds // 3600):02}:{int(seconds // 60 % 60):02}:{int(seconds % 60):02}'

    def format_artist(self, artist):
        return (
            artist[0],
            f'{artist[1]} albums, {artist[2]} tracks, {self.seconds_to_time(artist[3])}',
        )
