#include <LoggerSettings.h>
#include <SensorsLogger.h>


SensorsLogger::SensorsLogger(Input &aiinput,
			     ESensors &sensors,
			     SDCard &sdcard,
			     RTClock &rtclock,
			     Blink &blink) :
  Logger(aiinput, sdcard, rtclock, blink),
  Sensors(sensors),
  NLightSensors(0),
  IlluminationThreshold(0.0) {
}


SensorsLogger::SensorsLogger(Input &aiinput,
			     ESensors &sensors,
			     SDCard &sdcard,
			     RTClock &rtclock,
			     Blink &blink,
			     Blink &errorblink,
			     Blink &syncblink) :
  Logger(aiinput, sdcard, rtclock, blink, errorblink, syncblink),
  Sensors(sensors),
  NLightSensors(0),
  IlluminationThreshold(0.0) {
}


void SensorsLogger::setupSensors() {
  Sensors.setPrintTime(ESensors::NO_TIME);
  Sensors.start();
  for (uint8_t k=0; k<Sensors.sensors(); k++) {
    if (Sensors[k].available() && (strcmp(Sensors[k].unit(), "lx") == 0) &&
	(NLightSensors < MaxLight))
      LightSensors[NLightSensors++] = &Sensors[k];
  }
}


void SensorsLogger::checkVoltage(float startvoltage) {
  ESensor *vbat = Sensors.sensor("battery-voltage");
  if (vbat != 0 && startvoltage > 0.0) {
    float volt = vbat->read();
    if (volt < startvoltage) {
      Serial.printf("HALT --- battery voltage %.2fV lower than %.2fV!\n", volt, startvoltage);
      while (true)
	yield();
    }
  }
}


void SensorsLogger::startSensors(float interval,
				 float lightthreshold) {
  IlluminationThreshold = lightthreshold;
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


void SensorsLogger::start(float filetime, Config &config) {
  Logger::start(filetime, config);
  openSensorsFile();
}


void SensorsLogger::start(float filetime, Config &config,
			  Menu &amplifier) {
  Logger::start(filetime, config, amplifier);
  openSensorsFile();
}


void SensorsLogger::openSensorsFile() {
  String sname = File.name();
  sname.replace(".wav", "-sensors");
  Sensors.openCSV(*Disk, sname.c_str());
  Serial.print("Write sensor data to ");
  Serial.println(sname);
}


bool SensorsLogger::storeSensors() {
  if (Sensors.update(StatusLED.isOn() || SyncLED.isOn())) {
    if (Sensors.pendingCSV())
      Sensors.writeCSV();
    Sensors.print(true, true);
    // strongest illumination:
    if (NLightSensors > 0) {
      float illumination = 0.0;
      for (size_t k=0; k<NLightSensors; k++) {
	if (LightSensors[k]->value() > illumination)
	  illumination = LightSensors[k]->value();
      }
      if (illumination < IlluminationThreshold) {
	StatusLED.disablePins();
	SyncLED.disablePins();
      }
      else {
	StatusLED.enablePins();
	SyncLED.enablePins();
      }
    }
    return true;
  }
  return false;
}


void SensorsLogger::closeSensorsFile() {
  Sensors.closeCSV();
}


bool SensorsLogger::update() {
  Logger::update();
  return storeSensors();
}


void SensorsLogger::stop() {
  closeSensorsFile();
  Logger::stop();
}

