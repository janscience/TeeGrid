# https://github.com/pyserial/pyserial
try:
    from serial import Serial
    from serial.tools.list_ports import comports
    from serial.serialutil import SerialException
except ImportError:
    print('ERROR: failed to import serial module !')
    print('You need to install the pyserial package using')
    print('> pip install pyserial')
    exit()
    
# https://github.com/pyusb/pyusb
# pip install pyusb
try:
    import usb.core
except ImportError:
    print('ERROR: failed to import usb module !')
    print('You need to install the pyusb package using')
    print('> pip install pyusb')
    exit()
    
import sys
import numpy as np
from scipy.signal import welch
from abc import ABC, abstractmethod
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QObject, QTimer, QElapsedTimer, QDateTime, QLocale
from PyQt5.QtGui import QKeySequence, QFont, QPalette, QColor, QValidator
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtWidgets import QStackedWidget, QLabel, QScrollArea
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout, QSpacerItem
from PyQt5.QtWidgets import QWidget, QFrame, QPushButton, QSizePolicy
from PyQt5.QtWidgets import QAction, QShortcut
from PyQt5.QtWidgets import QCheckBox, QLineEdit, QComboBox
from PyQt5.QtWidgets import QSpinBox, QAbstractSpinBox
from PyQt5.QtWidgets import QFileDialog
try:
    import pyqtgraph as pg
except ImportError:
    print('ERROR: failed to import pyqtgraph module !')
    print('Install it using')
    print('> pip install pyqtgraph')
    exit()


__version__ = '1.1'


def parse_number(s):
    """Parse string with number and unit.

    From https://github.com/bendalab/audioio/blob/master/src/audioio/audiometadata.py
    
    Parameters
    ----------
    s: str, float, or int
        String to be parsed. The initial part of the string is
        expected to be a number, the part following the number is
        interpreted as the unit. If float or int, then return this
        as the value with empty unit.

    Returns
    -------
    v: None, int, or float
        Value of the string as float. Without decimal point, an int is returned.
        If the string does not contain a number, None is returned.
    u: str
        Unit that follows the initial number.
    n: int
        Number of digits behind the decimal point.
    """
    n = len(s)
    ip = n
    have_point = False
    for i in range(len(s)):
        if s[i] == '.':
            if have_point:
                n = i
                break
            have_point = True
            ip = i + 1
        if not s[i] in '0123456789.+-':
            n = i
            break
    if n == 0:
        return None, s, 0
    v = float(s[:n]) if have_point else int(s[:n])
    u = s[n:].strip()
    nd = n - ip if n >= ip else 0
    return v, u, nd


unit_prefixes = {'Deka': 1e1, 'deka': 1e1, 'Hekto': 1e2, 'hekto': 1e2,
                 'kilo': 1e3, 'Kilo': 1e3, 'Mega': 1e6, 'mega': 1e6,
                 'Giga': 1e9, 'giga': 1e9, 'Tera': 1e12, 'tera': 1e12, 
                 'Peta': 1e15, 'peta': 1e15, 'Exa': 1e18, 'exa': 1e18, 
                 'Dezi': 1e-1, 'dezi': 1e-1, 'Zenti': 1e-2, 'centi': 1e-2,
                 'Milli': 1e-3, 'milli': 1e-3, 'Micro': 1e-6, 'micro': 1e-6, 
                 'Nano': 1e-9, 'nano': 1e-9, 'Piko': 1e-12, 'piko': 1e-12, 
                 'Femto': 1e-15, 'femto': 1e-15, 'Atto': 1e-18, 'atto': 1e-18, 
                 'da': 1e1, 'h': 1e2, 'K': 1e3, 'k': 1e3, 'M': 1e6,
                 'G': 1e9, 'T': 1e12, 'P': 1e15, 'E': 1e18, 
                 'd': 1e-1, 'c': 1e-2, 'mu': 1e-6, 'u': 1e-6, 'm': 1e-3,
                 'n': 1e-9, 'p': 1e-12, 'f': 1e-15, 'a': 1e-18}
""" SI prefixes for units with corresponding factors. """


def change_unit(val, old_unit, new_unit):
    """Scale numerical value to a new unit.

    From https://github.com/bendalab/audioio/blob/master/src/audioio/audiometadata.py
    which is adapted from https://github.com/relacs/relacs/blob/1facade622a80e9f51dbf8e6f8171ac74c27f100/options/src/parameter.cc#L1647-L1703

    Parameters
    ----------
    val: float
        Value given in `old_unit`.
    old_unit: str
        Unit of `val`.
    new_unit: str
        Requested unit of return value.

    Returns
    -------
    new_val: float
        The input value `val` scaled to `new_unit`.

    Examples
    --------

    ```
    >>> from audioio import change_unit
    >>> change_unit(5, 'mm', 'cm')
    0.5

    >>> change_unit(5, '', 'cm')
    5.0

    >>> change_unit(5, 'mm', '')
    5.0

    >>> change_unit(5, 'cm', 'mm')
    50.0

    >>> change_unit(4, 'kg', 'g')
    4000.0

    >>> change_unit(12, '%', '')
    0.12

    >>> change_unit(1.24, '', '%')
    124.0

    >>> change_unit(2.5, 'min', 's')
    150.0

    >>> change_unit(3600, 's', 'h')
    1.0

    ```

    """
    # missing unit?
    if not old_unit and not new_unit:
        return val
    if not old_unit and new_unit != '%':
        return val
    if not new_unit and old_unit != '%':
        return val

    # special units that directly translate into factors:
    unit_factors = {'%': 0.01, 'hour': 60.0*60.0, 'h': 60.0*60.0, 'min': 60.0}

    # parse old unit:
    f1 = 1.0
    if old_unit in unit_factors:
        f1 = unit_factors[old_unit]
    else:
        for k in unit_prefixes:
            if len(old_unit) > len(k) and old_unit[:len(k)] == k:
                f1 = unit_prefixes[k]
  
    # parse new unit:
    f2 = 1.0
    if new_unit in unit_factors:
        f2 = unit_factors[new_unit]
    else:
        for k in unit_prefixes:
            if len(new_unit) > len(k) and new_unit[:len(k)] == k:
                f2 = unit_prefixes[k]
  
    return val*f1/f2


def get_teensy_model(vid, pid, serial_number):
    
    # map bcdDevice of USB device to Teensy model version:
    teensy_model = {   
        0x274: '30',
        0x275: '31',
        0x273: 'LC',
        0x276: '35',
        0x277: '36',
        0x278: '40 beta',
        0x279: '40',
        0x280: '41',
        0x281: 'MM'}

    dev = usb.core.find(idVendor=vid, idProduct=pid,
                        serial_number=serial_number)
    if dev is None:
        # this happens when we do not have permissions for the device!
        return ''
    else:
        return teensy_model[dev.bcdDevice]


def discover_teensy_ports():
    devices = []
    serial_numbers = []
    models = []
    for port in sorted(comports(False)):
        if port.vid is None and port.pid is None:
            continue
        #if port.vid == 0x16C0 and port.pid in [0x0483, 0x048B, 0x048C, 0x04D5]:
        if port.manufacturer == 'Teensyduino':
            teensy_model = get_teensy_model(port.vid, port.pid,
                                            port.serial_number)
            # TODO: we should also check for permissions!
            devices.append(port.device)
            serial_numbers.append(port.serial_number)
            models.append(teensy_model)
    return devices, models, serial_numbers


class ScanLogger(QLabel):

    sigLoggerFound = Signal(object, object, object)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText('Scanning for loggers ...\nPlease connect a logger to an USB port.')
        self.setAlignment(Qt.AlignCenter)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scan)
        self.start()

    def start(self):
        self.timer.start(50)

    def scan(self):
        devices, models, serial_numbers = discover_teensy_ports()
        if len(devices) > 0:
            self.timer.stop()
            self.sigLoggerFound.emit(devices[0],
                                     models[0],
                                     serial_numbers[0])

            
class Interactor(ABC):

    sigReadRequest = Signal(object, str, list, list)
    sigWriteRequest = Signal(str, list)
    sigTransmitRequest = Signal(object, str, list)
    sigDisplayTerminal = Signal(str, object)
    sigDisplayMessage = Signal(object)
    sigUpdate = Signal()

    @abstractmethod
    def setup(self, menu):
        pass

    def retrieve(self, key, menu, verbose=True):
        
        def find(keys, menu, ids):
            found = False
            for mk in menu:
                if keys[0] in mk.lower():
                    found = True
                    menu_item = menu[mk]
                    ids.append(menu_item[0])
                    if len(keys) > 1:
                        if menu_item[1] == 'menu' and \
                           find(keys[1:], menu_item[2], ids):
                            if len(menu_item[2]) == 0:
                                menu.pop(mk)
                            return True
                    else:
                        menu.pop(mk)
                        return True
                    break
            if not found:
                for mk in menu:
                    menu_item = menu[mk]
                    ids.append(menu_item[0])
                    if menu_item[1] == 'menu' and \
                       find(keys, menu_item[2], ids):
                        if len(menu_item[2]) == 0:
                            menu.pop(mk)
                        return True
                    ids.pop()
            return False

        keys = [k.strip() for k in key.split('>') if len(k.strip()) > 0]
        ids = []
        if find(keys, menu, ids):
            return ids
        elif verbose:
            print(key, 'not found')
        return []

    @abstractmethod
    def read(self, ident, stream, success):
        pass

        
class InteractorQObject(type(Interactor), type(QObject)):
    # this class is needed for multiple inheritance of ABC ...
    pass

        
class InteractorQWidget(type(Interactor), type(QWidget)):
    # this class is needed for multiple inheritance of ABC ...
    pass

        
class InteractorQFrame(type(Interactor), type(QFrame)):
    # this class is needed for multiple inheritance of ABC ...
    pass

        
class InteractorQPushButton(type(Interactor), type(QPushButton)):
    # this class is needed for multiple inheritance of ABC ...
    pass


class RTClock(Interactor, QWidget, metaclass=InteractorQWidget):
    
    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.time = QLabel(self)
        self.state = QLabel(self)
        self.state.setTextFormat(Qt.RichText)
        self.state.setToolTip('Indicate whether real-time clock matches computer clock')
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.addWidget(self.time)
        self.box.addWidget(self.state)
        self.start_get = []
        self.start_set = []
        self.set_count = 50
        self.set_state = 0
        self.prev_time = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.get_time)
    
    def setup(self, menu):
        self.retrieve('date & time>report', menu)   # not needed
        self.start_get = self.retrieve('date & time>print', menu)
        self.start_set = self.retrieve('date & time>set', menu)

    def start(self):
        self.set_state = -1
        self.set_count = 40  # wait 2 secs before setting the clock
        if len(self.start_get) > 0:
            self.timer.start(50)

    def stop(self):
        self.timer.stop()

    def get_time(self):
        if self.set_state > 0:
            self.set_time()
        else:            
            self.set_count -= 1
            if self.set_count == 0:
                self.set_state = 1
                self.set_time()
            else:
                self.prev_time = QDateTime.currentDateTime().toString(Qt.ISODate)
                self.sigReadRequest.emit(self, 'rtclock',
                                         self.start_get, ['select'])

    def read(self, ident, stream, success):
        if ident != 'rtclock':
            return
        for s in stream:
            if 'current time' in s.lower():
                next_time = QDateTime.currentDateTime().toString(Qt.ISODate)
                time = ':'.join(s.strip().split(':')[1:]).strip()
                if len(time.strip()) == 19:
                    self.time.setText('<b>' + time.replace('T', '  ') + '</b>')
                    if time == next_time or time == self.prev_time:
                        self.state.setText('&#x2705;')
                        if self.set_state >= 0:
                            self.set_count = 0
                    else:
                        self.state.setText('&#x274C;')
                        if self.set_state >= 0:
                            self.set_count = 1
                    break

    def set_time(self):
        if len(self.start_set) == 0:
            self.set_state = 0
            self.prev_time = None
            return
        if self.set_state == 1:
            self.prev_time = QDateTime.currentDateTime().toString(Qt.ISODate)
            self.set_state = 2
            self.timer.setInterval(1)
        elif self.set_state == 2:
            time = QDateTime.currentDateTime().toString(Qt.ISODate)
            if time != self.prev_time:
                self.sigWriteRequest.emit(time, self.start_set)
                self.set_state = 0
                self.prev_time = None
                self.timer.setInterval(50)

                
class ReportButton(Interactor, QPushButton, metaclass=InteractorQPushButton):
    
    def __init__(self, key, text, *args, **kwargs):
        super(QPushButton, self).__init__(*args, **kwargs)
        self.setText(text)
        self.clicked.connect(self.run)
        self.key = key
        self.start = []

    def setText(self, text):
        super().setText(text)
        bbox = self.fontMetrics().boundingRect(text)
        self.setMaximumWidth(bbox.width() + 10)
        self.setMaximumHeight(bbox.height() + 2)

    def set_button_color(self, color):
       pal = self.palette()
       pal.setColor(QPalette.Button, QColor(color))
       self.setAutoFillBackground(True)
       self.setPalette(pal)
       self.update()
     
    def setup(self, menu):
        self.start = self.retrieve(self.key, menu)

    def run(self):
        self.sigReadRequest.emit(self, 'run', self.start, ['select'])

                
class PSRAMTest(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('psram memory test', 'Test', *args, **kwargs)
        
    def read(self, ident, stream, success):
        title = None
        text = ''
        test = None
        for k in range(len(stream)):
            if title is None:
                if 'extmem memory test' in stream[k].lower():
                    title = stream[k].strip()
            else:
                text += stream[k].rstrip()
                text += '\n'
                if 'test ran' in stream[k].lower():
                    test = k + 1
                elif test is not None and k == test:
                    if 'all memory tests passed' in stream[k].lower():
                        self.setText('passed')
                        self.set_button_color(Qt.green)
                    else:
                        self.setText('failed')
                        self.set_button_color(Qt.red)
                    break
        self.sigDisplayTerminal.emit(title, text)


class LoggerInfo(Interactor, QFrame, metaclass=InteractorQFrame):
    
    def __init__(self, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.rtclock = RTClock(self)
        self.box = QGridLayout(self)
        title = QLabel('<b>Logger</b>', self)
        title.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(title, 0, 0, 1, 3)
        self.box.setRowStretch(0, 1)
        self.psramtest = PSRAMTest(self)
        self.psramtest.setToolTip('Test PSRAM memory (Ctrl+P)')
        self.psramtest.setVisible(False)
        key = QShortcut("CTRL+P", self)
        key.activated.connect(self.psramtest.animateClick)
        self.device = None
        self.model = None
        self.serial_number = None
        self.controller_start_get = []
        self.psram_start_get = []
        self.device_id_start_get = []
        self.device_id = []
        self.ampl_start_get = []
        self.eeprom_hexdump_start_get = []
        self.row = 1

    def set(self, device, model, serial_number):
        self.device = device
        self.model = model
        self.serial_number = serial_number

    def setup(self, menu):
        self.rtclock.setup(menu)
        self.controller_start_get = self.retrieve('teensy info', menu)
        self.psram_start_get = self.retrieve('psram memory info', menu)
        self.psramtest.setup(menu)
        self.device_id_start_get = self.retrieve('device id', menu)
        self.ampl_start_get = self.retrieve('amplifier board', menu)
        self.eeprom_hexdump_start_get = self.retrieve('eeprom memory content', menu)

    def add(self, label, value, button=None):
        self.box.addItem(QSpacerItem(0, 0,
                                     QSizePolicy.Policy.Minimum,
                                     QSizePolicy.Policy.Expanding),
                         self.row, 0)
        self.row += 1
        lw = QLabel(label, self)
        lw.setSizePolicy(QSizePolicy.Policy.Preferred,
                         QSizePolicy.Policy.Fixed)
        self.box.addWidget(lw, self.row, 0)
        vw = QLabel('<b>' + value + '</b>', self)
        vw.setSizePolicy(QSizePolicy.Policy.Preferred,
                         QSizePolicy.Policy.Fixed)
        if button is None:
            self.box.addWidget(vw, self.row, 1, 1, 2)
        else:
            self.box.addWidget(vw, self.row, 1)
            self.box.addWidget(button, self.row, 2, Qt.AlignRight)
        self.box.setRowStretch(self.row, 1)
        self.row += 1
        return vw
        
    def start(self):
        self.row = 1
        self.sigReadRequest.emit(self, 'amplifier',
                                 self.ampl_start_get, ['select'])
        #self.add('Device', self.device)  # name of USB device in operating system
        self.sigReadRequest.emit(self, 'controller',
                                 self.controller_start_get, ['select'])
        self.sigReadRequest.emit(self, 'psram',
                                 self.psram_start_get, ['select'])
        self.sigReadRequest.emit(self, 'deviceidsetup',
                                 self.device_id_start_get, ['select'])

    def read(self, ident, stream, success):
        if 'eepromhexdump' in ident:
            for i in range(10, len(stream)):
                if len(stream[i].strip()) == 0:
                    del stream[i:]
                    self.sigDisplayTerminal.emit('EEPROM memory', stream)
                    break
            return
        if 'deviceid' in ident:
            while len(stream) > 0 and len(stream[0].strip()) == 0:
                del stream[0]
            deviceid = False
            value = 'None'
            source = ''
            for s in stream:
                if 'device identifier' in s.lower():
                    deviceid = True
                else:
                    ss = s.split(':')
                    if 'value' in ss[0].lower():
                        value = ss[1].split()[0].strip()
                    elif 'source' in ss[0].lower():
                        source = ss[1].strip()
                    else:
                        break
            if deviceid:
                if ident == 'deviceidsetup':
                    if value == 'None':
                        self.device_id = self.add('Device ID', value)
                    else:
                        button = QPushButton('Get')
                        bbox = self.fontMetrics().boundingRect(button.text())
                        button.setMaximumWidth(bbox.width() + 10)
                        button.setMaximumHeight(bbox.height() + 2)
                        button.setToolTip('Get device ID (Ctrl+G)')
                        button.clicked.connect(self.get_device_id)
                        key = QShortcut('Ctrl+G', self)
                        key.activated.connect(button.animateClick)
                        self.device_id = self.add('Device ID', value, button)
                else:
                    self.device_id.setText('<b>' + value + '</b>')
            return
        r = 0
        for s in stream:
            if r > 0 and len(s.strip()) == 0:
                break
            x = s.split(':')
            if len(x) < 2 or len(x[1].strip()) == 0:
                continue
            r += 1
            label = x[0].strip()
            value = ':'.join(x[1:]).strip()
            if ident == 'psram':
                if label.lower() == 'size':
                    self.psramtest.setVisible(True)
                    self.add('<u>P</u>SRAM size', value, self.psramtest)
                else:
                    continue
            elif label.lower() == 'eeprom size':
                button = QPushButton('Hexdump')
                bbox = self.fontMetrics().boundingRect(button.text())
                button.setMaximumWidth(bbox.width() + 10)
                button.setMaximumHeight(bbox.height() + 2)
                button.setToolTip('Hexdump of EEPROM memory (Ctrl+H)')
                button.clicked.connect(self.get_eeprom_hexdump)
                key = QShortcut('Ctrl+H', self)
                key.activated.connect(button.animateClick)
                self.add(label, value, button)
            elif label.lower() != 'mac address':
                self.add(label, value)
        if ident == 'psram':
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.row += 1
            lw = QLabel('Time', self)
            lw.setSizePolicy(QSizePolicy.Policy.Preferred,
                             QSizePolicy.Policy.Fixed)
            self.box.addWidget(lw, self.row, 0)
            self.box.addWidget(self.rtclock, self.row, 1, 1, 2)
            self.box.setRowStretch(self.row, 1)
            self.row += 1
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.rtclock.start()

    def get_device_id(self):
        self.sigReadRequest.emit(self, 'deviceid',
                                 self.device_id_start_get, ['select'])

    def get_eeprom_hexdump(self):
        self.sigReadRequest.emit(self, 'eepromhexdump',
                                 self.eeprom_hexdump_start_get, ['select'])


class SoftwareInfo(QLabel):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def set(self, stream):
        text = '<style type="text/css"> th, td { padding: 0 15px; }</style>'
        text += '<table>'
        libs = False
        n = 0
        for s in stream:
            s = s.strip()
            if len(s) > 0:
                if n == 0:
                    text += f'<tr><td colspan=2><b>{s}</b></td></tr>'
                else:
                    if not libs:
                        text += '<tr><td>based on</td>'
                        libs = True
                    else:
                        text += '<tr><td></td>'
                    s = s.replace('based on ', '')
                    s = s.replace('and ', '')
                    text += f'<td><b>{s}</b></td></tr>'
                n += 1
        text += '</table>'
        self.setText(text)

                
class CheckSDCard(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('sd card check', 'Check',
                         *args, **kwargs)
        
    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        present = False
        text = ''
        for s in stream:
            if len(s.strip()) == 0:
                break
            text += s
            text += '\n'
            if 'present and writable' in s:
                present = True
                self.set_button_color(Qt.green)
        if success and not present:
            self.set_button_color(Qt.red)
        self.sigDisplayTerminal.emit('Check SD card', text)

                
class FormatSDCard(ReportButton):
    
    def __init__(self, key, text, *args, **kwargs):
        super().__init__(key, text, *args, **kwargs)
        
    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        for k in range(len(stream)):
            if stream[k].lower().startswith('read file'):
                i = stream[k].lower().find('on sd card ...')
                if i > 0 and i + 14 < len(stream[k]):
                    stream.insert(k + 1, stream[k][i + 14:])
                    stream.insert(k + 1, '')
                    stream[k] = stream[k][:i + 14]
            elif stream[k].lower().startswith('done.') and len(stream[k]) > 5:
                stream.insert(k + 1, stream[k][5:])
                stream.insert(k + 1, '')
                stream[k] = stream[k][:5]
            elif stream[k].rstrip().lower().endswith('sd card:'):
                while len(stream) > 0 and len(stream) >= k:
                    del stream[-1]
                break
        if len(stream) == 0:
            return
        if 'erase' in self.text().lower():
            title = 'Erase and format SD card'
        else:
            title = 'Format SD card'
        self.sigDisplayTerminal.emit(title, stream)
        if success:
            self.sigUpdate.emit()

                
class ListFiles(ReportButton):
    
    def __init__(self, name='List', *args, **kwargs):
        super().__init__('', name, *args, **kwargs)

    def setup(self, start):
        self.start = start
        
    def read(self, ident, stream, success):
        if len(stream) == 0:
            return
        title = None
        next_dir = False
        remove_dir = 0
        text = '<style type="text/css"> th, td { padding: 0 15px; }</style>'
        text += '<table>'
        for s in stream:
            if title is None:
                if 'does not exist' in s.lower():
                    self.sigDisplayMessage.emit(s)
                    return
                if s.lower().strip().startswith('files on') or \
                   s.lower().strip().startswith('files in') or \
                   s.lower().strip().startswith('erase all files in'):
                    title = s
                    if s.lower().strip().startswith('erase all files in'):
                        remove_dir = 1
            else:
                if ' name' in s.lower():
                    text += f'<tr><th align="right">size (bytes)</th><th align="left">name</th></tr>'
                elif 'files in' in s.lower():
                    ns = ''
                    if 'newest' in s.lower():
                        path = s[9:].strip()[1:-11]
                        ns = '<b>*</b> '
                    else:
                        path = s[9:].strip()[1:-2]
                    if len(path) > 0 and path[-1] != '/':
                        path += '/'
                    text += f'<tr><td colspan=2>{ns}<b>{path}</b></td></tr>'
                    next_dir = False
                elif 'no ' in s.lower() and ' found' in s.lower():
                    text = f'<tr></tr>' if remove_dir == 0 else ''
                    text += f'<tr><td colspan=2>{s.strip()}</td></tr>'
                    if remove_dir > 0:
                        remove_dir = 2
                    else:
                        break
                    next_dir = False
                elif ' file' in s.lower() or \
                     s.strip().lower().startswith('removed'):
                    text += f'<tr><td colspan=2>{s.strip()}</td></tr>'
                    next_dir = True
                elif len(s.strip()) == 0:
                    text += '<tr><td></td><td></td></tr>'
                else:
                    if next_dir:
                        break
                    text += '<tr>'
                    cs = s.split()
                    if len(cs) > 1:
                        text += f'<td align="right">{cs[0]}</td>'
                        text += f'<td align="left">{(" ".join(cs[1:]))}</td>'
                    else:
                        text += f'<td></td><td align="left">{s.strip()}</td>'
                    text += '</tr>'
                    if remove_dir >= 2:
                        break
        text += '</table>'
        if title is not None:
            self.sigDisplayTerminal.emit(title, text)
            if success and \
               title.lower().strip().startswith('erase all files in'):
                self.sigUpdate.emit()

                
class CleanDir(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('clean recent recordings', 'Clean', *args, **kwargs)
        
    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if len(stream) == 0:
            return
        title = None
        text = ''
        for s in stream:
            if title is None:
                if 'no folder exists that can be cleaned' in s.lower():
                    self.sigDisplayMessage.emit(s)
                    return
                if 'clean directory on ' in s.lower():
                    title = s.strip()
            elif len(s.strip()) == 0:
                break
            else:
                text += s.rstrip()
                text += '\n'
        if len(text) == 0:
            return
        self.sigDisplayTerminal.emit(title, text)
        if success:
            self.sigUpdate.emit()

                
class Benchmark(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('sd card benchmark', 'Test',
                         *args, **kwargs)
        self.value = None

    def set_value(self, value):
        self.value = value
        
    def read(self, ident, stream, success):
        title = None
        text = ''
        speeds = []
        start = None
        for k in range(len(stream)):
            if title is None:
                if 'benchmarking write and read speeds' in stream[k].lower():
                    title = stream[k].strip()
            else:
                text += stream[k].rstrip()
                text += '\n'
                if 'done' in stream[k].lower():
                    break
                if 'write speed and latency' in stream[k].lower():
                    start = k + 3
                if start is not None and k >= start:
                    if len(stream[k].strip()) == 0:
                        start = None
                    else:
                        speeds.append(float(stream[k].split()[0]))
        if len(speeds) > 0:
            self.value.setText(f'<b>{np.mean(speeds):.2f}MB/s</b>')
        self.sigDisplayTerminal.emit(title, text)

                
class InputConfiguration(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('report input configuration', 'Input',
                         *args, **kwargs)
        
    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if not success:
            return
        if len(stream) == 0:
            return
        title = None
        text = '<style type="text/css"> th, td { padding: 0 15px; }</style>'
        text += '<table>'
        for s in stream:
            if len(s.strip()) == 0:
                if title is None:
                    text += '</table><br/><table>'
                    continue
                else:
                    break
            ss = s.split(':')
            key = ss[0].strip()
            value = ss[1].strip()
            if len(value) == 0 and 'settings' in key and title is None:
                title = key.strip()
            else:
                text += f'<tr><td>{key}</td><td><b>{value}</b></td></tr>'
        text += '</table>'
        self.sigDisplayTerminal.emit(title, text)

                
class InputData(ReportButton):
    
    def __init__(self, plot, *args, **kwargs):
        super().__init__('start recording', 'Data',
                         *args, **kwargs)
        self.plot = plot
        self.plot.sigReplot.connect(self.get_data)
        self.plot.sigClose.connect(self.stop)
        self.timer = QTimer()
        self.timer.timeout.connect(self.get_data)
        self.start_data = []
        self.get_data = []
        self.stop_data = []
     
    def setup(self, menu):
        super().setup(menu)
        self.retrieve('record some data', menu)  # not needed
        self.get_data = self.retrieve('get data from running recording', menu)
        self.stop_data = self.retrieve('stop recording', menu)

    def run(self):
        self.sigReadRequest.emit(self, 'start', self.start, ['select'])
        self.timer.setSingleShot(True)
        self.timer.start(500)

    def get_data(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.sigReadRequest.emit(self, 'getdata', self.get_data, ['select'])
        
    def read(self, ident, stream, success):
        if ident != 'getdata':
            return
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if not success:
            return
        if len(stream) == 0:
            return
        while len(stream) > 0 and not '...' in stream[0]:
            del stream[0]
        rate = None
        bits = 16
        gain = 1
        unit = None
        while len(stream) > 0 and (':' in stream[0] or '...' in stream[0]):
            ss = stream[0].split(':')
            if 'rate' in ss[0].lower():
                rate = float(ss[1].strip().replace('Hz', ''))
            elif 'resolution' in ss[0].lower():
                bits = int(ss[1].strip().replace('bits', ''))
            elif 'gain' in ss[0].lower():
                vs = ss[1].strip()
                i = max([i for i in range(len(vs)) if vs[i].isdigit()]) + 1
                gain = float(vs[:i])
                unit = vs[i:]
            del stream[0]
        if rate is None:
            return
        data = []
        for s in stream:
            if len(s.strip()) == 0:
                break
            try:
                frame = [int(c.strip()) for c in s.split(';')]
                data.append(frame)
            except ValueError:
                print('Error in parsing line', s)
        if len(data) > 0:
            self.plot.plot_data(rate, bits, gain, unit, np.array(data))

    def stop(self):
        self.sigReadRequest.emit(self, 'run', self.stop_data, ['select'])


class PlotRecording(QWidget):
    
    sigReplot = Signal()
    sigClose = Signal()

    # from https://github.com/bendalab/plottools/blob/master/src/plottools/colors.py :
    colors_vivid = ['#D71000', '#FF9000', '#FFF700', '#B0FF00',
                    '#30D700', '#00A050', '#00D0B0', '#00B0C7',
                    '#1040C0', '#8000C0', '#B000B0', '#E00080']
  
    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        gtext = QLabel('y-axis')
        gtext.setFixedSize(gtext.sizeHint())
        utext = QLabel('update every')
        utext.setFixedSize(utext.sizeHint())
        self.gains = QComboBox()
        self.gains.addItem('raw')
        self.gains.addItem('normalized')
        self.gains.addItem('gain')
        self.gains.setCurrentIndex(0)
        self.gains.setEditable(False)
        self.gains.setMaximumWidth(self.gains.sizeHint().width())
        self.gains.currentIndexChanged.connect(self.update_plots)
        self.utime = SpinBox()
        self.utime.setSuffix('s')
        self.utime.setValue(1)
        self.utime.setMinimum(1)
        titlew = QWidget()
        tbox = QHBoxLayout(titlew)
        tbox.setContentsMargins(0, 0, 0, 0)
        tbox.addWidget(QLabel(title))
        tbox.addWidget(QLabel())
        tbox.addWidget(QLabel())
        tbox.addWidget(gtext)
        tbox.addWidget(self.gains)
        tbox.addWidget(QLabel())
        tbox.addWidget(utext)
        tbox.addWidget(self.utime)
        self.vbox = pg.GraphicsLayoutWidget()
        fm = self.fontMetrics()
        self.vbox.ci.setSpacing(fm.averageCharWidth())
        self.vbox.ci.layout.setColumnStretchFactor(0, 2)
        self.vbox.ci.layout.setColumnStretchFactor(1, 1)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.vbox)
        self.done = QPushButton(self)
        self.done.setText('Done')
        self.done.setToolTip('Close the plot (Escape, Return)')
        self.done.clicked.connect(self.close)
        self.plot = QPushButton(self)
        self.plot.setText('Replot')
        self.plot.setToolTip('Record and plot new data (Space, D, Ctrl+D)')
        self.plot.setCheckable(True)
        self.plot.toggled.connect(self.replot)
        self.repeat_plot = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.sigReplot)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.plot)
        hbox.addWidget(self.done)
        key = QShortcut(QKeySequence.Cancel, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Space, self)
        key.activated.connect(self.plot.toggle)
        key = QShortcut(Qt.Key_D, self)
        key.activated.connect(self.plot.toggle)
        key = QShortcut('Ctrl+D', self)
        key.activated.connect(self.plot.toggle)
        key = QShortcut('Y', self)
        key.activated.connect(self.zoom_out)
        key = QShortcut('Shift+Y', self)
        key.activated.connect(self.zoom_in)
        vbox = QVBoxLayout(self)
        vbox.addWidget(titlew)
        vbox.addWidget(self.scroll)
        vbox.addLayout(hbox)
        self.time = None
        self.data = None
        self.unit = None
        self.amax = None
        self.gain = None

    def replot(self, checked):
        self.scroll.setFocus()
        self.repeat_plot = checked
        if checked:
            self.sigReplot.emit()
        else:
            self.timer.stop()

    def close(self):
        self.timer.stop()
        self.repeat_plot = False
        self.plot.setChecked(False)
        self.sigClose.emit()

    def update_plots(self, gains):
        self.scroll.setFocus()
        for channel in range(self.data.shape[1]):
            plot = self.vbox.getItem(channel, 0)
            if gains == 0:
                plot.getAxis('left').setLabel(f'channel {channel}')
                plot.getViewBox().setLimits(yMin=-self.amax, yMax=self.amax,
                                            minYRange=10,
                                            maxYRange=2*self.amax)
                if not self.repeat_plot:
                    plot.getViewBox().setRange(yRange=(-self.amax, self.amax))
                plot.listDataItems()[0].setData(self.time, self.data[:, channel])
            elif gains == 1:
                plot.getAxis('left').setLabel(f'channel {channel}')
                plot.getViewBox().setLimits(yMin=-1, yMax=1,
                                            minYRange=0.0001, maxYRange=2)
                if not self.repeat_plot:
                    plot.getViewBox().setRange(yRange=(-1, 1))
                plot.listDataItems()[0].setData(self.time,
                                                self.data[:, channel]/self.amax)
            elif gains == 2:
                plot.getAxis('left').setLabel(f'channel {channel}', self.unit)
                plot.getViewBox().setLimits(yMin=-self.gain, yMax=self.gain,
                                            minYRange=0.0001*self.gain,
                                            maxYRange=2*self.gain)
                if not self.repeat_plot:
                    plot.getViewBox().setRange(yRange=(-self.gain, self.gain))
                plot.listDataItems()[0].setData(self.time,
                                                self.data[:, channel]*self.gain/self.amax)
        plot = self.vbox.getItem(self.data.shape[1] - 1, 0)
        plot.getAxis('bottom').setLabel('time', 's')
        plot.getAxis('bottom').setStyle(showValues=True)
        spec = self.vbox.getItem(self.data.shape[1] - 1, 1)
        spec.getAxis('bottom').setLabel('frequency', 'Hz')
        spec.getAxis('bottom').setStyle(showValues=True)

    def plot_trace(self, channel):
        # color:
        ns = channel
        nc = len(self.colors_vivid)
        i = (ns % (nc // 2))*2      # every second color
        i += (ns // (nc // 2)) % 2  # start at index 1 for odd cycles
        color = self.colors_vivid[i]
        text_color = self.palette().color(QPalette.WindowText)
        # add plot:
        plot = self.vbox.getItem(channel, 0)
        spec = self.vbox.getItem(channel, 1)
        if plot is None:
            fm = self.fontMetrics()
            # initialize trace plot:
            plot = self.vbox.addPlot(row=channel, col=0,
                                     enableMenu=False)
            plot.showGrid(True, True, 0.5)
            plot.getAxis('left').enableAutoSIPrefix(False)
            plot.getAxis('left').setWidth(10*fm.averageCharWidth())
            plot.getAxis('left').setLabel(f'channel {channel}', color=text_color)
            plot.getAxis('left').setPen('white')
            plot.getAxis('left').setTextPen(text_color)
            plot.getAxis('left').setStyle(textFillLimits=[(3, 1.0)], maxTickLevel=0)
            plot.getAxis('bottom').enableAutoSIPrefix(True)
            plot.getAxis('bottom').setLabel('time', 's', color=text_color)
            plot.getAxis('bottom').setPen('white')
            plot.getAxis('bottom').setTextPen(text_color)
            plot.getAxis('bottom').setStyle(maxTickLevel=0)
            plot.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            plot.getViewBox().setBackgroundColor('black')
            plot.getViewBox().setLimits(xMin=0,
                                        xMax=self.time[-1] + self.time[1],
                                        minXRange=self.time[11],
                                        maxXRange=self.time[-1] + self.time[1])
            plot.getViewBox().setRange(xRange=(0, self.time[-1] + self.time[1]),
                                       padding=0)
            plot.setMenuEnabled(False)
            plot.addItem(pg.PlotDataItem(pen=dict(color=color, width=2)))
            # initialize power spectrum plot:
            spec = self.vbox.addPlot(row=channel, col=1,
                                     enableMenu=False)
            spec.showGrid(True, True, 0.5)
            spec.getAxis('left').enableAutoSIPrefix(False)
            spec.getAxis('left').setWidth(7*fm.averageCharWidth())
            spec.getAxis('left').setLabel('power (dB)', color=text_color)
            spec.getAxis('left').setPen('white')
            spec.getAxis('left').setTextPen(text_color)
            spec.getAxis('left').setStyle(maxTickLevel=0)
            spec.getAxis('bottom').enableAutoSIPrefix(True)
            spec.getAxis('bottom').setLabel('frequency', 'Hz', color=text_color)
            spec.getAxis('bottom').setPen('white')
            spec.getAxis('bottom').setTextPen(text_color)
            spec.getAxis('bottom').setStyle(maxTickLevel=0)
            spec.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            spec.getViewBox().setBackgroundColor('black')
            spec.getViewBox().setLimits(xMin=0, xMax=0.5/self.time[1],
                                        yMin=-200, yMax=0,
                                        minXRange=1/(self.time[-1] + self.time[1]),
                                        maxXRange=0.5/self.time[1],
                                        minYRange=1,
                                        maxYRange=200)
            spec.getViewBox().setRange(xRange=(0, 0.5/self.time[1]),
                                       yRange=(-100, 0), padding=0)
            spec.setMenuEnabled(False)
            spec.addItem(pg.PlotDataItem(pen=dict(color=color, width=2)))
        plot.setVisible(True)
        spec.setVisible(True)
        nfft = 2**12
        if nfft > len(self.data[:, channel])//2:
            nfft = len(self.data[:, channel])
        freqs, power = welch(self.data[:, channel].astype(float)/self.amax,
                             1/self.time[1], nperseg=nfft)
        power *= freqs[1]
        dbpower = np.zeros(len(power)) - 200
        mask = power > 1e-20
        dbpower[mask] = 10*np.log10(power[mask])
        spec.listDataItems()[0].setData(freqs, dbpower)

    def plot_data(self, rate, bits, gain, unit, data):
        self.time = np.arange(len(data))/rate
        self.data = data
        self.amax = 2**bits
        self.unit = unit
        self.gain = gain
        fm = self.fontMetrics()
        for channel in range(self.data.shape[1]):
            self.plot_trace(channel)
        self.update_plots(self.gains.currentIndex())
        plot = self.vbox.getItem(data.shape[1] - 1, 0)
        spec = self.vbox.getItem(data.shape[1] - 1, 1)
        for channel in range(data.shape[1] - 1):
            p = self.vbox.getItem(channel, 0)
            p.getAxis('bottom').setStyle(showValues=False)
            p.setLabel('bottom', '', '')
            p.setXLink(plot.getViewBox())
            p.setYLink(plot.getViewBox())
            p.setMinimumHeight(14*fm.averageCharWidth())
            s = self.vbox.getItem(channel, 1)
            s.getAxis('bottom').setStyle(showValues=False)
            s.setLabel('bottom', '', '')
            s.setXLink(spec.getViewBox())
            s.setYLink(spec.getViewBox())
            s.setMinimumHeight(14*fm.averageCharWidth())
        plot.setMinimumHeight(19*fm.averageCharWidth())
        spec.setMinimumHeight(19*fm.averageCharWidth())
        for row in range(data.shape[1], data.shape[1] + 1000):
            plot = self.vbox.getItem(row, 0)
            if plot is None:
                break
            plot.setVisible(False)
            spec = self.vbox.getItem(row, 1)
            spec.setVisible(False)
        self.vbox.setMinimumHeight(data.shape[1]*18*fm.averageCharWidth())
        QApplication.restoreOverrideCursor()
        if self.repeat_plot:
            self.timer.start(int(1000*self.utime.value()))

    def zoom_in(self):
        plot = self.vbox.getItem(0, 0)
        if plot is None:
            return
        plot = plot.getViewBox()
        ymin, ymax = plot.viewRange()[1]
        dy = 0.5*(ymax - ymin)
        ay = 0.5*(ymin + ymax)
        dy *= 0.5
        ymin = ay - dy
        ymax = ay + dy
        plot.setYRange(ymin, ymax)

    def zoom_out(self):
        plot = self.vbox.getItem(0, 0)
        if plot is None:
            return
        plot = plot.getViewBox()
        ymin, ymax = plot.viewRange()[1]
        dy = 0.5*(ymax - ymin)
        ay = 0.5*(ymin + ymax)
        dy *= 2.0
        ymin = ay - dy
        ymax = ay + dy
        plot.setYRange(ymin, ymax)
    
        
class HardwareInfo(Interactor, QFrame, metaclass=InteractorQFrame):
    
    sigPlot = Signal()
    
    def __init__(self, plot, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.box = QGridLayout(self)
        title = QLabel('<b>Periphery</b>', self)
        title.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(title, 0, 0, 1, 4)
        self.box.setRowStretch(0, 1)
        self.row = 1
        self.add('<b>Type</b>', 0)
        self.add('<b>Device</b>', 1)
        self.add('<b>Bus</b>', 2)
        self.add('<b>Pin</b>', 3)
        self.add('<b>Identifier</b>', 4)
        self.box.setRowStretch(1, 1)
        self.row += 1
        self.box.addItem(QSpacerItem(0, 0,
                                     QSizePolicy.Policy.Minimum,
                                     QSizePolicy.Policy.Expanding),
                         self.row, 0)
        self.row += 1
        self.input_button = InputConfiguration(self)
        self.input_button.setVisible(False)
        self.input_button.sigReadRequest.connect(self.sigReadRequest)
        self.input_button.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.input_button.setToolTip('Check and report input configuration (Ctrl+I)')
        key = QShortcut('Ctrl+I', self)
        key.activated.connect(self.input_button.animateClick)
        self.data_button = InputData(plot, self)
        self.data_button.setVisible(False)
        self.data_button.sigReadRequest.connect(self.sigReadRequest)
        self.data_button.clicked.connect(self.sigPlot)
        self.data_button.setToolTip('Record and plot some data (Ctrl+D)')
        key = QShortcut('Ctrl+D', self)
        key.activated.connect(self.data_button.animateClick)
        self.sensors_start_get = []
        self.devices_start_get = []

    def setup(self, menu):
        self.devices_start_get = self.retrieve('input devices', menu)
        self.sensors_start_get = self.retrieve('sensor devices', menu, False)
        if len(self.devices_start_get) == 0 and (self.sensors_start_get) == 0:
            self.setVisible(False)
        self.input_button.setup(menu)
        self.data_button.setup(menu)

    def start(self):
        self.row = 3
        if self.devices_start_get is not None:
            self.sigReadRequest.emit(self, 'inputdevices',
                                     self.devices_start_get, ['select'])
        if self.sensors_start_get is not None:
            self.sigReadRequest.emit(self, 'sensordevices',
                                     self.sensors_start_get, ['select'])

    def add(self, text, col):
        label = QLabel(text)
        label.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(label, self.row, col)

    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if not success:
            return
        if int(stream[0].split()[0]) == 0:
            return
        first_input = True
        for s in stream[1:]:
            if len(s.strip()) == 0:
                break
            ss = s.split()
            dev_type = ss[0]
            self.add(dev_type, 0)
            if 'device' in ss:
                dev_idx = ss.index('device')
                device = ss[dev_idx + 1]
                self.add(device, 1)
            if 'on' in ss:
                bus_idx = ss.index('on')
                bus = ss[bus_idx + 1]
                self.add(bus, 2)
            if 'at' in ss:
                pin_idx = ss.index('at')
                pin = ss[pin_idx + 2]
                self.add(pin, 3)
            if dev_type == 'input' and first_input:
                hbox = QHBoxLayout()
                hbox.setContentsMargins(0, 0, 0, 0)
                hbox.addWidget(self.input_button)
                hbox.addWidget(self.data_button)
                self.box.addLayout(hbox, self.row, 4)
                self.input_button.setVisible(True)
                self.data_button.setVisible(True)
                first_input = False
            elif 'with' in ss and 'ID' in ss:
                id_idx = ss.index('ID')
                identifier = ' '.join(ss[id_idx + 1:])
                self.add(identifier, 4)
            self.box.setRowStretch(self.row, 1)
            self.row += 1
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.row += 1
        

class PlotSensors(QWidget):

    # from https://github.com/bendalab/plottools/blob/master/src/plottools/colors.py :
    colors_vivid = ['#D71000', '#FF9000', '#FFF700', '#B0FF00',
                    '#30D700', '#00A050', '#00D0B0', '#00B0C7',
                    '#1040C0', '#8000C0', '#B000B0', '#E00080']
  
    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = QLabel(title, self)
        self.vbox = pg.GraphicsLayoutWidget()
        fm = self.fontMetrics()
        self.vbox.ci.setSpacing(2*fm.averageCharWidth())
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.vbox)
        self.sensors = {}
        self.done = QPushButton(self)
        self.done.setText('&Done')
        self.done.setToolTip('Close the plot (Return, Escape, Space)')
        key = QShortcut(QKeySequence.Cancel, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Space, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.done.animateClick)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.title)
        vbox.addWidget(self.scroll)
        vbox.addWidget(self.done)
        self.time = QElapsedTimer()

    def addSensor(self, name, unit):
        # color:
        ns = len(self.sensors)
        nc = len(self.colors_vivid)
        i = (ns % (nc // 2))*2      # every second color
        i += (ns // (nc // 2)) % 2  # start at index 1 for odd cycles
        color = self.colors_vivid[i]
        text_color = self.palette().color(QPalette.WindowText)
        # add plot:
        plot = self.vbox.addPlot(row=len(self.sensors), col=0,
                                 enableMenu=False)
        fm = self.fontMetrics()
        plot.showGrid(True, True, 0.5)
        plot.getAxis('left').setWidth(10*fm.averageCharWidth())
        plot.getAxis('left').setLabel(name, unit, color=text_color)
        plot.getAxis('left').setPen('white')
        plot.getAxis('left').setTextPen(text_color)
        plot.getAxis('bottom').enableAutoSIPrefix(True)
        plot.getAxis('bottom').setLabel('time', 's', color=text_color)
        plot.getAxis('bottom').setPen('white')
        plot.getAxis('bottom').setTextPen(text_color)
        plot.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        plot.getViewBox().setBackgroundColor('black')
        plot.setMenuEnabled(False)
        plot.addItem(pg.PlotDataItem(pen=dict(color=color, width=3)))
        for p, _, _ in self.sensors.values():
            p.getAxis('bottom').setStyle(showValues=False)
            p.setLabel('bottom', '', '')
            p.setXLink(plot.getViewBox())
        self.sensors[name] = [plot, [], []]
        self.vbox.setMinimumHeight(len(self.sensors)*18*fm.averageCharWidth())
        self.time.start()

    def addData(self, name, value):
        if not name in self.sensors:
            return
        plot, time, data = self.sensors[name]
        time.append(0.001*self.time.elapsed())
        data.append(value)
        if len(data) > 1:
            plot.listDataItems()[0].setData(time, data)

        
class SensorsInfo(Interactor, QFrame, metaclass=InteractorQFrame):
    
    sigPlot = Signal()
    
    def __init__(self, plot, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.plot = plot
        self.box = QGridLayout(self)
        title = QLabel('<b>Environmental sensors</b>', self)
        title.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(title, 0, 0, 1, 4)
        self.plotb = QPushButton('Plot', self)
        bbox = self.fontMetrics().boundingRect('Plot')
        self.plotb.setMaximumWidth(bbox.width() + 10)
        self.plotb.setMaximumHeight(bbox.height() + 2)
        self.plotb.clicked.connect(self.sigPlot)
        self.plotb.setToolTip('Plot sensor readings (Ctrl+S)')
        key = QShortcut('Ctrl+S', self)
        key.activated.connect(self.plotb.animateClick)
        self.box.addWidget(self.plotb, 0, 5, Qt.AlignRight)
        self.box.setRowStretch(0, 1)
        self.row = 1
        self.add('<b>Parameter</b>', 0)
        self.add('<b>Symbol</b>', 1)
        self.add('<b>Value</b>', 2)
        self.add('<b>Error</b>', 3)
        self.add('<b>Unit</b>', 4)
        self.add('<b>Device</b>', 5)
        self.box.setRowStretch(1, 1)
        self.row += 1
        self.box.addItem(QSpacerItem(0, 0,
                                     QSizePolicy.Policy.Minimum,
                                     QSizePolicy.Policy.Expanding),
                         self.row, 0)
        self.row += 1
        self.sensors_get = []
        self.request_get = []
        self.values_get = []
        self.sensors = {}
        self.state = 0
        self.delay = 1000
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.read_sensors)

    def setup(self, menu):
        self.sensors_get = self.retrieve('environmental sensors',
                                         menu, False)
        self.request_get = self.retrieve('sensor request',
                                         menu, False)
        self.values_get = self.retrieve('sensor readings',
                                        menu, False)
        if len(self.sensors_get) == 0:
            self.setVisible(False)

    def start(self):
        self.row = 3
        if self.sensors_get is not None:
            self.sigReadRequest.emit(self, 'sensors',
                                     self.sensors_get, ['select'])
            if self.request_get is not None and \
               self.values_get is not None:
                self.state = 0
                self.timer.start(1000)

    def stop(self):
        self.timer.stop()

    def read_sensors(self):
        if self.state == 0:
            self.sigReadRequest.emit(self, 'request',
                                     self.request_get, ['select'])
            self.state = 1
            self.timer.start(self.delay)
        else:
            self.sigReadRequest.emit(self, 'values',
                                     self.values_get, ['select'])
            self.state = 0
            self.timer.start(max(0, 2000 - self.delay))

    def add(self, text, col):
        label = QLabel(text)
        label.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        align = Qt.AlignLeft
        if col == 2 or col == 3:
            align = Qt.AlignRight
        self.box.addWidget(label, self.row, col, align)

    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if not success:
            return
        if ident == 'request':
            for s in stream:
                if len(s.strip()) == 0:
                    break
                if 'are available after' in s.lower():
                    delaystr = s.strip().rstrip('.').split()[-1]
                    self.delay = int(delaystr.replace('ms', ''))
            return
        elif ident == 'values':
            for s in stream:
                if len(s.strip()) == 0:
                    break
                if '=' not in s:
                    continue
                name, value = [sx.strip() for sx in s.split('=')]
                if name in self.sensors:
                    unit, row = self.sensors[name]
                    value = value.replace(unit, '')
                    if self.box.itemAtPosition(row, 2) is not None:
                        w = self.box.itemAtPosition(row, 2).widget()
                        w.setText('<b>' + value + '</b>')
                    self.plot.addData(name, float(value))
            return
        self.sensors = {}
        if int(stream[0].split()[0]) == 0:
            label = QLabel('No sensors found')
            label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                QSizePolicy.Policy.Fixed)
            self.box.addWidget(label, self.row, 0, 1, 6)
            self.row += 1
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.row += 1
            self.plotb.setEnabled(False)
            return
        for s in stream[1:]:
            if len(s.strip()) == 0:
                break
            ss = s.split()
            if 'at' not in ss and 'resolution' not in ss:
                continue
            idx = ss.index('at')
            name = ' '.join(ss[:idx - 2])
            self.add(name, 0)
            symbol = ss[idx - 2]
            self.add(symbol, 1)
            self.add('-', 2)
            unit = ss[idx - 1].lstrip('(').rstrip(')')
            self.add(unit, 4)
            res_idx = ss.index('resolution')
            resolution = ss[res_idx + 2]
            for k in reversed(range(len(resolution))):
                if resolution[k].isdigit():
                    resolution = resolution[:k + 1]
                    break
            self.add(resolution, 3)
            if 'device' in ss:
                dev_idx = ss.index('device')
                device = ss[dev_idx - 1]
                self.add(device, 5)
            self.sensors[name] = (unit, self.row)
            self.plot.addSensor(name, unit)
            self.box.setRowStretch(self.row, 1)
            self.row += 1
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.row += 1
        
        
class SDCardInfo(Interactor, QFrame, metaclass=InteractorQFrame):
    
    def __init__(self, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.checkcard = CheckSDCard()
        self.checkcard.setToolTip('Check accessability of micro SD card (Ctrl+M)')
        self.erasecard = FormatSDCard('sd card>erase and format', 'Erase')
        self.erasecard.setToolTip('Flash erase and format SD card (Ctrl+E)')
        self.formatcard = FormatSDCard('sd card>format', '&Format')
        self.formatcard.setToolTip('Format SD card (Ctrl+F)')
        self.root = ListFiles()
        self.root.setToolTip('List files in root directory (Ctrl+O)')
        self.recordings = ListFiles()
        self.recordings.setToolTip('List all recordings (Ctrl+R)')
        self.eraserecordings = ListFiles('Delete')
        self.eraserecordings.setToolTip('Delete most recent recordings (Ctrl+U)')
        self.cleandir = CleanDir()
        self.bench = Benchmark()
        self.bench.setToolTip('Write and read data rates of SD card (Ctrl+W)')

        self.checkcard.sigReadRequest.connect(self.sigReadRequest)
        self.checkcard.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.formatcard.sigReadRequest.connect(self.sigReadRequest)
        self.formatcard.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.erasecard.sigReadRequest.connect(self.sigReadRequest)
        self.erasecard.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.recordings.sigReadRequest.connect(self.sigReadRequest)
        self.recordings.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.recordings.sigDisplayMessage.connect(self.sigDisplayMessage)
        self.eraserecordings.sigReadRequest.connect(self.sigReadRequest)
        self.eraserecordings.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.eraserecordings.sigDisplayMessage.connect(self.sigDisplayMessage)
        self.cleandir.sigReadRequest.connect(self.sigReadRequest)
        self.cleandir.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.cleandir.sigDisplayMessage.connect(self.sigDisplayMessage)
        self.root.sigReadRequest.connect(self.sigReadRequest)
        self.root.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.root.sigDisplayMessage.connect(self.sigDisplayMessage)
        self.bench.sigReadRequest.connect(self.sigReadRequest)
        self.bench.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.formatcard.sigUpdate.connect(self.start)
        self.erasecard.sigUpdate.connect(self.start)
        self.eraserecordings.sigUpdate.connect(self.start)
        self.cleandir.sigUpdate.connect(self.start)
        
        key = QShortcut('Ctrl+M', self)
        key.activated.connect(self.checkcard.animateClick)
        key = QShortcut('Ctrl+E', self)
        key.activated.connect(self.erasecard.animateClick)
        key = QShortcut('Ctrl+F', self)
        key.activated.connect(self.formatcard.animateClick)
        key = QShortcut('Ctrl+O', self)
        key.activated.connect(self.root.animateClick)
        key = QShortcut('Ctrl+R', self)
        key.activated.connect(self.recordings.animateClick)
        key = QShortcut('Ctrl+U', self)
        key.activated.connect(self.eraserecordings.animateClick)
        key = QShortcut('Ctrl+W', self)
        key.activated.connect(self.bench.animateClick)
        self.box = QGridLayout(self)
        title = QLabel('<b>SD card</b>', self)
        title.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(title, 0, 0, 1, 2)
        self.box.addWidget(self.checkcard, 0, 2, Qt.AlignRight)
        self.box.setRowStretch(0, 1)
        self.sdcard_start_get = []
        self.root_start_get = []
        self.recordings_start_get = []
        self.nrecordings = 0
        self.srecordings = None
        self.nroot = 0
        self.sroot = 0
        self.row = 1

    def setup(self, menu):
        self.sdcard_start_get = self.retrieve('sd card>sd card info', menu)
        self.root_start_get = \
            self.retrieve('sd card>list files in root', menu)
        self.recordings_start_get = \
            self.retrieve('sd card>list all recordings', menu)
        erase_recordings_start = \
            self.retrieve('sd card>erase recent recordings', menu)
        self.root.setup(self.root_start_get)
        self.recordings.setup(self.recordings_start_get)
        self.eraserecordings.setup(erase_recordings_start)
        self.checkcard.setup(menu)
        self.bench.setup(menu)
        self.formatcard.setup(menu)
        self.erasecard.setup(menu)
        self.cleandir.setup(menu)

    def add(self, label, value, button=None):
        if self.box.itemAtPosition(self.row, 0) is not None:
            w = self.box.itemAtPosition(self.row + 1, 1).widget()
            w.setText('<b>' + value + '</b>')
            self.row += 2
        else:
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)
            self.row += 1
            lw = QLabel(label, self)
            lw.setSizePolicy(QSizePolicy.Policy.Preferred,
                             QSizePolicy.Policy.Fixed)
            self.box.addWidget(lw, self.row, 0)
            vw = QLabel('<b>' + value + '</b>', self)
            vw.setSizePolicy(QSizePolicy.Policy.Preferred,
                             QSizePolicy.Policy.Fixed)
            self.box.addWidget(vw, self.row, 1, Qt.AlignRight)
            if button is not None:
                self.box.addWidget(button, self.row, 2, Qt.AlignRight)
            self.box.setRowStretch(self.row, 1)
            self.row += 1

    def start(self):
        self.row = 1
        self.sigReadRequest.emit(self, 'recordings',
                                 self.recordings_start_get, ['select'])
        self.sigReadRequest.emit(self, 'root',
                                 self.root_start_get, ['select'])
        self.sigReadRequest.emit(self, 'sdcard',
                                 self.sdcard_start_get, ['select'])

    def read(self, ident, stream, success):

        def num_files(stream):
            nf = 0
            ns = 0
            for s in stream:
                if ' file (' in s or ' files (' in s:
                    nf += int(s[:s.find(' file')])
                    if '(' in s and 'MB)' in s:
                        ns += float(s[s.find('(') + 1:s.find(' MB)')])
            return nf, ns

        if ident == 'recordings':
            self.nrecordings, self.srecordings = num_files(stream)
        elif ident == 'root':
            self.nroot, self.sroot = num_files(stream)
        elif ident == 'sdcard':
            r = 0
            items = []
            available = None
            for s in stream:
                if r > 0 and len(s.strip()) == 0:
                    break
                x = s.split(':')
                if len(x) < 2 or len(x[1].strip()) == 0:
                    continue
                r += 1
                label = x[0].strip()
                value = ':'.join(x[1:]).strip()
                if label.lower() == 'available':
                    available = value
                items.append([label, value])
            for keys in ['capacity', 'available', 'serial', 'system']:
                for i in range(len(items)):
                    if keys in items[i][0].lower():
                        if keys == 'serial':
                            self.add(items[i][0], items[i][1], self.erasecard)
                        elif keys == 'system':
                            self.add(items[i][0], items[i][1], self.formatcard)
                        elif keys == 'available':
                            self.add(items[i][0], items[i][1], self.cleandir)
                            if available is not None:
                                a = float(available.replace(' GB', ''))
                                c = float(items[i][1].replace(' GB', ''))
                                self.add('Used', f'{100 - 100*a/c:.0f} %',
                                         self.eraserecordings)
                            value = 'none'
                            if self.nrecordings > 0:
                                value = f'{self.nrecordings}'
                            if self.srecordings is not None:
                                value += f' ({self.srecordings:.0f}MB)'
                            self.add('<u>R</u>ecorded files', value,
                                     self.recordings)
                            value = 'none'
                            if self.nroot > 0:
                                value = f'{self.nroot}'
                            if self.sroot is not None:
                                value += f' ({self.sroot:.0f}MB)'
                            self.add('R<u>o</u>ot files', value, self.root)
                        else:
                            self.add(items[i][0], items[i][1])
            if len(items) > 1:
                self.add('<u>W</u>rite speed', 'none', self.bench)
                self.bench.set_value(self.box.itemAtPosition(self.row - 1, 1).widget())
            self.box.addItem(QSpacerItem(0, 0,
                                         QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding),
                             self.row, 0)


class Terminal(QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = QLabel(self)
        self.out = QLabel(self)
        self.out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.out)
        self.done = QPushButton(self)
        self.done.setText('&Done')
        self.done.setToolTip('Close the terminal (Return, Escape, Space)')
        self.done.clicked.connect(self.clear)
        key = QShortcut(QKeySequence.Cancel, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Space, self)
        key.activated.connect(self.done.animateClick)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.done.animateClick)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.title)
        vbox.addWidget(self.scroll)
        vbox.addWidget(self.done)

    def clear(self):
        self.title.setText('')
        self.out.setText('')
        self.out.setMinimumSize(1, 1)
        self.out.setMaximumSize(self.out.sizeHint())

    def update(self, stream):
        if len(stream) > 0:
            self.title.setText(stream[0])
        s = ''
        for l in stream[1:]:
            s += l + '\n'
        self.done.setEnabled(False)
        self.out.setText(s)
        self.out.setMinimumSize(self.out.sizeHint())
        vsb = self.scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def display(self, title, stream):
        if title:
            self.title.setText(title)
        self.done.setEnabled(True)
        if isinstance(stream, (tuple, list)):
            text = ''
            for s in stream:
                text += s
                text += '\n'
            self.out.setText(text)
            self.out.setFont(QFont('monospace'))
        else:
            self.out.setText(stream)
            self.out.setFont(QFont('sans'))
        self.out.setMinimumSize(self.out.sizeHint())
        vsb = self.scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())


class SpinBox(QAbstractSpinBox):

    textChanged = Signal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAccelerated(True)
        self.setAlignment(Qt.AlignLeft)
        self.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        self.setCorrectionMode(QAbstractSpinBox.CorrectToPreviousValue)
        self.setFrame(True)
        self.setKeyboardTracking(True)
        self.setReadOnly(False)
        self.setGroupSeparatorShown(False)
        self.setWrapping(False)
        self._minimum = None
        self._maximum = None
        self._decimals = 0
        self._value = 0
        self._unit = ''

    def setDecimals(self, n):
        self._decimals = n

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def setMinimum(self, minv):
        self._minimum = minv

    def setMaximum(self, maxv):
        self._maximum = maxv

    def setStepType(self, stype):
        pass

    def stepEnabled(self):
        steps = self.StepUpEnabled | self.StepDownEnabled
        try:
            if self._minimum is not None and self._value <= self._minimum:
                steps &= ~self.StepDownEnabled
            if self._maximum is not None and self._value >= self._maximum:
                steps &= ~self.StepUpEnabled
        except AttributeError:  # why does it not know self._minimum initially?
            pass
        return steps

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        locale = QLocale()
        text = f'{value:.{self._decimals}f}'
        text = text.replace('.', locale.decimalPoint())
        text += self._unit
        self.lineEdit().setText(text)

    def setSuffix(self, suffix):
        self._unit = suffix

    def validate(self, text, pos):
        locale = QLocale()
        s = text.replace(locale.decimalPoint(), '.')
        value, unit, ndec = parse_number(s)
        if value is None:
            return QValidator.State.Intermediate, text, pos
        if self._minimum is not None and value <= self._minimum:
            return QValidator.State.Intermediate, text, pos
        if self._maximum is not None and value >= self._maximum:
            return QValidator.State.Intermediate, text, pos
        if ndec > self._decimals:
            return QValidator.State.Intermediate, text, pos
        self._value = float(value)
        if not self._unit and unit:
            text = text[:-len(unit)]
        self.textChanged.emit(text)
        #return QValidator.State.Intermediate
        #return QValidator.State.Invalid
        return QValidator.State.Acceptable, text, pos

    def fixup(self, text):
        locale = QLocale()
        s = text.replace(locale.decimalPoint(), '.')
        value, unit, ndec = parse_number(s)
        if value is None:
            value = self._minimum  # TODO should be previous value
        if self._minimum is not None and value <= self._minimum:
            value = self._minimum
        if self._maximum is not None and value >= self._maximum:
            value = self._maximum
        if ndec > self._decimals:
            ndec = self._decimals
        text = f'{value:.{ndec}f}'.replace('.', locale.decimalPoint())
        text += unit
        self.setValue(float(value))
        self.textChanged.emit(text)

    def stepBy(self, steps):
        self.setValue(self._value + steps)

    
class Parameter(Interactor, QObject, metaclass=InteractorQObject):
    
    def __init__(self, ids, name, value, num_value=None,
                 out_unit=None, unit=None, type_str=None,
                 max_chars=None, ndec=None, min_val=None,
                 max_val=None, special_val=None, special_str=None,
                 selection=None, *args, **kwargs):
        super(QObject, self).__init__(*args, **kwargs)
        self.ids = list(ids)
        self.name = name
        self.value = value
        self.num_value = num_value
        self.out_unit = out_unit
        self.unit = unit
        self.type_str = type_str
        self.max_chars = max_chars
        self.ndec = ndec
        self.min_val = min_val
        self.max_val = max_val
        self.special_val = special_val
        self.special_str = special_str
        self.selection = selection
        self.edit_widget = None
        self.state_widget = None
        self.matches = False

    def initialize(self, s):
        ss = s.split(',')
        self.type_str = ss.pop(0)
        self.max_chars = 0
        self.min_val = None
        self.max_val = None
        self.special_val = None
        self.special_str = None
        if self.type_str.startswith('string'):
            self.max_chars = int(self.type_str.split()[-1].strip())
            self.type_str = 'string'
        self.num_value = None
        self.unit = None
        self.out_unit = None
        self.ndec = None
        if self.type_str in ['float', 'integer']:
            self.unit = ss.pop(0).strip()
            self.num_value, self.out_unit, self.ndec = parse_number(self.value)
        while len(ss) > 0:
            s = ss.pop(0).strip()
            if s.startswith('between'):
                mm = s.split()
                self.min_val = mm[1].strip()
                self.max_val = mm[3].strip()
            elif s.startswith('greater than'):
                self.min_val = s.split()[-1]
            elif s.startswith('less than'):
                self.max_val = s.split()[-1]
            elif s.startswith('or'):
                special = s.split('"')
                self.special_str = special[1]
                special = special[2]
                special = special[special.find('[') + 1:special.find(']')]
                if self.unit:
                    special = special[:-len(self.unit)]
                self.special_val = int(special)
        if self.type_str in ['float', 'integer'] and self.num_value is None:
            if self.value == self.special_str:
                self.num_value = self.special_val
                self.out_unit = self.unit

    def set_selection(self, stream):
        self.selection = []
        for k, l in enumerate(stream):
            sel = l[4:]
            i = sel.find(') ')
            if i >= 0 and sel[:i].isdigit():
                sel = (sel[:i], sel[i + 2:])
            else:
                sel = (None, sel)
            self.selection.append(sel)
        
    def setup(self, parent):
        if self.type_str == 'boolean':
            self.edit_widget = QCheckBox(parent)
            checked = self.value.lower() in ['yes', 'on', 'true', 'ok', '1']
            self.edit_widget.setChecked(checked)
            try:
                self.edit_widget.checkStateChanged.connect(self.transmit_bool)
            except AttributeError:
                self.edit_widget.stateChanged.connect(self.transmit_bool)
        elif len(self.selection) > 0:
            locale = QLocale()
            self.edit_widget = QComboBox(parent)
            idx = None
            for i, s in enumerate(self.selection):
                si = s[1]
                if si == self.value:
                    idx = i
                if self.type_str in ['integer', 'float']:
                    si = si.replace('.', locale.decimalPoint())
                self.edit_widget.addItem(si)
            self.edit_widget.setCurrentIndex(idx)
            self.edit_widget.setEditable(False)
            self.edit_widget.currentTextChanged.connect(self.transmit_str)
        elif self.type_str == 'integer' and not self.unit:
            self.edit_widget = QSpinBox(parent)
            if self.min_val is not None:
                self.edit_widget.setMinimum(int(self.min_val))
            if self.max_val is not None:
                self.edit_widget.setMaximum(int(self.max_val))
            else:
                self.edit_widget.setMaximum(100000)
            if self.special_val is not None and \
               self.special_str is not None and \
               self.special_val == self.edit_widget.minimum():
                self.edit_widget.setSpecialValueText(self.special_str)
            self.edit_widget.setValue(self.num_value)
            self.edit_widget.textChanged.connect(self.transmit_str)
        elif self.type_str in ['integer', 'float']:
            self.edit_widget = SpinBox(parent)
            self.edit_widget.setDecimals(self.ndec)
            if self.min_val is not None:
                if self.out_unit:
                    minv = float(self.min_val[:-len(self.out_unit)])
                else:
                    minv = float(self.min_val)
                self.edit_widget.setMinimum(minv)
            if self.edit_widget.minimum() is not None and \
               self.edit_widget.minimum() >= 0:
                self.edit_widget.setStepType(QSpinBox.AdaptiveDecimalStepType)
            if self.max_val is not None:
                if self.out_unit:
                    maxv = float(self.max_val[:-len(self.out_unit)])
                else:
                    maxv = float(self.max_val)
                self.edit_widget.setMaximum(maxv)
            else:
                self.edit_widget.setMaximum(1e9)
            if self.out_unit:
                self.edit_widget.setSuffix(self.out_unit)
            self.edit_widget.setValue(self.num_value)
            self.edit_widget.textChanged.connect(self.transmit_str)
        elif self.type_str == 'string':
            self.edit_widget = QLineEdit(self.value, parent)
            self.edit_widget.setMaxLength(self.max_chars)
            fm = self.edit_widget.fontMetrics()
            self.edit_widget.setMinimumWidth(32*fm.averageCharWidth())
            self.edit_widget.textChanged.connect(self.transmit_str)
        self.state_widget = QLabel(parent)
        self.state_widget.setTextFormat(Qt.RichText)
        self.state_widget.setToolTip('Indicate whether dialog value matches logger settings')
        self.state_widget.setText('&#x2705;')

    def transmit_bool(self, check_state):
        start = list(self.ids)
        start.append('2' if check_state > 0 else '1')
        self.sigTransmitRequest.emit(self, self.name, start)

    def transmit_str(self, text):
        start = list(self.ids)
        if len(self.selection) > 0:
            for s in self.selection:
                if s[1].lower() == text.lower() and s[0] is not None:
                    text = s[0]
                    break
        if self.type_str in ['integer', 'float']:
            locale = QLocale()
            text = text.replace(locale.groupSeparator(), '')
            text = text.replace(locale.decimalPoint(), '.')
        start.append(text)
        self.sigTransmitRequest.emit(self, self.name, start)

    def verify(self, text):
        self.matches = True
        if self.type_str == 'boolean':
            checked = text.lower() in ['yes', 'on', 'true', 'ok', '1']
            self.matches = checked == self.edit_widget.isChecked()
        elif len(self.selection) > 0:
            if self.type_str in ['integer', 'float']:
                value, unit, _ = parse_number(text)
                locale = QLocale()
                s = self.edit_widget.currentText()
                s = s.replace(locale.groupSeparator(), '')
                s = s.replace(locale.decimalPoint(), '.')
                svalue, sunit, _ = parse_number(s)
                self.matches = abs(value - svalue) < 1e-6 and unit == sunit
            else:
                self.matches = self.edit_widget.currentText() == text
        elif self.type_str in ['integer', 'float']:
            value, unit, _ = parse_number(text)
            if value is None and text == self.special_str:
                value = self.special_val
            locale = QLocale()
            s = self.edit_widget.text()
            s = s.replace(locale.groupSeparator(), '')
            s = s.replace(locale.decimalPoint(), '.')
            svalue, sunit, _ = parse_number(s)
            if svalue is None and s == self.special_str:
                svalue = self.special_val
            if self.out_unit:
                svalue = change_unit(svalue, sunit, unit)
            self.matches = abs(value - svalue) < 1e-6
        elif self.type_str == 'string':
            self.matches = (self.edit_widget.text() == text)
        if self.matches:
            self.state_widget.setText('&#x2705;')
        else:
            self.state_widget.setText('&#x274C;')

    def set_value(self, text):
        if self.type_str == 'boolean':
            checked = text.lower() in ['yes', 'on', 'true', 'ok', '1']
            self.edit_widget.setChecked(checked)
        elif len(self.selection) > 0:
            if self.type_str in ['integer', 'float']:
                value, unit, _ = parse_number(text)
                for i, s in enumerate(self.selection):
                    svalue, sunit, _ = parse_number(s[1])
                    if abs(value - svalue) < 1e-8 and unit == sunit:
                        self.edit_widget.setCurrentIndex(i)
                        break
            else:
                self.edit_widget.setCurrentText(text)
        elif self.type_str in ['integer', 'float']:
            value, unit, _ = parse_number(text)
            if value is None and text == self.special_str:
                value = self.special_val
            self.edit_widget.setValue(value)
        elif self.type_str == 'string':
            self.edit_widget.setText(text)
        self.verify(text)
    
    def read(self, ident, stream, success):
        for l in stream:
            if self.name in l:
                ss = l.split(':')
                if len(ss) > 1:
                    text = ':'.join(ss[1:]).strip()
                    self.verify(text)
            elif 'new value' in l:
                self.state_widget.setText('&#x274C;')
                

class LoggerActions(Interactor, QWidget, metaclass=InteractorQWidget):

    sigVerifyParameter = Signal(str, str)
    sigSetParameter = Signal(str, str)
    sigConfigFile = Signal(bool)
    
    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.put_button = QPushButton('&Put', self)
        self.put_button.setToolTip('Put configuration to EEPROM memory (Alt+P)')
        self.get_button = QPushButton('&Get', self)
        self.get_button.setToolTip('Get configuration from EEPROM memory (Alt+G)')
        self.clear_button = QPushButton('Clear', self)
        self.clear_button.setToolTip('Clear the full EEPROM memory')
        self.save_button = QPushButton('&Save', self)
        self.save_button.setToolTip('Save the configuration to file on SD card (Alt+S)')
        self.load_button = QPushButton('&Load', self)
        self.load_button.setToolTip('Load the configuration from file on SD card (Alt+L)')
        self.erase_button = QPushButton('&Erase', self)
        self.erase_button.setToolTip('Erase configuration file on SD card (Alt+E)')
        self.check_button = QPushButton('&Check', self)
        self.check_button.setToolTip('Check whether this GUI matches configuration on the logger (Alt+C)')
        self.import_button = QPushButton('&Import', self)
        self.import_button.setToolTip('Import configuration from host (Alt+I)')
        self.export_button = QPushButton('E&xport', self)
        self.export_button.setToolTip('Export configuration file to host (Alt+X)')
        self.firmware_button = QPushButton('Firmware', self)
        self.firmware_button.setToolTip('Upload new firmware (Alt+U)')
        key = QShortcut('Alt+U', self)
        key.activated.connect(self.firmware_button.animateClick)
        self.reboot_button = QPushButton('Re&boot', self)
        self.reboot_button.setToolTip('Reboot logger (Alt+B)')
        self.run_button = QPushButton('&Run', self)
        self.run_button.setToolTip('Run logger (Alt+R)')
        self.put_button.clicked.connect(self.put)
        self.get_button.clicked.connect(self.get)
        self.clear_button.clicked.connect(self.clear)
        self.save_button.clicked.connect(self.save)
        self.load_button.clicked.connect(self.load)
        self.erase_button.clicked.connect(self.erase)
        self.check_button.clicked.connect(self.check)
        self.import_button.clicked.connect(self.importc)
        self.export_button.clicked.connect(self.exportc)
        self.firmware_button.clicked.connect(self.firmware)
        self.reboot_button.clicked.connect(self.reboot)
        self.run_button.clicked.connect(self.run)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(QLabel('<b>EEPROM:</b>'))
        box.addWidget(self.put_button)
        box.addWidget(self.get_button)
        box.addWidget(self.clear_button)
        box.addItem(QSpacerItem(0, 1000, QSizePolicy.Expanding,
                                QSizePolicy.Expanding))
        box.addWidget(QLabel('<b>File:</b>'))
        box.addWidget(self.save_button)
        box.addWidget(self.load_button)
        box.addWidget(self.erase_button)
        box.addItem(QSpacerItem(0, 1000, QSizePolicy.Expanding,
                                QSizePolicy.Expanding))
        box.addWidget(QLabel('<b>Host:</b>'))
        box.addWidget(self.import_button)
        box.addWidget(self.export_button)
        box.addItem(QSpacerItem(0, 1000, QSizePolicy.Expanding,
                                QSizePolicy.Expanding))
        box.addWidget(QLabel('<b>Logger:</b>'))
        box.addWidget(self.check_button)
        box.addItem(QSpacerItem(0, 1000, QSizePolicy.Expanding,
                                QSizePolicy.Expanding))
        box.addWidget(self.reboot_button)
        box.addWidget(self.firmware_button)
        box.addWidget(self.run_button)
        self.start_check = []
        self.start_save = []
        self.start_load = []
        self.start_erase = []
        self.start_put = []
        self.start_get = []
        self.start_clear = []
        self.start_import = []
        self.start_list_firmware = []
        self.start_update_firmware = []
        self.update_stream = []
        self.matches = False
        self.stream_len = 0
        self.config_file = None
    
    def setup(self, menu):
        self.start_check = self.retrieve('configuration>print', menu)
        self.start_put = self.retrieve('configuration>write configuration to eeprom', menu)
        self.start_get = self.retrieve('configuration>read configuration from eeprom', menu)
        self.start_clear = self.retrieve('clear eeprom memory', menu)
        self.start_save = self.retrieve('configuration>save', menu)
        self.start_load = self.retrieve('configuration>load', menu)
        self.start_erase = self.retrieve('configuration>erase', menu)
        self.start_import = self.retrieve('configuration>read configuration from stream', menu)
        self.start_list_firmware = self.retrieve('firmware>list', menu)
        self.start_update_firmware = self.retrieve('firmware>update', menu)
        if len(self.start_list_firmware) == 0:
            self.firmware_button.setVisible(False)
        else:
            self.sigReadRequest.emit(self, 'firmwarecheck',
                                     self.start_list_firmware, ['select'])
        if len(self.start_update_firmware) > 0:
            self.start_update_firmware.append('STAY')

    def put(self):
        self.sigReadRequest.emit(self, 'confput', self.start_put, ['select'])

    def get(self):
        self.sigReadRequest.emit(self, 'confget', self.start_get, ['select'])

    def clear(self):
        self.sigReadRequest.emit(self, 'confclear', self.start_clear, ['select'])

    def save(self):
        self.sigReadRequest.emit(self, 'confsave', self.start_save, ['select'])

    def load(self):
        self.sigReadRequest.emit(self, 'confload', self.start_load, ['select'])

    def erase(self):
        self.sigReadRequest.emit(self, 'conferase', self.start_erase, ['select'])

    def check(self):
        self.sigReadRequest.emit(self, 'confcheck', self.start_check, ['select'])

    def importc(self):
        fname = 'logger.cfg' if self.config_file is None else self.config_file
        file_path, _ = QFileDialog.getOpenFileName(self,
                                                   'Load configuration file',
                                                   fname,
                                                   'configuration files (*.cfg)')
        if not file_path:
            return
        conf_lines = ''
        with open(file_path, 'r') as sf:
            conf_lines = [line.rstrip() for line in sf.readlines()]
        self.sigWriteRequest.emit('DONE', self.start_import + conf_lines)
        self.sigReadRequest.emit(self, 'confimport', self.start_check, ['select'])

    def exportc(self):
        self.sigReadRequest.emit(self, 'confexport', self.start_check,
                                 ['select'])

    def reboot(self):
        self.sigReadRequest.emit(self, 'reboot', ['reboot'], [''])

    def firmware(self):
        self.sigReadRequest.emit(self, 'updatefirmware',
                                 self.start_update_firmware, ['select'])

    def run(self):
        self.sigReadRequest.emit(self, 'run', ['q'], ['halt'])

    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if ident == 'run':
            if len(stream) != self.stream_len:
                self.sigDisplayTerminal.emit('Run logger', stream)
                self.stream_len = len(stream)
        elif 'firmware' in ident:
            if ident == 'firmwarecheck':
                if len(stream) > 1 and 'no firmware files' in stream[1].lower():
                    self.firmware_button.setVisible(False)
            elif ident == 'updatefirmware':
                self.update_stream = []
                if len(stream) > 0 and 'available' in stream[0].lower():
                    del stream[0]
                for k in range(len(stream)):
                    if len(stream[k].strip()) == 0:
                        while k < len(stream):
                            del stream[k]
                        break
                if len(stream) == 1:
                    self.sigReadRequest.emit(self, 'runfirmware1',
                                             ['1', 'STAY'],
                                             ['select', 'enter', 'error'])
                else:
                    text = '<style type="text/css"> td { padding: 0 15px; } th { padding: 0 15px; }</style>'
                    text += '<table>'
                    text += f'<tr><th align="right">No</th><th align="left">Name</th></tr>'
                    for l in stream:
                        p = l.split()
                        number = p[1].rstrip(')')
                        name = p[2]
                        text += f'<tr><td align="right">{number}</td><td align="left">{name}</td></tr>'
                    text += '</table>'
                    self.sigDisplayTerminal.emit('Firmware', text)
                    self.sigReadRequest.emit(self, 'runfirmware1',
                                             ['n', 'STAY'],
                                             ['select', 'enter', 'error'])
            elif ident == 'runfirmware1':
                if len(stream) > 0 and 'aborted' in stream[0].lower():
                    for k in range(len(self.start_update_firmware) - 2):
                        self.sigWriteRequest.emit('q', [])
                elif len(stream) > 0:
                    self.sigDisplayTerminal.emit('Update firmware', stream)
                    if len(stream) > 1 and \
                       'enter' in stream[-2] and 'to flash' in stream[-2]:
                        self.update_stream = list(stream)
                        unlock_code = stream[-2].split()[1]
                        self.sigReadRequest.emit(self, 'runfirmware2',
                                                 [unlock_code, 'STAY'],
                                                 ['reboot'])
            elif ident == 'runfirmware2':
                self.sigDisplayTerminal.emit('Update firmware',
                                             self.update_stream + stream)
        if not ident.startswith('conf'):
            return
        if ident == 'confcheck':
            top_key = None
            text = '<style type="text/css"> td { padding: 0 15px; }</style>'
            text += '<table>'
            for s in stream:
                if 'configuration:' in s.lower():
                    self.sigDisplayTerminal.emit('Current configuration on the logger', text)
                    break
                text += '<tr>'
                cs = s.split(':')
                if len(cs) > 1 and len(cs[1].strip()) > 0:
                    key = cs[0].strip()
                    value = (":".join(cs[1:])).strip()
                    keys = f'{top_key}>{key}' if top_key else key
                    self.sigVerifyParameter.emit(keys, value)
                    text += f'<td></td><td>{key}</td><td><b>{value}</b></td>'
                    if self.matches:
                        text += '<td>&#x2705;</td>'
                    else:
                        text += '<td>&#x274C;</td>'
                else:
                    top_key = cs[0].strip()
                    text += f'<td colspan=4><b>{top_key}</b></td>'
                text += '</tr>'
            text += '</table>'
        elif ident == 'confimport':
            top_key = None
            for s in stream:
                if 'configuration:' in s.lower():
                    break
                cs = s.split(':')
                if len(cs) > 1 and len(cs[1].strip()) > 0:
                    key = cs[0].strip()
                    value = (":".join(cs[1:])).strip()
                    keys = f'{top_key}>{key}' if top_key else key
                    self.sigSetParameter.emit(keys, value)
                else:
                    top_key = cs[0].strip()
        elif ident == 'confexport':
            if success:
                fname = 'logger.cfg' if self.config_file is None else self.config_file
                file_path, _ = QFileDialog.getSaveFileName(self,
                                                           'Save configuration file',
                                                           fname,
                                                           'configuration files (*.cfg)')
                if not file_path:
                    return
                with open(file_path, 'w') as df:
                    for s in stream:
                        if len(s.strip()) == 0:
                            break
                        df.write(s)
                        df.write('\n')
        elif ident == 'confload':
            while len(stream) > 0 and len(stream[0].strip()) == 0:
                del stream[0]
            if len(stream) > 0:
                if 'not found' in stream[0]:
                    self.sigDisplayMessage.emit(stream[0].strip())
                    return
                if 'configuration:' in stream[0].lower():
                    return
                title = stream[0].strip()
            text = '<style type="text/css"> td { padding: 0 15px; }</style>'
            text += '<table>'
            for s in stream[1:]:
                if len(s.strip()) == 0 or 'configuration:' in s.lower():
                    break
                cs = s.split(' to ')
                key = cs[0].strip()[4:]
                value = cs[1].strip()
                self.sigSetParameter.emit(key, value) 
                text += f'<tr><td>set {key}</td><td>to</td><td><b>{value}</b></td>'
                if self.matches:
                    text += '<td>&#x2705;</td></tr>'
                else:
                    text += '<td>&#x274C;</td></tr>'
            text += '</table>'
            self.sigDisplayTerminal.emit(title, text)
        elif ident == 'confget' or ident == 'confput':
            error = False
            text = ''
            for i in range(len(stream)):
                if 'error' in stream[i].lower():
                    error = True
                if 'configuration:' in stream[i].lower():
                    break
            if i > 0:
                if error:
                    self.sigDisplayMessage.emit('\n'.join(stream[:i]))
                else:
                    self.sigDisplayTerminal.emit('EEPROM', stream[:i])
            if success:
                self.sigUpdate.emit()
        elif ident == 'confclear':
            text = ''
            for i in range(len(stream)):
                if 'diagnostics:' in stream[i].lower():
                    break
            if i > 0:
                self.sigDisplayMessage.emit('\n'.join(stream[:i]))
            if success:
                self.sigUpdate.emit()
        else:
            text = ''
            for s in stream:
                if 'configuration:' in s.lower():
                    break
                if ident == 'confsave' and \
                   s.strip().lower().startswith('saved'):
                    self.sigConfigFile.emit(True)
                elif ident == 'conferase' and \
                   s.strip().lower().startswith('removed'):
                    self.sigConfigFile.emit(False)
                text += s.rstrip()
                text += '\n'
            if len(text) > 0:
                self.sigDisplayMessage.emit(text)
            if success:
                self.sigUpdate.emit()

        
class Logger(QWidget):

    sigLoggerDisconnected = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logo = QLabel(self)
        self.logo.setFont(QFont('monospace'))
        self.softwareinfo = SoftwareInfo(self)
        logoboxw = QWidget(self)
        logobox = QHBoxLayout(logoboxw)
        logobox.addWidget(self.logo)
        logobox.addWidget(QLabel())
        logobox.addWidget(self.softwareinfo)
        
        self.msg = QLabel(self)
        
        self.conf = QFrame(self)
        self.conf.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.configuration = QGridLayout()
        self.config_file = QLabel()
        self.config_status = QLabel()
        self.config_status.setTextFormat(Qt.RichText)
        self.config_status.setToolTip('Indicates presence of configuration file')
        self.loggeracts = LoggerActions(self)
        self.loggeracts.sigReadRequest.connect(self.read_request)
        self.loggeracts.sigWriteRequest.connect(self.write_request)
        self.loggeracts.sigDisplayTerminal.connect(self.display_terminal)
        self.loggeracts.sigDisplayMessage.connect(self.display_message)
        self.loggeracts.sigVerifyParameter.connect(self.verify_parameter)
        self.loggeracts.sigSetParameter.connect(self.set_parameter)
        self.loggeracts.sigConfigFile.connect(self.set_configfile_state)
        vbox = QVBoxLayout(self.conf)
        vbox.addLayout(self.configuration)
        
        self.plot_recording = PlotRecording('Recording from analog input', self)
        self.plot_recording.sigClose.connect(lambda: self.stack.setCurrentWidget(self.boxw))
        self.plot_sensors = PlotSensors('Environmental sensors', self)
        self.plot_sensors.done.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        
        self.loggerinfo = LoggerInfo(self)
        self.loggerinfo.sigReadRequest.connect(self.read_request)
        self.loggerinfo.sigDisplayTerminal.connect(self.display_terminal)
        self.loggerinfo.psramtest.sigReadRequest.connect(self.read_request)
        self.loggerinfo.psramtest.sigDisplayTerminal.connect(self.display_terminal)
        self.loggerinfo.rtclock.sigReadRequest.connect(self.read_request)
        self.loggerinfo.rtclock.sigWriteRequest.connect(self.write_request)
        self.hardwareinfo = HardwareInfo(self.plot_recording, self)
        self.hardwareinfo.sigPlot.connect(self.display_recording_plot)
        self.hardwareinfo.sigReadRequest.connect(self.read_request)
        self.hardwareinfo.sigDisplayTerminal.connect(self.display_terminal)
        self.hardwareinfo.sigPlot.connect(self.display_recording_plot)
        self.sensorsinfo = SensorsInfo(self.plot_sensors, self)
        self.sensorsinfo.sigReadRequest.connect(self.read_request)
        self.sensorsinfo.sigPlot.connect(self.display_sensors_plot)
        self.sdcardinfo = SDCardInfo(self)
        self.sdcardinfo.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.sigDisplayMessage.connect(self.display_message)
        self.loggeracts.sigUpdate.connect(self.sdcardinfo.start)
        iboxw = QWidget(self)
        ibox = QGridLayout(iboxw)
        ibox.setContentsMargins(0, 0, 0, 0)
        ibox.addWidget(self.loggerinfo, 0, 0)
        ibox.addWidget(self.sdcardinfo, 0, 1)
        ibox.addWidget(self.hardwareinfo, 1, 0)
        ibox.addWidget(self.sensorsinfo, 1, 1)
        self.boxw = QWidget(self)
        self.box = QHBoxLayout(self.boxw)
        self.box.addWidget(self.loggeracts)
        self.box.addWidget(self.conf)
        self.box.addWidget(iboxw)
        self.term = Terminal(self)
        self.term.done.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.msg)
        self.stack.addWidget(self.boxw)
        self.stack.addWidget(self.term)
        self.stack.addWidget(self.plot_recording)
        self.stack.addWidget(self.plot_sensors)
        self.stack.setCurrentWidget(self.msg)
        vbox = QVBoxLayout(self)
        vbox.addWidget(logoboxw)
        vbox.addWidget(self.stack)

        self.device = None
        self.ser = None
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.read)
        self.read_count = 0
        self.read_state = 0
        self.read_func = None
        self.input = []
        self.request_stack = []
        self.request_block = False
        self.request_type = None
        self.request_target = None
        self.request_ident = None
        self.request_start = None
        self.request_end = None
        self.request_stop = None
        self.request_stop_index = None

        self.menu = {}
        self.menu_iter = []
        self.menu_ids = []
        self.menu_key = None
        self.menu_item = None

    def activate(self, device, model, serial_number):
        #self.title.setText(f'Teensy{model} with serial number {serial_number} on {device}')
        QApplication.restoreOverrideCursor()
        self.device = device
        self.loggerinfo.set(device, model, serial_number)
        self.msg.setText('Reading configuration ...')
        self.msg.setAlignment(Qt.AlignCenter)
        self.stack.setCurrentWidget(self.msg)
        try:
            self.ser = Serial(device)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except (OSError, SerialException):
            self.ser = None
        self.input = []
        self.read_count = 0
        self.read_state = 0
        self.read_func = self.parse_logo
        self.read_timer.start(2)

    def write(self, text):
        if self.ser is not None:
            try:
                self.ser.write(text.encode('latin1'))
                self.ser.write(b'\n')
                self.ser.flush()
            except (OSError, SerialException):
                self.stop()

    def stop(self):
        self.read_timer.stop()
        self.loggerinfo.rtclock.stop()
        if self.ser is not None:
            self.ser.close()
        self.ser = None
        self.sigLoggerDisconnected.emit()

    def display_terminal(self, title, text):
        self.term.display(title, text)
        self.stack.setCurrentWidget(self.term)

    def display_message(self, text):
        if isinstance(text, (tuple, list)):
            text = '\n'.join(text)
        QMessageBox.information(self, 'LoggerConf', text)

    def ask(self, stream):
        text = []
        for s in reversed(stream):
            if len(s.strip()) == 0:
                break
            if s.strip() == '.':
                text.insert(0, '')
            else:
                text.insert(0, s)
        self.clear_input()
        default = '[Y/' in text[-1]
        text[-1] = text[-1][:text[-1].lower().find(' [y/n] ')]
        r = QMessageBox.question(self, 'LoggerConf', '\n'.join(text),
                                 QMessageBox.Yes | QMessageBox.No,
                                 QMessageBox.Yes if default
                                 else QMessageBox.No )
        if r == QMessageBox.Yes:
            self.write('y')
        else:
            self.write('n')

    def display_recording_plot(self):
        self.stack.setCurrentWidget(self.plot_recording)

    def display_sensors_plot(self):
        self.stack.setCurrentWidget(self.plot_sensors)
        
    def find_parameter(self, keys, menu):
        found = False
        for mk in menu:
            if keys[0] == mk:
                found = True
                menu_item = menu[mk]
                if len(keys) > 1:
                    if menu_item[1] == 'menu':
                        p = self.find_parameter(keys[1:], menu_item[2])
                        if p is not None:
                            return p
                        else:
                            found = False
                elif menu_item[1] == 'param':
                    return menu_item[2]
                else:
                    return None
                break
        if not found:
            for mk in menu:
                menu_item = menu[mk]
                if menu_item[1] == 'menu':
                    p = self.find_parameter(keys, menu_item[2])
                    if p is not None:
                        return p
        return None

    def verify_parameter(self, key, value):
        keys = [k.strip() for k in key.split('>') if len(k.strip()) > 0]
        p = self.find_parameter(keys, self.menu)
        if p is None:
            print('WARNING in verify():', key, 'not found')
        else:
            p.verify(value)
            self.loggeracts.matches = p.matches

    def set_parameter(self, key, value):
        keys = [k.strip() for k in key.split('>') if len(k.strip()) > 0]
        p = self.find_parameter(keys, self.menu)
        if p is None:
            print('WARNING in verify():', key, 'not found')
        else:
            p.set_value(value)
            self.loggeracts.matches = p.matches

    def set_configfile_state(self, present):
        if present:
            self.config_status.setText('&#x2705;')
        else:
            self.config_status.setText('&#x274C;')

    def parse_idle(self):
        pass
        
    def parse_halt(self, k):
        s = 'Logger halted\n'
        k -= 1
        while k >= 0 and len(self.input[k]) == 0:
            k -= 1
        self.msg.setText(s + self.input[k])
        self.stack.setCurrentWidget(self.msg)
        self.read_func = self.parse_idle

    def parse_logo(self):
        title_start = None
        title_mid = None
        title_end = None
        for k in range(len(self.input)):
            if 'HALT' in self.input[k]:
                self.parse_halt(k)
                return
            elif self.input[k][:20] == 20*'=':
                title_start = k
            elif title_start is not None and \
                 ' by ' in self.input[k]:
                title_mid = k
            elif title_start is not None and \
                 self.input[k][:20] == 20*'-':
                title_end = k
        if title_start is not None and \
           title_end is not None:
            if title_mid is not None:
                s = ''
                for l in self.input[title_start + 1:title_mid]:
                    if len(l.strip()) == 0:
                        continue
                    if len(s) > 0:
                        s += '\n'
                    s += l
                self.logo.setText(s)
                title_start = title_mid - 1
            self.softwareinfo.set(self.input[title_start + 1:title_end])
            self.input = self.input[title_end + 1:]
            self.read_func = self.parse_configfile
        elif self.read_count > 100:
            self.read_count = 0
            self.write('reboot')
        else:
            self.read_count += 1

    def parse_configfile(self):
        for k in range(len(self.input)):
            if 'configuration file "' in self.input[k].lower():
                config_file = self.input[k].split('"')[1].strip()
                self.config_file.setText(f'<b>{config_file}</b>')
                self.set_configfile_state(not 'not found' in self.input[k])
                self.loggeracts.config_file = config_file
                self.input = self.input[k + 1:]
                for k in range(len(self.input)):
                    if len(self.input[k].strip()) == 0:
                        self.input = self.input[k:]
                        break
                break
            elif '! error: no sd card present' in self.input[k].lower():
                self.input = self.input[k + 1:]
                self.set_configfile_state(False)
                break
        self.read_func = self.configure_menu

    def configure_menu(self):
        if self.read_state == 0:
            self.write('detailed on')
            self.read_state += 1
        elif self.read_state == 1:
            self.write('echo off')
            self.read_state = 0
            self.read_func = self.parse_mainmenu

    def parse_menu(self, title_str):
        menu_start = None
        menu_end = None
        for k in range(len(self.input)):
            if 'HALT' in self.input[k]:
                self.parse_halt(k)
                return
            elif title_str + ':' in self.input[k]:
                menu_start = k
            elif menu_start is not None and \
                 'Select' in self.input[k]:
                menu_end = k
        if menu_start is None or menu_end is None:
            return {}
        menu = {}
        for l in self.input[menu_start + 1:menu_end]:
            x = l.split()
            num = x[0][:-1]
            if x[-1] == '...':
                # sub menu:
                name = ' '.join(x[1:-1])
                menu[name] = (num, 'menu', {})
            else:
                l = ' '.join(x[1:])
                if ':' in l:
                    # parameter:
                    x = l.split(':')
                    name = x[0].strip()
                    value = x[1].strip()
                    menu[name] = [num, 'param', value]
                else:
                    # action:
                    menu[l] = (num, 'action')
        self.input = []
        return menu

    def parse_mainmenu(self):
        if self.read_state == 0:
            self.clear_input()
            self.write('print')
            self.read_state += 1
        elif self.read_state == 1:
            self.menu = self.parse_menu('Menu')
            if len(self.menu) > 0:
                self.menu_iter = [iter(self.menu.items())]
                self.menu_ids = [None]
                self.read_state = 0
                self.read_func = self.parse_submenus
                
    def parse_submenus(self):
        if self.read_state == 0:
            # get next menu entry:
            try:
                if len(self.menu_iter) == 0:
                    exit()
                self.menu_key, self.menu_item = next(self.menu_iter[-1])
                self.menu_ids[-1] = self.menu_item[0]
                if self.menu_item[1] == 'menu':
                    self.read_state = 10
                elif self.menu_item[1] == 'param':
                    self.read_state = 20
            except StopIteration:
                self.menu_iter.pop()
                self.menu_ids.pop()
                if len(self.menu_iter) == 0:
                    self.init_menu()
                    self.clear_input()
                    self.read_func = self.parse_request_stack
                else:
                    self.write('q')
        elif self.read_state == 10:
            # request submenu:
            self.clear_input()
            self.write(self.menu_item[0])
            self.read_state += 1
        elif self.read_state == 11:
            # parse submenu:
            submenu = {}
            if len(self.input) > 1 and 'Select' in self.input[-1]:
                submenu = self.parse_menu(self.menu_key)
            if len(submenu) > 0:
                self.menu_item[2].update(submenu)
                self.menu_iter.append(iter(self.menu_item[2].items()))
                self.menu_ids.append(None)
                self.read_state = 0
        elif self.read_state == 20:
            # request parameter:
            self.clear_input()
            self.write(self.menu_item[0])
            self.read_state += 1
        elif self.read_state == 21:
            # parse parameter:
            list_start = None
            list_end = None
            for k in range(len(self.input)):
                if list_start is None and \
                   self.input[k].lower().startswith(self.menu_key.lower()):
                    list_start = k + 1
                elif list_end is None and \
                     'new value' in self.input[k].lower() and \
                     self.input[k].rstrip()[-1] == ':':
                    list_end = k
            if list_start is None or list_end is None:
                return
            s = self.input[list_end]
            i = s.find('new value')
            s = s[i + s[i:].find('(') + 1:s.find('):')]
            param = Parameter(self.menu_ids, self.menu_key, self.menu_item[2])
            param.initialize(s)
            param.set_selection(self.input[list_start:list_end])
            param.sigTransmitRequest.connect(self.transmit_request)
            self.menu_item[2] = param
            self.write('keepthevalue')
            self.read_state = 0
            

    def init_menu(self):
        # init menu:
        if 'Help' in self.menu:
            self.menu.pop('Help')
        self.loggeracts.setup(self.menu)
        self.loggerinfo.setup(self.menu)
        self.hardwareinfo.setup(self.menu)
        self.sensorsinfo.setup(self.menu)
        self.sdcardinfo.setup(self.menu)
        missing_tools = False
        first_param = True
        row = 0
        for mk in self.menu:
            menu = self.menu[mk]
            add_title = True
            if menu[1] == 'menu':
                for sk in menu[2]:
                    if menu[2][sk][1] == 'param':
                        if add_title:
                            title = QLabel('<b>' + mk + '</b>', self)
                            title.setSizePolicy(QSizePolicy.Policy.Preferred,
                                                QSizePolicy.Policy.Fixed)
                            self.configuration.addWidget(title, row, 0, 1, 4)
                            row += 1
                            add_title = False
                        self.configuration.addItem(QSpacerItem(10, 0), row, 0)
                        self.configuration.addWidget(QLabel(sk + ': ', self),
                                                 row, 1)
                        param = menu[2][sk][2]
                        param.setup(self)
                        self.configuration.addWidget(param.edit_widget, row, 2)
                        self.configuration.addWidget(param.state_widget,
                                                 row, 3)
                        if first_param:
                            param.edit_widget.setFocus(Qt.MouseFocusReason)
                            first_param = False
                        row += 1
                    elif menu[2][sk][1] == 'action':
                        if not missing_tools:
                            print('WARNING! the following tool actions are not supported:')
                            missing_tools = True
                        if add_title:
                            print(f'{mk}:')
                            add_title = False
                        print(f'  {sk}')
        self.configuration.addWidget(QLabel('Configuration file'), row, 0, 1, 2)
        self.configuration.addWidget(self.config_file, row, 2)
        self.configuration.addWidget(self.config_status, row, 3)
        self.hardwareinfo.start()
        self.sensorsinfo.start()
        self.sdcardinfo.start()
        self.loggerinfo.start()
        self.stack.setCurrentWidget(self.boxw)
            
    def parse_request_stack(self):
        if len(self.request_stack) == 0:
            if self.request_type is None:
                self.request_block = False
            return
        self.clear_input()
        request = self.request_stack.pop(0)
        self.request_target = request[0]
        self.request_ident = request[1]
        self.request_start = request[2]
        self.request_end = request[3]
        self.request_stop = request[4]
        if not isinstance(self.request_stop, (list, tuple)):
            self.request_stop = (self.request_stop, )
        self.request_stop_index = None
        self.request_type = request[5]
        self.read_state = 0
        if self.request_type in ['read', 'transmit']:
            self.read_func = self.parse_read_request
        else:
            self.read_func = self.parse_write_request
        self.read_func()

    def read_request(self, target, ident, start, stop, act='read'):
        if len(start) == 0:
            return
        # put each request only once onto the stack:
        for req in self.request_stack:
            if req[0] == target and req[1] == ident and req[-1] == act:
                return
        block = self.request_block
        if start[-1] == 'STAY':
            start.pop()
            end = False
            self.request_block = True
            block = False
        else:
            end = True
        if not block:
            self.request_stack.append([target, ident, start, end, stop, act])
        if self.read_func == self.parse_request_stack:
            self.parse_request_stack()
            
    def transmit_request(self, target, ident, start):
        stop = ['select', 'new value']
        self.read_request(target, ident, start, stop, 'transmit')

    def parse_read_request(self):
        if self.read_state == 0:
            self.clear_input()
            self.write(self.request_start[0])
            self.request_start.pop(0)
            if len(self.request_start) > 0:
                self.read_state = 4
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            if self.request_type == 'read' and len(self.input) > 0 and \
               self.input[-1].lower().endswith(' [y/n] '):
                self.ask(self.input)
                self.read_state = 1
            elif self.request_stop is None or \
               len(self.request_stop) == 0:
                self.read_state += 1
            elif len(self.input) > 0:
                last_line = self.input[-1].lower()
                if len(last_line.strip()) == 0 and len(self.input) > 1:
                    last_line = self.input[-2].lower()
                for k in reversed(range(len(self.request_stop))):
                    if self.request_stop[k] in last_line:
                        self.request_stop = None
                        self.request_stop_index = k
                        self.read_state += 1
                        break
            if self.request_ident[:3] == 'run' and \
               self.request_target is not None and \
               self.request_stop_index != 0:
                    self.request_target.read(self.request_ident,
                                             self.input,
                                             self.request_stop_index == 0)
        elif self.read_state == 2:
            if self.request_target is not None:
                self.request_target.read(self.request_ident,
                                         self.input,
                                         self.request_stop_index == 0)
                self.request_target = None
            if self.request_type == 'transmit' and self.request_stop_index == 1:
                self.write('keepthevalue')
            self.read_state += 1
        elif self.read_state == 3:
            self.clear_input()
            if self.request_end:
                self.write('h')
            self.request_type = None
            self.read_func = self.parse_request_stack
        elif self.read_state == 4:
            stop_str = 'select'
            if self.request_type == 'transmit' and len(self.request_start) == 1:
                stop_str = 'new value'
            if len(self.input) > 0 and \
               stop_str in self.input[-1].lower():
                self.read_state = 0

    def write_request(self, msg, start):
        if len(start) == 0:
            return
        if not self.request_block:
            self.request_stack.append([msg, None, start,
                                       True, None, 'write'])
        if self.read_func == self.parse_request_stack:
            self.parse_request_stack()

    def parse_write_request(self):
        if self.read_state == 0:
            self.clear_input()
            if len(self.request_start) > 0:
                self.write(self.request_start[0])
                self.request_start.pop(0)
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            self.clear_input()
            self.write(self.request_target)
            self.request_target = None
            self.read_state += 1
        elif self.read_state == 2:
            self.clear_input()
            if self.request_end:
                self.write('h')
            self.request_type = None
            self.read_func = self.parse_request_stack

    def read(self):
        if self.ser is None:
            try:
                print('open serial')
                self.ser = Serial(self.device)
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except (OSError, SerialException):
                print('  FAILED')
                self.ser = None
                self.stop()
                return
        try:
            if self.ser.in_waiting > 0:
                # read in incoming data:
                x = self.ser.read(self.ser.in_waiting)
                lines = x.decode('utf8').split('\n')
                if len(self.input) == 0:
                    self.input = ['']
                self.input[-1] += lines[0].rstrip('\r')
                for l in lines[1:]:
                    self.input.append(l.rstrip('\r'))
            else:
                # execute requests:
                self.read_func()
        except (OSError, SerialException):
            self.stop()
            
    def clear_input(self):
        if self.ser is not None:
            try:
                self.ser.reset_input_buffer()
            except (OSError, SerialException):
                self.stop()
        self.input = []
        

class LoggerConf(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'LoggerConf {__version__}')
        self.scanlogger = ScanLogger(self)
        self.scanlogger.sigLoggerFound.connect(self.activate)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.scanlogger)
        self.stack.setCurrentWidget(self.scanlogger)
        self.setCentralWidget(self.stack)
        quit = QAction('&Quit', self)
        quit.setShortcuts(QKeySequence.Quit)
        quit.triggered.connect(QApplication.quit)
        self.addAction(quit)
        self.logger = None
        # default colors:
        back_color = self.palette().color(QPalette.Window)
        text_color = self.palette().color(QPalette.WindowText)
        pg.setConfigOption('background', back_color)
        pg.setConfigOption('foreground', text_color)

    def activate(self, device, model, serial_number):
        self.logger = Logger(self)
        self.logger.sigLoggerDisconnected.connect(self.disconnect)
        self.logger.activate(device, model, serial_number)
        self.stack.addWidget(self.logger)
        self.stack.setCurrentWidget(self.logger)

    def disconnect(self):
        self.stack.removeWidget(self.logger)
        del self.logger
        self.logger = None
        self.scanlogger.start()
        self.stack.setCurrentWidget(self.scanlogger)


def main():
    app = QApplication(sys.argv)
    main = LoggerConf()
    main.show()
    app.exec_()

    
if __name__ == '__main__':
    main()

