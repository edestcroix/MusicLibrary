import contextlib
from io import BytesIO
from gi.types import re
import mutagen
import os
import sqlite3
import mimetypes
from PIL import Image
from dataclasses import dataclass
from hashlib import sha256

from gi.repository import Gtk, GLib


@dataclass
class Album:
    name: str
    num_tracks: int
    length: int
    date: str
    artist: str
    cover: str

    def get_tracks(self):
        return self.tracks

    def set_tracks(self, tracks):
        self.tracks = tracks
        # sort tracks by their track number (which might be in the form 1/10)
        self.tracks.sort(key=lambda t: int(t.track.split('/')[0]))

    def to_row(self):
        return (
            self.name,
            f'{self.length_str()} - {self.num_tracks} tracks',
            self.artist,
            self.cover,
            str(self.date),
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


@dataclass
class Track:
    track: int
    title: str
    length: int
    path: str

    def to_row(self):
        return (self.track, self.title, self.length, self.path)
# TODO: Better detection of changed files. Currently the library sync is slow because
# it completely replaces everything in the database.
# This file is still really messy, maybe the database retrevial functions and the library parsing
# should be separated.
# Ideas for better parsing:
# - Store the modification time of the file in the database, and only reparse if it has changed
# - Store the hash of the file in the database, and only reparse if it has changed.
# - Skip the INSERT query if the path already exists and the hash matches.


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

        current_dir = list(os.scandir(os.path.expanduser(path)))

        print('In directory:', path)

        directories = [entry for entry in current_dir if entry.is_dir()]

        images = [
            entry
            for entry in current_dir
            if (mimetype := mimetypes.guess_type(entry.path)[0])
            and mimetype.startswith('image')
        ]

        current_dir = [entry for entry in current_dir if entry.is_file()]
        cover = self.find_cover(images)

        to_insert = []

        for entry in directories:
            self.parse_library(entry.path)

        embed_cover = None
        for entry in current_dir:
            if audio_list := mutagen.File(entry.path, easy=True):
                to_insert.append((entry, audio_list))

            embed_cover = self.get_embeded_cover(entry) or embed_cover

        cached_cover_path = None
        if cover := embed_cover or cover:
            cached_cover_path = self.cache_cover(cover)

        self.insert_to_db(to_insert, cached_cover_path)

    def find_cover(self, images):
        cover = next(
            (
                image.path
                for image in images
                if image.name.lower()[:-4] in ('cover', 'folder', 'front')
            ),
            None,
        )
        if not cover and images:
            cover = images[0].path
        return cover

    def hash_cover(self, cover):
        if type(cover) == str:
            return sha256(open(cover, 'rb').read()).hexdigest()
        elif type(cover) == bytes:
            return sha256(cover).hexdigest()

    def get_embeded_cover(self, audio_path):
        embed_cover = None
        if full := mutagen.File(audio_path.path):
            # look for APIC, covr, or pictures
            if 'covr' in full.tags:
                embed_cover = full.tags['covr'][0].data
            elif 'APIC:' in full:
                embed_cover = full.tags.get('APIC:').data
            else:
                with contextlib.suppress(AttributeError):
                    embed_cover = (
                        full.pictures[0].data if full.pictures else None
                    )
        return embed_cover

    def cache_cover(self, cover):
        cache_name = self.hash_cover(cover)
        cover = BytesIO(cover) if type(cover) == bytes else cover
        cached_cover_path = (
            f'{GLib.get_user_cache_dir()}/musiclibrary/{cache_name}.jpg'
        )
        if not os.path.exists(cached_cover_path):
            print('Generating cached image from cover')
            self.create_thumbnail(cover, cached_cover_path)
        return cached_cover_path

    def insert_to_db(self, to_insert, cover):
        for (entry, audio) in to_insert:
            self.insert(
                'albums',
                audio['album'][0],
                audio['artist'][0],
                audio['date'][0],
                cover,
            )
            self.insert(
                'tracks',
                audio['album'][0],
                audio['tracknumber'][0],
                audio['title'][0],
                audio.info.length,
                entry.path,
            )
            self.conn.commit()

    def insert(self, table, *args):
        self.c.execute(
            f'INSERT INTO {table} VALUES ({", ".join(["?"] * len(args))})',
            args,
        )

    def create_thumbnail(self, cover, out_path):
        img = Image.open(cover)
        rgb_img = img.convert('RGB')
        rgb_img.thumbnail((320, 320))
        # generate a unique string for the cover
        rgb_img.save(out_path)

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
            'SELECT name, COUNT(title), SUM(length), year, artist, cover FROM albums JOIN tracks ON albums.name = tracks.album WHERE name = ? GROUP BY name',
            (album,),
        )
        return Album(*self.c.fetchone())

    def get_tracks(self, album):
        self.c.execute(
            'SELECT track, title, length, path FROM tracks WHERE album = ? ORDER BY track',
            (album,),
        )
        return [Track(*t) for t in self.c.fetchall()]
