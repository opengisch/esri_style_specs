#!/usr/bin/env python

from struct import unpack
from color_parser import (read_color_model,
                          read_color)
import binascii

"""
Extracts a symbol from a style blob
"""


def read_string(file_handle):
    """
    From the .dot BinaryWriter code: 'This method first writes the length of the string as
    a four-byte unsigned integer, and then writes that many characters
    to the stream'
    """
    length = unpack("<I", file_handle.read(4))[0]
    buffer = file_handle.read(length)
    return buffer.decode('utf-16')

def read_object_header(handle):
    """
    Reads and interprets the header for a new object block
    """
    object_type = binascii.hexlify(handle.file_handle.read(2))
    magic_1 = binascii.hexlify(handle.file_handle.read(14))
    assert magic_1 == '147992c8d0118bb6080009ee4e41', 'Differing object header at {}, got {}'.format(hex(handle.file_handle.tell()-16),magic_1)
    handle.dive()

    # expect next byte to match current depth
    current_depth = unpack("<H", handle.file_handle.read(2))[0]
    assert current_depth == handle.depth, 'Depth marker {}, expected {}'.format(current_depth, handle.depth)

    return object_type

def create_object(handle):
    """
    Reads an object header and returns the corresponding object class
    """
    object_code = read_object_header(handle)
    object_dict = {
        '04e6': FillSymbol,
        'ffe5': MarkerSymbol,
        'fae5': LineSymbol,
        'f9e5': SimpleLineSymbolLayer,
        'fbe5': CartographicLineSymbolLayer,
        '03e6': SimpleFillSymbolLayer
    }
    assert object_code in object_dict, 'Unknown object code at {}, got {}'.format(hex(handle.file_handle.tell()-16),object_code)
    return object_dict[object_code]


def consume_padding(file_handle):
    # read padding
    last_position = file_handle.tell()
    while binascii.hexlify(file_handle.read(1)) == '00':
        last_position = file_handle.tell()
        pass
    file_handle.seek(last_position)


class SymbolLayer():
    def __init__(self):
        self.locked = False
        self.enabled = True
        self.locked = False

    def read_enabled(self, file_handle):
        enabled = unpack("<I", file_handle.read(4))[0]
        self.enabled = enabled == 1

    def read_locked(self, file_handle):
        locked = unpack("<I", file_handle.read(4))[0]
        self.locked = locked == 1


class LineSymbolLayer(SymbolLayer):
    def __init__(self):
        SymbolLayer.__init__(self)
        self.color_model = None
        self.color = None

    @staticmethod
    def create(handle):
        layer_object = create_object(handle)
        assert issubclass(layer_object, LineSymbolLayer) or issubclass(layer_object, LineSymbol), 'Expected LineSymbolLayer or LineSymbol, got {}'.format(layer_object)
        return layer_object()


class SimpleLineSymbolLayer(LineSymbolLayer):
    def __init__(self):
        LineSymbolLayer.__init__(self)
        self.width = None
        self.line_type = None

    def read(self, handle):
        unknown = binascii.hexlify(handle.file_handle.read(1))
        assert unknown == '01', 'Differing unknown byte'
        consume_padding(handle.file_handle)

        self.color_model = read_color_model(handle.file_handle)

        magic_2 = binascii.hexlify(handle.file_handle.read(18))
        assert magic_2 == 'c4e97e23d1d0118383080009b996cc010001', 'Differing magic string 2: {}'.format(magic_2)
        consume_padding(handle.file_handle)

        self.color = read_color(handle.file_handle)
        self.width = unpack("<d", handle.file_handle.read(8))[0]
        self.line_type = LineSymbol.read_line_type(handle.file_handle)

        terminator = binascii.hexlify(handle.file_handle.read(1))
        assert terminator == '0d', 'Expecting 0d terminator, got {}'.format(terminator)
        handle.rise()
        handle.file_handle.read(7)

class CartographicLineSymbolLayer(LineSymbolLayer):
    def __init__(self):
        LineSymbolLayer.__init__(self)
        self.width = None
        self.cap = None
        self.join = None
        self.offset = None

    def read_cap(self, file_handle):
        cap_bin = unpack("<B", file_handle.read(1))[0]
        if cap_bin == 0:
            self.cap = 'butt'
        elif cap_bin == 1:
            self.cap = 'round'
        elif cap_bin == 2:
            self.cap = 'square'
        else:
            assert False, 'unknown cap style {}'.format(cap_bin)

    def read_join(self, file_handle):
        join_bin = unpack("<B", file_handle.read(1))[0]
        if join_bin == 0:
            self.join = 'miter'
        elif join_bin == 1:
            self.join = 'round'
        elif join_bin == 2:
            self.join = 'bevel'
        else:
            assert False, 'unknown join style {}'.format(join_bin)

    def read(self, handle):
        unknown = binascii.hexlify(handle.file_handle.read(2))
        assert unknown == '0100', 'Differing unknown byte'

        self.read_cap(handle.file_handle)

        unknown = binascii.hexlify(handle.file_handle.read(3))
        assert unknown == '000000', 'Differing unknown string {}'.format(unknown)
        self.read_join(handle.file_handle)
        unknown = binascii.hexlify(handle.file_handle.read(3))
        assert unknown == '000000', 'Differing unknown string {}'.format(unknown)

        self.width = unpack("<d", handle.file_handle.read(8))[0]

        unknown = binascii.hexlify(handle.file_handle.read(1))
        assert unknown == '00', 'Differing unknown byte'

        self.offset= unpack("<d", handle.file_handle.read(8))[0]

        self.color_model = read_color_model(handle.file_handle)

        magic_2 = binascii.hexlify(handle.file_handle.read(18))
        assert magic_2 == 'c4e97e23d1d0118383080009b996cc010001', 'Differing magic string 1: {}'.format(magic_2)
        consume_padding(handle.file_handle)

        self.color = read_color(handle.file_handle)

        # 48 unknown bytes!
        terminator = binascii.hexlify(handle.file_handle.read(46))
        terminator = binascii.hexlify(handle.file_handle.read(1))
        assert terminator == '0d', 'Expecting 0d terminator, got {} at {}'.format(terminator, hex(handle.file_handle.tell()-1))
        handle.rise()
        handle.file_handle.read(24)


class FillSymbolLayer(SymbolLayer):
    def __init__(self):
        SymbolLayer.__init__(self)
        self.color_model = None
        self.color = None
        self.outline_layer = None
        self.outline_symbol = None

    @staticmethod
    def create(handle):
        layer_object = create_object(handle)
        assert issubclass(layer_object, FillSymbolLayer), 'Expected FillSymbolLayer, got {}'.format(layer_object)
        return layer_object()


class SimpleFillSymbolLayer(FillSymbolLayer):
    def __init__(self):
        FillSymbolLayer.__init__(self)

    def read(self, handle):
        unknown = binascii.hexlify(handle.file_handle.read(1))
        assert unknown == '01', 'Differing unknown byte'
        consume_padding(handle.file_handle)

        outline = LineSymbolLayer.create(handle)
        if isinstance(outline, LineSymbol):
            # embedded outline symbol line
            self.outline_symbol = outline
            print 'starting outline symbol at {}'.format(hex(handle.file_handle.tell()))
            self.outline_symbol.read(handle)

        else:
            self.outline_layer = outline
            self.outline_layer.read(handle)

        consume_padding(handle.file_handle)

        # sometimes an extra 02 terminator here
        start = handle.file_handle.tell()
        symbol_terminator = binascii.hexlify(handle.file_handle.read(1))
        if symbol_terminator == '02':
            consume_padding(handle.file_handle)
        else:
            handle.file_handle.seek(start)

        self.color_model = read_color_model(handle.file_handle)

        magic_2 = binascii.hexlify(handle.file_handle.read(18))
        assert magic_2 == 'c4e97e23d1d0118383080009b996cc010001', 'Differing magic string 1: {}'.format(magic_2)
        handle.file_handle.read(2)

        self.color = read_color(handle.file_handle)

        terminator = binascii.hexlify(handle.file_handle.read(1))
        assert terminator == '0d', 'Expecting 0d terminator, got {}'.format(terminator)
        handle.rise()
        handle.file_handle.read(11)


class Symbol:
    def __init__(self):
        self.levels = []

    def read(self, handle):
        unknown_b = binascii.hexlify(handle.file_handle.read(1))
        assert unknown_b == '0d', 'Differing magic string b {}'.format(unknown_b)
        handle.rise()
        consume_padding(handle.file_handle)
        self._read(handle)


class LineSymbol(Symbol):
    def __init__(self):
        Symbol.__init__(self)

    def _read(self, handle):
        number_layers = unpack("<L", handle.file_handle.read(4))[0]
        print 'detected {} layers at {}'.format(number_layers, hex(handle.file_handle.tell() - 4))

        for i in range(number_layers):
            layer = LineSymbolLayer.create(handle)
            if layer:
                layer.read(handle)
            self.levels.extend([layer])

        for l in self.levels:
            l.read_enabled(handle.file_handle)
        for l in self.levels:
            l.read_locked(handle.file_handle)

        print 'consuming padding at {}'.format(hex(handle.file_handle.tell()))
        consume_padding(handle.file_handle)

        symbol_terminator = binascii.hexlify(handle.file_handle.read(1))
        assert symbol_terminator == '02', 'Differing terminator byte, expected 02 got {}'.format(symbol_terminator)

    @staticmethod
    def read_line_type(file_handle):
        type = unpack("<I", file_handle.read(4))[0]
        types = {0: 'solid',
                 1: 'dashed',
                 2: 'dotted',
                 3: 'dash dot',
                 4: 'dash dot dot',
                 5: 'null'
                 }
        return types[type]


class FillSymbol(Symbol):
    def __init__(self):
        Symbol.__init__(self)

    def _read(self, handle):

        # consume section of unknown purpose
        self.color_model = read_color_model(handle.file_handle)
        magic_2 = binascii.hexlify(handle.file_handle.read(18))
        assert magic_2 == 'c4e97e23d1d0118383080009b996cc010001', 'Differing magic string 1: {}'.format(magic_2)

        # either before or after this unknown color?
        handle.file_handle.read(2)

        unknown_color = read_color(handle.file_handle)
        assert unknown_color['R'] == 0
        assert unknown_color['G'] == 0
        assert unknown_color['B'] == 0
        assert not unknown_color['dither']
        assert not unknown_color['is_null']

        number_layers = unpack("<L", handle.file_handle.read(4))[0]

        for i in range(number_layers):
            layer = FillSymbolLayer.create(handle)
            if layer:
                layer.read(handle)
            self.levels.extend([layer])

        for l in self.levels:
            l.read_enabled(handle.file_handle)
        for l in self.levels:
            l.read_locked(handle.file_handle)

            # symbol_terminator = binascii.hexlify(file_handle.read(1))
            # assert symbol_terminator == '02', 'Differing terminator byte, expected 02 got {}'.format(symbol_terminator)
            # consume_padding(file_handle)


class MarkerSymbol(Symbol):
    pass

class Handle:

    def __init__(self, file_handle):
        self.file_handle = file_handle
        self.depth = 1

    def dive(self):
        self.depth += 1

    def rise(self):
        self.depth -= 1



def read_symbol(file_handle):
    handle = Handle(file_handle)
    symbol_object = create_object(handle)
    assert issubclass(symbol_object,Symbol), 'Expected Symbol, got {}'.format(symbol_object)
    symbol = symbol_object()

    symbol.read(handle)
    return symbol
