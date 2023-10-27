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

from gi.repository import Gtk, Gio, Adw

from .window import RecordBoxWindow
from .preferences import RecordBoxPreferencesWindow
from .mpris import MPRIS


class RecordBoxApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id='com.github.edestcroix.RecordBox',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action, ['F10'])
        self.create_action('refresh', self.on_refresh_action, ['<primary>r'])

        self.settings = Gio.Settings.new('com.github.edestcroix.RecordBox')
        self.mpris = None

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        if self.props.active_window:
            win = self.props.active_window
        else:
            win = RecordBoxWindow(application=self)
            win.set_title('RecordBox')

            if not self.mpris:
                self.mpris = MPRIS(self)

        win.present()

    def on_about_action(self, widget, _):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(
            transient_for=self.props.active_window,
            application_name='RecordBox',
            application_icon='com.github.edestcroix.RecordBox',
            developer_name='Emmett de St. Croix',
            version='0.3.0-rc1',
            developers=['Emmett de St. Croix'],
            copyright='© 2023 Emmett de St. Croix',
            website='https://github.com/edestcroix/RecordBox/',
        )
        about.present()

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        preferences = RecordBoxPreferencesWindow(
            transient_for=self.props.active_window,
            application=self,
        )
        preferences.bind_settings(self.settings)
        preferences.present()

    def on_refresh_action(self, widget, _):
        self.props.active_window.sync_library(_)

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

    def player(self):
        """Return the application's player object."""
        return self.props.active_window.main_view.player


def main(version):
    """The application's entry point."""
    app = RecordBoxApplication()
    return app.run(sys.argv)
