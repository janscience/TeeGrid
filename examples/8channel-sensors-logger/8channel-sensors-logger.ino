#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SDCard.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <TestSignals.h>
#include <MicroConfig.h>
#include <Settings.h>
#include <InputADCSettings.h>
#include <InputMenu.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <DiagnosticMenu.h>
#include <ESensorsMenu.h>
#include <TeensyBoard.h>
#include <PowerSave.h>
#include <SensorsLogger.h>
#include <ESensors.h>
#include <TemperatureDS18x20.h>
#include <SenseBME280.h>
#include <LightTSL2591.h>
#include <DewPoint.h>


// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)

#define SAMPLING_RATE 20000 // samples per second and channel in Hertz
#define BITS             12 // resolution: 10bit 12bit, or 16bit
#define AVERAGING         4 // number of averages per sample: 0, 4, 8, 16, 32
#define CONVERSION    ADC_CONVERSION_SPEED::HIGH_SPEED
#define SAMPLING      ADC_SAMPLING_SPEED::HIGH_SPEED
#define REFERENCE     ADC_REFERENCE::REF_3V3
int8_t channels0 [] =  {A4, A5, A6, A7, -1, A4, A5, A6, A7, A8, A9};      // input pins for ADC0
int8_t channels1 [] =  {A2, A3, A20, A22, -1, A20, A22, A12, A13};  // input pins for ADC1
#define PREGAIN       1

#define TEMP_PIN         25   // pin for DATA of thermometer
#define SENSORS_INTERVAL 10.0 // interval between sensors readings in seconds

#define PATH          "recordings"       // folder where to store the recordings
#define DEVICEID      1                  // may be used for naming files
#define FILENAME      "gridID-SDATETIME" // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 10*60 // seconds
#define INITIAL_DELAY  2.0   // seconds

#define PULSE_FREQUENCY 230 // Hertz
int signalPins[] = {9, 8, 7, 6, 5, 4, 3, 2, -1}; // pins where to put out test signals

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-sensors-logger v2.0"

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_BUILTIN);
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

Config config("teegrid.cfg", &sdcard);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, false, PULSE_FREQUENCY,
		  0.0, SENSORS_INTERVAL);
InputADCSettings aisettings(config, SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE, PREGAIN);
RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard, settings);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings);
ESensorsMenu sensors_menu(config, sensors);
DiagnosticMenu diagnostic_menu(config, sdcard, &aidata, &rtclock);
HelpAction help_act(config, "Help");

SensorsLogger files(aidata, sensors, sdcard, rtclock, deviceid, blink);


void setupSensors() {
  temp.begin(TEMP_PIN);
  temp.setName("water-temperature", "Tw");
  Wire1.begin();
  bme.beginI2C(Wire1, 0x77);
  tempbme.setName("air-temperature", "Ta");
  hum.setPercent();
  pres.setHecto();
  tsl.begin(Wire1);
  tsl.setGain(LightTSL2591::AUTO_GAIN);
  irratio.setPercent();
  files.setupSensors();
}


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
  files.check();
  rtclock.setFromFile(sdcard);
  setupSensors();
  settings.enable("InitialDelay");
  settings.enable("PulseFreq");
  settings.enable("SensorsInterval");
  aisettings.disable("Reference");
  aisettings.enable("Pregain");
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  Serial.println();
  files.startSensors(settings.sensorsInterval());
  tsl.setTemperature(bme.temperature());
  setupTestSignals(signalPins, settings.pulseFrequency());
  aisettings.configure(&aidata);
  blink.switchOff();
  if (!aidata.check()) {
    Serial.println("Fix ADC settings and check your hardware.");
    halt();
  }
  aidata.reset();
  aidata.start();
  aidata.report();
  files.report();
  files.setup(settings.path(), settings.fileName(), SOFTWARE);
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  files.start(settings.fileTime());
}


void loop() {
  if (files.update())
    tsl.setTemperature(bme.temperature());
}
