# main.py
#
# Copyright 2023 Emmett de St. Croix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw, GLib

from .window import RecordBoxWindow
from .preferences import RecordBoxPreferencesWindow
from .mpris import MPRIS
from .player import Player


class RecordBoxApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self, version, app_id):
        self.version = version
        self.app_id = app_id
        self.dev = 'Devel' in app_id
        self.app_name = 'RecordBox' + (' (Devel)' if self.dev else '')
        super().__init__(
            application_id=app_id,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.set_resource_base_path('/com/github/edestcroix/RecordBox')

        GLib.set_prgname(self.app_name)
        GLib.set_application_name(self.app_name)

        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action(
            'preferences', self.on_preferences_action, ['<control>comma']
        )
        self.create_action('refresh', self.on_refresh_action, ['<control>r'])

        self.player = Player()
        MPRIS(self)
        self.settings = Gio.Settings.new('com.github.edestcroix.RecordBox')

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        if self.props.active_window:
            win = self.props.active_window
        else:
            win = RecordBoxWindow(application=self)
            if self.dev:
                win.set_css_classes(win.get_css_classes() + ['devel'])

            win.attach_to_player(self.player)
            win.set_title(self.app_name)
            self.bind_window_actions()
        win.present()

    def on_about_action(self, *_):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(
            transient_for=self.props.active_window,
            application_name=self.app_name,
            application_icon=self.app_id,
            developer_name='Emmett de St. Croix',
            version=self.version,
            developers=['Emmett de St. Croix'],
            copyright='© 2023 Emmett de St. Croix',
            website='https://github.com/edestcroix/RecordBox/',
        )
        about.present()

    def on_preferences_action(self, *_):
        """Callback for the app.preferences action."""
        preferences = RecordBoxPreferencesWindow(
            transient_for=self.props.active_window,
            application=self,
        )
        preferences.bind_settings(self.settings)
        preferences.present()

    def on_refresh_action(self, *_):
        self.props.active_window.library.sync_library(_)

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f'app.{name}', shortcuts)

    def bind_window_actions(self):
        """Bind the window's actions to accelerators."""
        self.set_accels_for_action('win.play(0)', ['<control>space'])
        self.set_accels_for_action('win.add-album', ['<control>plus'])
        self.set_accels_for_action('win.replace-queue', ['<control>minus'])

        self.set_accels_for_action(
            'win.return-to-playing', ['<control>BackSpace']
        )

        self.set_accels_for_action('win.filter-all', ['<control>slash'])

        self.set_accels_for_action('win.open-queue', ['<control>o'])
        self.set_accels_for_action('win.undo-queue', ['<control>z'])
        self.set_accels_for_action('win.redo-queue', ['<control><shift>z'])

        self.set_accels_for_action('win.exit_player', ['<control>e'])
        self.set_accels_for_action('win.stop', ['<control>period'])
        self.set_accels_for_action(
            'win.stop_after_current', ['<control>greater']
        )


def main(version, app_id):
    """The application's entry point."""
    app = RecordBoxApplication(version, app_id)
    return app.run(sys.argv)
