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

import gi

gi.require_version('Gtk', '4.0')

from .items import AlbumItem, TrackItem
from gi.repository import Adw, Gtk, GLib, GObject, Gio


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/album_view.ui')
class AlbumView(Adw.BreakpointBin):
    __gtype_name__ = 'RecordBoxAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    album_box = Gtk.Template.Child()

    album_title = Gtk.Template.Child()
    album_artist = Gtk.Template.Child()

    stack = Gtk.Template.Child()

    current_album = GObject.Property(type=GObject.TYPE_PYOBJECT)
    expand_discs = GObject.Property(type=bool, default=False)

    def update_cover(self, cover_path: str):
        self.cover_image.set_from_file(cover_path)

    def clear_all(self):
        self.track_list.remove_all()

    def update_album(self, album: AlbumItem):
        self.current_album = album
        self.clear_all()
        self.update_cover(album.cover)
        self.update_tracks(album.tracks)
        self.album_title.set_text(album.raw_name)
        self.album_artist.set_text(album.artists[0])
        self.stack.set_visible_child_name('album_view')

    def update_tracks(self, tracks: list[TrackItem]):
        current_disc, disc_row = 0, None
        for i, track in enumerate(tracks):
            if track.discnumber != current_disc:
                current_disc = track.discnumber
                disc_row = DiscRow(
                    discnumber=current_disc,
                    discsubtitle=track.discsubtitle,
                    expanded=self.expand_discs,
                )
                self.track_list.append(disc_row)
            if disc_row:
                disc_row.add_row(TrackRow(track=track, index=i))
            else:
                self.track_list.append(TrackRow(track=track, index=i))


class DiscRow(Adw.ExpanderRow):
    __gtype_name__ = 'RecordBoxDiscRow'

    def __init__(self, discnumber: int, discsubtitle: str | None, **kwargs):
        super().__init__(
            title=discsubtitle or f'Disc {discnumber}',
            subtitle=f'Disc {discnumber}' if discsubtitle else None,
            selectable=False,
            **kwargs,
        )
        box = self.get_child()
        revealer = box.get_last_child()
        listbox = revealer.get_child()
        listbox.set_activate_on_single_click(False)

        self.menu_model = Gio.Menu.new()
        self.menu_model.append('Play Disc', f'win.play-disc({discnumber})')
        self.menu_model.append(
            'Add To Queue', f'win.append-disc({discnumber})'
        )
        self.menu_model.append(
            'Replace Queue', f'win.replace-disc({discnumber})'
        )
        self.new_popover = Gtk.PopoverMenu.new_from_model(self.menu_model)
        btn = Gtk.MenuButton()
        btn.set_icon_name('view-more-symbolic')
        btn.set_css_classes(['flat'])
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_popover(self.new_popover)
        self.add_suffix(btn)


class TrackRow(Adw.ActionRow):
    def __init__(self, track: TrackItem, index: int, **kwargs):
        super().__init__(
            title_lines=1, selectable=False, activatable=True, **kwargs
        )

        artists = f'\n{track.artists}' if track.artists else ''
        self.set_subtitle(
            GLib.markup_escape_text(
                f'{track.track:0>2} - {track.length}{artists}'
            )
        )
        self.set_title(track.title)
        self.set_tooltip_text(track.raw_title)
        self.set_detailed_action_name(f'win.play({index})')

        self.menu_model = Gio.Menu.new()
        self.menu_model.append('Play Track', f'win.play-single({index})')
        self.menu_model.append('Add To Queue', f'win.append({index})')
        self.new_popover = Gtk.PopoverMenu.new_from_model(self.menu_model)

        btn = Gtk.MenuButton()
        btn.set_icon_name('view-more-symbolic')
        btn.set_css_classes(['flat'])
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_popover(self.new_popover)

        self.add_suffix(btn)
