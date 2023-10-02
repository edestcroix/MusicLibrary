from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


class PlayQueue(Gtk.ListBox):
    __gtype_name__ = 'PlayQueue'

    def add_album(self, album):
        album_row = Adw.ExpanderRow()
        album_row.set_title(album.name)
        album_row.set_title_lines(1)
        album_row.set_subtitle(album.artist)
        remove_button = Gtk.Button()
        remove_button.get_style_context().add_class('flat')
        remove_button.set_icon_name('list-remove-symbolic')
        remove_button.set_tooltip_text('Remove from queue')

        album_row.add_suffix(remove_button)
        remove_button.connect('clicked', lambda _: self.remove(album_row))

        if album.cover:
            image = Gtk.Image()
            image.set_from_file(album.cover)
            image.set_pixel_size(32)
            album_row.add_prefix(image)

        for track in album.tracks:
            row = Adw.ActionRow()
            row.get_style_context().add_class('queue-row')
            row.set_title(track[1])
            album_row.add_row(row)

        self.append(album_row)

    def clear(self):
        self.remove_all()
