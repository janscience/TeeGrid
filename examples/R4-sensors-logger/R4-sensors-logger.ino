#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SDCard.h>
#include <RTClockDS1307.h>
#include <DeviceID.h>
#include <Blink.h>
#include <MicroConfig.h>
#include <Settings.h>
#include <InputTDMSettings.h>
#include <SetupPCM.h>
#include <InputMenu.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <ESensorsMenu.h>
#include <DiagnosticMenu.h>
#include <TeensyBoard.h>
#include <PowerSave.h>
#include <SensorsLogger.h>
#include <ESensors.h>
#include <TemperatureDS18x20.h>
#include <TemperatureDS3231.h>
#include <TemperatureSTS4x.h>
#include <LightBH1750.h>
#include <DigitalIOPCA9536.h>


// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg)
#define NCHANNELS           16    // number of channels (even, from 2 to 16)
#define SAMPLING_RATE    48000    // samples per second and channel in Hertz
#define PREGAIN            1.0    // gain factor of preamplifier
#define GAIN               0.0    // dB

#define DEVICEID         -1       // may be used for naming pathes and files
#define PATH             "flonaID2-SDATETIMEM-NUM1"   // folder where to store the recordings, may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM
#define FILENAME         "loggerID2-SDATETIME.wav"   // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM, ANUM, COUNT
#define FILE_SAVE_TIME   5*60     // seconds
#define INITIAL_DELAY    60.0     // seconds
#define SENSORS_INTERVAL 30.0     // interval between sensors readings in seconds
#define RANDOM_BLINKS    true     // set to true for blinking the LED randomly
#define BLINK_TIMEOUT    2*60     // time after which internal LEDs are switched off in seconds


// ----------------------------------------------------------------------------

#define LED_PIN          26       // R4.1

int DIPPins[] = { 34, 35, 36, 37, -1 }; // Device ID pins:

#define TEMP_PIN_R41     35       // pin for DATA line of DS18x20 themperature sensor for R4.1
#define TEMP_PIN_R41b     9       // pin for DATA line of DS18x20 themperature sensor for R4.1b
#define STS4x_ADDR  STS4x_ADDR2   // I2C address of STS4x temperature sensor


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R4-sensors-logger v3.1"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 4
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
ControlPCM186x pcm3(Wire1, PCM186x_I2C_ADDR1, InputTDM::TDM2);
ControlPCM186x pcm4(Wire1, PCM186x_I2C_ADDR2, InputTDM::TDM2);
Device *pcms[NPCMS] = {&pcm1, &pcm2, &pcm3, &pcm4};

RTClockDS1307 rtclock;
DeviceID deviceid(DEVICEID);
DigitalIOPCA9536 gpio;
Blink blink("status", LED_BUILTIN);
Blink errorblink("error");
Blink syncblink("sync", LED_PIN, true);
SDCard sdcard;

ESensors sensors;
TemperatureDS3231 temprtc(&sensors);
TemperatureDS18x20 temp(&sensors);
TemperatureSTS4x tempsts(&sensors);
LightBH1750 light1(&sensors);
LightBH1750 light2(&sensors);

Config config("logger.cfg", &sdcard);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS, 0, 0,
                  SENSORS_INTERVAL, BLINK_TIMEOUT);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard, settings);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R4SetupPCMs);
ESensorsMenu sensors_menu(config, sensors);
DiagnosticMenu diagnostic_menu(config, sdcard, &deviceid, &pcm1, &pcm2, &pcm3, &pcm4, &rtclock, &gpio);
InfoAction ampl_info(diagnostic_menu, "Amplifier board");
HelpAction help_act(config, "Help");

SensorsLogger files(aidata, sensors, sdcard, rtclock, deviceid,
                    blink, errorblink, syncblink);


void setupLEDs() {
  Wire2.begin();
  gpio.begin(Wire2);
  if (gpio.available()) {
    blink.setPin(gpio, 0);
    errorblink.setPin(gpio, 1);
    syncblink.setPin(gpio, 3);
    errorblink.switchOff();
    syncblink.switchOff();
  }
  blink.switchOn();
}


void setupSensors(int temp_pin) {
  temprtc.begin(Wire);
  temprtc.setName("logger-temperature");
  temprtc.setSymbol("Ti");
  temp.begin(temp_pin);
  temp.setName("water-temperature");
  temp.setSymbol("Tw");
  gpio.setMode(2, INPUT);
  light1.begin(Wire2, BH1750_TO_GROUND);
  //light1.setAutoRanging();
  light1.setQuality(BH1750_QUALITY_HIGH2);
  light1.setName("illuminance1");
  light1.setSymbol("I1");
  light2.begin(Wire2, BH1750_TO_VCC);
  //light2.setAutoRanging();
  light2.setQuality(BH1750_QUALITY_HIGH2);
  light2.setName("illuminance2");
  light2.setSymbol("I2");
  tempsts.begin(Wire2, STS4x_ADDR);
  tempsts.setPrecision(STS4x_HIGH);
  files.setupSensors();
}


// -----------------------------------------------------------------------------

void setup() {
  setupLEDs();
  settings.enable("InitialDelay");
  if (syncblink.nPins() > 1) {
    settings.disable("RandomBlinks");
    settings.setRandomBlinks(true);
  }
  else
    settings.enable("RandomBlinks");
  settings.enable("SensorsInterval");
  settings.enable("BlinkTimeout");
  aisettings.setRateSelection(ControlPCM186x::SamplingRates,
                              ControlPCM186x::MaxSamplingRates);
  aisettings.enable("Pregain");
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.begin();
  rtclock.check();
  bool R41b = (strcmp(rtclock.chip(), "DS3231/MAX31328") == 0);
  if (R41b) {
     deviceid.setPins(DIPPins);
     ampl_info.add("Version", "R4.1b");
  }
  else {
     files.R41powerDownCAN();
     ampl_info.add("Version", "R4.1");
  }
  setupSensors(R41b ? TEMP_PIN_R41b : TEMP_PIN_R41);
  sdcard.begin();
  files.check(config);
  rtclock.setFromFile(sdcard);
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  for (size_t k=0; ; k++) {
    Device *dev = diagnostic_menu.DevicesAct.device(k);
    if (dev == 0)
      break;
    if (dev->available())
      ampl_info.add(dev->deviceType(), dev->chip());
  }
  for (uint8_t k=0; k<sensors.size(); k++) {
    ESensor &sensor = sensors[k];
    if (sensor.available())
      ampl_info.add(sensor.name(), sensor.chip());
  }
  Serial.println();
  files.startSensors(settings.sensorsInterval());
  deviceid.setID(settings.deviceID());
  if (R41b && deviceid.id() == -1)
    deviceid.read();
  files.setCPUSpeed(aisettings.rate());
  R4SetupPCMs(aidata, aisettings, pcms, NPCMS);
  blink.switchOff();
  aidata.begin();
  if (!aidata.check(aisettings.nchannels())) {
    Serial.println("Fix ADC settings and check your hardware.");
    files.halt(2);
  }
  aidata.start();
  aidata.report();
  files.report();
  files.setup(settings.path(), settings.fileName(),
              SOFTWARE, settings.randomBlinks(),
	            settings.blinkTimeout());
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  files.start(settings.fileTime());
}


void loop() {
  files.update();
}
