Disclaimer: This project has moved to `codeberg <https://codeberg.org/edestcroix/Recordbox>`_.


.. image:: https://github.com/edestcroix/RecordBox/actions/workflows/flatpak.yml/badge.svg
   :target: https://github.com/edestcroix/RecordBox/actions/workflows/flatpak.yml
Record Box
==============================================
A relatively simple, opinionated music player.

.. image:: ./data/icons/hicolor/scalable/apps/com.github.edestcroix.RecordBox.svg
   :width: 128px
   :alt: RecordBox icon
   :align: left


RecordBox is a music player and library browser designed primarilly to be as simple as possible. Unlike music players such as 
`Lollypop <https://gitlab.gnome.org/World/lollypop>`_ or `Rhythmbox <https://wiki.gnome.org/Apps/Rhythmbox>`_, it does not offer multiple views,
playlist management, or tag editing. Instead, it offers a single, simple view of your music library, filtered by artists and albums. In this, RecordBox is similar
in motivation to `Amberol <https://gitlab.gnome.org/World/Amberol>`_, however it provides *slightly* more functionality in that it has an
integrated library browser. (It also provides *slightly* less functionality in that I don't plan on adding shuffle)

.. image:: ./screenshot.png
  :alt: RecordBox screenshot
  :align: center

Features
--------
- Navigating music library by artist and album
- Tag parsing supported by the `Mutagen <https://mutagen.readthedocs.io/en/latest/>`_ tagging library that
  (hopefully) accomodates all kinds of tagging schemes.
- Detection and display of album art
- Playback of music using GStreamer, with gapless playback and ReplayGain support
- Support for whatever file formats GStreamer supports
- Fully responsive interface using LibAdwaita's new sidebar widgets


Reason For Existing
--------------------
For a while, I've had the idea of creating a music player, but couldn't settle fully on a UI design, and was mostly satisfied with `Quod Libet <https://quodlibet.readthedocs.io/en/latest/>`_.
While I really like Quod Libet, and still use it to tag and manage my library, it bothered me that the album list page that showed cover art couldn't be filtered by artist
like the paned browser could. Still, I continued to use it, until I had an amazing idea for a music player UI. At the time I did not have time to start a new project though, so I 
didn't do anything with the idea, until around 2 weeks later Amberol was released and was almost exactly the idea I had, so I scrapped it.

Then recently, LibAdwaita 1.4 release with new sidebar widgets, and as soon as I saw the example triple-pane layout I immediatly got the idea for RecordBox's UI and started
obsessively working on it. 
  
And now we're here, and I have created a music player that exists as a fusion of my experiences with
Lollypop, Quod Libet, and Amberol while offering no significant advantage over any of them. Instead, I have a music player that exactly fits only my use-case, and has
the added bonus that all the bugs are exclusively my fault :)
