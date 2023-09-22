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

gi.require_version('Gtk', '4.0')


# TODO: Chunck this up into other files/classes as needed
#       - Track display page

# NOTE: I Bet after getting a nice UI i'm going to end up getting stuck on gstreamer and get mad probably.

from .musicdb import MusicDB


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/window.ui')
class MusicLibraryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MusicLibraryWindow'

    # The two Adw.NavigationSplitViews, first one
    # contains inner_view and the track view page
    outer_view = Gtk.Template.Child()
    # inner_view contains the artist and album lists.
    inner_view = Gtk.Template.Child()

    artist_box = Gtk.Template.Child()
    album_box = Gtk.Template.Child()

    # cover_image = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # update_music_library()
        self.db = MusicDB()

        self.__setup_actions()
        self.populate_lists()

    def __setup_actions(self):
        self.artist_box.connect('row-activated', self.select_artist)
        self.album_box.connect('row-activated', self.select_album)

    def sync_library(self, _):
        self.thread = threading.Thread(target=self.update_db)
        self.thread.daemon = True
        self.create_toast('Syncronizing music database...', 3)
        self.thread.start()

    def update_db(self):
        db = MusicDB()
        db.parse_library()
        self.create_toast('Done!', 2)
        GLib.MainContext.default().invoke_full(1, self.populate_lists)

    # TODO Rename this here and in `sync_library` and `update_db`
    def create_toast(self, title, timeout):
        toast = Adw.Toast()
        toast.set_title(title)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def populate_lists(self):
        # Clear the lists
        self.artist_box.remove_all()
        self.album_box.remove_all()

        print('Populating lists')

        for artist in self.db.get_artists():
            self.artist_box.append(self.create_row(artist))
        for album in self.db.get_albums():
            self.album_box.append(
                self.create_row(album[0], *self.format_album(album))
            )

    def select_album(self, _, clicked_row):
        # TODO: Create a template for the track view with methods
        # to update it's display based on the album selected.
        self.outer_view.set_show_content('track_view')
        album = self.db.get_album(clicked_row.get_name())
        print(album)
        # self.cover_image.set_from_file(album[4])

    def select_artist(self, _, clicked_row):
        if clicked_row:
            self.album_box.remove_all()
            albums = self.db.get_albums(clicked_row.get_name())
            for album in albums:
                self.album_box.append(
                    self.create_row(album[0], *self.format_album(album))
                )

        self.inner_view.set_show_content('album_view')

    def format_album(self, album):
        seconds = album[2]
        # convert to HH:MM:SS
        length = f'{int(seconds // 3600):02}:{int(seconds // 60 % 60):02}:{int(seconds % 60):02}'
        return (f'{length} - {album[1]} tracks', album[4])

    def create_row(self, title, subtitle='', image_path=''):
        # print(image_path)
        row = Adw.ActionRow(activatable=True, name=title, subtitle=subtitle)
        # TODO: Images need to be loaded in a separate thread or something,
        # and there should be some form of caching.
        # if image_path:
        #     image = Gtk.Image()
        #     image.set_pixel_size(64)
        #     image.set_from_file(image_path)
        #     row.add_prefix(image)

        row.set_title(GLib.markup_escape_text(title))

        return row
