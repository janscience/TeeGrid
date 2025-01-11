#include <Configurator.h>
#include <HardwareActions.h>


ESensorsAction::ESensorsAction(const char *name, ESensors &sensors) :
  ESensorsAction(*Configurator::MainConfig->Config, name, sensors) {
}


ESensorsAction::ESensorsAction(Configurable &menu, const char *name,
			       ESensors &sensors) :
  Action(menu, name, StreamInput),
  Sensors(sensors) {
}


void ESensorSensorsAction::configure(Stream &stream, unsigned long timeout,
				     bool echo, bool detailed) {
  Sensors.report(stream);
}


void ESensorDevicesAction::configure(Stream &stream, unsigned long timeout,
				     bool echo, bool detailed) {
  Sensors.reportDevices(stream);
}


void ESensorRequestAction::configure(Stream &stream, unsigned long timeout,
				     bool echo, bool detailed) {
  Sensors.request();
  stream.println("Requested new sensor readings.");
  stream.printf("Sensor values are available after %dms.\n\n",
		Sensors.delayTime());
}


void ESensorValuesAction::configure(Stream &stream, unsigned long timeout,
				    bool echo, bool detailed) {
  if (detailed)
    Sensors.get();
  else
    Sensors.read();
  Sensors.print(false, false, stream);
}
