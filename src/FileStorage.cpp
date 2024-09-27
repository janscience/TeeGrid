// Define SINGLE_FILE_MTP to stop recording after the first file has
// been written, and make then the SD card available over USB as MTB
// filesystem.
//#define SINGLE_FILE_MTP

#include <FileStorage.h>
#ifdef SINGLE_FILE_MTP
#include <MTP_Teensy.h>
#endif


FileStorage::FileStorage(Input &aiinput, SDCard &sdcard0, SDCard &sdcard1,
			 const RTClock &rtclock, const DeviceID &deviceid,
			 Blink &blink) :
  AIInput(aiinput),
  SDCard0(sdcard0),
  SDCard1(sdcard1),
  File0(sdcard0, aiinput, 5),
  File1(sdcard1, aiinput, 5),
  Clock(rtclock),
  DeviceIdent(deviceid),
  BlinkLED(blink),
  Filename(NULL),
  PrevFilename(""),
  FileCounter(0),
  Restarts(0),
  NextStore(0),
  NextOpen(0) {
}


bool FileStorage::check(bool check_backup, Stream &stream) {
  if (!SDCard0.check(1e9)) {
    stream.println("HALT");
    SDCard0.end();
    BlinkLED.switchOff();
    while (true) { yield(); };
    return false;
  }
  if ((SDCard1.available() || check_backup) && !SDCard1.check(SDCard0.free()))
    SDCard1.end();
  return true;
}

  
void FileStorage::report(Stream &stream) const {
  DeviceIdent.report(stream);
  Clock.report(stream);
}


void FileStorage::initialDelay(float initial_delay) {
  if (initial_delay >= 2.0) {
    delay(1000);
    BlinkLED.setDouble();
    BlinkLED.delay(uint32_t(1000.0*initial_delay) - 1000);
  }
  else
    delay(uint32_t(1000.0*initial_delay));
}


void FileStorage::setup(SDWriter &sdfile, float filetime,
			const char *software, char *gainstr) {
  sdfile.setWriteInterval(2*AIInput.DMABufferTime());
  sdfile.setMaxFileTime(filetime);
  sdfile.header().setSoftware(software);
  if (gainstr != 0)
    sdfile.header().setGain(gainstr);
}


void FileStorage::start(const char *path, const char *filename,
			float filetime, const char *software,
			char *gainstr) {
  Filename = filename;
  PrevFilename = "";
  Restarts = 0;
  if (filetime > 30)
    BlinkLED.setTiming(5000);
  else
    BlinkLED.setTiming(2000);
  if (File0.sdcard()->dataDir(path))
    Serial.printf("Save recorded data in folder \"%s\" on %sSD card.\n\n", path, File0.sdcard()->name());
  File1.sdcard()->dataDir(path);
  setup(File0, filetime, software, gainstr);
  setup(File1, filetime, software, gainstr);
  File0.start();
  File1.start(File0);
  open(false);
  open(true);
  NextStore = 0;
  NextOpen = 0;
}


void FileStorage::open(bool backup) {
  if (backup) {
    if (!File1.sdcard()->available())
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
      FsFile mf = SDCard1.openWrite(mfs);
      mf.close();
    }
  }
  else {
    BlinkLED.setSingle();
    BlinkLED.blinkSingle(0, 2000);
    String fname = DeviceIdent.makeStr(Filename);
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
      Serial.println("SD card probably not inserted -> HALT");
      Serial.println();
      AIInput.stop();
      BlinkLED.switchOff();
      while (true) { yield(); };
      return;
    }
    char dts[20];
    Clock.dateTime(dts, t);
    if (! File0.openWave(fname.c_str(), -1, dts)) {
      BlinkLED.clear();
      Serial.println();
      Serial.printf("WARNING: failed to open file on %sSD card.\n", File0.sdcard()->name());
      Serial.println("SD card probably not inserted or full -> HALT");
      AIInput.stop();
      BlinkLED.switchOff();
      while (true) { yield(); };
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
      FsFile mf = SDCard0.openWrite(mfs);
      mf.close();
    }
    Serial.println(File0.name());
  }
}


bool FileStorage::store(SDWriter &sdfile, bool backup) {
  if (!sdfile.pending())
    return false;
  ssize_t samples = sdfile.write();
  if (samples < 0) {
    BlinkLED.clear();
    Serial.println();
    Serial.printf("ERROR in writing data to file on %sSD card in FileStorage::store():\n", sdfile.sdcard()->name());
    char errorstr[20];
    switch (samples) {
      case -1:
        Serial.printf("  file on %sSD card not open.\n", sdfile.sdcard()->name());
        strcpy(errorstr, "notopen");
        break;
      case -2:
        Serial.printf("  file on %sSD card already full.\n", sdfile.sdcard()->name());
        strcpy(errorstr, "full");
        break;
      case -3:
        AIInput.stop();
        Serial.println("  no data available, data acquisition probably not running.");
        Serial.printf("  dmabuffertime = %.2fms, writetime = %.2fms\n", 1000.0*AIInput.DMABufferTime(), 1000.0*sdfile.writeTime());
        strcpy(errorstr, "nodata");
        break;
      case -4:
        Serial.printf("  %sbuffer overrun for %sSD card.\n", sdfile.sdcard()->name());
        Serial.printf("  dmabuffertime = %.2fms, writetime = %.2fms\n", 1000.0*AIInput.DMABufferTime(), 1000.0*sdfile.writeTime());
        strcpy(errorstr, "overrun");
        break;
      case -5:
        Serial.printf("  nothing written into the file on %sSD card.\n", sdfile.sdcard()->name());
	if (backup) {
	  Serial.printf("  %sSD card probably full.\n", sdfile.sdcard()->name());
	  SDCard1.end();
	}
	else {
	  Serial.printf("  %sSD card probably full -> HALT\n", sdfile.sdcard()->name());
	  AIInput.stop();
	  BlinkLED.switchOff();
	  while (true) { yield(); };
	}
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
    FsFile mf = SDCard0.openWrite(mfs);
    mf.close();
    Serial.println();
    // halt after too many errors:
    Restarts++;
    Serial.printf("Incremented restarts to %d, samples=%d on %sSD card\n", Restarts, samples, sdfile.sdcard()->name());
    if (Restarts >= 5) {
      Serial.printf("ERROR in FileStorage::storeData() on %sSD card: too many file errors", sdfile.sdcard()->name());
      if (backup) {
	Serial.println(" -> end backups");
	SDCard1.end();
      }
      else {
	Serial.println(" -> HALT");
	AIInput.stop();
	BlinkLED.switchOff();
	while (true) { yield(); };
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


void FileStorage::update() {
  if (NextStore == 0) {
    if (store(File0, false) && SDCard1.available())
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
      MTP.addFilesystem(SDCard0, "logger");
      while (true) {
	MTP.loop();
	BlinkLED.update();
	yield();
      }
#endif      
      open(false);
      if (SDCard1.available())
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
}
