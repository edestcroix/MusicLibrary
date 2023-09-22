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

from gi.repository import Adw
from gi.repository import Gtk

import mutagen


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/window.ui')
class MusiclibraryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MusicLibraryWindow'

    artist_box = Gtk.Template.Child()
    album_box = Gtk.Template.Child()

    test_button = Gtk.Template.Child()

    c = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # artist_box is a GtkListBox

        # artist_model = Gtk.ListStore(str)
        # album_model = Gtk.ListStore(str)

        # bind test_button to test_button_clicked
        self.test_button.connect('clicked', self.test_button_clicked)

        for i in range(100):
            # self.artist_box.append(Gtk.Label(label=f'Artist {i}'))
            self.album_box.append(Gtk.Label(label=f'Album {i}'))

        # bind clicks on elements of artist_box to artist_clicked
        self.artist_box.connect('row-activated', self.select_artist)

        # renderer = Gtk.CellRendererText()

        # artist_column = Gtk.TreeViewColumn('Artist', renderer, text=0)
        # album_column = Gtk.TreeViewColumn('Album', renderer, text=0)

        # artist_column.set_sort_column_id(0)
        # album_column.set_sort_column_id(0)

        # self.artist_view.set_model(artist_model)
        # self.artist_view.append_column(artist_column)
        # self.album_view.set_model(album_model)
        # self.album_view.append_column(album_column)

    def test_button_clicked(self, _):
        print('test button clicked')

        self.artist_box.append(Gtk.Label(label=f'test ({self.c})'))
        self.c += 1

    # TODO: This will need to update the album list to show
    # only albums by the selected artist.
    def select_artist(self, _, clicked_row):
        if clicked_row:
            print(clicked_row.get_index())
            print(clicked_row.get_child().get_label())
