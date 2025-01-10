#include <SensorsLoggerFileStorage.h>


SensorsLoggerFileStorage::SensorsLoggerFileStorage(Input &aiinput,
						   ESensors &sensors,
						   SDCard &sdcard,
						   const RTClock &rtclock,
						   const DeviceID &deviceid,
						   Blink &blink) :
  LoggerFileStorage(aiinput, sdcard, rtclock, deviceid, blink),
  Sensors(sensors) {
}


void SensorsLoggerFileStorage::initSensors(float interval) {
  Sensors.setInterval(interval);
  Sensors.setPrintTime(ESensors::ISO_TIME);
  Sensors.reportDevices();
  Sensors.report();
  Sensors.start();
  Sensors.read();
  Sensors.start();
  Sensors.read();
}


void SensorsLoggerFileStorage::start(const char *path, const char *filename,
				     float filetime, const char *software,
				     char *gainstr, bool randomblinks) {
  LoggerFileStorage::start(path, filename, filetime, software,
			   gainstr, randomblinks);
  openSensorsFile();
}


void SensorsLoggerFileStorage::openSensorsFile() {
  String sname = File0.name();
  sname.replace(".wav", "-sensors");
  Sensors.openCSV(*SDCard0, sname.c_str());
}


bool SensorsLoggerFileStorage::storeSensors() {
  if (Sensors.update()) {
    Sensors.writeCSV();
    Sensors.print(true, true);
    return true;
  }
  return false;
}


bool SensorsLoggerFileStorage::update() {
  LoggerFileStorage::update();
  return storeSensors();
}
