#include <ESensorsMenu.h>


ESensorsAction::ESensorsAction(Menu &menu, const char *name,
			       ESensors &sensors, unsigned int roles) :
  Action(menu, name, roles),
  Sensors(sensors) {
}


void ESensorDevicesAction::execute(Stream &stream, unsigned long timeout,
				   bool echo, bool detailed) {
  Sensors.reportDevices(stream);
}


ESensorSensorsAction::ESensorSensorsAction(Menu &menu, const char *name,
					   ESensors &sensors) :
  ESensorsAction(menu, name, sensors, StreamInput | Report) {
}


void ESensorSensorsAction::report(Stream &stream, unsigned int roles,
				  size_t indent, size_t w, bool descend) const {
  if (disabled(roles))
    return;
  if (descend) {
    if (strlen(name()) > 0) {
      stream.printf("%*s%s:\n", indent, "", name());
      indent += indentation();
    }
    w = 0;
    for (size_t k=0; k<Sensors.size(); k++) {
      if (Sensors[k].available() && (strlen(Sensors[k].name()) > w))
	w = strlen(Sensors[k].name());
    }
    for (size_t k=0; k<Sensors.size(); k++) {
      if (Sensors[k].available()) {
	size_t kw = w >= strlen(Sensors[k].name()) ? w - strlen(Sensors[k].name()) : 0;
	stream.printf("%*s%s:%*s %s (%s)\n", indent, "",
		      Sensors[k].name(), kw, "",
		      Sensors[k].chip(), Sensors[k].identifier());
      }
    }
  }
  else if (strlen(name()) > 0)
    Action::report(stream, roles, indent, w, descend);
}


void ESensorSensorsAction::execute(Stream &stream, unsigned long timeout,
				   bool echo, bool detailed) {
  Sensors.report(stream);
}


void ESensorRequestAction::execute(Stream &stream, unsigned long timeout,
				   bool echo, bool detailed) {
  Sensors.request();
  stream.println("Requested new sensor readings.");
  stream.printf("Sensor values are available after %dms.\n\n",
		Sensors.delayTime());
}


void ESensorValuesAction::execute(Stream &stream, unsigned long timeout,
				  bool echo, bool detailed) {
  if (detailed)
    Sensors.get();
  else
    Sensors.read();
  Sensors.print(false, false, stream);
}


ESensorsMenu::ESensorsMenu(Menu &menu, ESensors &sensors) :
  Menu(menu, "Sensors", Action::StreamInput),
  DevicesAct(*this, "Sensor devices", sensors),
  SensorsAct(*this, "Environmental sensors", sensors),
  ValuesAct(*this, "Sensor readings", sensors),
  RequestAct(*this, "Sensor request", sensors) {
}

