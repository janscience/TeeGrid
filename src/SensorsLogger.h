/*
  SensorsLogger - High level handling of file storage of logger and sensors data.
  Created by Jan Benda, January 4th, 2025.
*/

#ifndef SenorsLogger_h
#define SensorsLogger_h

#include <ESensors.h>
#include <Logger.h>


class SensorsLogger : public Logger {
  
public:

  SensorsLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard0,
		const RTClock &rtclock, const DeviceID &deviceid,
		Blink &blink);

  // Initialize environmental sensors.
  void initSensors(float interval);

  // Initialize recording directory and first files.
  void start(const char *path, const char *filename, float filetime,
	     const char *software, char *gainstr=0, bool randomblinks=false);

  // Call this in loop() for writing data to files.
  // Returns true if sensors have been updated.
  bool update();


protected:
  
  // Open file that stores sensor data.
  void openSensorsFile();
  
  // Store sensor readings in file.
  bool storeSensors();

  // Write recorded data to files.
  bool store(SDWriter &sdfile, bool backup);

  ESensors &Sensors;
  
};


#endif

