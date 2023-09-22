import mutagen
import sys
import os
import sqlite3


# TODO: Needs refactoring, this isn't very good.
# When parsing the library, files that no longer exists need to be removed from the db.

from gi.repository import Gtk, GLib


class MusicDB:
    def __init__(self):
        # database path should be Gtk.get_user_data_dir() + '/music.db'

        self.conn = sqlite3.connect(f'{GLib.get_user_data_dir()}/music.db')
        self.c = self.conn.cursor()
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS music
                    (path text, title text, artist text, album text, length real)"""
        )

    # def parse_metadata(audio, path):

    def parse_library(self, path='~/Music'):

        with os.scandir(os.path.expanduser(path)) as it:
            for entry in it:
                if entry.is_dir():
                    self.parse_library(entry.path)
                elif entry.is_file():
                    if audio := mutagen.File(entry.path, easy=True):
                        # print(entry.path, audio.info.length)

                        # itentify file type and parse metadata
                        print(audio['title'])

                        # audio.info.pprint()

                        # insert if not exists
                        self.c.execute(
                            'INSERT INTO music VALUES (?, ?, ?, ?, ?) EXCEPT SELECT * FROM music',
                            (
                                entry.path,
                                audio['title'][0],
                                audio['artist'][0],
                                audio['album'][0],
                                audio.info.length,
                            ),
                        )
                        self.conn.commit()

    def get_artists(self):
        self.c.execute('SELECT DISTINCT artist FROM music')

        return [artist[0] for artist in self.c.fetchall()]

    def get_albums(self, artist=None):

        if artist:
            self.c.execute(
                'SELECT DISTINCT album FROM music WHERE artist = ?', (artist,)
            )
        else:
            self.c.execute('SELECT DISTINCT album FROM music')
        return [album[0] for album in self.c.fetchall()]
