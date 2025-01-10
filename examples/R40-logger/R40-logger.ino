#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SDCard.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <Configurator.h>
#include <Settings.h>
#include <InputTDMSettings.h>
#include <SetupPCM.h>
#include <ToolMenus.h>
#include <HardwareActions.h>
#include <TeensyBoard.h>
#include <PowerSave.h>
#include <LoggerFileStorage.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)
#define NCHANNELS     8        // number of channels (2, 4, 6, 8)
#define SAMPLING_RATE 48000    // samples per second and channel in Hertz
#define PREGAIN       10.0     // gain factor of preamplifier (1 or 10).
#define GAIN          20.0     // dB

#define PATH          "recordings"   // folder where to store the recordings
#define DEVICEID      1              // may be used for naming files
#define FILENAME      "loggerID-SDATETIME.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 5*60   // seconds
#define INITIAL_DELAY  10.0  // seconds
#define RANDOM_BLINKS  false  // set to true for blinking the LED randomly

// ----------------------------------------------------------------------------

#define LED_PIN       31

#define SOFTWARE      "TeeGrid R40-logger v2.0"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 2
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
ControlPCM186x *pcms[NPCMS] = {&pcm1, &pcm2};
uint32_t SamplingRates[3] = {24000, 48000, 96000};

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard;

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS);
InputTDMSettings aisettings(SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

DateTimeMenu datetime_menu(rtclock);
ConfigurationMenu configuration_menu(sdcard);
SDCardMenu sdcard0_menu(sdcard, settings);
#ifdef FIRMWARE_UPDATE
FirmwareMenu firmware_menu(sdcard0);
#endif
DiagnosticMenu diagnostic_menu("Diagnostics", sdcard, &pcm1, &pcm2, &rtclock);
HelpAction help_act(config, "Help");

LoggerFileStorage files(aidata, sdcard, rtclock, deviceid, blink);


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  Wire.begin();
  rtclock.init();
  rtclock.check();
  sdcard.begin();
  files.check();
  rtclock.setFromFile(sdcard);
  settings.enable("InitialDelay");
  settings.enable("RandomBlinks");
  aisettings.setRateSelection(SamplingRates, 3);
  aisettings.enable("Pregain");
  config.setConfigFile("logger.cfg");
  config.load(sdcard);
  if (Serial)
    config.configure(Serial);
  config.report();
  Serial.println();
  deviceid.setID(settings.deviceID());
  aidata.setSwapLR();
  files.setCPUSpeed(aisettings.rate());
  for (int k=0;k < NPCMS; k++) {
    Serial.printf("Setup PCM186x %d: ", k);
    R40SetupPCM(aidata, *pcms[k], k%2==1, aisettings);
  }
  Serial.println();
  blink.switchOff();
  aidata.begin();
  if (!aidata.check(aisettings.nchannels())) {
    Serial.println("Fix ADC settings and check your hardware.");
    halt();
  }
  aidata.start();
  aidata.report();
  files.report();
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  char gs[16];
  pcm1.gainStr(gs, aisettings.pregain());
  files.start(settings.path(), settings.fileName(), settings.fileTime(),
              SOFTWARE, gs, settings.randomBlinks());
}


void loop() {
  files.update();
}
