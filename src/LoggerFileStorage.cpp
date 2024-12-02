// Define SINGLE_FILE_MTP to stop recording after the first file has
// been written, and make then the SD card available over USB as MTB
// filesystem.
//#define SINGLE_FILE_MTP

#include <LoggerFileStorage.h>
#ifdef SINGLE_FILE_MTP
#include <MTP_Teensy.h>
#endif


LoggerFileStorage::LoggerFileStorage(Input &aiinput, SDCard &sdcard0,
				     const RTClock &rtclock,
				     const DeviceID &deviceid, Blink &blink) :
  AIInput(aiinput),
  SDCard0(&sdcard0),
  SDCard1(0),
  File0(sdcard0, aiinput, 5),
  File1(),
  Clock(rtclock),
  DeviceIdent(deviceid),
  BlinkLED(blink),
  RandomBlinks(false),
  Filename(NULL),
  PrevFilename(""),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
}


LoggerFileStorage::LoggerFileStorage(Input &aiinput, SDCard &sdcard0,
				     SDCard &sdcard1, const RTClock &rtclock,
				     const DeviceID &deviceid, Blink &blink) :
  AIInput(aiinput),
  SDCard0(&sdcard0),
  SDCard1(&sdcard1),
  File0(sdcard0, aiinput, 5),
  File1(sdcard1, aiinput, 5),
  Clock(rtclock),
  DeviceIdent(deviceid),
  BlinkLED(blink),
  RandomBlinks(false),
  Filename(NULL),
  PrevFilename(""),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
}


void LoggerFileStorage::halt(Stream &stream) {
  stream.println("HALT");
  while (true) { yield(); };
}


bool LoggerFileStorage::check(bool check_backup, Stream &stream) {
  if (!SDCard0->check(1e9)) {
    SDCard0->end();
    BlinkLED.switchOff();
    halt(stream);
    return false;
  }
  if (SDCard1 != NULL &&
      (SDCard1->available() || check_backup) &&
       !SDCard1->check(SDCard0->free()))
    SDCard1->end();
  return true;
}


void LoggerFileStorage::endBackup(SPIClass *spi) {
  if (SDCard1 != NULL && !SDCard1->available()) {
    SDCard1->end();
    if (spi != NULL)
      spi->end();
    BlinkLED.reset();
  }
}

  
void LoggerFileStorage::report(Stream &stream) const {
  DeviceIdent.report(stream);
  Clock.report(stream);
}


void LoggerFileStorage::initialDelay(float initial_delay) {
  if (initial_delay >= 2.0) {
    delay(1000);
    BlinkLED.setDouble();
    BlinkLED.delay(uint32_t(1000.0*initial_delay) - 1000);
  }
  else
    delay(uint32_t(1000.0*initial_delay));
}


void LoggerFileStorage::setup(SDWriter &sdfile, float filetime,
			      const char *software, char *gainstr) {
  sdfile.setWriteInterval(2*AIInput.DMABufferTime());
  sdfile.setMaxFileTime(filetime);
  sdfile.header().setSoftware(software);
  sdfile.header().setCPUSpeed();
  if (gainstr != 0)
    sdfile.header().setGain(gainstr);
}


void LoggerFileStorage::start(const char *path, const char *filename,
			      float filetime, const char *software,
			      char *gainstr, bool randomblinks) {
  RandomBlinks = randomblinks;
  Filename = filename;
  PrevFilename = "";
  Restarts = 0;
  if (RandomBlinks)
    BlinkLED.setTiming(5000, 100, 1200);
  else if (filetime > 30)
    BlinkLED.setTiming(5000);
  else
    BlinkLED.setTiming(2000);
  if (File0.sdcard()->dataDir(path))
    Serial.printf("Save recorded data in folder \"%s\" on %sSD card.\n\n",
		  path, File0.sdcard()->name());
  setup(File0, filetime, software, gainstr);
  if (File1.sdcard() != NULL) {
    File1.sdcard()->dataDir(path);
    setup(File1, filetime, software, gainstr);
  }
  BlinkLED.clearSwitchTimes();
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


void LoggerFileStorage::open(bool backup) {
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
    if (RandomBlinks) {
      BlinkLED.setRandom();
      BlinkLED.blinkMultiple(5, 0, 200, 200);
    }
    else {
      BlinkLED.setSingle();
      BlinkLED.blinkSingle(0, 2000);
    }
    String fname = DeviceIdent.makeStr(Filename);
    char cs[16];
    sprintf(cs, "%04d", FileCounter+1);
    fname.replace("COUNT", cs);
    time_t t = now();
    fname = Clock.makeStr(fname, t, true);
    if (fname != PrevFilename) {
      File0.sdcard()->resetFileCounter();
      PrevFilename = fname;
    }
    fname = File0.sdcard()->incrementFileName(fname);
    if (fname.length() == 0) {
      BlinkLED.clear();
      Serial.printf("WARNING: failed to increment file name on %sSD card.\n", File0.sdcard()->name());
      Serial.println("SD card probably not inserted -> ");
      AIInput.stop();
      BlinkLED.switchOff();
      halt();
      return;
    }
    char dts[20];
    Clock.dateTime(dts, t);
    if (! File0.openWave(fname.c_str(), -1, dts)) {
      BlinkLED.clear();
      Serial.println();
      Serial.printf("WARNING: failed to open file on %sSD card.\n", File0.sdcard()->name());
      Serial.println("SD card probably not inserted or full -> ");
      AIInput.stop();
      BlinkLED.switchOff();
      halt();
      return;
    }
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


bool LoggerFileStorage::store(SDWriter &sdfile, bool backup) {
  if (!sdfile.pending())
    return false;
  ssize_t samples = sdfile.write();
  if (samples < 0) {
    BlinkLED.clear();
    Serial.println();
    Serial.printf("ERROR in writing data to file on %sSD card in LoggerFileStorage::store():\n", sdfile.sdcard()->name());
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
	  BlinkLED.switchOff();
	  halt();
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
      Serial.printf("ERROR in LoggerFileStorage::storeData() on %sSD card: too many file errors", sdfile.sdcard()->name());
      if (backup) {
	Serial.println(" -> end backups");
	SDCard1->end();
      }
      else {
	AIInput.stop();
	BlinkLED.switchOff();
	Serial.println(" -> ");
	halt();
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


void LoggerFileStorage::openBlinkFiles() {
  String fname = File0.name();
  fname.replace(".wav", "-blinks.dat");
  BlinkFile0 = SDCard0->openWrite(fname.c_str());
  BlinkFile0.write("time;on\n");
  if (SDCard1 != NULL && SDCard1->available()) {
    BlinkFile1 = SDCard1->openWrite(fname.c_str());
    BlinkFile1.write("time;on\n");
  }
  Serial.print("Store blink times in ");
  Serial.println(fname);
}


void LoggerFileStorage::storeBlinks() {
  if (BlinkLED.nswitchTimes() < Blink::MaxTimes/2)
    return;
  uint32_t tstart = File0.startWriteTime();
  uint32_t times[Blink::MaxTimes];
  bool states[Blink::MaxTimes];
  size_t n;
  BlinkLED.getSwitchTimes(times, states, &n);
  char buffer[Blink::MaxTimes*14];
  size_t m = 0;
  for (size_t k=0; k<n; k++)
    m += sprintf(buffer + m, "%lu;%u\n", times[k] - tstart, states[k]);
  BlinkFile0.write(buffer, m);
  BlinkFile0.flush();
  if (SDCard1 != NULL && SDCard1->available()) {
    BlinkFile1.write(buffer, m);
    BlinkFile1.flush();
  }
}


void LoggerFileStorage::update() {
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
      AIInput.stop();
      delay(50);
      Serial.println();
      Serial.println("MTP file transfer.");
      Serial.flush();
      BlinkLED.setTriple();
      MTP.begin();
      MTP.addFilesystem(*SDCard0, "logger");
      while (true) {
	MTP.loop();
	BlinkLED.update();
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
}
