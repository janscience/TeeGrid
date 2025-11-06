// Define SINGLE_FILE_MTP to stop recording after the first file has
// been written, and make then the SD card available over USB as MTB
// filesystem.
//#define SINGLE_FILE_MTP

#include <TeensyBoard.h>
#include <Logger.h>
#ifdef SINGLE_FILE_MTP
#include <MTP_Teensy.h>
#endif


Logger::Logger(Input &aiinput, SDCard &sdcard0,
	       const RTClock &rtclock, Blink &blink) :
  AIInput(aiinput),
  SDCard0(&sdcard0),
  SDCard1(0),
  File0(sdcard0, aiinput, 5),
  File1(),
  Clock(rtclock),
  NoBlink(""),
  StatusLED(blink),
  ErrorLED(NoBlink),
  SyncLED(NoBlink),
  RandomBlinks(false),
  BlinkTimeout(0),
  Filename(""),
  PrevFilename(""),
  Saving(false),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
}


Logger::Logger(Input &aiinput, SDCard &sdcard0,
	       const RTClock &rtclock, Blink &blink,
	       Blink &errorblink, Blink &syncblink) :
  AIInput(aiinput),
  SDCard0(&sdcard0),
  SDCard1(0),
  File0(sdcard0, aiinput, 5),
  File1(),
  Clock(rtclock),
  NoBlink(""),
  StatusLED(blink),
  ErrorLED(errorblink),
  SyncLED(syncblink),
  RandomBlinks(false),
  BlinkTimeout(0),
  Filename(""),
  PrevFilename(""),
  Saving(false),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
}


Logger::Logger(Input &aiinput, SDCard &sdcard0,
	       SDCard &sdcard1, const RTClock &rtclock,
	       Blink &blink) :
  AIInput(aiinput),
  SDCard0(&sdcard0),
  SDCard1(&sdcard1),
  File0(sdcard0, aiinput, 5),
  File1(sdcard1, aiinput, 5),
  Clock(rtclock),
  NoBlink(""),
  StatusLED(blink),
  ErrorLED(NoBlink),
  SyncLED(NoBlink),
  RandomBlinks(false),
  BlinkTimeout(0),
  Filename(""),
  PrevFilename(""),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
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


void Logger::flashLEDs() {
  if (ErrorLED.available() || SyncLED.available()) {
    StatusLED.switchOff();
    delay(100);
    StatusLED.switchOn();
    delay(100);
    StatusLED.switchOff();
    delay(100);
    if (ErrorLED.available()) {
      ErrorLED.switchOn();
      delay(100);
      ErrorLED.switchOff();
      delay(100);
    }
    if (SyncLED.available()) {
      SyncLED.switchOn();
      delay(100);
      SyncLED.switchOff();
      delay(100);
    }
    StatusLED.switchOn();
  }
}


bool Logger::check(Config &config, bool check_backup) {
  // cleanup previous recordings:
  char folder[64];
  SDCard0->latestDir("/", folder, 64);
  if (strlen(folder) > 0)
    SDCard0->cleanDir(folder, 1024, ".wav", true, true, Serial);
  // check for enough space:
  if (!SDCard0->check(1e9)) {
    SDCard0->end();
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
  if (SDCard1 != NULL &&
      (SDCard1->available() || check_backup) &&
       !SDCard1->check(SDCard0->free()))
    SDCard1->end();
  return true;
}


void Logger::endBackup(SPIClass *spi) {
  if (SDCard1 != NULL && !SDCard1->available()) {
    SDCard1->end();
    if (spi != NULL)
      spi->end();
    StatusLED.reset();
  }
}


void Logger::setCPUSpeed(uint32_t rate) {
  if (SDCard1 != NULL && !SDCard1->available()) {
    setTeensySpeed(150);
  }
  else {
    rate /= 1000;                    // sampling rate in kHz
    int speed = ((12+rate/2)/24)*24; // CPU speed in MHz, steps of 24, TODO: take channels into account?
    if (speed < 24)
      speed = 24;
    setTeensySpeed(speed);
  }
  Serial.printf("Set CPU speed to %dMHz\n\n", teensySpeed());
}

  
void Logger::report(Stream &stream) const {
  StatusLED.report(stream);
  if (ErrorLED.available())
    ErrorLED.report(stream);
  if (SyncLED.available())
    SyncLED.report(stream);
  Clock.report(stream);
  stream.println();
}


void Logger::initialDelay(float initial_delay, Stream &stream) {
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
}


void Logger::setup(const char *path, const char *filename,
		   const char *software, bool randomblinks,
		   float blinktimeout) {
  RandomBlinks = randomblinks;
  BlinkTimeout = (unsigned long)(1000*blinktimeout);
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
  if (File0.sdcard()->dataDir(path_name.c_str(), true))
    Serial.printf("Save recorded data in folder \"%s\" on %sSD card.\n\n",
		  File0.sdcard()->workingDir(), File0.sdcard()->name());
  File0.header().setSoftware(software);
  File0.header().setCPUSpeed();
  if (File1.sdcard() != NULL) {
    File1.sdcard()->dataDir(File0.sdcard()->workingDir());
    File1.header().setSoftware(software);
    File1.header().setCPUSpeed();
  }
}


void Logger::start(float filetime) {
  File0.setWriteInterval(2*AIInput.DMABufferTime());
  File0.setMaxFileTime(filetime);
  if (File1.sdcard() != NULL) {
    File1.setWriteInterval(2*AIInput.DMABufferTime());
    File1.setMaxFileTime(filetime);
  }
  if (RandomBlinks && SyncLED.available()) {
    SyncLED.setTiming(5000, 100, 1200);
    if (filetime > 30)
      StatusLED.setTiming(5000);
    else
      StatusLED.setTiming(2000);    
    SyncLED.clearSwitchTimes();
  }
  else {
    if (RandomBlinks)
      StatusLED.setTiming(5000, 100, 1200);
    else if (filetime > 30)
      StatusLED.setTiming(5000);
    else
      StatusLED.setTiming(2000);
    StatusLED.clearSwitchTimes();
  }
  File0.start();
  if (File1.sdcard() != NULL)
    File1.start(File0);
  open(false);
  open(true);
  NextStore = 0;
  NextOpen = 0;
  if (RandomBlinks)
    openBlinkFiles();
}


void Logger::start(float filetime, Config &config, InfoAction &amplifier) {
  start(filetime);
  if (strlen(File0.header().channels()) > 0)
    amplifier.add("Channels", File0.header().channels());
  if (strlen(File0.header().averaging()) > 0)
    amplifier.add("Averaging", File0.header().averaging());
  if (strlen(File0.header().conversionSpeed()) > 0)
    amplifier.add("Conversion speed", File0.header().conversionSpeed());
  if (strlen(File0.header().samplingSpeed()) > 0)
    amplifier.add("Sampling speed", File0.header().samplingSpeed());
  if (strlen(File0.header().reference()) > 0)
    amplifier.add("Reference", File0.header().reference());
  if (strlen(File0.header().gain()) > 0)
    amplifier.add("Gain", File0.header().gain());
  if (strlen(File0.header().software()) > 0)
    amplifier.add("Software", File0.header().software());
  writeMetadata(config);
}


void Logger::open(bool backup) {
  if (backup) {
    if (File1.sdcard() == NULL || !File1.sdcard()->available())
      return;
    File1.openWave(File0.name().c_str(), File0.header());
    ssize_t samples = File1.write();
    if (samples == -4) {   // overrun
      File1.start(AIInput.nbuffer()/2);   // skip half a buffer
      File1.write();                      // write all available data
      // report overrun:
      char mfs[100];
      sprintf(mfs, "%s-backup-error0-overrun.msg", File1.baseName().c_str());
      Serial.println(mfs);
      FsFile mf = SDCard1->openWrite(mfs);
      mf.close();
    }
    Serial.printf("and %sSD card)\n", File1.sdcard()->name());
  }
  else {
    StatusLED.setSingle();
    StatusLED.blinkSingle(0, 2000);
    if (RandomBlinks) {
      if (SyncLED.available()) {
	SyncLED.setRandom();
	SyncLED.blinkMultiple(5, 0, 200, 200);
      }
      else {
	StatusLED.setRandom();
	StatusLED.blinkMultiple(5, 0, 200, 200);
      }
    }
    String fname(Filename);
    char cs[16];
    sprintf(cs, "%04d", FileCounter + 1);
    fname.replace("COUNT", cs);
    time_t t = now();
    fname = Clock.makeStr(fname, t, true);
    if (fname != PrevFilename) {
      File0.sdcard()->resetFileCounter();
      PrevFilename = fname;
    }
    fname = File0.sdcard()->incrementFileName(fname);
    if (fname.length() == 0) {
      StatusLED.clear();
      SyncLED.clear();
      AIInput.stop();
      halt(3);
      return;
    }
    char dts[20];
    Clock.dateTime(dts, t);
    if (! File0.openWave(fname.c_str(), -1, dts)) {
      StatusLED.clear();
      SyncLED.clear();
      Serial.println();
      Serial.printf("WARNING: failed to open file on %sSD card.\n", File0.sdcard()->name());
      Serial.println("SD card probably not inserted or full -> ");
      AIInput.stop();
      halt(4);
      return;
    }
    Saving = true;
    FileCounter++;
    ssize_t samples = File0.write();
    if (samples == -4) {   // overrun
      File0.start(AIInput.nbuffer()/2);   // skip half a buffer
      File0.write();                      // write all available data
      // report overrun:
      char mfs[100];
      sprintf(mfs, "%s-error0-overrun.msg", File0.baseName().c_str());
      Serial.println(mfs);
      FsFile mf = SDCard0->openWrite(mfs);
      mf.close();
    }
    if (File1.sdcard() != NULL && File1.sdcard()->available()) {
      Serial.print(File0.name());
      Serial.printf(" (on %s", File0.sdcard()->name());
    }
    else
      Serial.println(File0.name());
  }
}


void Logger::close() {
  if (! Saving)
    return;
  File0.closeWave();
  if (File1.sdcard() != NULL && File1.sdcard()->available())
    File1.closeWave();
  Saving = false;
  SyncLED.clear();
  StatusLED.setDouble();
}


bool Logger::store(SDWriter &sdfile, bool backup) {
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
	if (backup) {
	  Serial.printf("  %sSD card probably full.\n", sdfile.sdcard()->name());
	  SDCard1->end();
	}
	else {
	  Serial.printf("  %sSD card probably full -> \n", sdfile.sdcard()->name());
	  AIInput.stop();
	  StatusLED.clear();
	  SyncLED.clear();
	  halt(5);
	}
        strcpy(errorstr, "nowrite");
	break;
    }
    sdfile.closeWave();
    // write error file:
    char mfs[100];
    if (backup)
      sprintf(mfs, "%s-backup-error%d-%s.msg", sdfile.baseName().c_str(),
	      Restarts+1, errorstr);
    else
      sprintf(mfs, "%s-error%d-%s.msg", sdfile.baseName().c_str(),
	      Restarts+1, errorstr);
    Serial.println(mfs);
    FsFile mf = SDCard0->openWrite(mfs);
    mf.close();
    // halt after too many errors:
    Restarts++;
    Serial.printf("Incremented restarts to %d, samples=%d on %sSD card\n", Restarts, samples, sdfile.sdcard()->name());
    if (Restarts >= 5) {
      Serial.printf("ERROR in Logger::storeData() on %sSD card: too many file errors", sdfile.sdcard()->name());
      if (backup) {
	Serial.println(" -> end backups");
	SDCard1->end();
      }
      else {
	AIInput.stop();
	StatusLED.clear();
	SyncLED.clear();
	Serial.println(" -> ");
	halt(6);
      }
    }
    // restart analog input:
    if (!AIInput.running())
      AIInput.start();
    // open next file:
    sdfile.start();
    open(backup);
  }
  return true;
}


void Logger::writeMetadata(Config &config) {
  String fname = File0.name();
  fname.replace(".wav", "-metadata.yml");
  FsFile file0 = SDCard0->openWrite(fname.c_str());
  config.report(file0, config.FileOutput | config.Report);
  file0.close();
  if (SDCard1 != NULL && SDCard1->available()) {
    FsFile file1 = SDCard1->openWrite(fname.c_str());
    config.report(file1, config.FileOutput | config.Report);
    file1.close();
  }
  Serial.print("Wrote metadata to ");
  Serial.println(fname);
}


void Logger::openBlinkFiles() {
  String fname = File0.name();
  fname.replace(".wav", "-blinks.csv");
  BlinkFile0 = SDCard0->openWrite(fname.c_str());
  BlinkFile0.write("time/ms,on\n");
  if (SDCard1 != NULL && SDCard1->available()) {
    BlinkFile1 = SDCard1->openWrite(fname.c_str());
    BlinkFile1.write("time/ms,on\n");
  }
  Serial.print("Store blink times in ");
  Serial.println(fname);
}


void Logger::storeBlinks() {
  Blink &led = SyncLED.available() ? SyncLED : StatusLED;

  if (led.nswitchTimes() < Blink::MaxTimes/2)
    return;
  uint32_t tstart = File0.startWriteTime();
  uint32_t times[Blink::MaxTimes];
  bool states[Blink::MaxTimes];
  size_t n;
  led.getSwitchTimes(times, states, &n);
  char buffer[Blink::MaxTimes*14];
  size_t m = 0;
  for (size_t k=0; k<n; k++)
    m += sprintf(buffer + m, "%lu,%u\n", times[k] - tstart, states[k]);
  BlinkFile0.write(buffer, m);
  BlinkFile0.flush();
  if (SDCard1 != NULL && SDCard1->available()) {
    BlinkFile1.write(buffer, m);
    BlinkFile1.flush();
  }
}


void Logger::update() {
  if (NextStore == 0) {
    if (store(File0, false) && SDCard1 != NULL && SDCard1->available())
      NextStore = 1;
  }
  if (NextStore == 1) {
    if (store(File1, true))
      NextStore = 0;
  }
  if (NextOpen == 0) {
    if (File0.endWrite()) {
      File0.close();  // file size was set by openWave()
#ifdef SINGLE_FILE_MTP
      SyncLED.clear();
      AIInput.stop();
      delay(50);
      Serial.println();
      Serial.println("MTP file transfer.");
      Serial.flush();
      StatusLED.setTriple();
      MTP.begin();
      MTP.addFilesystem(*SDCard0, "logger");
      while (true) {
	MTP.loop();
	StatusLED.update();
	yield();
      }
#endif
      synchronize(); // TODO: make this working also for backup.
      open(false);
      if (SDCard1 != NULL && SDCard1->available())
	NextOpen = 1;
    }
  }
  if (NextOpen == 1) {
    if (File1.endWrite()) {
      File1.close();  // file size was set by openWave()
      open(true);
      NextOpen = 0;
    }
  }
  if (RandomBlinks)
    storeBlinks();
  if ((BlinkTimeout > 0) && (millis() > BlinkTimeout)) {
    StatusLED.disablePin(0);
    SyncLED.clearPins();
  }
  if ((BlinkTimeout > 0) && (millis() > 2*BlinkTimeout))
    StatusLED.disablePin(1);
  StatusLED.update();
  SyncLED.update();
}


void Logger::R41powerDownCAN() {
  #define CAN_SHDN_PIN 37      // R4.1 CAN shutdown pin
  pinMode(CAN_SHDN_PIN, OUTPUT);
  digitalWrite(CAN_SHDN_PIN, HIGH);
}

