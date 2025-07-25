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
#include <DiagnosticMenu.h>
#include <TeensyBoard.h>
#include <PowerSave.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)
#define NCHANNELS     8        // number of channels (2, 4, 6, 8)
#define SAMPLING_RATE 96000    // samples per second and channel in Hertz
#define PREGAIN       10.0     // gain factor of preamplifier (1 or 10).
#define GAIN          20.0     // dB

#define PATH          "recordings"   // folder where to store the recordings
#define DEVICEID      1              // may be used for naming files
#define FILENAME      "micarrayID-SDATETIME.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 5*60   // seconds
#define INITIAL_DELAY  10.0  // seconds
#define RANDOM_BLINKS  false  // set to true for blinking the LED randomly

// ----------------------------------------------------------------------------

#define LED_PIN       31

#define SOFTWARE      "TeeGrid R40-logger v2.3"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 2
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
Device *pcms[NPCMS] = {&pcm1, &pcm2};

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard;

Config config("logger.cfg", &sdcard);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard0_menu(config, sdcard, settings);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R40SetupPCMs);
DiagnosticMenu diagnostic_menu(config, sdcard, &pcm1, &pcm2, &rtclock);
HelpAction help_act(config, "Help");

Logger files(aidata, sdcard, rtclock, deviceid, blink);


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
  files.check(config);
  rtclock.setFromFile(sdcard);
  settings.enable("InitialDelay");
  settings.enable("RandomBlinks");
  aisettings.enable("Pregain");
  aisettings.setRateSelection(ControlPCM186x::SamplingRates,
                              ControlPCM186x::MaxSamplingRates);
  config.load();
  if (Serial)
    config.execute(Serial);
  config.report();
  Serial.println();
  deviceid.setID(settings.deviceID());
  files.setCPUSpeed(aisettings.rate());
  R40SetupPCMs(aidata, aisettings, pcms, NPCMS);
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
