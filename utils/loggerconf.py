# https://github.com/pyserial/pyserial
try:
    import serial
    from serial.tools.list_ports import comports
except ImportError:
    print('ERROR: failed to import serial module !')
    print('You need to install the pyserial package using')
    print('> pip install pyserial')
    exit()
    
# https://github.com/pyusb/pyusb
# pip install pyusb
try:
    import usb.core
    has_usb = True
except ImportError:
    has_usb = False
    
import sys
import numpy as np
from abc import ABC, abstractmethod
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QObject, QTimer, QDateTime, QLocale
from PyQt5.QtGui import QKeySequence, QFont, QPalette, QColor, QValidator
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QStackedWidget, QLabel, QScrollArea
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout, QSpacerItem
from PyQt5.QtWidgets import QWidget, QFrame, QPushButton, QSizePolicy
from PyQt5.QtWidgets import QAction, QShortcut
from PyQt5.QtWidgets import QCheckBox, QLineEdit, QComboBox, QSpinBox, QAbstractSpinBox


__version__ = '1.0'


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
                f1 = unit_prefixes[k];
  
    # parse new unit:
    f2 = 1.0
    if new_unit in unit_factors:
        f2 = unit_factors[new_unit]
    else:
        for k in unit_prefixes:
            if len(new_unit) > len(k) and new_unit[:len(k)] == k:
                f2 = unit_prefixes[k];
  
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

    if has_usb:
        dev = usb.core.find(idVendor=vid, idProduct=pid,
                            serial_number=serial_number)
        if dev is None:
            # this happens when we do not have permissions for the device!
            return ''
        else:
            return teensy_model[dev.bcdDevice]
    else:
        return ''


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
            # we should also check for permissions!
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

    sigReadRequest = Signal(object, str, list, str)
    sigWriteRequest = Signal(str, list)
    sigTransmitRequest = Signal(object, str, list)
    sigDisplayTerminal = Signal(str, object)
    sigDisplayMessage = Signal(object)
    sigUpdateSDCard = Signal()

    @abstractmethod
    def setup(self, menu):
        pass

    def retrieve(self, key, menu):
        
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
        else:
            print(key, 'not found')
            return None

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
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.addWidget(self.time)
        self.box.addWidget(self.state)
        self.start_get = None
        self.start_set = None
        self.set_count = 50
        self.set_state = 0
        self.prev_time = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.get_time)
    
    def setup(self, menu):
        self.start_get = self.retrieve('date & time>print', menu)
        self.start_set = self.retrieve('date & time>set', menu)

    def start(self):
        self.set_count = 50
        if self.start_get is not None:
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
                                         self.start_get, 'select')

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
                    else:
                        self.state.setText('&#x274C;')
                        self.set_count = 1
                    break

    def set_time(self):
        if self.start_set is None:
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
        self.start = None

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
        self.sigReadRequest.emit(self, 'run', self.start, 'select')

                
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
        self.box.addWidget(title, 0, 0, 1, 3)
        self.psramtest = PSRAMTest(self)
        self.psramtest.setToolTip('Test PSRAM memory (Ctrl+P)')
        key = QShortcut("CTRL+P", self)
        key.activated.connect(self.psramtest.animateClick)
        self.device = None
        self.model = None
        self.serial_number = None
        self.controller_start_get = None
        self.psram_start_get = None
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

    def add(self, label, value, button=None):
        self.box.addWidget(QLabel(label, self), self.row, 0)
        if button is None:
            self.box.addWidget(QLabel('<b>' + value + '</b>', self),
                               self.row, 1, 1, 2)
        else:
            self.box.addWidget(QLabel('<b>' + value + '</b>', self),
                               self.row, 1)
            self.box.addWidget(button, self.row, 2)
        self.row += 1
        
    def start(self):
        self.row = 1
        self.add('device', self.device)
        self.sigReadRequest.emit(self, 'controller',
                                 self.controller_start_get, 'select')
        self.sigReadRequest.emit(self, 'psram',
                                 self.psram_start_get, 'select')

    def read(self, ident, stream, success):
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
                    self.add('<u>P</u>SRAM size', value, self.psramtest)
                else:
                    continue
            else:
                self.add(label, value)
        if ident == 'psram':
            self.box.addWidget(QLabel('Time', self), self.row, 0)
            self.box.addWidget(self.rtclock, self.row, 1, 1, 2)
            self.row += 1
            self.rtclock.start()


class SoftwareInfo(QFrame):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.box = QGridLayout(self)
        title = QLabel('<b>Software</b>', self)
        self.box.addWidget(title, 0, 0, 1, 2)
        self.row = 1

    def add(self, label, value):
        self.box.addWidget(QLabel(label, self), self.row, 0)
        self.box.addWidget(QLabel('<b>' + value + '</b>', self), self.row, 1)
        self.row += 1

    def set(self, stream):
        n = 0
        for s in stream:
            s = s.strip()
            if len(s) > 0:
                if n == 0:
                    i = s.find(' by ')
                    if i < 0:
                        i = len(s)
                    j = s[:i].find(' v')
                    if j < 0:
                        j = i
                    self.add('Software', s[:j])
                    if j < i:
                        self.add('Version', s[j + 2:i])
                    if i < len(s):
                        self.add('Author', s[i + 4:])
                else:
                    s = s.replace('based on ', '')
                    s = s.replace('and ', '')
                    self.add(f'Library {n}', s)
                n += 1

                
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
            self.sigUpdateSDCard.emit()

                
class ListFiles(ReportButton):
    
    def __init__(self, name='List', *args, **kwargs):
        super().__init__('', name, *args, **kwargs)

    def setup(self, start):
        self.start = start
        
    def read(self, ident, stream, success):
        if len(stream) == 0:
            return
        title = None
        text = '<style type="text/css"> th, td { padding: 0 15px; }</style>'
        text += '<table>'
        for s in stream:
            if title is None:
                if 'does not exist' in s.lower():
                    self.sigDisplayMessage.emit(s)
                    return
                if s.lower().strip().startswith('files in') or s.lower().strip().startswith('erase all files in'):
                    title = s
            else:
                if ' name' in s.lower():
                    text += f'<tr><th align="right">size (bytes)</th><th align="left">name</th></tr>'
                elif 'found' in s.lower() or s.strip().lower().startswith('removed'):
                    text += f'<tr><td colspan=2>{s.strip()}</td></tr>'
                    break
                else:
                    text += '<tr>'
                    cs = s.split()
                    if len(cs) > 1:
                        text += f'<td align="right">{cs[0]}</td>'
                        text += f'<td align="left">{(" ".join(cs[1:]))}</td>'
                    else:
                        text += f'<td></td><td align="left">{s.strip()}</td>'
                    text += '</tr>'
        text += '</table>'
        if title is not None:
            self.sigDisplayTerminal.emit(title, text)

                
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
        self.eraserecordings = ListFiles('&Delete')
        self.eraserecordings.setToolTip('Delete all recordings (Ctrl+D)')
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
        self.root.sigReadRequest.connect(self.sigReadRequest)
        self.root.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.root.sigDisplayMessage.connect(self.sigDisplayMessage)
        self.bench.sigReadRequest.connect(self.sigReadRequest)
        self.bench.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.formatcard.sigUpdateSDCard.connect(self.start)
        self.erasecard.sigUpdateSDCard.connect(self.start)
        
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
        key = QShortcut('Ctrl+D', self)
        key.activated.connect(self.eraserecordings.animateClick)
        key = QShortcut('Ctrl+W', self)
        key.activated.connect(self.bench.animateClick)
        self.box = QGridLayout(self)
        title = QLabel('<b>SD card</b>', self)
        self.box.addWidget(title, 0, 0, 1, 2)
        self.box.addWidget(self.checkcard, 0, 2, Qt.AlignRight)
        self.sdcard_start_get = None
        self.root_start_get = None
        self.recordings_start_get = None
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
            self.retrieve('sd card>erase all recordings', menu)
        self.root.setup(self.root_start_get)
        self.recordings.setup(self.recordings_start_get)
        self.eraserecordings.setup(erase_recordings_start)
        self.checkcard.setup(menu)
        self.bench.setup(menu)
        self.formatcard.setup(menu)
        self.erasecard.setup(menu)

    def add(self, label, value, button2=None, button1=None):
        if self.box.itemAtPosition(self.row, 0) is not None:
            w = self.box.itemAtPosition(self.row, 1).widget()
            w.setText('<b>' + value + '</b>')
        else:
            self.box.addWidget(QLabel(label, self), self.row, 0)
            self.box.addWidget(QLabel('<b>' + value + '</b>', self),
                               self.row, 1, Qt.AlignRight)
            if button1 is not None:
                box = QHBoxLayout()
                box.setContentsMargins(0, 0, 0, 0)
                self.box.addLayout(box, self.row, 2)
                box.addWidget(button1)
                box.addWidget(button2)
            elif button2 is not None:
                self.box.addWidget(button2, self.row, 2, Qt.AlignRight)
        self.row += 1

    def start(self):
        self.row = 1
        self.sigReadRequest.emit(self, 'recordings',
                                 self.recordings_start_get, 'select')
        self.sigReadRequest.emit(self, 'root',
                                 self.root_start_get, 'select')
        self.sigReadRequest.emit(self, 'sdcard',
                                 self.sdcard_start_get, 'select')

    def read(self, ident, stream, success):

        def num_files(stream):
            for s in stream:
                if 'does not exist' in s:
                    return 0, None
                if 'file' in s and 'found' in s and s[:2] != 'No':
                    nf = int(s[:s.find(' file')])
                    ns = None
                    if '(' in s and 'MB)' in s:
                        ns = s[s.find('(') + 1:s.find(')')]
                    return nf, ns
            return 0, None

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
                        if keys == 'capacity':
                            self.add(items[i][0], items[i][1], self.formatcard)
                        elif keys == 'available':
                            self.add(items[i][0], items[i][1], self.erasecard)
                            if available is not None:
                                a = float(available.replace(' GB', ''))
                                c = float(items[i][1].replace(' GB', ''))
                                self.add('Used', f'{100 - 100*a/c:.0f} %')
                            value = 'none'
                            if self.nrecordings > 0:
                                value = f'{self.nrecordings}'
                            if self.srecordings is not None:
                                value += f' ({self.srecordings})'
                            self.add('<u>R</u>ecorded files', value,
                                     self.recordings, self.eraserecordings)
                            value = 'none'
                            if self.nroot > 0:
                                value = f'{self.nroot}'
                            if self.sroot is not None:
                                value += f' ({self.sroot})'
                            self.add('R<u>o</u>ot files', value, self.root)
                        else:
                            self.add(items[i][0], items[i][1])
            self.add('<u>W</u>rite speed', 'none', self.bench)
            self.bench.set_value(self.box.itemAtPosition(self.row - 1, 1).widget())


class Terminal(QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = QLabel(self)
        self.out = QLabel(self)
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
        else:
            self.out.setText(stream)
        self.out.setMinimumSize(self.out.sizeHint())
        vsb = self.scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())


class Message(QLabel):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignCenter)

    def clear(self):
        self.setText('')

    def display(self, stream):
        if isinstance(stream, (tuple, list)):
            text = ''
            for s in stream:
                text += s
                text += '\n'
            self.setText(text)
        else:
            self.setText(stream)


class YesNoQuestion(QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg = QLabel(self)
        self.msg.setAlignment(Qt.AlignCenter)
        self.yesb = QPushButton(self)
        self.yesb.setText('&Yes')
        self.yesb.setToolTip('Accept (Return, Y, Ctrl+Y)')
        self.yesb.clicked.connect(self.accept)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.yesb.animateClick)
        key = QShortcut(Qt.Key_Y, self)
        key.activated.connect(self.yesb.animateClick)
        key = QShortcut('Ctrl+Y', self)
        key.activated.connect(self.yesb.animateClick)
        self.nob = QPushButton(self)
        self.nob.setText('&No')
        self.yesb.setToolTip('Reject (Escape, N, Ctrl+N)')
        self.nob.clicked.connect(self.reject)
        key = QShortcut(QKeySequence.Cancel, self)
        key.activated.connect(self.nob.animateClick)
        key = QShortcut(Qt.Key_N, self)
        key.activated.connect(self.nob.animateClick)
        key = QShortcut('Ctrl+N', self)
        key.activated.connect(self.nob.animateClick)
        buttons = QWidget(self)
        hbox = QHBoxLayout(buttons)
        hbox.addWidget(self.nob)
        hbox.addWidget(QLabel(self))
        hbox.addWidget(self.yesb)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.msg)
        vbox.addWidget(buttons)
        self.yes = None

    def clear(self):
        self.yes = None
        self.msg.setText('')

    def ask(self, stream):
        self.yes = None
        text = []
        for s in reversed(stream):
            if len(s.strip()) == 0:
                break
            text.insert(0, s)
        text[-1] = text[-1][:text[-1].lower().find(' [y/n] ')]
        self.msg.setText('\n'.join(text))
        self.setFocus(Qt.MouseFocusReason)

    def accept(self):
        self.yes = True
        
    def reject(self):
        self.yes = False


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
        self._maxmimum = None
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
                self.special_val = int(special[special.find('[') + 1:special.find(']')])
        if self.type_str in ['float', 'integer'] and self.num_value is None:
            if self.value == self.special_str:
                self.num_value = self.special_val

    def set_selection(self, stream):
        self.selection = []
        for k, l in enumerate(stream):
            sel = l[4:]
            i = sel.find(') ')
            if sel[:i].isdigit():
                sel = (sel[:i], sel[i + 2:])
            else:
                sel = (k, sel)
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
            for s in self.selection:
                si = s[1]
                if si == self.value:
                    idx = s[0]
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
        start.append("yes" if check_state > 0 else "no")
        self.sigTransmitRequest.emit(self, self.name, start)

    def transmit_str(self, text):
        start = list(self.ids)
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
                for s in self.selection:
                    svalue, sunit, _ = parse_number(s[1])
                    if abs(value - svalue) < 1e-8 and unit == sunit:
                        self.edit_widget.setCurrentIndex(s[0])
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
                

class ConfigActions(Interactor, QWidget, metaclass=InteractorQWidget):

    sigVerifyParameter = Signal(str, str)
    sigSetParameter = Signal(str, str)
    sigConfigFile = Signal(bool)
    
    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.save_button = QPushButton('&Save', self)
        self.save_button.setToolTip('Save the configuration to file on SD card (Alt+S)')
        self.load_button = QPushButton('&Load', self)
        self.load_button.setToolTip('Load the configuration from file on SD card (Alt+L)')
        self.erase_button = QPushButton('&Erase', self)
        self.erase_button.setToolTip('Erase configuration file on SD card (Alt+E)')
        self.check_button = QPushButton('&Check', self)
        self.check_button.setToolTip('Check the configuration on the logger (Alt+C)')
        self.run_button = QPushButton('&Run', self)
        self.run_button.setToolTip('Run logger (Alt+R)')
        self.save_button.clicked.connect(self.save)
        self.load_button.clicked.connect(self.load)
        self.erase_button.clicked.connect(self.erase)
        self.check_button.clicked.connect(self.check)
        self.run_button.clicked.connect(self.run)
        box = QGridLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.save_button, 0, 0)
        box.addWidget(self.load_button, 0, 1)
        box.addWidget(self.erase_button, 0, 2)
        box.addWidget(self.check_button, 0, 3)
        box.addWidget(self.run_button, 1, 3)
        self.start_check = None
        self.start_load = None
        self.start_save = None
        self.start_erase = None
        self.matches = False
    
    def setup(self, menu):
        self.start_check = self.retrieve('configuration>print', menu)
        self.start_load = self.retrieve('configuration>load', menu)
        self.start_save = self.retrieve('configuration>save', menu)
        self.start_erase = self.retrieve('configuration>erase', menu)

    def save(self):
        self.sigReadRequest.emit(self, 'confsave', self.start_save, 'select')

    def load(self):
        self.sigReadRequest.emit(self, 'confload', self.start_load, 'select')

    def erase(self):
        self.sigReadRequest.emit(self, 'conferase', self.start_erase, 'select')

    def check(self):
        self.sigReadRequest.emit(self, 'confcheck', self.start_check, 'select')

    def run(self):
        self.sigReadRequest.emit(self, 'run', ['q'], 'halt')

    def read(self, ident, stream, success):
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if ident == 'run':
            self.sigDisplayTerminal.emit('Run logger', stream)
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
                self.sigUpdateSDCard.emit()

        
class Logger(QWidget):

    sigLoggerDisconnected = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logo = QLabel(self)
        self.logo.setFont(QFont('monospace'))
        self.msg = QLabel(self)
        
        self.conf = QFrame(self)
        self.conf.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.conf_grid = QGridLayout()
        self.config_file = QLabel()
        self.config_status = QLabel()
        self.config_status.setTextFormat(Qt.RichText)
        self.config_status.setToolTip('Indicates presence of configuration file')
        self.configuration = ConfigActions(self)
        self.configuration.sigReadRequest.connect(self.read_request)
        self.configuration.sigDisplayTerminal.connect(self.display_terminal)
        self.configuration.sigDisplayMessage.connect(self.display_message)
        self.configuration.sigVerifyParameter.connect(self.verify_parameter)
        self.configuration.sigSetParameter.connect(self.set_parameter)
        self.configuration.sigConfigFile.connect(self.set_configfile_state)
        self.question = YesNoQuestion(self)
        self.question.yesb.clicked.connect(self.close_question)
        self.question.nob.clicked.connect(self.close_question)
        self.message = Message(self)
        self.cstack = QStackedWidget(self)
        self.cstack.addWidget(self.message)
        self.cstack.addWidget(self.question)
        self.cstack.setCurrentWidget(self.message)
        vbox = QVBoxLayout(self.conf)
        vbox.addLayout(self.conf_grid)
        vbox.addWidget(self.configuration)
        vbox.addWidget(self.cstack)
        
        self.loggerinfo = LoggerInfo(self)
        self.loggerinfo.sigReadRequest.connect(self.read_request)
        self.loggerinfo.psramtest.sigReadRequest.connect(self.read_request)
        self.loggerinfo.psramtest.sigDisplayTerminal.connect(self.display_terminal)
        self.loggerinfo.rtclock.sigReadRequest.connect(self.read_request)
        self.loggerinfo.rtclock.sigWriteRequest.connect(self.write_request)
        self.softwareinfo = SoftwareInfo(self)
        self.sdcardinfo = SDCardInfo(self)
        self.sdcardinfo.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.sigDisplayMessage.connect(self.display_message)
        self.configuration.sigUpdateSDCard.connect(self.sdcardinfo.start)
        iboxw = QWidget(self)
        ibox = QVBoxLayout(iboxw)
        ibox.setContentsMargins(0, 0, 0, 0)
        ibox.addWidget(self.loggerinfo)
        ibox.addWidget(self.softwareinfo)
        ibox.addWidget(self.sdcardinfo)
        self.boxw = QWidget(self)
        self.box = QHBoxLayout(self.boxw)
        self.box.addWidget(self.conf)
        self.box.addWidget(iboxw)
        self.term = Terminal(self)
        self.term.done.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.msg)
        self.stack.addWidget(self.boxw)
        self.stack.addWidget(self.term)
        self.stack.setCurrentWidget(self.msg)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.logo)
        vbox.addWidget(self.stack)
        self.last_focus = None

        self.device = None
        self.ser = None
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.read)
        self.read_count = 0
        self.read_state = 0
        self.read_func = None
        self.input = []
        self.request_stack = []
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
        self.device = device
        self.loggerinfo.set(device, model, serial_number)
        self.msg.setText('Reading configuration ...')
        self.msg.setAlignment(Qt.AlignCenter)
        self.stack.setCurrentWidget(self.msg)
        try:
            self.ser = serial.Serial(device)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except (OSError, serial.serialutil.SerialException):
            self.ser = None
        self.input = []
        self.read_count = 0
        self.read_state = 0
        self.read_func = self.parse_logo
        self.read_timer.start(2)

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
        self.message.display(text)
        self.cstack.setCurrentWidget(self.message)

    def close_question(self):
        if self.last_focus is not None:
            self.last_focus.setFocus(Qt.MouseFocusReason)
            self.last_focus = None
        self.cstack.setCurrentWidget(self.message)
        
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
            self.configuration.matches = p.matches

    def set_parameter(self, key, value):
        keys = [k.strip() for k in key.split('>') if len(k.strip()) > 0]
        p = self.find_parameter(keys, self.menu)
        if p is None:
            print('WARNING in verify():', key, 'not found')
        else:
            p.set_value(value)
            self.configuration.matches = p.matches

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
            self.ser.write('reboot\n'.encode('latin1'))
            self.ser.flush()
        else:
            self.read_count += 1

    def parse_configfile(self):
        for k in range(len(self.input)):
            if 'configuration file "' in self.input[k].lower():
                config_file = self.input[k].split('"')[1].strip()
                self.config_file.setText(f'<b>{config_file}</b>')
                self.set_configfile_state(not 'not found' in self.input[k])
                self.input = self.input[k + 1:]
                for k in range(len(self.input)):
                    if len(self.input[k].strip()) == 0:
                        self.input = self.input[k:]
                        break
                self.read_func = self.configure_menu
                break

    def configure_menu(self):
        if self.read_state == 0:
            self.ser.write(b'detailed on\n')
            self.ser.flush()
            self.read_state += 1
        elif self.read_state == 1:
            self.ser.write(b'echo off\n')
            self.ser.flush()
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
            self.ser.write(b'print\n')
            self.ser.flush()
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
                    self.ser.write('q\n'.encode('latin1'))
                    self.ser.flush()
        elif self.read_state == 10:
            # request submenu:
            self.clear_input()
            self.ser.write(self.menu_item[0].encode('latin1'))
            self.ser.write(b'\n')
            self.ser.flush()
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
            self.ser.write(self.menu_item[0].encode('latin1'))
            self.ser.write(b'\n')
            self.ser.flush()
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
                     self.input[k].lower().startswith('select new value'):
                    list_end = k
                elif list_end is None and \
                     self.input[k].lower().startswith('enter new value'):
                    list_end = k
            if list_start is None or list_end is None:
                return
            s = self.input[list_end]
            s = s[s.find('new value (') + 11:s.find('):')]
            param = Parameter(self.menu_ids, self.menu_key, self.menu_item[2])
            param.initialize(s)
            param.set_selection(self.input[list_start:list_end])
            param.sigTransmitRequest.connect(self.transmit_request)
            self.menu_item[2] = param
            self.ser.write(b'keepthevalue\n')
            self.ser.flush()
            self.read_state = 0
            

    def init_menu(self):
        # init menu:
        if 'Help' in self.menu:
            self.menu.pop('Help')
        self.configuration.setup(self.menu)
        self.loggerinfo.setup(self.menu)
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
                            self.conf_grid.addWidget(title, row, 0, 1, 4)
                            row += 1
                            add_title = False
                        self.conf_grid.addItem(QSpacerItem(10, 0), row, 0)
                        self.conf_grid.addWidget(QLabel(sk + ': ', self),
                                                 row, 1)
                        param = menu[2][sk][2]
                        param.setup(self)
                        self.conf_grid.addWidget(param.edit_widget, row, 2)
                        self.conf_grid.addWidget(param.state_widget,
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
        self.conf_grid.addWidget(QLabel('Configuration file'), row, 0, 1, 2)
        self.conf_grid.addWidget(self.config_file, row, 2)
        self.conf_grid.addWidget(self.config_status, row, 3)
        self.sdcardinfo.start()
        self.loggerinfo.start()
        self.stack.setCurrentWidget(self.boxw)
            
    def parse_request_stack(self):
        if len(self.request_stack) == 0:
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
        if start is None:
            return
        # put each request only once onto the stack:
        for req in self.request_stack:
            if req[0] == target and req[1] == ident and req[-1] == act:
                return
        end = len(start) - 1
        if act == 'transmit':
            end -= 1
        self.request_stack.append([target, ident, start, end,
                                   stop, act])
        if self.read_func == self.parse_request_stack:
            self.parse_request_stack()
            
    def transmit_request(self, target, ident, start):
        stop = ['select', 'new value']
        self.read_request(target, ident, start, stop, 'transmit')

    def parse_read_request(self):
        if self.read_state == 0:
            if len(self.request_start) > 0:
                self.clear_input()
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.ser.flush()
                self.request_start.pop(0)
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            if len(self.input) > 0 and \
               self.input[-1].lower().endswith(' [y/n] '):
                self.message.clear()
                self.last_focus = QApplication.focusWidget()
                self.question.ask(self.input)
                self.cstack.setCurrentWidget(self.question)
                self.input = []
                self.read_state = 5
            elif self.request_stop is None or \
               len(self.request_stop) == 0:
                self.read_state += 1
            elif len(self.input) > 0:
                for k in range(len(self.request_stop)):
                    if self.request_stop[k] in self.input[-1].lower():
                        self.request_stop = None
                        self.request_stop_index = k
                        self.read_state += 1
                        break
            if self.request_ident[:3] == 'run':
                if self.request_target is not None:
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
                self.ser.write(b'keepthevalue\n')
                self.ser.flush()
            self.read_state += 1
        elif self.read_state == 3:
            self.clear_input()
            if self.request_end > 0:
                self.ser.write(b'q\n')
                self.ser.flush()
                self.request_end -= 1
            else:
                self.request_end = None
                self.request_type = None
                self.read_func = self.parse_request_stack
        elif self.read_state == 5:
            if self.question.yes is not None:
                self.clear_input()
                if self.question.yes:
                    self.ser.write(b'y\n')
                else:
                    self.ser.write(b'n\n')
                self.ser.flush()
                self.question.clear()
                self.cstack.setCurrentWidget(self.message)
                self.read_state = 1

    def write_request(self, msg, start):
        if start is None:
            return
        self.request_stack.append([msg, None, start,
                                   len(start) - 1, None, 'write'])
        if self.read_func == self.parse_request_stack:
            self.parse_request_stack()

    def parse_write_request(self):
        if self.read_state == 0:
            self.clear_input()
            if len(self.request_start) > 0:
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.ser.flush()
                self.request_start.pop(0)
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            self.clear_input()
            self.ser.write(self.request_target.encode('latin1'))
            self.ser.write(b'\n')
            self.ser.flush()
            self.request_target = None
            self.read_state += 1
        elif self.read_state == 2:
            self.clear_input()
            if self.request_end > 0:
                self.ser.write(b'q\n')
                self.ser.flush()
                self.request_end -= 1
            else:
                self.request_end = None
                self.request_type = None
                self.read_func = self.parse_request_stack

    def read(self):
        if self.ser is None:
            try:
                print('open serial')
                self.ser = serial.Serial(self.device)
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except (OSError, serial.serialutil.SerialException):
                print('  FAILED')
                self.ser = None
                self.stop()
                return
        try:
            if self.ser.in_waiting > 0:
                # read in incoming data:
                x = self.ser.read(self.ser.in_waiting)
                lines = x.decode('latin1').split('\n')
                if len(self.input) == 0:
                    self.input = ['']
                self.input[-1] += lines[0].rstrip('\r')
                for l in lines[1:]:
                    self.input.append(l.rstrip('\r'))
            else:
                # execute requests:
                self.read_func()
        except (OSError, serial.serialutil.SerialException):
            self.stop()
            
    def clear_input(self):
        self.ser.reset_input_buffer()
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

