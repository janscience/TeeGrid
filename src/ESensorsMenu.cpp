#include <ESensorsMenu.h>


ESensorsAction::ESensorsAction(Menu &menu, const char *name,
			       ESensors &sensors, unsigned int roles) :
  Action(menu, name, roles),
  Sensors(sensors) {
}


void ESensorDevicesAction::execute(Stream &stream) {
  Sensors.reportDevices(stream);
}


ESensorSensorsAction::ESensorSensorsAction(Menu &menu, const char *name,
					   ESensors &sensors) :
  ESensorsAction(menu, name, sensors, StreamInput | Report) {
}


void ESensorSensorsAction::write(Stream &stream, unsigned int roles,
				 size_t indent, size_t width) const {
  if (disabled(roles))
    return;
  if (strlen(name()) > 0) {
    stream.printf("%*s%s:\n", indent, "", name());
    indent += indentation();
  }
  width = 0;
  for (size_t k=0; k<Sensors.size(); k++) {
    if (Sensors[k].available() && (strlen(Sensors[k].name()) > width))
      width = strlen(Sensors[k].name());
  }
  for (size_t k=0; k<Sensors.size(); k++) {
    if (Sensors[k].available()) {
      size_t kw = width >= strlen(Sensors[k].name()) ? width - strlen(Sensors[k].name()) : 0;
      stream.printf("%*s%s:%*s %s (%s)\n", indent, "",
		    Sensors[k].name(), kw, "",
		    Sensors[k].chip(), Sensors[k].identifier());
    }
  }
  Sensors.writeDevices(stream, indent, indentation());
}


void ESensorSensorsAction::execute(Stream &stream) {
  Sensors.report(stream);
}


void ESensorRequestAction::execute(Stream &stream) {
  Sensors.request();
  stream.println("Requested new sensor readings.");
  stream.printf("Sensor values are available after %dms.\n\n",
		Sensors.delayTime());
}


void ESensorValuesAction::execute(Stream &stream) {
  if (gui())
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

