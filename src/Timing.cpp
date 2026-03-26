#include <Timing.h>


Timing::Timing(Menu &menu, float initialdelay, const char *starttime,
	       const char *stoptime, float sensorsinterval) :
  Menu(menu, "Timing"),
  InitialDelay(*this, "InitialDelay", initialdelay, 0.0, 1e8, "%.0f", "s"),
  StartTime(*this, "StartTime", ""),
  StopTime(*this, "StopTime", ""),
  SensorsInterval(*this, "SensorsInterval", sensorsinterval, 1.0, 1e8, "%.0f", "s") {
  if (initialdelay < 0)
    InitialDelay.disable();
  StartTime.disable();
  StopTime.disable();
  SensorsInterval.disable();
}


void Timing::setInitialDelay(float time) {
  InitialDelay.setValue(time);
}


void Timing::setStartTime(const char *starttime) {
  StartTime.setValue(starttime);
}


void Timing::setStopTime(const char *stoptime) {
  StopTime.setValue(stoptime);
}


void Timing::setSensorsInterval(float time) {
  SensorsInterval.setValue(time);
}

