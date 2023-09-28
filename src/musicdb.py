import mutagen
import os
import sqlite3


# TODO: Needs refactoring, this isn't very good.

from gi.repository import Gtk, GLib


class MusicDB:
    def __init__(self):
        # database path should be Gtk.get_user_data_dir() + '/music.db'

        # make sure the directory exists
        # os.remove(f'{GLib.get_user_data_dir()}/musiclibrary/music.db')

        None if os.path.exists(
            f'{GLib.get_user_data_dir()}/musiclibrary'
        ) else os.mkdir(f'{GLib.get_user_data_dir()}/musiclibrary')

        self.conn = sqlite3.connect(
            f'{GLib.get_user_data_dir()}/musiclibrary/music.db'
        )
        self.c = self.conn.cursor()
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS music
                    (path text, title text, artist text, album text, length real, year date, cover text, track text, UNIQUE(path) ON CONFLICT REPLACE)"""
        )

    # TODO: more efficient way of parsing library
    def parse_library(self, path='~/Music'):

        self.remove_missing(self.find_missing())

        with os.scandir(os.path.expanduser(path)) as dir:
            # check if there is an image called cover.*
            to_insert = []
            cover = None
            for entry in dir:
                if entry.is_dir():
                    self.parse_library(entry.path)
                elif entry.is_file():
                    if audio := mutagen.File(entry.path, easy=True):
                        to_insert.append((entry, audio))

                    if entry.name.startswith('cover'):
                        cover = entry.path

            for (entry, audio) in to_insert:
                # itentify file type and parse metadata
                print(audio['title'], audio['date'], cover)

                # insert if not exists
                self.c.execute(
                    'INSERT INTO music VALUES (?, ?, ?, ?, ?, ?, ?, ?) EXCEPT SELECT * FROM music',
                    (
                        entry.path,
                        audio['title'][0],
                        audio['artist'][0],
                        audio['album'][0],
                        audio.info.length,
                        audio['date'][0],
                        cover,
                        audio['tracknumber'][0],
                    ),
                )
                self.conn.commit()

    def find_missing(self):
        self.c.execute('SELECT path FROM music')
        return [
            path[0]
            for path in self.c.fetchall()
            if not os.path.exists(path[0])
        ]

    def remove_missing(self, paths):
        for path in paths:
            self.c.execute('DELETE FROM music WHERE path = ?', (path,))
        self.conn.commit()

    def get_artists(self):
        self.c.execute('SELECT DISTINCT artist FROM music')

        return [self.get_artist(artist[0]) for artist in self.c.fetchall()]

    def get_artist(self, artist):
        # return the number of albums, number of tracks, total length

        self.c.execute(
            'SELECT COUNT(DISTINCT album), COUNT(title), SUM(length) FROM music WHERE artist = ?',
            (artist,),
        )
        return (artist, *self.c.fetchone())

    def get_albums(self, artist=None):
        if artist:
            self.c.execute(
                # TODO: Expose setting to change sort order.
                'SELECT DISTINCT album FROM music WHERE artist = ? ORDER BY year',
                (artist,),
            )

        else:
            self.c.execute('SELECT DISTINCT album FROM music ORDER BY year')
        return [self.get_album(album[0]) for album in self.c.fetchall()]

    def get_album(self, album):
        self.c.execute(
            'SELECT COUNT(title), SUM(length), year, artist, cover FROM music WHERE album = ?',
            (album,),
        )
        return (album, *self.c.fetchone())

    def get_tracks(self, album):
        self.c.execute(
            'SELECT path, title, length FROM music WHERE album = ? ORDER BY track',
            (album,),
        )
        return self.c.fetchall()
