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

// ----------------------------------------------------------------------------

#define LED_PIN       31

#define SOFTWARE      "TeeGrid R40-logger v1.6"

//DATA_BUFFER(AIBuffer, NAIBuffer, 512*256)
EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 2
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
ControlPCM186x *pcms[NPCMS] = {&pcm1, &pcm2};
ControlPCM186x *pcm = 0;
uint32_t SamplingRates[3] = {24000, 48000, 96000};

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard0;
SDCard sdcard1;

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME, 0.0,
                  0.0, INITIAL_DELAY);
InputTDMSettings aisettings(SAMPLING_RATE, NCHANNELS, GAIN);                  

LoggerFileStorage files(aidata, sdcard0, sdcard1, rtclock, deviceid, blink);


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.check();
  sdcard0.begin();
  files.check();
  rtclock.setFromFile(sdcard0);
  settings.disable("PulseFreq");
  settings.disable("DisplayTime");
  settings.disable("SensorsInterval");
  aisettings.setRateSelection(SamplingRates, 3);
  config.setConfigFile("teegrid.cfg");
  config.load(sdcard0);
  if (Serial)
    config.configure(Serial);
  config.report();
  aidata.setSwapLR();
  Wire.begin();
  for (int k=0;k < NPCMS; k++) {
    Serial.printf("Setup PCM186x %d: ", k);
    R40SetupPCM(aidata, *pcms[k], k%2==1, PREGAIN, aisettings, &pcm);
  }
  Serial.println();
  aidata.begin();
  if (!aidata.check()) {
    Serial.println("Fix ADC settings and check your hardware.");
    Serial.println("HALT");
    while (true) { yield(); };
  }
  aidata.start();
  aidata.report();
  blink.switchOff();
  files.report();
  files.initialDelay(settings.initialDelay());
  char gs[16];
  pcm1.gainStr(gs, PREGAIN);
  files.start(settings.path(), settings.fileName(), settings.fileTime(),
              SOFTWARE, gs);
}


void loop() {
  files.update();
  blink.update();
}
