/*
  HardwareActions - Actions for diagnosing external hardware.
  Created by Jan Benda, January 5th, 2025.
*/

#ifndef HardwareActions_h
#define HardwareActions_h


#include <Action.h>
#include <Configurable.h>
#include <ESensors.h>


class ESensorsAction : public Action {

 public:

  /* Initialize and add to default menu. */
  ESensorsAction(const char *name, ESensors &sensors);

  /* Initialize and add to configuration menu. */
  ESensorsAction(Configurable &menu, const char *name, ESensors &sensors);

protected:

  ESensors &Sensors;
};


class ESensorSensorsAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print infos about available environmental sensors. */
  virtual void configure(Stream &stream=Serial, unsigned long timeout=0,
			 bool echo=true, bool detailed=false);
};


class ESensorDevicesAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print infos about available environmental sensor devices. */
  virtual void configure(Stream &stream=Serial, unsigned long timeout=0,
			 bool echo=true, bool detailed=false);
};


class ESensorRequestAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Request sensor values. */
  virtual void configure(Stream &stream=Serial, unsigned long timeout=0,
			 bool echo=true, bool detailed=false);
};


class ESensorValuesAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print sensor values. */
  virtual void configure(Stream &stream=Serial, unsigned long timeout=0,
			 bool echo=true, bool detailed=false);
};


#endif
