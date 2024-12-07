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
from PyQt5.QtGui import QKeySequence, QFont, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QStackedWidget, QLabel, QScrollArea
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout
from PyQt5.QtWidgets import QWidget, QFrame, QPushButton, QSizePolicy
from PyQt5.QtWidgets import QAction, QShortcut
from PyQt5.QtWidgets import QCheckBox, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox


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
                    submenu = menu_item[1]
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
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.addWidget(self.time)
        self.box.addWidget(self.state)
        self.is_set = 0
        self.start_get = None
        self.start_set = None
        self.set_state = 0
        self.prev_time = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.get_time)
    
    def setup(self, menu):
        self.start_get = self.retrieve('date & time>print', menu)
        self.start_set = self.retrieve('date & time>set', menu)

    def start(self):
        self.is_set = 0
        if self.start_get is not None:
            self.timer.start(50)

    def stop(self):
        self.timer.stop()

    def get_time(self):
        if self.set_state > 0:
            self.set_time()
        else:            
            self.is_set += 1
            if self.is_set == 50:
                self.set_state = 1
                self.set_time()
            else:
                self.sigReadRequest.emit(self, 'rtclock',
                                         self.start_get, 'select')

    def read(self, ident, stream, success):
        if ident != 'rtclock':
            return
        for s in stream:
            if 'current time' in s.lower():
                time = ':'.join(s.strip().split(':')[1:])
                if len(time.strip()) == 19:
                    self.time.setText('<b>' + time.replace('T', '  ') + '</b>')
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
                    self.add('PSRAM size', value, self.psramtest)
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
    
    def __init__(self, *args, **kwargs):
        super().__init__('', 'List', *args, **kwargs)

    def setup(self, start):
        self.start = start
        
    def read(self, ident, stream, success):
        title = None
        text = '<style type="text/css"> th, td { padding: 0 15px; }</style>'
        text += '<table>'
        for s in stream:
            if title is None:
                if 'files in' in s.lower():
                    title = s
            else:
                if ' name' in s.lower():
                    text += f'<tr><th align="right">size (bytes)</th><th align="left">name</th></tr>'
                elif 'found' in s.lower():
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
        self.erasecard = FormatSDCard('sd card>erase and format', 'Erase')
        self.formatcard = FormatSDCard('sd card>format', 'Format')
        self.root = ListFiles()
        self.recordings = ListFiles()
        self.bench = Benchmark()
        self.box = QGridLayout(self)
        title = QLabel('<b>SD card</b>', self)
        self.box.addWidget(title, 0, 0, 1, 4)
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
        self.root.setup(self.root_start_get)
        self.recordings.setup(self.recordings_start_get)
        self.bench.setup(menu)
        self.formatcard.setup(menu)
        self.erasecard.setup(menu)

    def add(self, label, value, button2=None, button1=None):
        if self.box.itemAtPosition(self.row, 0) is not None:
            w = self.box.itemAtPosition(self.row, 1).widget()
            w.setText('<b>' + value + '</b>')
        else:
            self.box.addWidget(QLabel(label, self), self.row, 0)
            nspan = 3
            if button2 is not None:
                nspan -= 1
                self.box.addWidget(button2, self.row, 3, Qt.AlignRight)
            elif button1 is not None:
                nspan -= 1
                self.box.addWidget(button1, self.row, 2)
            self.box.addWidget(QLabel('<b>' + value + '</b>', self),
                               self.row, 1, 1, nspan, Qt.AlignRight)
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
                            self.add('Recorded files', value, self.recordings)
                            value = 'none'
                            if self.nroot > 0:
                                value = f'{self.nroot}'
                            if self.sroot is not None:
                                value += f' ({self.sroot})'
                            self.add('Root files', value, self.root)
                        else:
                            self.add(items[i][0], items[i][1])
            self.add('Write speed', 'none', self.bench)
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
        self.done.clicked.connect(self.clear)
        done = QShortcut(QKeySequence.Cancel, self)
        done.activated.connect(self.done.animateClick)
        done = QShortcut(Qt.Key_Return, self)
        done.activated.connect(self.done.animateClick)
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


class Message(QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg = QLabel(self)
        self.msg.setAlignment(Qt.AlignCenter)
        self.done = QPushButton('&Done', self)
        self.done.clicked.connect(self.clear)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.done.animateClick)
        buttons = QWidget(self)
        hbox = QHBoxLayout(buttons)
        hbox.addWidget(self.done)
        vbox = QVBoxLayout(self)
        vbox.addWidget(QLabel(self))
        vbox.addWidget(self.msg)
        vbox.addWidget(buttons)

    def clear(self):
        self.msg.setText('')

    def display(self, stream):
        if isinstance(stream, (tuple, list)):
            text = ''
            for s in stream:
                text += s
                text += '\n'
            self.msg.setText(text)
        else:
            self.msg.setText(stream)


class YesNoQuestion(QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg = QLabel(self)
        self.msg.setAlignment(Qt.AlignCenter)
        self.yesb = QPushButton(self)
        self.yesb.setText('&Yes')
        self.yesb.clicked.connect(self.accept)
        key = QShortcut(Qt.Key_Return, self)
        key.activated.connect(self.yesb.animateClick)
        self.nob = QPushButton(self)
        self.nob.setText('&No')
        self.nob.clicked.connect(self.reject)
        key = QShortcut(QKeySequence.Cancel, self)
        key.activated.connect(self.nob.animateClick)
        buttons = QWidget(self)
        hbox = QHBoxLayout(buttons)
        hbox.addWidget(self.nob)
        hbox.addWidget(QLabel(self))
        hbox.addWidget(self.yesb)
        vbox = QVBoxLayout(self)
        vbox.addWidget(QLabel(self))
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

    def accept(self):
        self.yes = True
        
    def reject(self):
        self.yes = False

        
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
        self.unit_widget = None

    def set(self, s):
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
            self.edit_widget = QComboBox(parent)
            for s in self.selection:
                si = s[1]
                if self.out_unit and si.endswith(self.out_unit):
                    si = si[:-len(self.out_unit)]
                self.edit_widget.addItem(si)
            if self.out_unit:
                self.unit_widget = QLabel(self.out_unit, parent)
            si = self.value
            if self.out_unit and si.endswith(self.out_unit):
                si = si[:-len(self.out_unit)]
            self.edit_widget.setCurrentText(si)
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
            self.edit_widget = QDoubleSpinBox(parent)
            self.edit_widget.setDecimals(self.ndec)
            if self.min_val is not None:
                minv = float(self.min_val[:-len(self.out_unit)])
                self.edit_widget.setMinimum(minv)
            if self.edit_widget.minimum() >= 0:
                self.edit_widget.setStepType(QSpinBox.AdaptiveDecimalStepType)
            if self.max_val is not None:
                maxv = float(self.max_val[:-len(self.out_unit)])
                self.edit_widget.setMaximum(maxv)
            else:
                self.edit_widget.setMaximum(1e9)
            self.edit_widget.setValue(self.num_value)
            self.edit_widget.textChanged.connect(self.transmit_str)
            if self.out_unit:
                self.unit_widget = QLabel(self.out_unit, parent)
        elif self.type_str == 'string':
            self.edit_widget = QLineEdit(self.value, parent)
            self.edit_widget.setMaxLength(self.max_chars)
            fm = self.edit_widget.fontMetrics()
            self.edit_widget.setMinimumWidth(32*fm.averageCharWidth())
            self.edit_widget.textChanged.connect(self.transmit_str)

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
    
    def read(self, ident, stream, success):
        for l in stream:
            if self.name in l:
                print(ident, success, l)
                #self.edit_widget.setStyleSheet('border: 0px solid red')
            elif 'new value' in l:
                print(ident, success, l)
                #self.edit_widget.setStyleSheet('border: 2px solid red')
                

class ConfigActions(Interactor, QWidget, metaclass=InteractorQWidget):
    
    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.check_button = QPushButton('&check', self)
        self.save_button = QPushButton('&save', self)
        self.load_button = QPushButton('&load', self)
        self.erase_button = QPushButton('&erase', self)
        self.check_button.clicked.connect(self.check)
        self.save_button.clicked.connect(self.save)
        self.load_button.clicked.connect(self.load)
        self.erase_button.clicked.connect(self.erase)
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.check_button)
        hbox.addWidget(self.save_button)
        hbox.addWidget(self.load_button)
        hbox.addWidget(self.erase_button)
        self.start_check = None
        self.start_load = None
        self.start_save = None
        self.start_erase = None
    
    def setup(self, menu):
        self.start_check = self.retrieve('configuration>print', menu)
        self.start_load = self.retrieve('configuration>load', menu)
        self.start_save = self.retrieve('configuration>save', menu)
        self.start_erase = self.retrieve('configuration>erase', menu)

    def check(self):
        self.sigReadRequest.emit(self, 'confcheck', self.start_check, 'select')

    def save(self):
        self.sigReadRequest.emit(self, 'confsave', self.start_save, 'select')

    def load(self):
        self.sigReadRequest.emit(self, 'confload', self.start_load, 'select')

    def erase(self):
        self.sigReadRequest.emit(self, 'conferase', self.start_erase, 'select')

    def read(self, ident, stream, success):
        if not ident.startswith('conf'):
            return
        while len(stream) > 0 and len(stream[0].strip()) == 0:
            del stream[0]
        if ident == 'confcheck':
            text = '<style type="text/css"> td { padding: 0 15px; }</style>'
            text += '<table>'
            for s in stream:
                if 'configuration:' in s.lower():
                    self.sigDisplayTerminal.emit('Current configuration', text)
                    break
                text += '<tr>'
                cs = s.split(':')
                if len(cs) > 1 and len(cs[1].strip()) > 0:
                    text += f'<td></td><td>{cs[0].strip()}</td><td><b>{(":".join(cs[1:])).strip()}</b></td>'
                else:
                    text += f'<td colspan=3><b>{cs[0].strip()}</b></td>'
                text += '</tr>'
            text += '</table>'
        else:
            while len(stream) > 0 and len(stream[0].strip()) == 0:
                del stream[0]
            text = ''
            for s in stream:
                if 'configuration:' in s.lower():
                    break
                text += s.rstrip()
                text += '\n'
            if len(text) > 0:
                self.sigDisplayMessage.emit(text)
            if success and (ident == 'confsave' or ident == 'conferase'):
                self.sigUpdateSDCard.emit()

        
class Logger(QWidget):

    sigLoggerDisconnected = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logo = QLabel(self)
        self.logo.setFont(QFont('monospace'))
        self.msg = QLabel(self)
        self.conf = QWidget(self)
        self.conf_grid = QGridLayout(self.conf)
        self.configuration = ConfigActions(self)
        self.configuration.sigReadRequest.connect(self.read_request)
        self.configuration.sigDisplayTerminal.connect(self.display_terminal)
        self.configuration.sigDisplayMessage.connect(self.display_message)
        self.tools = QWidget(self)
        self.tools_vbox = QVBoxLayout(self.tools)
        tabs = QTabWidget(self)
        tabs.setDocumentMode(True) # ?
        tabs.setMovable(False)
        tabs.setTabBarAutoHide(False)
        tabs.setTabsClosable(False)
        tabs.addTab(self.conf, 'Configuration')
        tabs.addTab(self.tools, 'Tools')
        self.loggerinfo = LoggerInfo(self)
        self.loggerinfo.sigReadRequest.connect(self.read_request)
        self.loggerinfo.psramtest.sigReadRequest.connect(self.read_request)
        self.loggerinfo.psramtest.sigDisplayTerminal.connect(self.display_terminal)
        self.loggerinfo.rtclock.sigReadRequest.connect(self.read_request)
        self.loggerinfo.rtclock.sigWriteRequest.connect(self.write_request)
        self.softwareinfo = SoftwareInfo(self)
        self.sdcardinfo = SDCardInfo(self)
        self.sdcardinfo.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.formatcard.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.formatcard.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.erasecard.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.erasecard.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.recordings.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.recordings.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.root.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.root.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.bench.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.bench.sigDisplayTerminal.connect(self.display_terminal)
        self.sdcardinfo.formatcard.sigUpdateSDCard.connect(self.sdcardinfo.start)
        self.sdcardinfo.erasecard.sigUpdateSDCard.connect(self.sdcardinfo.start)
        self.configuration.sigUpdateSDCard.connect(self.sdcardinfo.start)
        iboxw = QWidget(self)
        ibox = QVBoxLayout(iboxw)
        ibox.addWidget(self.loggerinfo)
        ibox.addWidget(self.softwareinfo)
        ibox.addWidget(self.sdcardinfo)
        self.boxw = QWidget(self)
        self.box = QHBoxLayout(self.boxw)
        self.box.addWidget(tabs)
        self.box.addWidget(iboxw)
        self.term = Terminal(self)
        self.term.done.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.question = YesNoQuestion(self)
        self.question.yesb.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.question.nob.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.message = Message(self)
        self.message.done.clicked.connect(lambda x: self.stack.setCurrentWidget(self.boxw))
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.msg)
        self.stack.addWidget(self.boxw)
        self.stack.addWidget(self.term)
        self.stack.addWidget(self.question)
        self.stack.addWidget(self.message)
        self.stack.setCurrentWidget(self.msg)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.logo)
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
        self.stack.setCurrentWidget(self.message)

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
            self.read_func = self.configure_menu
        elif self.read_count > 100:
            self.read_count = 0
            self.ser.write('reboot\n'.encode('latin1'))
            self.ser.flush
        else:
            self.read_count += 1

    def configure_menu(self):
        if self.read_state == 0:
            self.ser.write(b'detailed on\n')
            self.read_state += 1
        elif self.read_state == 1:
            self.input = []
            self.ser.write(b'echo off\n')
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
            self.input = []
            self.ser.write(b'print\n')
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
                    self.input = []
                    self.read_func = self.parse_request_stack
                else:
                    self.ser.write('q\n'.encode('latin1'))
        elif self.read_state == 10:
            # request submenu:
            self.input = []
            self.ser.write(self.menu_item[0].encode('latin1'))
            self.ser.write(b'\n')
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
            self.input = []
            self.ser.write(self.menu_item[0].encode('latin1'))
            self.ser.write(b'\n')
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
            param.set(s)
            param.set_selection(self.input[list_start:list_end])
            param.sigTransmitRequest.connect(self.transmit_request)
            self.menu_item[2] = param
            self.ser.write(b'keepthevalue\n')
            self.read_state = 0
            

    def init_menu(self):
        # init menu:
        if 'Help' in self.menu:
            self.menu.pop('Help')
        self.configuration.setup(self.menu)
        self.loggerinfo.setup(self.menu)
        self.sdcardinfo.setup(self.menu)
        row = 0
        for mk in self.menu:
            menu = self.menu[mk]
            add_title = True
            if menu[1] == 'menu':
                for sk in menu[2]:
                    if menu[2][sk][1] == 'action':
                        if add_title:
                            self.tools_vbox.addWidget(QLabel('<b>' + mk + '</b>', self))
                            add_title = False
                        self.tools_vbox.addWidget(QLabel(sk, self))
                    elif menu[2][sk][1] == 'param':
                        if add_title:
                            title = QLabel('<b>' + mk + '</b>', self)
                            title.setSizePolicy(QSizePolicy.Policy.Preferred,
                                                QSizePolicy.Policy.Fixed)
                            self.conf_grid.addWidget(title, row, 0, 1, 3)
                            row += 1
                            add_title = False
                        self.conf_grid.addWidget(QLabel(sk + ': ', self),
                                                 row, 0)
                        param = menu[2][sk][2]
                        param.setup(self)
                        if param.unit_widget is None:
                            self.conf_grid.addWidget(param.edit_widget,
                                                     row, 1, 1, 2)
                        else:
                            self.conf_grid.addWidget(param.edit_widget, row, 1)
                            self.conf_grid.addWidget(param.unit_widget, row, 2)
                        row += 1
        self.conf_grid.addWidget(self.configuration, row, 0, 1, 3)
        self.sdcardinfo.start()
        self.loggerinfo.start()
        self.stack.setCurrentWidget(self.boxw)
            
    def parse_request_stack(self):
        if len(self.request_stack) == 0:
            return
        self.input = []
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
                self.input = []
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.request_start.pop(0)
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            if len(self.input) > 0 and \
               self.input[-1].lower().endswith(' [y/n] '):
                self.question.ask(self.input)
                self.stack.setCurrentWidget(self.question)
                self.read_state = 5
                self.input = []
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
                    self.request_target.read(self.request_ident, self.input, self.request_stop_index == 0)
        elif self.read_state == 2:
            if self.request_target is not None:
                self.request_target.read(self.request_ident, self.input, self.request_stop_index == 0)
                self.request_target = None
            if self.request_type == 'transmit' and self.request_stop_index == 1:
                self.ser.write(b'keepthevalue\n')
            self.read_state += 1
        elif self.read_state == 3:
            self.input = []
            if self.request_end > 0:
                self.ser.write(b'q\n')
                self.request_end -= 1
            else:
                self.request_end = None
                self.request_type = None
                self.read_func = self.parse_request_stack
        elif self.read_state == 5:
            if self.question.yes is not None:
                if self.question.yes:
                    self.ser.write(b'y\n')
                else:
                    self.ser.write(b'n\n')
                self.stack.setCurrentWidget(self.boxw)
                self.question.clear()
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
            if len(self.request_start) > 0:
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.request_start.pop(0)
            else:
                self.input = []
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 1:
            self.ser.write(self.request_target.encode('latin1'))
            self.ser.write(b'\n')
            self.request_target = None
            self.read_state += 1
        elif self.read_state == 2:
            self.input = []
            if self.request_end > 0:
                self.ser.write(b'q\n')
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

