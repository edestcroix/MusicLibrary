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
#       - Page navigation when sidebars are collapsed.
#       - Track display page

# NOTE: I Bet after getting a nice UI i'm going to end up getting stuck on gstreamer and get mad probably.

from musiclibrary.musicdb import MusicDB


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/window.ui')
class MusiclibraryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MusicLibraryWindow'

    # The two Adw.NavigationSplitViews, first one
    # contains inner_view and the track view page
    outer_view = Gtk.Template.Child()
    # inner_view contains the artist and album lists.
    inner_view = Gtk.Template.Child()

    artist_box = Gtk.Template.Child()
    album_box = Gtk.Template.Child()
    sync_button = Gtk.Template.Child()

    c = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # update_music_library()
        self.db = MusicDB()

        self.sync_button.connect('clicked', self.sync_library)

        self.populate_lists()

        self.artist_box.connect('row-activated', self.select_artist)
        self.album_box.connect('row-activated', self.select_album)

    # FIXME: This still freezes the UI, it's not fully detatched.
    # Also, the lists need to be repopulated after the thread finishes.
    def sync_library(self, _):
        self.thread = threading.Thread(target=self.update_music_library)
        self.thread.daemon = True
        self.thread.start()

    def update_music_library(self):
        db = MusicDB()
        db.parse_library()

    def populate_lists(self):
        # Clear the lists
        self.artist_box.remove_all()
        self.album_box.remove_all()


        for artist in self.db.get_artists():
            self.artist_box.append(self.create_label(artist))
        for album in self.db.get_albums():
            self.album_box.append(self.create_label(album))

    def select_album(self, _, clicked_row):
        # TODO: Create a template for the track view with methods
        # to update it's display based on the album selected.
        self.outer_view.set_show_content('track_view')

    def select_artist(self, _, clicked_row):
        if clicked_row:
            self.album_box.remove_all()
            albums = self.db.get_albums(clicked_row.get_child().get_label())
            for album in albums:
                self.album_box.append(self.create_label(album))

        self.inner_view.set_show_content('album_view')

    def create_label(self, label):
        label = Gtk.Label(label=label)
        label.set_width_chars(20)
        label.set_ellipsize(Pango.EllipsizeMode.END)

        return label
