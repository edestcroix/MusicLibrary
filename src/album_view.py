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

gi.require_version('Gtk', '4.0')


# TODO: Chunck this up into other files/classes as needed
#       - Track display page

# NOTE: I Bet after getting a nice UI i'm going to end up getting stuck on gstreamer and get mad probably.

from .musicdb import MusicDB


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/album_view.ui')
class MusicLibraryAlbumView(Gtk.Box):
    __gtype_name__ = 'MusicLibraryAlbumView'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_cover(self, cover_path):
        pass
