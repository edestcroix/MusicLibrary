from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


# TODO: Allow adding lone tracks to the queue. (Then allow for that in the UI)
# Highlight the current song in the queue. Connect this highlight function to some
# global signal that is emitted on track change.


# TODO: get_next_track() Returns the next track in the queue, None if not.
# Then, im the window, when the player emits about-to-finish, get the next track,
# set it up to play, play it (blah blah). Once it's playing the window will
# call back to the PlayQueue. For this use function update_queue() which
# will set up the next track and highlight the playing one.


class PlayQueue(Gtk.ListBox):
    __gtype_name__ = 'PlayQueue'

    # NOTE: Need some way to deal with the children of the ExpanderRows to
    # be able to highlight them and remove them. Might be better to use
    # a TreeView (GridView now? TreeView was deprecated).

    # Might have to subclass both ExpanderRow and ActionRow, so the ExpanderRow
    # can track its children better.

    def add_album(self, album):
        album_row = Adw.ExpanderRow()
        album_row.set_title(album.name)
        album_row.set_title_lines(1)
        album_row.set_subtitle(GLib.markup_escape_text(album.artist))
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
            row.set_title(GLib.markup_escape_text(track.title))
            remove_button = Gtk.Button()
            remove_button.get_style_context().add_class('flat')
            remove_button.set_icon_name('list-remove-symbolic')
            remove_button.set_tooltip_text('Remove from queue')
            row.add_suffix(remove_button)
            album_row.add_row(row)
            remove_button.connect(
                'clicked',
                lambda r: self._remove(
                    album_row, r.get_ancestor(Adw.ActionRow)
                ),
            )

        self.append(album_row)

    def _remove(self, album_row, row):
        album_row.remove(row)
        if not album_row.get_child():
            self.remove(album_row)

    def clear(self):
        self.remove_all()
