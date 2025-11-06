#include <SensorsLogger.h>


SensorsLogger::SensorsLogger(Input &aiinput,
			     ESensors &sensors,
			     SDCard &sdcard,
			     const RTClock &rtclock,
			     Blink &blink) :
  Logger(aiinput, sdcard, rtclock, blink),
  Sensors(sensors) {
}


SensorsLogger::SensorsLogger(Input &aiinput,
			     ESensors &sensors,
			     SDCard &sdcard,
			     const RTClock &rtclock,
			     Blink &blink,
			     Blink &errorblink,
			     Blink &syncblink) :
  Logger(aiinput, sdcard, rtclock, blink, errorblink, syncblink),
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


void SensorsLogger::start(float filetime, Config &config,
			  InfoAction &amplifier) {
  Logger::start(filetime, config, amplifier);
  openSensorsFile();
}


void SensorsLogger::openSensorsFile() {
  String sname = File0.name();
  sname.replace(".wav", "-sensors");
  Sensors.openCSV(*SDCard0, sname.c_str());
}


bool SensorsLogger::storeSensors() {
  if (Sensors.update(StatusLED.isOn() || SyncLED.isOn())) {
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
