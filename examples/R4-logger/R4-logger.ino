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
#include <DiagnosticMenu.h>
#include <TeensyBoard.h>
#include <PowerSave.h>
#include <Logger.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg)
#define NCHANNELS      16       // number of channels (even, from 2 to 16)
#define SAMPLING_RATE  24000    // samples per second and channel in Hertz
#define PREGAIN        10.0     // gain factor of preamplifier
#define GAIN           20.0     // dB

#define DEVICEID       -1            // may be used for naming files
#define PATH           "recordings"  // folder where to store the recordings, may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM
#define FILENAME       "bigtankID2-SDATETIME.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 20          // seconds
#define INITIAL_DELAY  10.0          // seconds
#define RANDOM_BLINKS  true          // set to true for blinking the LED randomly

// ----------------------------------------------------------------------------

#define LED_PIN        26    // R4.1
//#define LED_PIN      27    // R4.2

// Device ID pins:
int DIPPins[] = { 34, 35, 36, 37, -1 };


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R4-logger v3.0"

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
Blink blink("status", LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard;

Config config("logger.cfg", &sdcard);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu datetime_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard0_menu(config, sdcard, settings);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R4SetupPCMs);
DiagnosticMenu diagnostic_menu(config, sdcard, &deviceid,
                               &pcm1, &pcm2, &pcm3, &pcm4, &rtclock);
HelpAction help_act(config, "Help");

Logger files(aidata, sdcard, rtclock, deviceid, blink);


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  settings.enable("InitialDelay");
  settings.enable("RandomBlinks");
  aisettings.setRateSelection(ControlPCM186x::SamplingRates,
                              ControlPCM186x::MaxSamplingRates);
  aisettings.enable("Pregain");
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  Wire1.begin();
  rtclock.begin();
  rtclock.check();
  bool R41b = (strcmp(rtclock.chip(), "DS3231/MAX31328") == 0);
  if (R41b)
     deviceid.setPins(DIPPins);
  else
     files.R41powerDownCAN();
  sdcard.begin();
  files.check(config, true);
  rtclock.setFromFile(sdcard);
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  Serial.println();
  deviceid.setID(settings.deviceID());
  if (R41b && deviceid.id() == -1)
    deviceid.read();
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
