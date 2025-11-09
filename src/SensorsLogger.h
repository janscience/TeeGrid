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
		const RTClock &rtclock, Blink &blink);
  SensorsLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard0,
		const RTClock &rtclock, Blink &blink,
		Blink &errorblink, Blink &syncblink);

  // Initialize environmental sensors.
  void setupSensors();

  // Start environmental sensors.
  void startSensors(float interval, float lightthreshold=0.0);

  // Open files.
  void start(float filetime);
  
  // Open files and write metadata from config.
  // Add more metadata to amplifier.
  void start(float filetime, Config &config, Menu &amplifier);

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

  static const size_t MaxLight = 4;
  ESensor *LightSensors[MaxLight];
  size_t NLightSensors;
  float IlluminationThreshold;
  
};


#endif

