"""Gstreamer API."""

import logging
import multiprocessing
import os
import queue
import time
import urllib
import urllib.request

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
        # self.bus.connect('about-to-finish', self.on_about_to_finish)

    def play(self):
        """Start playback."""

        track = self.play_queue.get_next_track()
        path = os.path.realpath(track.path.strip())
        self._player.set_state(Gst.State.NULL)
        self._player.set_property('uri', f'file:/{path}')
        self._player.set_state(Gst.State.PLAYING)
        print(self._player.get_state(1 * Gst.SECOND))

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
        next_track = self.play_queue.get_next_track()
        path = os.path.realpath(next_track.path.strip())
        self._player.set_property('uri', f'file:/{path}')
