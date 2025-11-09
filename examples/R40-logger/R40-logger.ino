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
#include <Logger.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)
#define NCHANNELS     8        // number of channels (2, 4, 6, 8)
#define SAMPLING_RATE 96000    // samples per second and channel in Hertz
#define PREGAIN       10.0     // gain factor of preamplifier (1 or 10).
#define GAIN          20.0     // dB

#define LABEL         "logger"              // may be used for naming files
#define DEVICEID      1                     // may be used for naming files
#define PATH          "LABELID2-SDATETIMEM" // folder where to store the recordings
#define FILENAME      "LABELID2-SDATETIME"  // ".wav" is appended, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 10*60   // seconds
#define INITIAL_DELAY  10      // seconds
#define RANDOM_BLINKS  false   // set to true for blinking the LED randomly
#define BLINK_TIMEOUT    0     // time after which internal LEDs are switched off in seconds

// ----------------------------------------------------------------------------

#define LED_PIN       31

#define SOFTWARE      "TeeGrid R40-logger v2.4"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 2
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
Device *pcms[NPCMS] = {&pcm1, &pcm2};

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink("status", LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard;

Config config("logger.cfg", &sdcard);
Settings settings(config, LABEL, DEVICEID, PATH, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS, 0, 0, 0, BLINK_TIMEOUT);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard0_menu(config, sdcard);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R40SetupPCMs);
DiagnosticMenu diagnostic_menu(config, sdcard, 0, &pcm1, &pcm2, &rtclock);
Menu ampl_info(diagnostic_menu, "Amplifier board");
HelpAction help_act(config, "Help");

Logger files(aidata, sdcard, rtclock, blink);


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  settings.disable("Path", settings.StreamInput);
  settings.disable("FileName", settings.StreamInput);
  settings.enable("InitialDelay");
  settings.enable("RandomBlinks");
  settings.enable("BlinkTimeout");
  aisettings.enable("Pregain");
  aisettings.setRateSelection(ControlPCM186x::SamplingRates,
                              ControlPCM186x::MaxSamplingRates);
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  rtclock.begin();
  rtclock.check();
  ampl_info.addConstString("Version", "R4.0");
  sdcard.begin();
  files.check(config);
  rtclock.setFromFile(sdcard);
  config.load();
  if (Serial)
    config.execute();
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
  settings.preparePaths(deviceid);
  files.setup(settings.path(), settings.fileName(),
              SOFTWARE, settings.randomBlinks(),
	      settings.blinkTimeout());
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  files.start(settings.fileTime(), config);
}


void loop() {
  files.update();
}
