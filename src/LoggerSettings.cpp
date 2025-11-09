#include <DeviceID.h>
#include <LoggerSettings.h>


LoggerSettings::LoggerSettings(Menu &menu, const char *label, int deviceid,
			       const char *path, const char *filename,
			       float filetime, float initialdelay,
			       bool randomblinks, float blinktimeout,
			       float sensorsinterval, float lightthreshold) :
  Menu(menu, "Settings"),
  Label(*this, "Label", label),
  ID(*this, "DeviceID", deviceid, -1, 127, "%d"),
  Path(*this, "Path", path),
  FileName(*this, "FileName", filename),
  FileTime(*this, "FileTime", filetime, 1.0, 8640.0, "%.0f", "s"),
  InitialDelay(*this, "InitialDelay", initialdelay, 0.0, 1e8, "%.0f", "s"),
  RandomBlinks(*this, "RandomBlinks", randomblinks),
  BlinkTimeout(*this, "BlinkTimeout", blinktimeout, 0.0, 1e8, "%.0f", "s"),
  SensorsInterval(*this, "SensorsInterval", sensorsinterval, 1.0, 1e8, "%.0f", "s"),
  LightThreshold(*this, "LightThreshold", lightthreshold, 0.0, 1e8, "%.0f", "lx") {
  ID.setSpecial(-1, "device");
  SensorsInterval.disable();
  LightThreshold.disable();
}


void LoggerSettings::setLabel(const char *label) {
  Path.setValue(label);
}

								
void LoggerSettings::setDeviceID(int id) {
  ID.setValue(id);
}


void LoggerSettings::setPath(const char *path) {
  Path.setValue(path);
}


void LoggerSettings::setFileName(const char *fname) {
  FileName.setValue(fname);
}


void LoggerSettings::preparePaths(const DeviceID &deviceid) {
  // path:
  String s = Path.value();
  s.replace("LABEL", Label.value());
  s = deviceid.makeStr(s);
  Path.setValue(s.c_str());
  // filename:
  s = FileName.value();
  s.replace("LABEL", Label.value());
  s = deviceid.makeStr(s);
  FileName.setValue(s.c_str());
}


void LoggerSettings::setFileTime(float time) {
  FileTime.setValue(time);
}


void LoggerSettings::setInitialDelay(float time) {
  InitialDelay.setValue(time);
}


void LoggerSettings::setRandomBlinks(bool random) {
  RandomBlinks.setBoolValue(random);
}


void LoggerSettings::setBlinkTimeout(float time) {
  BlinkTimeout.setValue(time);
}


void LoggerSettings::setSensorsInterval(float time) {
  SensorsInterval.setValue(time);
}


void LoggerSettings::setLightThreshold(float thresh) {
  LightThreshold.setValue(thresh);
}


