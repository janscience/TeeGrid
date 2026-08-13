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


void SensorsLogger::configure(Config &config) {
  // get configuration from EEPROM:
  config.get();
  Serial.println();
  // check SD card:
  check(config);
  Clock.setFromFile(*SDCard0);
  // cleanup previous recordings:
  char folder[64];
  SDCard0->latestDir("/", folder, 64);
  if (strlen(folder) > 0) {
    SDCard0->cleanDir(folder, 1024, ".wav", true, ".csv", true);
    if (SDCard1 != NULL && SDCard1->available())
      SDCard1->cleanDir(folder, 1024, ".wav", true, ".csv", true);
  }
  Serial.println();
  // get configuration from file:
  config.load();
  // check voltage:
  LoggerSettings *settings = static_cast<LoggerSettings*>(config.action("Settings"));
  float minvoltage = settings != 0 ? settings->minimumVoltage() : 0.0;
  ESensor *vbat = Sensors.sensor("battery-voltage");
  if (vbat != 0 && minvoltage > 0.0) {
    float volt = vbat->read();
    if (volt < minvoltage) {
      Serial.printf("HALT --- battery voltage %.2fV lower than %.2fV!\n", volt, minvoltage);
      while (true)
	yield();
    }
  }
  if (Serial)
    config.execute();
  config.report();
  Serial.println();
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
  String sname = File0.name();
  sname.replace(".wav", "-sensors");
  Sensors.openCSV(*SDCard0, sname.c_str());
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

