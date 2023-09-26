#define SENSORS

#include <Arduino.h>
#include <RTClock.h>
#include <Blink.h>
#include <R41CAN.h>
#ifdef SENSORS
#include <SDWriter.h>
#include <ESensors.h>
#include <TemperatureDS18x20.h>
#include <SenseBME280.h>
#include <LightTSL2591.h>
#include <DewPoint.h>
#endif

#define GRID              "grid1"    // unique name of the grid
#define SAMPLING_RATE     96000      // sampling rate in Hz
#define GAIN              20.0       // gain in dB
#define FILE_TIME         20.0       // seconds
#define INITIAL_DELAY     20.0       // seconds

#define PATH              "recordings"   // folder where to store the sensor recordings
#define TEMP_PIN          10         // pin for DATA line of DS18x20 themperature sensor
#define SENSORS_INTERVAL  10.0       // interval between sensors readings in seconds

R41CAN can;
RTClock rtclock;
Blink blink(LED_BUILTIN);

elapsedMillis Time;

#ifdef SENSORS
SDCard sdcard;
ESensors sensors;
TemperatureDS18x20 temp(&sensors);
SenseBME280 bme;
TemperatureBME280 tempbme(&bme, &sensors);
HumidityBME280 hum(&bme, &sensors);
DewPoint dp(&hum, &tempbme, &sensors);
PressureBME280 pres(&bme, &sensors);
LightTSL2591 tsl;
IRRatioTSL2591 irratio(&tsl, &sensors);
IlluminanceTSL2591 illum(&tsl, &sensors);


void setupSensors() {
  temp.begin(TEMP_PIN);
  Wire.begin();
  bme.beginI2C(Wire, 0x77);
  hum.setPercent();
  pres.setHecto();
  tsl.begin(Wire);
  tsl.setGain(LightTSL2591::AUTO_GAIN);
  irratio.setPercent();
  sensors.setInterval(SENSORS_INTERVAL);
  sensors.setPrintTime(ESensors::ISO_TIME);
  sensors.report();
  char date_time[24];
  rtclock.dateTime(date_time, 0, true);
  char file_name[64];
  sprintf(file_name, "%s-%s-sensors.csv", GRID, date_time);
  sensors.openCSV(sdcard, file_name);
  sensors.start();
  sensors.read();
  tsl.setTemperature(bme.temperature());
  sensors.start();
  sensors.read();
}
#endif


void setup() {
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  char dts[] = "2024-09-16T23:20:42";
  rtclock.set(dts);
#ifdef SENSORS
  sdcard.begin();
  setupSensors();
#endif
  can.begin();
  can.detectDevices();
  // stop if no device have been found
  //can.setupControllerMBs();
  delay(100);
  can.sendGrid(GRID);
  can.sendTime();
  can.sendSamplingRate(SAMPLING_RATE);
  can.sendGain(GAIN);
  can.sendFileTime(FILE_TIME);
  blink.switchOff();
  if (INITIAL_DELAY >= 2.0) {
    delay(1000);
    blink.setDouble();
    blink.delay(uint32_t(1000.0*INITIAL_DELAY)-1000);
  }
  else
    delay(uint32_t(1000.0*INITIAL_DELAY));
  Time = 0;
  can.sendStart();
  blink.setSingle();
}


void loop() {
  can.events();
  blink.update();
#ifdef SENSORS
  if (sensors.update()) {
    tsl.setTemperature(bme.temperature());
    sensors.print();
    Serial.println();
  }
  if (sensors.pendingCSV())
    sensors.writeCSV();
#endif
  if (0.001*Time > FILE_TIME - 0.05) {
    can.receiveEndFile();
    can.sendStart();
    Time = 0;
    blink.setSingle();
  }
}
