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
  ESensorsAction(Menu &menu, const char *name, ESensors &sensors,
		 unsigned int roles=StreamInput);

protected:

  ESensors &Sensors;
};


class ESensorDevicesAction : public ESensorsAction {

 public:
  
  using ESensorsAction::ESensorsAction;

  /* Print infos about available environmental sensor devices. */
  virtual void execute(Stream &stream=Serial);
};


class ESensorSensorsAction : public ESensorsAction {

 public:

  /* Initialize and add to menu. */
  ESensorSensorsAction(Menu &menu, const char *name, ESensors &sensors);

  /* Print infos about available environmental sensors. */
  virtual void write(Stream &stream=Serial, unsigned int roles=AllRoles,
		     size_t indent=0, size_t width=0, bool descend=true) const;

  /* Print infos about available environmental sensors. */
  virtual void execute(Stream &stream=Serial);
};


class ESensorRequestAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Request sensor values. */
  virtual void execute(Stream &stream=Serial);
};


class ESensorValuesAction : public ESensorsAction {

 public:

  using ESensorsAction::ESensorsAction;

  /* Print sensor values. If detailed, just get previously requested values.
     Otherwise request and read them. */
  virtual void execute(Stream &stream=Serial);
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
