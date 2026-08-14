#include <PowerSettings.h>


PowerSettings::PowerSettings(Menu &menu,
			     float startvoltage, float stopvoltage) :
  Menu(menu, "Power supply"),
  StartVoltage(*this, "StartVoltage", startvoltage, 0.0, 10.0, "%.2f", "V", "V", Admin),
  StopVoltage(*this, "StopVoltage", stopvoltage, 0.0, 10.0, "%.2f", "V", "V", Admin) {
}


void PowerSettings::setStartVoltage(float startvoltage) {
  StartVoltage.setValue(startvoltage);
}


void PowerSettings::setStopVoltage(float stopvoltage) {
  StopVoltage.setValue(stopvoltage);
}
