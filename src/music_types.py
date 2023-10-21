from dataclasses import dataclass
import re


@dataclass
class Album:
    name: str
    num_tracks: int
    length: int
    date: str
    thumb: str
    cover: str
    artists: str

    def get_tracks(self):
        return self.tracks

    def set_tracks(self, tracks):
        self.tracks = tracks
        # sort tracks by their track number (which might be in the form 1/10)
        self.tracks.sort(key=self._sort_tracks)

    def _sort_tracks(self, t):
        if t.discnumber is None:
            return int(t.track.split('/')[0])
        discnum = int(t.discnumber.split('/')[0])
        tracknum = int(t.track.split('/')[0])
        return discnum * 100 + tracknum

    def length_str(self):
        if hours := int(self.length // 3600):
            return f'{hours}:{int(self.length // 60 % 60):02}:{int(self.length % 60):02}'
        else:
            return f'{int(self.length // 60):02}:{int(self.length % 60):02}'


@dataclass
class Track:
    track: str
    discnumber: str
    title: str
    length: int
    path: str
    album: str
    artists: list[str]
    # albumartist is the primary artist for the album. It is set to the value of the albumartist tag
    # if it exists, otherwise it is set to the first artist tag value found. It should never be empty.
    albumartist: str

    def to_row(self):
        return (self.track, self.title, self.length, self.path)

    def disc_num(self):
        return (
            int(re.sub(r'/.*', '', self.discnumber)) if self.discnumber else 0
        )

    def track_num(self):
        return int(re.sub(r'/.*', '', self.track)) if self.track else 0

    def length_str(self):
        return f'{int(self.length // 60):02}:{int(self.length % 60):02}'
