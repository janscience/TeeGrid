// Define SINGLE_FILE_MTP to stop recording after the first file has
// been written, and make then the SD card available over USB as MTB
// filesystem.
//#define SINGLE_FILE_MTP

#include <PowerSave.h>
#include <TeensyBoard.h>
#include <Logger.h>
#ifdef SINGLE_FILE_MTP
#include <MTP_Teensy.h>
#endif


Logger::Logger(Input &aiinput, SDCard &sdcard,
	       RTClock &rtclock, Blink &blink) :
  AIInput(aiinput),
  Disk(&sdcard),
  File(sdcard, aiinput, 5),
  Clock(rtclock),
  NoBlink(""),
  StatusLED(blink),
  ErrorLED(NoBlink),
  SyncLED(NoBlink),
  RandomBlinks(false),
  BlinkTimeout(0),
  SyncTimeout(0),
  Filename(""),
  PrevFilename(""),
  Saving(false),
  FileCounter(0),
  Restarts(0),
  StartTime(0),
  StopTime(0),
  Alarm(),
  SnoozeSDCard(),
  SnoozeConfig(Alarm, SnoozeSDCard) {
}


Logger::Logger(Input &aiinput, SDCard &sdcard,
	       RTClock &rtclock, Blink &blink,
	       Blink &errorblink, Blink &syncblink) :
  AIInput(aiinput),
  Disk(&sdcard),
  File(sdcard, aiinput, 5),
  Clock(rtclock),
  NoBlink(""),
  StatusLED(blink),
  ErrorLED(errorblink),
  SyncLED(syncblink),
  RandomBlinks(false),
  BlinkTimeout(0),
  SyncTimeout(0),
  Filename(""),
  PrevFilename(""),
  Saving(false),
  FileCounter(0),
  Restarts(0),
  StartTime(0),
  StopTime(0),
  Alarm(),
  SnoozeSDCard(),
  SnoozeConfig(Alarm, SnoozeSDCard) {
}


void Logger::halt(int errorcode, Stream &stream) {
  if (errorcode > 0) {
    stream.printf("HALT (%d)\n", errorcode);
    ErrorLED.setMultiple(errorcode);
  }
  else
    stream.println("HALT");
  char reboot_s[] = "reboot";
  size_t i = 0;
  while (true) {
    yield();
    ErrorLED.update();
    int b = stream.read();
    if (b >= 0) {
      char c = char(b);
      if (c == reboot_s[i]) {
        i++;
        if (i >= strlen(reboot_s)) {
          stream.println("REBOOT NOW");
          delay(100);
          reboot();
        }
      }
      else
        i = 0;
    }
  };
}


bool Logger::check(Config &config) {
  // check for enough space:
  if (!Disk->check(1e9)) {
    Disk->end();
    StatusLED.switchOff();
    if (Serial) {
      config.execute(Serial);
      Serial.println();
      Serial.println("Need to reboot, because SD card was not properly inserted initially.");
      Serial.println();
    }
    halt(1);
    return false;
  }
  return true;
}


void Logger::configure(Config &config) {
  // get configuration from EEPROM:
  config.get();
  Serial.println();
  // check SD card:
  check(config);
  Clock.setFromFile(*Disk);
  // cleanup previous recordings:
  char folder[64];
  Disk->latestDir("/", folder, 64);
  if (strlen(folder) > 0)
    Disk->cleanDir(folder, 1024, ".wav", true, ".csv", true);
  Serial.println();
  // get configuration from file:
  config.load();
  // menu:
  if (Serial)
    config.execute();
  config.report();
  Serial.println();
}


void Logger::snooze(const char *start_time) {
  StartTime = 0;
  if (start_time == 0 || strlen(start_time) == 0)
    return;
  SnoozeSDCard.setClockPin(BUILTIN_SDCARD);
  tmElements_t ttm;
  if (!Clock.parseDateTimeStr(start_time, ttm))
    return;
  StartTime = makeTime(ttm);
  //Alarm.setAlarm(StartTime);   // does not wake up
  time_t ct = now();
  //while (StartTime < ct)
  //  StartTime += SECS_PER_DAY;
  time_t dt = StartTime - ct;
  dt -= 1;           // make up for delay until first file is recorded
  if (dt <= 0)
    return;          // no hibernate required
  if (dt <= 5) {
    delay(1000*dt);  // no hibernate required
    return;
  }
  tmElements_t dtm;
  breakTime(dt, dtm);
  Alarm.setRtcTimer(dtm.Hour, dtm.Minute, dtm.Second);
  char dts[24];
  Clock.dateTime(dts, StartTime);
  Serial.printf("Going to sleep until %s ... \n", dts);
  Serial.flush();
  bool on = StatusLED.isOn();
  StatusLED.switchOff();
  delay(1000);
  Snooze.sleep(SnoozeConfig);
  Serial.println("\n... woke up!\n");
  Clock.sync();
  if (Disk != 0)
    Disk->restart();
  if (on)
    StatusLED.switchOn();
}


void Logger::setCPUSpeed(uint32_t rate) {
  rate /= 1000;                    // sampling rate in kHz
  int speed = ((12+rate/2)/24)*24; // CPU speed in MHz, steps of 24, TODO: take channels into account?
  if (speed < 24)
    speed = 24;
  setTeensySpeed(speed);
  Serial.printf("Set CPU speed to %dMHz\n\n", teensySpeed());
}

  
void Logger::reportBlink(Stream &stream) const {
  StatusLED.report(stream);
  if (ErrorLED.available())
    ErrorLED.report(stream);
  if (SyncLED.available())
    SyncLED.report(stream);
}


void Logger::startInput(uint8_t nchannels) {
  StatusLED.switchOff();
  AIInput.begin();
  if (!AIInput.check(nchannels)) {
    Serial.println("Fix ADC settings and check your hardware.");
    halt(2);
  }
  AIInput.start();
  AIInput.report();
}


void Logger::setup(const char *path, const char *filename,
		   const char *software, bool randomblinks,
		   float blinktimeout, float synctimeout) {
  RandomBlinks = randomblinks;
  BlinkTimeout = (unsigned long)(1000*blinktimeout);
  SyncTimeout = (unsigned long)(1000*synctimeout);
  StopTime = 0;
  Filename = filename;
  int i = Filename.lastIndexOf('.');
  if (i >= 0)
    Filename.remove(i);
  Filename += ".wav";
  PrevFilename = "";
  Restarts = 0;
  String path_name = path;
  time_t t = now();
  path_name = Clock.makeStr(path_name, t, true);
  if (File.sdcard()->dataDir(path_name.c_str(), true))
    Serial.printf("Save recorded data in folder \"%s\" on %sSD card.\n\n",
		  File.sdcard()->workingDir(), File.sdcard()->name());
  File.header().setSoftware(software);
  File.header().setCPUSpeed();
}


void Logger::initialDelay(float initial_delay, const char *stop_time,
			  Stream &stream) {
  shutdown_usb();   // saves power!
  if (StartTime > 0)
    initial_delay = 0.0;
  if (initial_delay < 1e-8) {
    StatusLED.setDouble();
  }
  else {
    stream.printf("Delay for %.0fs ... ", initial_delay);
    if (initial_delay >= 2.0) {
      delay(1000);
      StatusLED.setDouble();
      StatusLED.delay(uint32_t(1000.0*initial_delay) - 1000);
    }
    else
      delay(uint32_t(1000.0*initial_delay));
    stream.println();
    stream.println();
  }
  StopTime = 0;
  if (stop_time != 0 and strlen(stop_time) > 0) {
    tmElements_t ttm;
    if (Clock.parseDateTimeStr(stop_time, ttm)) {
      StopTime = makeTime(ttm);
      if (StopTime < now() + 10)
	StopTime += SECS_PER_DAY;
      char dts[24];
      Clock.dateTime(dts, StopTime);
      stream.printf("Stop recording at %s.\n\n", dts);
    }
  }
}


void Logger::start(float filetime) {
  File.setWriteInterval(2*AIInput.DMABufferTime());
  File.setMaxFileTime(filetime);
  if (RandomBlinks)
    StatusLED.setTiming(5000, 100, 1200);
  else if (filetime > 30)
    StatusLED.setTiming(5000);
  else
    StatusLED.setTiming(2000);
  StatusLED.clearSwitchTimes();
  SyncLED.setTiming(5000, 100, 1200);
  SyncLED.clearSwitchTimes();
  if (BlinkTimeout > 0)
    BlinkTimeout += millis();
  if (SyncTimeout > 0)
    SyncTimeout += millis();
  File.start();
  open();
  openBlinkFiles();
}


void Logger::start(float filetime, Config &config) {
  start(filetime);
  writeMetadata(config);
}


void Logger::start(float filetime, Config &config, Menu &amplifier) {
  start(filetime);
  InfoAction ampl(amplifier, 0);
  if (strlen(File.header().channels()) > 0)
    ampl.add("Channels", File.header().channels());
  if (strlen(File.header().averaging()) > 0)
    ampl.add("Averaging", File.header().averaging());
  if (strlen(File.header().conversionSpeed()) > 0)
    ampl.add("Conversion speed", File.header().conversionSpeed());
  if (strlen(File.header().samplingSpeed()) > 0)
    ampl.add("Sampling speed", File.header().samplingSpeed());
  if (strlen(File.header().reference()) > 0)
    ampl.add("Reference", File.header().reference());
  if (strlen(File.header().gain()) > 0)
    ampl.add("Gain", File.header().gain());
  if (strlen(File.header().software()) > 0)
    ampl.add("Software", File.header().software());
  writeMetadata(config);
}


void Logger::open() {
  if (RandomBlinks) {
    StatusLED.setRandom();
    StatusLED.blinkMultiple(5, 0, 200, 200);
  }
  else {
    StatusLED.setSingle();
    StatusLED.blinkSingle(0, 2000);
  }
  SyncLED.setRandom();
  SyncLED.blinkMultiple(5, 0, 200, 200);
  String fname(Filename);
  char cs[16];
  sprintf(cs, "%04d", FileCounter + 1);
  fname.replace("COUNT", cs);
  time_t t = now();
  // align on StartTime:
  while (StartTime > 0 && t < StartTime && StartTime - t < 2) {
    delay(100);
    t = now();
  }
  fname = Clock.makeStr(fname, t, true);
  if (fname != PrevFilename) {
    File.sdcard()->resetFileCounter();
    PrevFilename = fname;
  }
  fname = File.sdcard()->incrementFileName(fname);
  if (fname.length() == 0) {
    StatusLED.clear();
    SyncLED.clear();
    AIInput.stop();
    halt(3);
    return;
  }
  char dts[20];
  Clock.dateTime(dts, t);
  if (! File.openWave(fname.c_str(), -1, dts)) {
    StatusLED.clear();
    SyncLED.clear();
    Serial.println();
    Serial.printf("WARNING: failed to open file on %sSD card.\n", File.sdcard()->name());
    Serial.println("SD card probably not inserted or full -> ");
    AIInput.stop();
    halt(4);
    return;
  }
  Saving = true;
  FileCounter++;
  ssize_t samples = File.write();
  if (samples == -4) {   // overrun
    File.start(AIInput.nbuffer()/2);   // skip half a buffer
    File.write();                      // write all available data
    // report overrun:
    char mfs[100];
    sprintf(mfs, "%s-error0-overrun.msg", File.baseName().c_str());
    Serial.println(mfs);
    FsFile mf = Disk->openWrite(mfs);
    mf.close();
  }
  Serial.print("Write recording   to ");
  Serial.print(File.name());
  Serial.println();
}


void Logger::close() {
  if (! Saving)
    return;
  File.closeWave();
  Saving = false;
  SyncLED.clear();
  StatusLED.setDouble();
}


bool Logger::store(SDWriter &sdfile) {
  if (!sdfile.pending())
    return false;
  ssize_t samples = sdfile.write();
  if (samples < 0) {
    Serial.println();
    Serial.printf("ERROR in writing data to file on %sSD card in Logger::store():\n", sdfile.sdcard()->name());
    char errorstr[20];
    switch (samples) {
      case -1:
        Serial.println("  file not open.");
        strcpy(errorstr, "notopen");
        break;
      case -2:
        Serial.println("  file already full.");
        strcpy(errorstr, "full");
        break;
      case -3:
        AIInput.stop();
        Serial.println("  no data available, data acquisition probably not running.");
        Serial.printf("  dmabuffertime = %.2fms, writetime = %.2fms\n", 1000.0*AIInput.DMABufferTime(), 1000.0*sdfile.writeTime());
        strcpy(errorstr, "nodata");
        break;
      case -4:
        Serial.println("  buffer overrun.");
        Serial.printf("  dmabuffertime = %.2fms, writetime = %.2fms\n", 1000.0*AIInput.DMABufferTime(), 1000.0*sdfile.writeTime());
        strcpy(errorstr, "overrun");
        break;
      case -5:
        Serial.println("  failed to write anything.");
	Serial.printf("  %sSD card probably full -> \n", sdfile.sdcard()->name());
	AIInput.stop();
	StatusLED.clear();
	SyncLED.clear();
	halt(5);
        strcpy(errorstr, "nowrite");
	break;
    }
    sdfile.closeWave();
    // write error file:
    char mfs[100];
    sprintf(mfs, "%s-error%d-%s.msg", sdfile.baseName().c_str(),
	    Restarts+1, errorstr);
    Serial.println(mfs);
    FsFile mf = Disk->openWrite(mfs);
    mf.close();
    // halt after too many errors:
    Restarts++;
    Serial.printf("Incremented restarts to %d, samples=%d on %sSD card\n", Restarts, samples, sdfile.sdcard()->name());
    if (Restarts >= 5) {
      Serial.printf("ERROR in Logger::storeData() on %sSD card: too many file errors", sdfile.sdcard()->name());
      AIInput.stop();
      StatusLED.clear();
      SyncLED.clear();
      Serial.println(" -> ");
      halt(6);
    }
    // restart analog input:
    if (!AIInput.running())
      AIInput.start();
    // open next file:
    sdfile.start();
    open();
  }
  return true;
}


void Logger::writeMetadata(Config &config) {
  String fname = File.name();
  fname.replace(".wav", "-metadata.yml");
  FsFile file = Disk->openWrite(fname.c_str());
  config.write(file, config.FileOutput | config.Report);
  file.close();
  Serial.print("Wrote metadata    to ");
  Serial.println(fname);
}


void Logger::openBlinkFiles() {
  if (RandomBlinks || SyncLED.available()) {
    String fname = File.name();
    fname.replace(".wav", "-blinks.csv");
    BlinkFile = Disk->openWrite(fname.c_str());
    BlinkFile.write("time/ms,on\n");
    Serial.print("Write blink times to ");
    Serial.println(fname);
  }
}


void Logger::storeBlinks() {
  if (RandomBlinks || SyncLED.available()) {
    Blink &led = RandomBlinks ? StatusLED : SyncLED;

    if (led.nswitchTimes() < Blink::MaxTimes/2)
      return;
    uint32_t tstart = File.startWriteTime();
    uint32_t times[Blink::MaxTimes];
    bool states[Blink::MaxTimes];
    size_t n;
    led.getSwitchTimes(times, states, &n);
    char buffer[Blink::MaxTimes*14];
    size_t m = 0;
    for (size_t k=0; k<n; k++)
      m += sprintf(buffer + m, "%lu,%u\n", times[k] - tstart, states[k]);
    BlinkFile.write(buffer, m);
    BlinkFile.flush();
  }
}


void Logger::closeBlinks() {
  BlinkFile.close();
}


void Logger::update() {
  if (store(File)) {
    if (StopTime > 0 && now() >= StopTime)
      stop();
  }
  if (File.endWrite()) {
    File.close();  // file size was set by openWave()
#ifdef SINGLE_FILE_MTP
    SyncLED.clear();
    AIInput.stop();
    delay(50);
    Serial.println();
    Serial.println("MTP file transfer.");
    Serial.flush();
    StatusLED.setTriple();
    MTP.begin();
    MTP.addFilesystem(*Disk, "logger");
    while (true) {
      MTP.loop();
      StatusLED.update();
      yield();
    }
#endif
    if (StopTime > 0 && now() >= StopTime)
      stop();
    synchronize(); // TODO: make this working also for backup.
    open();
  }
  storeBlinks();
  if ((BlinkTimeout > 0) && (millis() > BlinkTimeout))
    StatusLED.disablePin(0);
  if ((BlinkTimeout > 0) && (millis() > 2*BlinkTimeout))
    StatusLED.disablePin(1);
  if ((SyncTimeout > 0) && (millis() > SyncTimeout))
    SyncLED.clearPins();
  StatusLED.update();
  SyncLED.update();
}


void Logger::stop() {
  closeBlinks();
  char dts[24];
  Clock.dateTime(dts, StopTime);
  Serial.printf("\nStop time %s reached: stop recording and reboot.\n", dts);
  delay(100);
  reboot();
}


void Logger::R41powerDownCAN() {
  #define CAN_SHDN_PIN 37      // R4.1 CAN shutdown pin
  pinMode(CAN_SHDN_PIN, OUTPUT);
  digitalWrite(CAN_SHDN_PIN, HIGH);
}

