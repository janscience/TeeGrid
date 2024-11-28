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
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QKeySequence, QFont, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QStackedWidget, QLabel, QScrollArea
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout
from PyQt5.QtWidgets import QWidget, QFrame, QPushButton
from PyQt5.QtWidgets import QAction


__version__ = '1.0'

    
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
"""Map bcdDevice of USB device to Teensy model version."""


def get_teensy_model(vid, pid, serial_number):
    if has_usb:
        dev = usb.core.find(idVendor=vid, idProduct=pid,
                            serial_number=serial_number)
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
                    submenu = menu_item[1]
                    if len(keys) > 1:
                        if isinstance(submenu, dict) and \
                           find(keys[1:], submenu, ids):
                            if len(submenu) == 0:
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
                    if isinstance(submenu, dict) and \
                       find(keys, submenu, ids):
                        if len(submenu) == 0:
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
    def read(self, stream, ident):
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

    def read(self, stream, ident):
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
        
    def read(self, stream, ident):
        while len(stream) > 0 and 'extmem memory test' not in stream[0].lower():
            del stream[0]
        for k in range(len(stream)):
            if 'test ran' in stream[k].lower():
                while len(stream) > k + 2:
                    del stream[-1]
                if k + 1 < len(stream):
                    if 'all memory tests passed' in stream[k + 1].lower():
                        self.setText('passed')
                        self.set_button_color(Qt.green)
                    else:
                        self.setText('failed')
                        self.set_button_color(Qt.red)
                break

        
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

    def read(self, stream, ident):
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

                
class ListFiles(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('', 'List',
                         *args, **kwargs)

    def setup(self, start):
        self.start = start
        
    def read(self, stream, ident):
        while len(stream) > 0 and 'files in' not in stream[0].lower():
            del stream[0]
        for k in range(len(stream)):
            if 'found' in stream[k].lower():
                while len(stream) > k + 1:
                    del stream[-1]
                break

                
class Benchmark(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('sd card benchmark', 'Test',
                         *args, **kwargs)
        self.value = None

    def set_value(self, value):
        self.value = value
        
    def read(self, stream, ident):
        while len(stream) > 0 and \
              'benchmarking write and read speeds' not in stream[0].lower():
            del stream[0]
        start = None
        speeds = []
        for k in range(len(stream)):
            if 'write speed and latency' in stream[k].lower():
                start = k + 3
            if start is not None and k >= start:
                if len(stream[k].strip()) == 0:
                    start = None
                else:
                    speeds.append(float(stream[k].split()[0]))
            if 'done' in stream[k].lower():
                while len(stream) > k + 1:
                    del stream[-1]
                if len(speeds) > 0:
                    self.value.setText(f'<b>{np.mean(speeds):.2f}MB/s</b>')
                break

            
class SDCardInfo(Interactor, QFrame, metaclass=InteractorQFrame):
    
    def __init__(self, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.root = ListFiles()
        self.recordings = ListFiles()
        self.bench = Benchmark()
        self.box = QGridLayout(self)
        title = QLabel('<b>SD card</b>', self)
        self.box.addWidget(title, 0, 0, 1, 2)
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
        self.sigReadRequest.emit(self, 'recordings',
                                 self.recordings_start_get, 'select')
        self.sigReadRequest.emit(self, 'root',
                                 self.root_start_get, 'select')
        self.sigReadRequest.emit(self, 'sdcard',
                                 self.sdcard_start_get, 'select')

    def read(self, stream, ident):

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
                        self.add(items[i][0], items[i][1])
                        if keys == 'available':
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

        
class Logger(QWidget):

    sigLoggerDisconnected = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logo = QLabel(self)
        self.logo.setFont(QFont('monospace'))
        self.msg = QLabel(self)
        self.conf = QWidget(self)
        self.conf_grid = QGridLayout(self.conf)
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
        self.loggerinfo.rtclock.sigReadRequest.connect(self.read_request)
        self.loggerinfo.rtclock.sigWriteRequest.connect(self.write_request)
        self.softwareinfo = SoftwareInfo(self)
        self.sdcardinfo = SDCardInfo(self)
        self.sdcardinfo.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.recordings.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.root.sigReadRequest.connect(self.read_request)
        self.sdcardinfo.bench.sigReadRequest.connect(self.read_request)
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
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.msg)
        self.stack.addWidget(self.boxw)
        self.stack.addWidget(self.term)
        self.stack.setCurrentWidget(self.msg)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.logo)
        vbox.addWidget(self.stack)

        self.device = None
        self.ser = None
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.read)
        self.read_state = 0
        self.input = []
        self.request_stack = []
        self.request_target = None
        self.request_ident = None
        self.request_start = None
        self.request_end = None
        self.request_stop = None

        self.menu = {}
        self.menu_iter = iter([])
        self.menu_key = None

    def activate(self, device, model, serial_number):
        #self.title.setText(f'Teensy{model} with serial number {serial_number} on {device}')
        self.device = device
        self.loggerinfo.set(device, model, serial_number)
        self.msg.setText('Reading configuration ...')
        self.stack.setCurrentWidget(self.msg)
        try:
            self.ser = serial.Serial(device)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except (OSError, serial.serialutil.SerialException):
            self.ser = None
        self.input = []
        self.read_state = 0
        self.read_timer.start(2)

    def stop(self):
        self.read_timer.stop()
        self.loggerinfo.rtclock.stop()
        if self.ser is not None:
            self.ser.close()
        self.ser = None
        self.sigLoggerDisconnected.emit()
        
    def parse_halt(self, k):
        s = 'Logger halted\n'
        k -= 1
        while k >= 0 and len(self.input[k]) == 0:
            k -= 1
        self.msg.setText(s + self.input[k])
        self.stack.setCurrentWidget(self.msg)
        self.read_state = 10000

    def parse_logo(self):
        if self.read_state == 0:
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
                self.read_state += 1

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
            sub_menu = (x[-1] == '...')
            if sub_menu:
                name = ' '.join(x[1:-1])
                menu[name] = (num, {})
            else:
                l = ' '.join(x[1:])
                if ':' in l:
                    x = l.split(':')
                    name = x[0].strip()
                    value = x[1].strip()
                    menu[name] = (num, value)
                else:
                    menu[l] = (num, None)
        self.input = []
        return menu

    def parse_mainmenu(self):
        if self.read_state == 1:
            self.ser.write(b'detailed: on\n')
            self.read_state += 1
        elif self.read_state == 2:
            self.input = []
            self.ser.write(b'print\n')
            self.read_state += 1
        elif self.read_state == 3:
            self.menu = self.parse_menu('Menu')
            if len(self.menu) > 0:
                self.menu_iter = iter(self.menu.keys())
                self.read_state += 1

    def parse_submenu(self):
        if self.read_state == 4:
            # get next menu entry:
            try:
                self.menu_key = next(self.menu_iter)
                if isinstance(self.menu[self.menu_key][1], dict):
                    self.read_state += 1
            except StopIteration:
                self.init_menu()
                self.input = []
                self.read_state = 10
        elif self.read_state == 5:
            # request submenu:
            self.input = []
            self.ser.write(self.menu[self.menu_key][0].encode('latin1'))
            self.ser.write(b'\n')
            self.read_state += 1
        elif self.read_state == 6:
            # parse submenu:
            submenu = {}
            if len(self.input) > 1 and 'Select' in self.input[-1]:
                submenu = self.parse_menu(self.menu_key)
            if len(submenu) > 0:
                self.menu[self.menu_key][1].update(submenu)
                self.ser.write('q\n'.encode('latin1'))
                self.read_state = 4

    def init_menu(self):
        # init menu:
        if 'Help' in self.menu:
            self.menu.pop('Help')
        self.loggerinfo.setup(self.menu)
        self.sdcardinfo.setup(self.menu)
        row = 0
        for mk in self.menu:
            menu = self.menu[mk]
            add_title = True
            if isinstance(menu[1], dict):
                for sk in menu[1]:
                    if menu[1][sk][1] is None:
                        if add_title:
                            self.tools_vbox.addWidget(QLabel('<b>' + mk + '</b>', self))
                            add_title = False
                        self.tools_vbox.addWidget(QLabel(sk, self))
                    elif not isinstance(menu[1][sk][1], dict):
                        if add_title:
                            self.conf_grid.addWidget(QLabel('<b>' + mk + '</b>', self), row, 0, 1, 2)
                            row += 1
                            add_title = False
                        self.conf_grid.addWidget(QLabel(sk + ': ', self),
                                                 row, 0)
                        self.conf_grid.addWidget(QLabel(menu[1][sk][1], self),
                                                 row, 1)
                        row += 1
        self.sdcardinfo.start()
        self.loggerinfo.start()
        self.stack.setCurrentWidget(self.boxw)
            
    def parse_request_stack(self):
        if self.read_state == 10:
            if len(self.request_stack) == 0:
                return
            self.input = []
            request = self.request_stack.pop(0)
            self.request_target = request[0]
            self.request_ident = request[1]
            self.request_start = request[2]
            self.request_end = request[3]
            self.request_stop = request[4]
            self.read_state = request[5]

    def read_request(self, target, ident, start, stop):
        if start is None:
            return
        # put each request only once onto the stack:
        for req in self.request_stack:
            if req[0] == target and req[1] == ident and req[-1] == 20:
                return
        self.request_stack.append([target, ident, start,
                                   len(start) - 1, stop, 20])
        if self.read_state == 10:
            self.parse_request_stack()

    def parse_read_request(self):
        if self.read_state == 20:
            if len(self.request_start) > 0:
                self.input = []
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.request_start.pop(0)
            else:
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 21:
            if self.request_stop is None or \
               len(self.request_stop) == 0 or \
               (len(self.input) > 3 and \
                self.request_stop in self.input[-1].lower()):
                self.request_stop = None
                self.read_state += 1
            if self.request_ident == 'run':
                if self.read_state == 22:
                    for l in self.input:
                        print(l)
                if self.request_target is not None:
                    self.request_target.read(self.input, self.request_ident)
                self.term.update(self.input)
                self.stack.setCurrentWidget(self.term)
        elif self.read_state == 22:
            if self.request_target is not None:
                self.request_target.read(self.input, self.request_ident)
                self.request_target = None
            if self.request_ident == 'run':
                self.term.update(self.input)
                self.term.done.setEnabled(True)
            self.read_state += 1
        elif self.read_state == 23:
            self.input = []
            if self.request_end > 0:
                self.ser.write(b'q\n')
                self.request_end -= 1
            else:
                self.request_end = None
                self.read_state = 10

    def write_request(self, msg, start):
        if start is None:
            return
        self.request_stack.append([msg, None, start, len(start) - 1, None, 30])
        if self.read_state == 10:
            self.parse_request_stack()

    def parse_write_request(self):
        if self.read_state == 30:
            if len(self.request_start) > 0:
                self.ser.write(self.request_start[0].encode('latin1'))
                self.ser.write(b'\n')
                self.request_start.pop(0)
            else:
                self.input = []
                self.request_start = None
                self.read_state += 1
        elif self.read_state == 31:
            self.ser.write(self.request_target.encode('latin1'))
            self.ser.write(b'\n')
            self.request_target = None
            self.read_state += 1
        elif self.read_state == 32:
            self.input = []
            if self.request_end > 0:
                self.ser.write(b'q\n')
                self.request_end -= 1
            else:
                self.request_end = None
                self.read_state = 10

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
                x = self.ser.read(self.ser.in_waiting)
                lines = x.decode('latin1').split('\n')
                if len(self.input) == 0:
                    self.input = ['']
                self.input[-1] += lines[0].rstrip('\r')
                for l in lines[1:]:
                    self.input.append(l.rstrip('\r'))
            else:
                self.parse_logo()
                self.parse_mainmenu()
                self.parse_submenu()
                self.parse_read_request()
                self.parse_write_request()
                self.parse_request_stack()
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

