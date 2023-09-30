import mutagen
import os
import sqlite3
from PIL import Image
from dataclasses import dataclass
from hashlib import sha256

# TODO: Needs refactoring, this isn't very good.

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
    num_tracks: int
    length: int

    def to_row(self):
        return (
            self.name,
            f'{self.num_albums} albums, {self.num_tracks} tracks, {self.length_str()}',
        )

    def length_str(self):
        return f'{int(self.length // 3600):02}:{int(self.length // 60 % 60):02}:{int(self.length % 60):02}'


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

        # os.mkdir(f'{GLib.get_user_cache_dir()}/musiclibrary')

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

            if cover and not os.path.exists(
                cache_name := sha256(open(cover, 'rb').read()).hexdigest()
            ):
                path = self.create_thumbnail(cover, cache_name)
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
                        path,
                        audio['tracknumber'][0],
                    ),
                )
                self.conn.commit()

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
        return Artist(artist, *self.c.fetchone())

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
        return Album(album, *self.c.fetchone())

    def get_tracks(self, album):
        self.c.execute(
            'SELECT path, title, length FROM music WHERE album = ? ORDER BY track',
            (album,),
        )
        return self.c.fetchall()
