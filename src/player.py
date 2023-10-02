"""Gstreamer API."""

import logging
import multiprocessing
import os
import queue
import time
import urllib
import urllib.parse

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst


Gst.init(None)

# TODO: Improved playy queue. This will mostly be implementened in play_queue.py, because
# all the player needs to do is get the next track out of it.


class Player:
    def __init__(self, play_queue):
        """Initialize the player."""
        # self._player = Gst.ElementFactory.make('playbin', 'player')
        self._player = Gst.parse_launch(
            'playbin audio-sink="rgvolume ! autoaudiosink"'
        )
        self._player.connect('about-to-finish', self.on_about_to_finish)
        self.bus = self._player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_message)
        self.play_queue = play_queue
        self.state = 'stopped'
        # self.bus.connect('about-to-finish', self.on_about_to_finish)

    def play(self):
        """Start playback."""
        url = self.prepare_url()
        self._player.set_state(Gst.State.NULL)
        self._player.set_property('uri', url)
        self._player.set_state(Gst.State.PLAYING)
        self.state = 'playing'
        print(self._player.get_state(1 * Gst.SECOND))

    def toggle(self):
        if self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PLAYING:
            self._player.set_state(Gst.State.PAUSED)
            self.state = 'paused'
        elif self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PAUSED:
            self._player.set_state(Gst.State.PLAYING)
            self.state = 'playing'

    def get_progress(self):
        """Get the current progress of the track."""
        return self._player.query_position(Gst.Format.TIME)[1]

    def get_duration(self):
        return self._player.query_duration(Gst.Format.TIME)[1]

    def on_message(self, _, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._player.set_state(Gst.State.NULL)
        # elif t == Gst.MessageType.ABOUT_TO_FINISH:
        #     print('about to finish')
        elif t == Gst.MessageType.ERROR:
            self._player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            print(f'Error: {err}', debug)

    def on_about_to_finish(self, _):
        url = self.prepare_url()
        self._player.set_property('uri', url)

    # TODO Rename this here and in `play` and `on_about_to_finish`
    def prepare_url(self):
        track = self.play_queue.get_next_track()
        path = os.path.realpath(track.path.strip())
        result = urllib.parse.ParseResult(
            scheme='file',
            path=path,
            netloc='',
            query='',
            fragment='',
            params='',
        )
        result = urllib.parse.urlunparse(result)
        return result
