#include <DeviceID.h>
#include <SDCard.h>
#include <LoggerSettings.h>


const CAN_MODE LoggerSettings::CANModeEnums[NCANModes] = {
  CAN_NONE, CAN_MASTER, CAN_SLAVE};

const char *LoggerSettings::CANModes[NCANModes] = {
  "none", "master", "slave" };


LoggerSettings::LoggerSettings(Menu &menu, const char *label, int deviceid,
			       const char *path, const char *filename,
			       float filetime, float initialdelay,
			       CAN_MODE canmode) :
  Menu(menu, "Settings"),
  Label(*this, "Label", label),
  ID(*this, "DeviceID", 1, 1, 127, "%d"),
  Path(*this, "Path", path, Admin),
  FileName(*this, "FileName", filename, Admin),
  FileTime(*this, "FileTime", filetime, 1.0, 8640.0, "%.0f", "s"),
  InitialDelay(*this, "InitialDelay", initialdelay, 0.0, 1e8, "%.0f", "s"),
  CANMode(*this, "Synchronization", canmode,
	  CANModeEnums, CANModes, NCANModes, Admin) {
  if (deviceid < 0)
    setDeviceIDDevice();
  ID.setValue(deviceid);
  if (initialdelay < 0)
    InitialDelay.disable();
  CANMode.disable();
}


void LoggerSettings::setLabel(const char *label) {
  Label.setValue(label);
}

								
void LoggerSettings::setDeviceID(int id) {
  ID.setValue(id);
}


void LoggerSettings::setDeviceIDAdmin() {
  ID.setMode(Action::Admin);
}


void LoggerSettings::setDeviceIDDevice() {
  ID.setMinimum(-1);
  ID.setSpecial(-1, "device");
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


void LoggerSettings::setCANMode(CAN_MODE canmode) {
  CANMode.setEnumValue(canmode);
}

