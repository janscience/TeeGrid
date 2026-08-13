/*
  SensorsLogger - High level handling of file storage of logger and sensors data.
  Created by Jan Benda, January 4th, 2025.
*/

#ifndef SensorsLogger_h
#define SensorsLogger_h

#include <ESensors.h>
#include <Logger.h>


class SensorsLogger : public Logger {
  
public:

  SensorsLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard,
		RTClock &rtclock, Blink &blink);
  SensorsLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard,
		RTClock &rtclock, Blink &blink,
		Blink &errorblink, Blink &syncblink);

  // Check battery voltage.
  void checkVoltage(float minvoltage);

  // Initialize environmental sensors.
  void setupSensors();

  // Start environmental sensors.
  void startSensors(float interval, float lightthreshold=0.0);

  // Open files.
  void start(float filetime);
  
  // Open files and write metadata from config.
  void start(float filetime, Config &config);
  
  // Open files and write metadata from config.
  // Add more metadata to amplifier.
  void start(float filetime, Config &config, Menu &amplifier);

  // Call this in loop() for writing data to files.
  // Returns true if sensors have been updated.
  bool update(float stopvoltage=0.0);


protected:
  
  // Open file that stores sensor data.
  void openSensorsFile();
  
  // Store sensor readings in file.
  bool storeSensors();
  
  // Close sensors file.
  void closeSensorsFile();

  // Stop recording if battery voltage is too low.
  virtual void synchronize(float stopvoltage);

  // Close all files and reboot.
  virtual void stop();  

  ESensors &Sensors;

  static const size_t MaxLight = 4;
  ESensor *LightSensors[MaxLight];
  size_t NLightSensors;
  float IlluminationThreshold;
  
};


#endif

