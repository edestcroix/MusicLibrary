import mutagen
import os
import sqlite3
from PIL import Image
from dataclasses import dataclass
from hashlib import sha256

from gi.repository import Gtk, GLib


@dataclass
class Album:
    name: str
    num_tracks: int
    length: int
    year: str
    artist: str
    cover: str

    def get_tracks(self):
        return self.tracks

    def set_tracks(self, tracks):
        self.tracks = tracks

    def to_row(self):
        return (
            self.name,
            f'{self.length_str()} - {self.num_tracks} tracks',
            self.artist,
            self.cover,
        )

    def length_str(self):
        return f'{int(self.length // 3600):02}:{int(self.length // 60 % 60):02}:{int(self.length % 60):02}'


@dataclass
class Artist:
    name: str
    num_albums: int

    def to_row(self):
        return (
            self.name,
            f'{self.num_albums} albums',
        )


# TODO: Better detection of changed files. Currently the library sync is slow because
# it completely replaces everything in the database.


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
            """CREATE TABLE IF NOT EXISTS albums
                (name text, artist text, year date, cover text, UNIQUE(name, artist) ON CONFLICT REPLACE)
                """
        )
        self.c.execute(
            """
                CREATE TABLE IF NOT EXISTS tracks
                (album text, track text, title text, length real, path text, UNIQUE(album, track) ON CONFLICT REPLACE)
                """
        )

    # TODO: more efficient way of parsing library
    def parse_library(self, path='~/Music'):

        self.remove_missing(self.find_missing())

        with os.scandir(os.path.expanduser(path)) as dir:
            # check if there is an image called cover.*
            to_insert = []
            cover = None
            # TODO: Better detection of cover images.
            for entry in dir:
                if entry.is_dir():
                    self.parse_library(entry.path)
                elif entry.is_file():
                    if audio := mutagen.File(entry.path, easy=True):
                        to_insert.append((entry, audio))

                    if entry.name.startswith('cover'):
                        # shrink image

                        cover = entry.path

            # FIXME: Change how the cache name is generated.
            if cover and not os.path.exists(
                cache_name := sha256(open(cover, 'rb').read()).hexdigest()
            ):
                path = self.create_thumbnail(cover, cache_name)
            for (entry, audio) in to_insert:
                # itentify file type and parse metadata
                print(audio['title'], audio['date'], cover)
                self.insert(
                    'albums',
                    (
                        audio['album'][0],
                        audio['artist'][0],
                        audio['date'][0],
                        path,
                    ),
                )
                self.insert(
                    'tracks',
                    (
                        audio['album'][0],
                        audio['tracknumber'][0],
                        audio['title'][0],
                        audio.info.length,
                        entry.path,
                    ),
                )
                self.conn.commit()

    def insert(self, table, values):
        self.c.execute(
            f'INSERT INTO {table} VALUES ({", ".join(["?"] * len(values))})',
            values,
        )

    def create_thumbnail(self, cover, cache_name):
        print(f'Converting {cover}')
        img = Image.open(cover)
        rgb_img = img.convert('RGB')
        rgb_img.thumbnail((320, 320))
        # generate a unique string for the cover
        rgb_img.save(
            result := f'{GLib.get_user_cache_dir()}/musiclibrary/{cache_name}.jpg'
        )

        print(result)

        return result

    def find_missing(self):
        self.c.execute('SELECT path FROM tracks')
        return [
            path[0]
            for path in self.c.fetchall()
            if not os.path.exists(path[0])
        ]

    def remove_missing(self, paths):
        for path in paths:
            self.c.execute('DELETE FROM tracks WHERE path = ?', (path,))
            self.conn.commit()

        self.c.execute(
            'DELETE FROM albums WHERE name NOT IN (SELECT DISTINCT album FROM tracks)'
        )
        self.conn.commit()

    def get_artists(self):
        # return a list of artists, and the number of albums in one query

        self.c.execute(
            'SELECT DISTINCT artist, COUNT(DISTINCT name) FROM albums GROUP BY artist'
        )
        return [Artist(*a) for a in self.c.fetchall()]

    def get_albums(self):
        self.c.execute(
            'SELECT DISTINCT name, COUNT(title), SUM(length), year, artist, cover FROM albums JOIN tracks ON albums.name = tracks.album GROUP BY name ORDER BY year',
        )
        return [Album(*a) for a in self.c.fetchall()]

    def get_album(self, album):
        self.c.execute(
            'SELECT DISTINCT name, COUNT(title), SUM(length), year, artist, cover FROM albums JOIN tracks ON albums.name = tracks.album WHERE name = ? GROUP BY name',
            (album,),
        )
        return Album(*self.c.fetchone())

    def get_tracks(self, album):
        self.c.execute(
            'SELECT track, title, length, path FROM tracks WHERE album = ? ORDER BY track',
            (album,),
        )
        return self.c.fetchall()
