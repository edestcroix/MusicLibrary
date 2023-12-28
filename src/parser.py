from gi.repository import GLib, GObject
from hashlib import sha256
from io import BytesIO
import mimetypes
import mutagen
import os
from PIL import Image
from PIL import UnidentifiedImageError
import contextlib

from .musicdb import MusicDB, ArtistTags, TrackTags

CoverPaths = tuple[str, str]


class CoverImage:
    """A class that represents a cover image for an album,
    with methods for converting it to a thumbnail and a larger
    image, and saving these images to the cache. Must be
    provided with the image data as a bytes object on init"""

    def __init__(self, image: bytes):
        self.image = image

    def sha256(self) -> str:
        return sha256(self.image).hexdigest()

    def cache_path(self) -> str:
        cache_dir = f'{GLib.get_user_cache_dir()}/RecordBox'
        return f'{cache_dir}/{self.sha256()}.png'

    def thumbnail(self) -> Image.Image | None:
        return self._resize(128)

    def large(self) -> Image.Image | None:
        return self._resize(512)

    def save(self) -> CoverPaths | None:
        thumbnail = self.save_thumbnail()
        large = self.save_large()
        return (thumbnail, large) if thumbnail and large else None

    def save_thumbnail(self) -> str | None:
        path = self._save('/RecordBox/thumbnails')
        if os.path.exists(path):
            return path
        if image := self.thumbnail():
            image.save(path)
            return path

    def save_large(self) -> str | None:
        path = self._save('/RecordBox/large')
        if os.path.exists(path):
            return path
        if image := self.large():
            image.save(path)
            return path

    def _save(self, path):
        thumb_dir = f'{GLib.get_user_cache_dir()}{path}'
        result = f'{thumb_dir}/{self.sha256()}.png'
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
        return result

    def _resize(self, size):
        try:
            image = Image.open(BytesIO(self.image))
            image = image.convert('RGB')
            image.thumbnail((size, size))
            return image
        except UnidentifiedImageError:
            return None


class AudioFile:
    """A wrapper around mutagen's File class that provides an interface
    for extracting metadata from audio files in a format more suitable
    for inserting into RecordBox's database."""

    def __init__(self, audio, file: str):
        self.audio = audio
        self.file = file

    def try_key(self, key: str) -> str | None:
        """Attempts to get a key from the audio file.
        Args:
            key: The key to get from the audio file.
        """

        return self.audio[key][0] if key in self.audio else None

    def try_key_all(self, key: str) -> list[str]:
        return self.audio[key] if key in self.audio else []

    def artists(self) -> list[ArtistTags]:
        """Returns a list of the artists associated with the audio file."""
        return [
            ArtistTags(str(artist), self.try_key('artistsort'), self.file)
            for artist in self.try_key_all('artist')
        ]

    def track_tags(self, cover_paths: CoverPaths | None) -> TrackTags:
        """Returns the track information from the audio file."""
        thumb, cover = cover_paths or (None, None)
        return TrackTags(
            self.try_key('title') or 'Unknown Title',
            self.try_key('tracknumber') or '0',
            self.try_key('discnumber'),
            self.try_key('discsubtitle'),
            self.try_key('album') or 'Unknown Album',
            self.try_key('albumartist'),
            self.try_key('date'),
            self.audio.info.length,
            thumb,
            cover,
            self.file,
            os.path.getmtime(self.file),
            self.artists(),
        )

    def embedded_cover(self) -> CoverImage | None:
        """Extracts the embedded cover image from the audio file,
        if it exists. Otherwise, returns None."""
        if full := mutagen.File(self.file):
            if 'covr' in full.tags:
                try:
                    return CoverImage(full.tags['covr'][0].data)
                except AttributeError:
                    return None
            elif 'APIC:' in full:
                return CoverImage(full.tags.get('APIC:').data)
            else:
                with contextlib.suppress(AttributeError):
                    return (
                        CoverImage(full.pictures[0].data)
                        if full.pictures
                        else None
                    )

    def check_need_update(self, mod_time: float) -> bool:
        """Checks if the audio file has been modified since the last time it was parsed
        Args:
            mod_time: The last time the audio file was parsed
        """
        return os.path.getmtime(self.file) > mod_time


class MusicParser(GObject.Object):
    """A class that parses a directory of audio files and sends them to a database."""

    path = GObject.Property(type=str, default='')

    def __init__(self, path=os.path.expanduser('~/Music'), **kwargs):
        super().__init__(**kwargs)
        self._total_dirs = int(os.popen(f'find {path} -type d | wc -l').read())
        self._dirs_visited = 0

    progress = GObject.Property(type=float, default=0.0)

    def build(self, db: MusicDB):
        """Builds the database from the given directory.
        Args:
            db: The MusicDB object to send the parsed data to.
        """
        db.remove_missing(self.path)
        self._parse(db, self.path)
        db.commit()
        self._dirs_visited = 0

    def _parse(self, db: MusicDB, path: str):
        """Recursively parses the given directory and sends the parsed data to the database."""
        for root, _, files in os.walk(path):
            tracks = []
            for file in files:
                if track := self._parse_file(f'{root}/{file}', db):
                    tracks.append(track)

            self._update_progress()
            if tracks:
                external_cover = self._pick_cover(root)
                self._send_to_db(db, tracks, external_cover)

    def _update_progress(self):
        self._dirs_visited += 1
        GLib.idle_add(
            self.set_property,
            'progress',
            self._dirs_visited / self._total_dirs,
        )

    def _parse_file(self, file: str, db: MusicDB) -> AudioFile | None:
        if (mod_time := db.modify_time(file)) and (
            mod_time >= os.path.getmtime(file)
        ):
            return None
        elif audio := self._parse_audio(file):
            return audio

    def _pick_cover(self, root: str) -> CoverImage | None:
        possible_covers = [
            f'{root}/{file}'
            for file in os.listdir(root)
            if file.lower().endswith(('.png', '.jpg', '.jpeg'))
            and file.lower().startswith(('cover', 'folder'))
        ]
        return (
            CoverImage(open(possible_covers[0], 'rb').read())
            if possible_covers
            else None
        )

    def _parse_audio(self, file: str) -> AudioFile | None:
        if (mime := self._mime_type(file)) and not mime.startswith('audio'):
            return None
        try:
            audio = mutagen.File(file, easy=True)
            return AudioFile(audio, file) if audio else None
        except mutagen.MutagenError:
            return None

    def _mime_type(self, file: str) -> str | None:
        return mimetypes.guess_type(file)[0]

    def _send_to_db(
        self, db: MusicDB, tracks: list[AudioFile], cover: CoverImage | None
    ):
        cover = cover or tracks[0].embedded_cover()
        cover_paths = cover.save() if cover else None

        tags = [t.track_tags(cover_paths) for t in tracks]
        self._find_albumartist(tags)

        for track in tags:
            db.insert_track(track)

    def _find_albumartist(self, tracks: list[TrackTags]):
        """Finds and sets an albumartist for the given tracks, if possible.
        (If the tracks don't have an albumartist tag, then one is selected
        from the artists of the tracks. If no albumartist can be found, then
        it's left as None to signify it is a compilation album.)"""
        if all(track.albumartist for track in tracks):
            return
        # get the sets of artists for each track,
        # find the intersection of all of them.
        artists = [
            {artist.name for artist in track.artists} for track in tracks
        ]
        # if there are no artists at all, set albumartist to Unknown Artist
        if not artists:
            for i in range(len(tracks)):
                tracks[i] = tracks[i]._replace(albumartist='Unknown Artist')
        elif intersection := set.intersection(*artists):
            albumartist = intersection.pop()
            for i in range(len(tracks)):
                tracks[i] = tracks[i]._replace(albumartist=albumartist)
        else:
            for i in range(len(tracks)):
                tracks[i] = tracks[i]._replace(albumartist='[Various Artists]')
                tracks[i].artists.append(
                    ArtistTags('[Various Artists]', 'AAAAAA', tracks[i].path)
                )
