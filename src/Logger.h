/*
  Logger - High level handling of file storage of logger data.
  Created by Jan Benda, August 28th, 2024.
*/

#ifndef Logger_h
#define Logger_h

#include <Input.h>
#include <SDCard.h>
#include <SDWriter.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <MicroConfig.h>


class Logger {
  
public:

  Logger(Input &aiinput, SDCard &sdcard0,
	 const RTClock &rtclock, const DeviceID &deviceid,
	 Blink &blink);
  Logger(Input &aiinput, SDCard &sdcard0, SDCard &sdcard1,
	 const RTClock &rtclock, const DeviceID &deviceid,
	 Blink &blink);

  // Check accessibility of SD cards.
  // Run menu and halt if the main SD card can not be written.
  // If check_backup force checking backup SD card as well.
  bool check(Config &config, bool check_backup=false);

  // If secondary SD card is not available, end its usage.
  void endBackup(SPIClass *spi=NULL);

  // Reduce CPU speed according to sampling rate.
  void setCPUSpeed(uint32_t rate);

  // Report device identifier and current date and time.
  void report(Stream &stream=Serial) const;

  // Delay with double blinks for initial_delay seconds.
  void initialDelay(float initial_delay, Stream &stream=Serial);
  
  // Initialize recording directory and file metadata.
  void setup(const char *path, const char *filename,
	     const char *software, bool randomblinks);

  // Open files.
  void start(float filetime);

  // Close files.
  void close();

  // Call this in loop() for writing data to files.
  void update();

  // True, if data are stored in files.
  bool saving() const { return Saving; };

  String baseName() const { return File0.baseName(); };


protected:
  
  // Generate file name, open main file and write first chunk of data.
  void open(bool backup);
  
  // Open file that stores blink times.
  void openBlinkFiles();
  
  // Store blink times in files.
  void storeBlinks();

  // Write recorded data to files.
  bool store(SDWriter &sdfile, bool backup);

  // Derived classes can insert code here before the next file is opened.
  virtual bool synchronize() { return false; };

  Input &AIInput;
  SDCard *SDCard0;
  SDCard *SDCard1;
  SDWriter File0;
  SDWriter File1;
  const RTClock &Clock;
  const DeviceID &DeviceIdent;
  Blink &BlinkLED;
  
  bool RandomBlinks;
  FsFile BlinkFile0;
  FsFile BlinkFile1;
  
  const char *Filename;  // Template for filename
  String PrevFilename;   // Previous file name
  bool Saving;
  int FileCounter;
  int Restarts;
  int NextStore;
  int NextOpen;
  
};


#endif

