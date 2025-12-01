import sys
import numpy as np

from microconfig import MicroConfig

try:
    from microconfig import discover_teensy
    from microconfig import parse_number, change_unit
    from microconfig import Interactor, InteractorQWidget
    from microconfig import ReportButton, InfoFrame
    from microconfig import Terminal
    from microconfig import SpinBox
    from microconfig import ConfigActions
    from microconfig import Parameter
    from microconfig import Scanner
except ImportError:
    print('ERROR: failed to import microconfig package !')
    print('- download https://github.com/janscience/MicroConfig')
    print('- change into the microconfig/ directory')
    print('- in there execute `pip install .`')
    exit()

from scipy.signal import welch

try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, QDateTime
from PyQt5.QtGui import QKeySequence, QPalette, QColor, QValidator
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QLabel, QScrollArea
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout, QSpacerItem
from PyQt5.QtWidgets import QWidget, QPushButton
from PyQt5.QtWidgets import QShortcut, QSizePolicy
from PyQt5.QtWidgets import QComboBox

try:
    import pyqtgraph as pg
except ImportError:
    print('ERROR: failed to import pyqtgraph package !')
    print('Install it using')
    print('> pip install pyqtgraph')
    exit()


__version__ = '2.0'


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
        if not success:
            return
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


class LoggerInfo(InfoFrame):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def set(self, device):
        self.device = device.device
        self.model = device.model
        self.serial_number = device.serial_number

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
        if not success:
            return
        if 'eepromhexdump' in ident:
            self.sigDisplayTerminal.emit('EEPROM memory', stream)
            return
        if 'deviceid' in ident:
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
        for s in stream:
            x = s.split(':')
            if len(x) < 2 or len(x[1].strip()) == 0:
                continue
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

                
class CheckSDCard(ReportButton):
    
    sigSDCardPresence = Signal(bool)
    
    def __init__(self, *args, **kwargs):
        super().__init__('check sd card availability', 'Check',
                         *args, **kwargs)
        
    def read(self, ident, stream, success):
        present = False
        for s in stream:
            if 'present and writable' in s:
                present = True
                self.set_button_color(Qt.green)
        if success:
            if not present:
                self.set_button_color(Qt.red)
            self.sigSDCardPresence.emit(present)
        self.sigDisplayTerminal.emit('Check SD card', stream)

                
class FormatSDCard(ReportButton):
    
    def __init__(self, key, text, *args, **kwargs):
        super().__init__(key, text, *args, **kwargs)
        
    def read(self, ident, stream, success):
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
        super().__init__('run benchmark test', 'Test',
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
    
        
class BlinkLEDs(ReportButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__('blink leds', 'Blink', *args, **kwargs)
        
    def read(self, ident, stream, success):
        if len(stream) == 0:
            return
        self.sigDisplayTerminal.emit(stream[0], stream[1:])
    
        
class HardwareInfo(InfoFrame):
    
    sigPlot = Signal()
    
    def __init__(self, plot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.box = QGridLayout(self)
        title = QLabel('<b>Periphery</b>', self)
        title.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Fixed)
        self.box.addWidget(title, 0, 0, 1, 2)
        self.blink_button = BlinkLEDs(self)
        self.blink_button.sigDisplayTerminal.connect(self.sigDisplayTerminal)
        self.blink_button.sigReadRequest.connect(self.sigReadRequest)
        self.blink_button.setToolTip('Blink available LED pins')
        key = QShortcut('Ctrl+B', self)
        key.activated.connect(self.blink_button.animateClick)
        self.box.addWidget(self.blink_button, 0, 4, Qt.AlignRight)
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
        self.blink_button.setup(menu)
        self.retrieve('list led pins', menu)
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
        if not success:
            return
        if int(stream[0].split()[0]) == 0:
            return
        first_input = True
        for s in stream[1:]:
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

        
class SensorsInfo(InfoFrame):
    
    sigPlot = Signal()
    
    def __init__(self, plot, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        if not success:
            return
        if ident == 'request':
            for s in stream:
                if 'are available after' in s.lower():
                    delaystr = s.strip().rstrip('.').split()[-1]
                    self.delay = int(delaystr.replace('ms', ''))
            return
        elif ident == 'values':
            for s in stream:
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
        
        
class SDCardInfo(InfoFrame):
    
    sigSDCardPresence = Signal(bool)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        self.checkcard.sigSDCardPresence.connect(self.sigSDCardPresence)
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

        if not success:
            return
        if ident == 'recordings':
            self.nrecordings, self.srecordings = num_files(stream)
        elif ident == 'root':
            self.nroot, self.sroot = num_files(stream)
        elif ident == 'sdcard':
            items = []
            available = None
            for s in stream:
                x = s.split(':')
                if len(x) < 2 or len(x[1].strip()) == 0:
                    continue
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
            self.sigSDCardPresence.emit(len(items) > 2)

        
class Logger(MicroConfig):
    
    def __init__(self, title, device, *args, **kwargs):
        super().__init__('LoggerConf', device, *args, **kwargs)
        self.setWindowTitle(f'{self.title} {__version__}: {device.device}')
        
        # default plot colors:
        back_color = self.palette().color(QPalette.Window)
        text_color = self.palette().color(QPalette.WindowText)
        pg.setConfigOption('background', back_color)
        pg.setConfigOption('foreground', text_color)
                
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
        self.sdcardinfo.sigSDCardPresence.connect(self.configacts.set_sdcard)
        self.configacts.sigUpdate.connect(self.sdcardinfo.start)

        iboxw = QWidget(self)
        ibox = QGridLayout(iboxw)
        ibox.setContentsMargins(0, 0, 0, 0)
        ibox.addWidget(self.loggerinfo, 0, 0)
        ibox.addWidget(self.sdcardinfo, 0, 1)
        ibox.addWidget(self.hardwareinfo, 1, 0)
        ibox.addWidget(self.sensorsinfo, 1, 1)
        self.box.addWidget(iboxw)
        
        self.stack.addWidget(self.plot_recording)
        self.stack.addWidget(self.plot_sensors)

    def start(self, device):
        self.loggerinfo.set(device)
        super().start(device)

    def stop(self):
        self.loggerinfo.rtclock.stop()
        super().stop()

    def display_recording_plot(self):
        self.stack.setCurrentWidget(self.plot_recording)

    def display_sensors_plot(self):
        self.stack.setCurrentWidget(self.plot_sensors)

    def setup(self):
        self.loggerinfo.setup(self.menu)
        self.hardwareinfo.setup(self.menu)
        self.sensorsinfo.setup(self.menu)
        self.sdcardinfo.setup(self.menu)
        super().setup()
        self.hardwareinfo.start()
        self.sensorsinfo.start()
        self.sdcardinfo.start()
        self.loggerinfo.start()
                    

def main():
    app = QApplication(sys.argv)
    main = Scanner('logger', [discover_teensy], Logger)
    main.show()
    app.exec_()

    
if __name__ == '__main__':
    main()

