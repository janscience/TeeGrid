#include <SensorsLogger.h>


SensorsLogger::SensorsLogger(Input &aiinput,
			     ESensors &sensors,
			     SDCard &sdcard,
			     const RTClock &rtclock,
			     const DeviceID &deviceid,
			     Blink &blink) :
  Logger(aiinput, sdcard, rtclock, deviceid, blink),
  Sensors(sensors) {
}


void SensorsLogger::setupSensors() {
  Sensors.setPrintTime(ESensors::NO_TIME);
  Sensors.start();
}


void SensorsLogger::startSensors(float interval) {
  Sensors.setInterval(interval);
  Sensors.setPrintTime(ESensors::ISO_TIME);
  Sensors.reportDevices();
  Sensors.report();
  Sensors.start();
  Sensors.read();
  Sensors.start();
  Sensors.read();
}


void SensorsLogger::start(float filetime) {
  Logger::start(filetime);
  openSensorsFile();
}


void SensorsLogger::openSensorsFile() {
  String sname = File0.name();
  sname.replace(".wav", "-sensors");
  Sensors.openCSV(*SDCard0, sname.c_str());
}


bool SensorsLogger::storeSensors() {
  if (Sensors.update()) {
    Sensors.writeCSV();
    Sensors.print(true, true);
    return true;
  }
  return false;
}


bool SensorsLogger::update() {
  Logger::update();
  return storeSensors();
}
