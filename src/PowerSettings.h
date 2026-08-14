/*
  PowerSettings - settings for power thresholds.
  Created by Jan Benda, August 14th, 2026.
*/

#ifndef PowerSettings_h
#define PowerSettings_h


#include <MicroConfig.h>

class DeviceID;


class PowerSettings : public Menu {

public:

  PowerSettings(Menu &menu, float startvoltage=0.0, float stopvoltage=0.0);

  /* Minimum battery voltage required to start logging data. */
  float startVoltage() const { return StartVoltage.value(); };

  /* Set minimum battery voltage required to start logging data. */
  void setStartVoltage(float startvoltage);

  /* Minimum battery voltage required to start a new recording file. */
  float stopVoltage() const { return StopVoltage.value(); };

  /* Set minimum battery voltage required to start a new recording file. */
  void setStopVoltage(float stopvoltage);


protected:

  NumberParameter<float> StartVoltage;
  NumberParameter<float> StopVoltage;
  
};

#endif
