/*
  ESensorsMenu - Actions and menu for environmental sensors.
  Created by Jan Benda, January 5th, 2025.
*/

#ifndef ESensorsMenu_h
#define ESensorsMenu_h


#include <MicroConfig.h>
#include <ESensors.h>


class ESensorsAction : public Action {

 public:

  /* Initialize and add to menu. */
  ESensorsAction(Menu &menu, const char *name, ESensors &sensors);

protected:

  ESensors &Sensors;
};


class ESensorSensorsAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print infos about available environmental sensors. */
  virtual void execute(Stream &stream=Serial, unsigned long timeout=0,
		       bool echo=true, bool detailed=false);
};


class ESensorDevicesAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print infos about available environmental sensor devices. */
  virtual void execute(Stream &stream=Serial, unsigned long timeout=0,
		       bool echo=true, bool detailed=false);
};


class ESensorRequestAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Request sensor values. */
  virtual void execute(Stream &stream=Serial, unsigned long timeout=0,
		       bool echo=true, bool detailed=false);
};


class ESensorValuesAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print sensor values. If detailed, just get previously requested values.
     Otherwise request and read them. */
  virtual void execute(Stream &stream=Serial, unsigned long timeout=0,
		       bool echo=true, bool detailed=false);
};


class ESensorsMenu : public Menu {

public:

  ESensorsMenu(Menu &menu, ESensors &sensors);

protected:

  ESensorDevicesAction DevicesAct;
  ESensorSensorsAction SensorsAct;
  ESensorValuesAction ValuesAct;
  ESensorRequestAction RequestAct;
};


#endif
