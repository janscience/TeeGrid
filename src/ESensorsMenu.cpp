#include <ESensorsMenu.h>


ESensorsAction::ESensorsAction(Menu &menu, const char *name,
			       ESensors &sensors) :
  Action(menu, name, StreamInput),
  Sensors(sensors) {
}


void ESensorSensorsAction::execute(Stream &stream, unsigned long timeout,
				   bool echo, bool detailed) {
  Sensors.report(stream);
}


void ESensorDevicesAction::execute(Stream &stream, unsigned long timeout,
				   bool echo, bool detailed) {
  Sensors.reportDevices(stream);
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

