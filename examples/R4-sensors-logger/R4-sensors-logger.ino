#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SDCard.h>
#include <RTClock.h>
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
#include <R41CAN.h>
#include <ESensors.h>
#include <TemperatureDS18x20.h>
#include <LightTSL2591.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg)
#define NCHANNELS        8       // number of channels (even, from 2 to 16)
#define SAMPLING_RATE    48000    // samples per second and channel in Hertz
#define PREGAIN          1.0     // gain factor of preamplifier
#define GAIN             0.0      // dB

#define PATH             "recordings"   // folder where to store the recordings
#define DEVICEID         1              // may be used for naming files
#define FILENAME         "gridID-SDATETIME.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM, ANUM
#define FILE_SAVE_TIME   20    // seconds
#define INITIAL_DELAY    10.0    // seconds
#define SENSORS_INTERVAL 10.0    // interval between sensors readings in seconds
#define RANDOM_BLINKS    false    // set to true for blinking the LED randomly


// ----------------------------------------------------------------------------

#define LED_PIN          26    // R4.1
//#define LED_PIN        27    // R4.2

#define TEMP_PIN         35    // pin for DATA line of DS18x20 themperature sensor


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R4-sensors-logger v2.2"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 4
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
ControlPCM186x pcm3(Wire1, PCM186x_I2C_ADDR1, InputTDM::TDM2);
ControlPCM186x pcm4(Wire1, PCM186x_I2C_ADDR2, InputTDM::TDM2);
Device *pcms[NPCMS] = {&pcm1, &pcm2, &pcm3, &pcm4};

R41CAN can;

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard;

ESensors sensors;
TemperatureDS18x20 temp(&sensors);
LightTSL2591 tsl;
IRRatioTSL2591 irratio(&tsl, &sensors);
IlluminanceTSL2591 illum(&tsl, &sensors);

Config config("logger.cfg", &sdcard);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS, 0, 0,
                  SENSORS_INTERVAL);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard, settings);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R4SetupPCMs);
ESensorsMenu sensors_menu(config, sensors);
DiagnosticMenu diagnostic_menu(config, sdcard, &pcm1, &pcm2, &pcm3, &pcm4, &rtclock);
HelpAction help_act(config, "Help");

SensorsLogger files(aidata, sensors, sdcard, rtclock, deviceid, blink);


void setupSensors() {
  temp.begin(TEMP_PIN);
  temp.setName("water-temperature");
  temp.setSymbol("Tw");
  tsl.begin(Wire);
  tsl.setGain(LightTSL2591::AUTO_GAIN);
  irratio.setPercent();
  files.setupSensors();
}


// -----------------------------------------------------------------------------

void setup() {
  can.powerDown();
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  Wire1.begin();
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
  files.check();
  rtclock.setFromFile(sdcard);
  setupSensors();
  settings.enable("InitialDelay");
  settings.enable("RandomBlinks");
  settings.enable("SensorsInterval");
  aisettings.setRateSelection(ControlPCM186x::SamplingRates,
                              ControlPCM186x::MaxSamplingRates);
  aisettings.enable("Pregain");
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  Serial.println();
  files.startSensors(settings.sensorsInterval());
  deviceid.setID(settings.deviceID());
  files.setCPUSpeed(aisettings.rate());
  R4SetupPCMs(aidata, aisettings, pcms, NPCMS);
  blink.switchOff();
  aidata.begin();
  if (!aidata.check(aisettings.nchannels())) {
    Serial.println("Fix ADC settings and check your hardware.");
    halt();
  }
  aidata.start();
  aidata.report();
  files.report();
  files.setup(settings.path(), settings.fileName(),
              SOFTWARE, settings.randomBlinks());
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  files.start(settings.fileTime());
}


void loop() {
  files.update();
}
