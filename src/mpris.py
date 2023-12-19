from gi.repository import Gio, GLib
from .player import LoopMode, PlayerState
from random import randint

import logging

# logging.basicConfig(level=logging.DEBUG)

# full credit for the bulk of this MPRIS implementation goes to Lollyop
# at https://gitlab.gnome.org/World/lollypop/-/blob/master/lollypop/mpris.py
class Server:
    def __init__(self, con, path):
        method_outargs = {}
        method_inargs = {}
        for interface in Gio.DBusNodeInfo.new_for_xml(self.__doc__).interfaces:

            for method in interface.methods:
                out_args = (
                    f'({"".join([arg.signature for arg in method.out_args])})'
                )
                method_outargs[method.name] = out_args
                method_inargs[method.name] = tuple(
                    arg.signature for arg in method.in_args
                )

            con.register_object(
                object_path=path,
                interface_info=interface,
                method_call_closure=self.on_method_call,
            )

        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

    def on_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):

        args = list(parameters.unpack())
        for i, sig in enumerate(self.method_inargs[method_name]):
            if sig == 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        try:
            result = getattr(self, method_name)(*args)
            result = (result,)
            out_args = self.method_outargs[method_name]
            if out_args != '()':
                variant = GLib.Variant(out_args, result)
                invocation.return_value(variant)
            else:
                invocation.return_value(None)
        except Exception as e:
            logging.error(f'Error: {e}')
            invocation.return_gerror(
                GLib.G_DBUS_ERROR, GLib.G_DBUS_ERROR_FAILED, str(e)
            )


class MPRIS(Server):
    """
    <!DOCTYPE node PUBLIC
    "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
    "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
    <node>
        <interface name="org.freedesktop.DBus.Introspectable">
            <method name="Introspect">
                <arg name="data" direction="out" type="s"/>
            </method>
        </interface>
        <interface name="org.freedesktop.DBus.Properties">
            <method name="Get">
                <arg name="interface" direction="in" type="s"/>
                <arg name="property" direction="in" type="s"/>
                <arg name="value" direction="out" type="v"/>
            </method>
            <method name="Set">
                <arg name="interface_name" direction="in" type="s"/>
                <arg name="property_name" direction="in" type="s"/>
                <arg name="value" direction="in" type="v"/>
            </method>
            <method name="GetAll">
                <arg name="interface" direction="in" type="s"/>
                <arg name="properties" direction="out" type="a{sv}"/>
            </method>
        </interface>
        <interface name="org.mpris.MediaPlayer2">
            <method name="Raise">
            </method>
            <method name="Quit">
            </method>
            <property name="CanQuit" type="b" access="read" />
            <property name="Fullscreen" type="b" access="readwrite" />
            <property name="CanSetFullscreen" type="b" access="read" />
            <property name="CanRaise" type="b" access="read" />
            <property name="HasTrackList" type="b" access="read"/>
            <property name="Identity" type="s" access="read"/>
            <property name="DesktopEntry" type="s" access="read"/>
            <property name="SupportedUriSchemes" type="as" access="read"/>
            <property name="SupportedMimeTypes" type="as" access="read"/>
        </interface>
        <interface name="org.mpris.MediaPlayer2.Player">
            <method name="Next"/>
            <method name="Previous"/>
            <method name="Pause"/>
            <method name="PlayPause"/>
            <method name="Stop"/>
            <method name="Play"/>
            <method name="Seek">
                <arg direction="in" name="Offset" type="x"/>
            </method>
            <method name="SetPosition">
                <arg direction="in" name="TrackId" type="o"/>
                <arg direction="in" name="Position" type="x"/>
            </method>
            <method name="OpenUri">
                <arg direction="in" name="Uri" type="s"/>
            </method>
            <signal name="Seeked">
                <arg name="Position" type="x"/>
            </signal>
            <property name="PlaybackStatus" type="s" access="read"/>
            <property name="LoopStatus" type="s" access="readwrite"/>
            <property name="Rate" type="d" access="readwrite"/>
            <property name="Shuffle" type="b" access="readwrite"/>
            <property name="Metadata" type="a{sv}" access="read"/>
            <property name="Volume" type="d" access="readwrite"/>
            <property name="Position" type="x" access="read"/>
            <property name="MinimumRate" type="d" access="read"/>
            <property name="MaximumRate" type="d" access="read"/>
            <property name="CanGoNext" type="b" access="read"/>
            <property name="CanGoPrevious" type="b" access="read"/>
            <property name="CanPlay" type="b" access="read"/>
            <property name="CanPause" type="b" access="read"/>
            <property name="CanSeek" type="b" access="read"/>
            <property name="CanControl" type="b" access="read"/>
        </interface>
    </node>
    """

    _MPRIS_IFACE = 'org.mpris.MediaPlayer2'
    _MPRIS_PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
    _MPRIS_RECORDBOX = 'org.mpris.MediaPlayer2.RecordBox'
    _MPRIS_PATH = '/org/mpris/MediaPlayer2'

    _MPRIS_PROPERTIES = (
        'CanQuit',
        'CanRaise',
        'HasTrackList',
        'CanSetFullscreen',
        'Identity',
        'DesktopEntry',
        'SupportedUriSchemes',
        'SupportedMimeTypes',
    )
    _MPRIS_PLAYER_PROPERTIES = (
        'PlaybackStatus',
        'LoopStatus',
        'Rate',
        'Shuffle',
        'Metadata',
        'Volume',
        'Position',
        'MinimumRate',
        'MaximumRate',
        'CanGoNext',
        'CanGoPrevious',
        'CanPlay',
        'CanPause',
        'CanSeek',
        'CanControl',
    )

    def __init__(self, app):
        self._app = app
        self._player = app.player
        self._volume = 0.0
        self._metadata = {
            'mpris:trackid': GLib.Variant(
                'o', '/org/mpris/MediaPlayer2/NoTrack'
            )
        }
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(
            self._bus,
            self._MPRIS_RECORDBOX,
            Gio.BusNameOwnerFlags.NONE,
            None,
            None,
        )
        Server.__init__(self, self._bus, self._MPRIS_PATH)

        self._player.connect('stream-start', self._on_current_changed)
        self._player.connect('state-changed', self._on_state_changed)
        self._player.connect('seeked', self._on_seeked)
        self._player.connect('notify::volume', self._on_volume_changed)
        self._player.connect('notify::loop', self._on_loop_changed)
        self._player.connect('eos', self._on_eos)

    def Raise(self):
        self._app.props.active_window.present()

    def Quit(self):
        self._app.quit()

    def Next(self):
        playing = self._player.state == PlayerState.PLAYING
        self._player.go_next()
        if not playing:
            self._player.toggle()

    def Previous(self):
        playing = self._player.state == PlayerState.PLAYING
        self._player.go_previous()
        if not playing:
            self._player.toggle()

    def Pause(self):
        if self._player.state == PlayerState.PLAYING:
            self._player.toggle()

    def PlayPause(self):
        self._player.toggle()

    def Stop(self):
        self._player.stop()

    def Play(self):
        if self._player.state == PlayerState.PAUSED:
            self._player.toggle()

    def OpenUri(self, uri):
        pass

    def Seek(self, offset):
        offset = offset * 1000
        position = self._player.position
        duration = self._player.duration
        logging.debug(f'Seek: {offset} from {position}')
        if position + offset > duration:
            self._player.go_next()
        elif position + offset < 0:
            self._player.go_previous()
        else:
            self._player.position = position + offset

    def Seeked(self, position):
        logging.debug(f'Seeked: {position / 1000}')
        self._bus.emit_signal(
            None,
            self._MPRIS_PATH,
            self._MPRIS_PLAYER_IFACE,
            'Seeked',
            GLib.Variant.new_tuple(GLib.Variant('x', position / 1000)),
        )

    def Get(self, interface, property_name):
        logging.debug(f'Get: {interface} {property_name}')

        match property_name:
            case 'CanQuit' | 'CanRaise' | 'CanSeek' | 'CanControl':
                return GLib.Variant('b', True)
            case 'CanSetFullscreen' | 'Fullscreen' | 'HasTrackList' | 'Shuffle':
                return GLib.Variant('b', False)
            case 'Identity':
                return GLib.Variant('s', 'RecordBox')
            case 'DesktopEntry':
                return GLib.Variant('s', 'com.github.edestcroix.RecordBox')
            case 'SupportedUriSchemes':
                return GLib.Variant('as', ['file'])
            case 'SupportedMimeTypes':
                return GLib.Variant(
                    'as',
                    [
                        'application/ogg',
                        'audio/x-vorbis+ogg',
                        'audio/x-flac',
                        'audio/mpeg',
                    ],
                )
            case 'CanGoNext' | 'CanGoPrevious' | 'CanPlay' | 'CanPause':
                return GLib.Variant(
                    'b', self._player.current_track is not None
                )
            case 'Rate' | 'MinimumRate' | 'MaximumRate':
                return GLib.Variant('d', 1.0)
            case 'PlaybackStatus':
                return GLib.Variant('s', self._get_status())
            case 'LoopStatus':
                return GLib.Variant('s', self._player.loop.capitalize())
            case 'Metadata':
                return GLib.Variant('a{sv}', self._metadata)
            case 'Volume':
                return GLib.Variant('d', self._player.volume)
            case 'Position':
                return GLib.Variant('x', self._player.position / 1000)
            case _:
                logging.warning(f'Unknown: {property_name} for {interface})')
                return GLib.Variant('s', 'Unknown')

    def GetAll(self, interface):
        ret = {}
        match interface:
            case self._MPRIS_IFACE:
                for property_name in self._MPRIS_PROPERTIES:
                    ret[property_name] = self.Get(interface, property_name)
            case self._MPRIS_PLAYER_IFACE:
                for property_name in self._MPRIS_PLAYER_PROPERTIES:
                    ret[property_name] = self.Get(interface, property_name)
        return ret

    def Set(self, _, property_name, new_value):
        logging.debug(f'Set: {property_name} {new_value}')
        if property_name == 'LoopStatus':
            self._player.loop = LoopMode(new_value.lower())

        elif property_name == 'Volume':
            self._player.volume = new_value

    def PropertiesChanged(
        self, interface_name, changed_properties, invalidated_properties
    ):
        logging.debug(
            f'PropertiesChanged: {interface_name} {changed_properties} {invalidated_properties}'
        )
        self._bus.emit_signal(
            None,
            self._MPRIS_PATH,
            'org.freedesktop.DBus.Properties',
            'PropertiesChanged',
            GLib.Variant.new_tuple(
                GLib.Variant('s', interface_name),
                GLib.Variant('a{sv}', changed_properties),
                GLib.Variant('as', invalidated_properties),
            ),
        )

    def Introspect(self):
        return self.__doc__

    ## End of spec methods

    ## Private methods

    def _get_status(self):
        return self._player.state.capitalize()

    def _update_metadata(self):
        self._metadata = {}
        if self._player.current_track is None:
            self._metadata = {
                'mpris:trackid': GLib.Variant(
                    'o', '/org/mpris/MediaPlayer2/TrackList/NoTrack'
                )
            }
        else:
            self._build_metadata()

    def _build_metadata(self):
        current_track = self._player.current_track
        if not (track_number := current_track.track):
            track_number = 1
        self._metadata = {
            'mpris:trackid': GLib.Variant('o', self._track_id()),
            'xesam:trackNumber': GLib.Variant('i', track_number),
            'xesam:title': GLib.Variant('s', current_track.raw_title),
            'xesam:album': GLib.Variant('s', current_track.album),
            'xesam:artist': GLib.Variant('as', (current_track.albumartist,)),
            'mpris:length': GLib.Variant('x', self._length()),
            'xesam:url': GLib.Variant('s', f'file://{current_track.path}'),
        }
        cover_path = current_track.cover
        if cover_path is not None:
            self._metadata['mpris:artUrl'] = GLib.Variant(
                's', f'file://{cover_path}'
            )

    def _track_id(self):
        track_id = randint(1000, 1000000000)
        return f'/org/mpris/MediaPlayer2/Track{track_id}'

    def _length(self):
        return self._player.duration / 1000

    def _on_seeked(self, _, position):
        self.Seeked(position / 1000)

    def _on_volume_changed(self, _, __):
        volume = self._player.volume
        if self._volume == volume:
            return
        self._volume = volume
        volume = GLib.Variant('d', volume)
        self.PropertiesChanged(
            self._MPRIS_PLAYER_IFACE, {'Volume': volume}, []
        )

    def _on_loop_changed(self, _, __):
        loop = GLib.Variant('s', self._player.loop.capitalize())
        self.PropertiesChanged(
            self._MPRIS_PLAYER_IFACE, {'LoopStatus': loop}, []
        )

    def _on_current_changed(self, _):
        self._update_metadata()
        properties = {
            'Metadata': GLib.Variant('a{sv}', self._metadata),
            'CanPlay': GLib.Variant('b', True),
            'CanPause': GLib.Variant('b', True),
            'CanGoNext': GLib.Variant('b', True),
            'CanGoPrevious': GLib.Variant('b', True),
            'PlaybackStatus': GLib.Variant('s', self._get_status()),
        }
        try:
            self.PropertiesChanged(self._MPRIS_PLAYER_IFACE, properties, [])
        except Exception as e:
            print(f'MPRIS::__on_current_changed(): {e}')

    def _on_state_changed(self, *_):
        if self._player.current_track is None:
            properties = {
                'Metadata': GLib.Variant('a{sv}', self._metadata),
                'CanPlay': GLib.Variant('b', False),
                'CanPause': GLib.Variant('b', False),
                'CanGoNext': GLib.Variant('b', False),
                'CanGoPrevious': GLib.Variant('b', False),
                'PlaybackStatus': GLib.Variant('s', self._get_status()),
            }
        else:
            properties = {
                'PlaybackStatus': GLib.Variant('s', self._get_status())
            }
        self.PropertiesChanged(self._MPRIS_PLAYER_IFACE, properties, [])

    def _on_eos(self, *_):
        self._update_metadata()
        properties = {
            'Metadata': GLib.Variant('a{sv}', self._metadata),
            'PlaybackStatus': GLib.Variant('s', self._get_status()),
        }
        self.PropertiesChanged(self._MPRIS_PLAYER_IFACE, properties, [])
