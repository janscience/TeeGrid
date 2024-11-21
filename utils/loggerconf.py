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
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QStackedWidget, QLabel
from PyQt5.QtWidgets import QWidget, QVBoxLayout
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
        self.timer.start(200)

    def scan(self):
        devices, models, serial_numbers = discover_teensy_ports()
        if len(devices) > 0:
            self.timer.stop()
            self.sigLoggerFound.emit(devices[0],
                                     models[0],
                                     serial_numbers[0])


class Logger(QWidget):

    sigLoggerDisconnected = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vbox = QVBoxLayout(self)
        self.title = QLabel(self)
        self.title.setText('Logger available')
        self.logo = QLabel(self)
        self.logo.setFont(QFont('monospace'))
        self.software = QLabel(self)
        self.msg = QLabel(self)
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True) # ?
        self.tabs.setMovable(False)
        self.tabs.setTabBarAutoHide(False)
        self.tabs.setTabsClosable(False)
        self.conf = QWidget(self)
        self.tools = QWidget(self)
        self.tabs.addTab(self.conf, 'Configuration')
        self.tabs.addTab(self.tools, 'Tools')
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.msg)
        self.stack.addWidget(self.tabs)
        self.stack.setCurrentWidget(self.msg)
        self.vbox.addWidget(self.title)
        self.vbox.addWidget(self.logo)
        self.vbox.addWidget(self.software)
        self.vbox.addWidget(self.stack)
        
        self.ser = None
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.read)
        self.input = []

        self.menu = {}

    def activate(self, device, model, serial_number):
        self.title.setText(f'Teensy{model} with serial number {serial_number} on {device}')
        self.msg.setText('Reading configuration ...')
        self.stack.setCurrentWidget(self.msg)
        try:
            self.ser = serial.Serial(device)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except (OSError, serial.serialutil.SerialException):
            self.ser = None
        self.input = ['']
        self.read_state = 0
        self.read_timer.start(10)
        
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
                    title_start = title_mid
                s = ''
                for l in self.input[title_start + 1:title_end]:
                    if len(s) > 0:
                        s += '\n'
                    s += l
                self.software.setText(s)
                if title_end >= len(self.input[title_end]):
                    self.input = ['']
                else:
                    self.input = self.input[title_end + 1:]
                self.read_state += 1

    def parse_menu(self):
        if self.read_state == 1:
            menu_start = None
            menu_end = None
            for k in range(len(self.input)):
                if 'HALT' in self.input[k]:
                    self.parse_halt(k)
                    return
                elif 'Menu:' in self.input[k]:
                    menu_start = k
                elif menu_start is not None and \
                     'Select:' in self.input[k]:
                    menu_end = k
            if menu_start is not None and \
               menu_end is not None:
                self.menu = {}
                for l in self.input[menu_start + 1:menu_end]:
                    x = l.split()
                    sub_menu = x[-1] == '...'
                    name = ' '.join(x[1:-1]) if sub_menu else ' '.join(x[1:])
                    self.menu[name] = (x[0][:-1], sub_menu, {})
                for k in self.menu:
                    print(self.menu[k][0], k, self.menu[k][1])
                if menu_end >= len(self.input[menu_end]):
                    self.input = ['']
                else:
                    self.input = self.input[menu_end + 1:]
                self.read_state += 1
                self.stack.setCurrentWidget(self.tabs)

    def read(self):
        if self.ser is None:
            try:
                print('open serial')
                self.ser = serial.Serial(device)
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except (OSError, serial.serialutil.SerialException):
                print('  FAILED')
                self.ser = None
                self.read_timer.stop()
                return
        try:
            if self.ser.in_waiting > 0:
                x = self.ser.read(self.ser.in_waiting)
                lines = x.decode('latin1').split('\n')
                for l in lines:
                    self.input[-1] += l.rstrip()
                    self.input.append('')
            else:
                self.parse_logo()
                self.parse_menu()
        except (OSError, serial.serialutil.SerialException):
            self.read_timer.stop()
            self.ser.close()
            self.sigLoggerDisconnected.emit()
        

class LoggerConf(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'LoggerConf {__version__}')
        self.scanlogger = ScanLogger(self)
        self.scanlogger.sigLoggerFound.connect(self.activate)
        self.logger = Logger(self)
        self.logger.sigLoggerDisconnected.connect(self.disconnect)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.scanlogger)
        self.stack.addWidget(self.logger)
        self.stack.setCurrentWidget(self.scanlogger)
        self.setCentralWidget(self.stack)
        quit = QAction('&Quit', self)
        quit.setShortcuts(QKeySequence.Quit)
        quit.triggered.connect(QApplication.quit)
        self.addAction(quit)

    def activate(self, device, model, serial_number):
        self.logger.activate(device, model, serial_number)
        self.stack.setCurrentWidget(self.logger)

    def disconnect(self):
        self.scanlogger.start()
        self.stack.setCurrentWidget(self.scanlogger)


def main():
    app = QApplication(sys.argv)
    main = LoggerConf()
    main.show()
    app.exec_()

    
if __name__ == '__main__':
    main()

