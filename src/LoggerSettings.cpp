#include <DeviceID.h>
#include <SDCard.h>
#include <LoggerSettings.h>


LoggerSettings::LoggerSettings(Menu &menu, const char *label, int deviceid,
			       const char *path, const char *filename,
			       float filetime, float initialdelay,
			       float sensorsinterval) :
  Menu(menu, "Settings"),
  Label(*this, "Label", label),
  ID(*this, "DeviceID", deviceid, -1, 127, "%d"),
  Path(*this, "Path", path),
  FileName(*this, "FileName", filename),
  FileTime(*this, "FileTime", filetime, 1.0, 8640.0, "%.0f", "s"),
  InitialDelay(*this, "InitialDelay", initialdelay, 0.0, 1e8, "%.0f", "s"),
  SensorsInterval(*this, "SensorsInterval", sensorsinterval, 1.0, 1e8, "%.0f", "s")
 {
  ID.setSpecial(-1, "device");
  SensorsInterval.disable();
}


void LoggerSettings::setLabel(const char *label) {
  Label.setValue(label);
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


void LoggerSettings::preparePaths() {
  // path:
  String s = SDCard::preparePath(Path.value(), ID.value(), Label.value());
  Path.setValue(s.c_str());
  // filename:
  s = SDCard::preparePath(FileName.value(), ID.value(), Label.value());
  FileName.setValue(s.c_str());
}


void LoggerSettings::preparePaths(const DeviceID &deviceid) {
  int id = deviceid.id();
  if (id == 0 && deviceid.maxid() > 0)
    id = deviceid.maxid();
  // path:
  String s = SDCard::preparePath(Path.value(), id, Label.value());
  Path.setValue(s.c_str());
  // filename:
  s = SDCard::preparePath(FileName.value(), id, Label.value());
  FileName.setValue(s.c_str());
}


void LoggerSettings::setFileTime(float time) {
  FileTime.setValue(time);
}


void LoggerSettings::setInitialDelay(float time) {
  InitialDelay.setValue(time);
}


void LoggerSettings::setSensorsInterval(float time) {
  SensorsInterval.setValue(time);
}

