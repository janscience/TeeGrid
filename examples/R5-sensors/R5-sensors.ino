#include <TeeGridBanner.h>
#include <Wire.h>
#include <SDCard.h>
#include <I2CEEPROMStorage.h>
#include <RTClockDS1307.h>
#include <Blink.h>
#include <MicroConfig.h>
#include <LoggerSettings.h>
#include <BlinkSettings.h>
#include <Timing.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <DiagnosticMenu.h>
#include <BlinkMenu.h>
#include <TeensyBoard.h>
#include <ESensors.h>
#include <VoltageADC.h>
#include <TemperatureDS3231.h>
#include <TemperatureSTS4x.h>
#include <LightBH1750.h>
#include <DigitalIOPCA9536.h>
#include <ESensorsMenu.h>


// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg or EEPROM)
#define LABEL            "iriri01-sensor01"       // may be used for naming files
#define DEVICEID         1                      // may be used for naming files
#define PATH             "LABEL-devID2-SDATETIMEM"  // folder where to store the recordings, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM
#define FILENAME         "LABEL-devID2-SDATETIME"   // ".wav" is appended, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define BLINK_TIMEOUT    0         // time after which internal LEDs are switched off in seconds
#define SENSORS_INTERVAL 10.0      // interval between sensors readings in seconds

// ----------------------------------------------------------------------------

#define TLV_SHDNZ_PIN    3

#define SYNC_LED_PIN     11
#define ERROR_LED_PIN    12

#define STS4x_ADDR  STS4x_ADDR2   // I2C address of STS4x temperature sensor


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R5-sensor v1.0"

RTClockDS1307 rtclock;
Blink blink("Status", LED_BUILTIN);
Blink errorblink("Error", ERROR_LED_PIN, true);
Blink syncblink("Synchronization", SYNC_LED_PIN, true);
unsigned long blinktimeout;
SDCard sdcard;
I2CEEPROMStorage storage(0x50, I2C_DEVICESIZE_24LC128);

ESensors sensors;
VoltageADC vbat(&sensors, A0, 2*3.3);
DigitalIOPCA9536 gpio;
TemperatureDS3231 temprtc(&sensors);
TemperatureSTS4x tempsts(&sensors);
LightBH1750 light1(&sensors);
LightBH1750 light2(&sensors);

Config config("logger.cfg", &sdcard);
LoggerSettings settings(config, LABEL, DEVICEID, PATH, FILENAME);
Timing timing(config, 10, "", "", SENSORS_INTERVAL);
BlinkSettings blinksettings(config, false, BLINK_TIMEOUT);

RTClockMenu datetime_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard, storage);
SDCardMenu sdcard_menu(config, sdcard);
FirmwareMenu firmware_menu(config, sdcard);
ESensorsMenu sensors_menu(config, sensors);
DiagnosticMenu diagnostic_menu(config, storage, &rtclock, &gpio);
BlinkMenu blink_menu(diagnostic_menu, &blink, &errorblink, &syncblink);
Menu ampl_info(diagnostic_menu, "Amplifier board");
HelpAction help_act(config, "Help");


void setupLEDs() {
  Wire2.begin();
  gpio.begin(Wire2);
  if (gpio.available()) {
    blink.setPin(gpio, 0);
    errorblink.setPin(gpio, 1);
    syncblink.setPin(gpio, 3);
  }
  errorblink.switchOff();
  syncblink.switchOff();
  blink.switchOn();
}


void setupMenu() {
  settings.setDeviceIDAdmin();
  settings.disable("FileTime");
  settings.disable("InitialDelay");
  settings.disable("Synchronization");
  timing.disable("InitialDelay");
  timing.enable("SensorsInterval");
  sdcard_menu.CleanRecsAct.setRemove(true);
  blinksettings.disable("RandomBlinks");
  blinksettings.enable("BlinkTimeout");
  blinksettings.disable("SyncTimeout");
}



void setupBoard() {
  Wire.begin();
  rtclock.begin();
  rtclock.check();
  ampl_info.addConstString("Version", "R5.0");
  sdcard.begin();
  storage.begin();
}


void setupSensors() {
  temprtc.begin(Wire);
  temprtc.setName("logger-temperature");
  temprtc.setSymbol("Ti");
  vbat.setName("battery-voltage");
  vbat.setSymbol("Vbat");
  vbat.setAveraging(32);
  gpio.setMode(2, INPUT);
  tempsts.begin(Wire2, STS4x_ADDR);
  tempsts.setPrecision(STS4x_HIGH);
  tempsts.setSymbol("Tw");
  light1.begin(Wire2, BH1750_TO_GROUND);
  light1.setQuality(BH1750_QUALITY_HIGH2);
  light1.setName("illuminance1");
  light1.setSymbol("I1");
  light2.begin(Wire2, BH1750_TO_VCC);
  light2.setQuality(BH1750_QUALITY_HIGH2);
  light2.setName("illuminance2");
  light2.setSymbol("I2");
  sensors.setPrintTime(ESensors::NO_TIME);
  sensors.start();
}


// -----------------------------------------------------------------------------

void setup() {
  setupLEDs();
  setupMenu();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  setupBoard();
  setupSensors();
  config.setRoot();
  config.setIdentifier();
  // get configuration from EEPROM:
  config.get(storage);
  Serial.println();
  // check SD card:
  //check(config);
  // get configuration from file:
  config.load();
  // menu:
  if (Serial)
    config.execute();
  config.report();
  Serial.println();
  sensors.setInterval(timing.sensorsInterval());
  sensors.setPrintTime(ESensors::ISO_TIME);
  sensors.reportDevices();
  sensors.report();
  sensors.start();
  sensors.read();
  sensors.start();
  sensors.read();
  setTeensySpeed(24);
  Serial.printf("Set CPU speed to %dMHz\n\n", teensySpeed());
  settings.preparePaths();
  blinktimeout = (unsigned long)(1000*blinksettings.blinkTimeout());
  time_t t = now();
  String filename = settings.fileName();
  filename = rtclock.makeStr(filename, t, true);
  int i = filename.lastIndexOf('.');
  if (i >= 0)
    filename.remove(i);
  filename += "-sensors";
  String path_name = settings.path();
  path_name = rtclock.makeStr(path_name, t, true);
  if (sdcard.dataDir(path_name.c_str(), true))
    Serial.printf("Save sensor data in folder \"%s\" on %sSD card.\n\n",
		  sdcard.workingDir(), sdcard.name());
  if (blinktimeout > 0)
    blinktimeout += millis();
  blink.setTiming(5000);
  blink.setSingle();
  blink.blinkSingle(0, 2000);
  syncblink.setTiming(5000);
  syncblink.setSingle();
  syncblink.blinkSingle(0, 2000);
  diagnostic_menu.updateCPUSpeed();
  String fname = filename;
  fname.replace("-sensors", "-metadata.yml");
  FsFile file = sdcard.openWrite(fname.c_str());
  config.write(file, config.FileOutput | config.Report);
  file.close();
  Serial.print("Wrote metadata    to ");
  Serial.println(fname);
  sensors.openCSV(sdcard, filename.c_str());
  Serial.print("Write sensor data to ");
  Serial.println(filename);
}


void loop() {
  if (sensors.update(blink.isOn() || syncblink.isOn())) {
    if (sensors.pendingCSV())
      sensors.writeCSV();
    sensors.print(true, true);
  }
  if ((blinktimeout > 0) && (millis() > blinktimeout)) {
    blink.clearPins();
    //syncblink.clearPins();
  }
  blink.update();
  syncblink.update();
}
