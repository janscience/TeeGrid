#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SPI.h>
#include <SDWriter.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <Configurator.h>
#include <Settings.h>
#include <InputTDMSettings.h>
#include <SetupPCM.h>
#include <ToolMenus.h>
#include <CANFileStorage.h>
#include <R41CAN.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg and by can bus communication)
#define NCHANNELS     16       // number of channels (even, from 2 to 16)
#define SAMPLING_RATE 48000    // samples per second and channel in Hertz
#define PREGAIN       1.0     // gain factor of preamplifier
#define GAIN          0.0     // dB

#define PATH          "recordings"   // folder where to store the recordings
#define DEVICEID      0              // may be used for naming files
#define FILENAME      "gridID-SDATETIME-RECCOUNT-DEV.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
//String LoggerFileName = "loggergrid-RECNUM4-DEV.wav";
#define FILE_SAVE_TIME 20 //5*60   // seconds
#define INITIAL_DELAY  10.0  // seconds

// ----------------------------------------------------------------------------

#define LED_PIN        26    // R4.1

//#define SDCARD1_CS     10    // CS pin for second SD card on SPI bus
#define SDCARD1_CS     38    // CS pin for second SD card on SPI1 bus


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R41-CAN-recorder v2.0"

//DATA_BUFFER(AIBuffer, NAIBuffer, 512*256)
EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NPCMS 4
ControlPCM186x pcm1(Wire, PCM186x_I2C_ADDR1, InputTDM::TDM1);
ControlPCM186x pcm2(Wire, PCM186x_I2C_ADDR2, InputTDM::TDM1);
ControlPCM186x pcm3(Wire1, PCM186x_I2C_ADDR1, InputTDM::TDM2);
ControlPCM186x pcm4(Wire1, PCM186x_I2C_ADDR2, InputTDM::TDM2);
ControlPCM186x *pcms[NPCMS] = {&pcm1, &pcm2, &pcm3, &pcm4};
ControlPCM186x *pcm = 0;
uint32_t SamplingRates[3] = {24000, 48000, 96000};

R41CAN can;
RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_PIN, true, LED_BUILTIN, false);
SDCard sdcard0("primary");
SDCard sdcard1("secondary");

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME, 0.0,
                  0.0, INITIAL_DELAY);
InputTDMSettings aisettings(SAMPLING_RATE, NCHANNELS, GAIN);                  
DateTimeMenu datetime_menu(rtclock);
ConfigurationMenu configuration_menu(sdcard0);
SDCardMenu sdcard0_menu("Primary SD card", sdcard0, settings);
SDCardMenu sdcard1_menu("Secondary SD card", sdcard1, settings);
#ifdef FIRMWARE_UPDATE
FirmwareMenu firmware_menu(sdcard0);
#endif
DiagnosticMenu diagnostic_menu("Diagnostics", sdcard0, sdcard1);
HelpAction help_act(config, "Help");

CANFileStorage files(aidata, sdcard0, sdcard1, can, false,
	             rtclock, deviceid, blink);


void setupCAN() {
  can.begin();
  can.assignDevice();
  if (can.id() > 0 )
    blink.setMultiple(can.id());
  else
    blink.switchOff();
  //can.setupRecorderMBs();
  char gs[32];
  can.receiveGrid(gs);
  /*
  TODO: should receive full file name!!!
  if (strlen(gs) == 0 || can.id() > 0)
    strncpy(gs, GRID, 32);
  else
    Serial.printf("  got grid name %s\n", gs);
    */
  can.receiveTime();
  int rate = can.receiveSamplingRate();
  if (rate > 0 || can.id() > 0) {
    aisettings.setRate(rate);
    Serial.printf("  got %dHz sampling rate\n", aisettings.rate());
  }
  float gain = can.receiveGain();
  if (gain > -1000 || can.id() > 0) {
    aisettings.setGain(gain);
    Serial.printf("  got gain of %.1fdB\n", aisettings.gain());
  }
  float time = can.receiveFileTime();
  if (time > 0.0 && can.id() > 0)
    settings.setFileTime(time);
    /*
  if (can.id() == 0)
    FileName = settings.fileName();
  FileName.replace("GRID", gs);
  if (can.id() == 0)
    FileName.replace("DEV", DEV);
  else {
    char devs[2];
    devs[1] = '\0';
	  devs[0] = char('A' + can.id() - 1);
    FileName.replace("DEV", devs);
  }
  */
}


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  blink.switchOff();
  printTeeGridBanner(SOFTWARE);
  rtclock.check();
  pinMode(SDCARD1_CS, OUTPUT);
  //SPI.begin();
  SPI1.setMISO(39);    // Use alternate MISO pin for SPI1 bus
  SPI1.begin();
  sdcard0.begin();
  sdcard1.begin(SDCARD1_CS, DEDICATED_SPI, 40, &SPI1);
  files.check(true);
  rtclock.setFromFile(sdcard0);
  settings.disable("PulseFreq");
  settings.disable("DisplayTime");
  settings.disable("SensorsInterval");
  aisettings.setRateSelection(SamplingRates, 3);
  config.setConfigFile("logger.cfg");
  config.load(sdcard0);
  if (Serial)
    config.configure(Serial, 10000);
  config.report();
  Serial.println();
  setupCAN();  
  aidata.setSwapLR();
  Wire.begin();
  Wire1.begin();
  for (int k=0;k < NPCMS; k++) {
    Serial.printf("Setup PCM186x %d on TDM %d: ", k, pcms[k]->TDMBus());
    R4SetupPCM(aidata, *pcms[k], k%2==1, aisettings, &pcm);
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
  files.report();
  if (can.id() > 0)
    can.receiveStart();
  else {
    blink.switchOff();
    files.initialDelay(settings.initialDelay());
  }
  char gs[16];
  pcm->gainStr(gs, PREGAIN);
  files.start(settings.path(), settings.fileName(), settings.fileTime(),
              SOFTWARE, gs);
}


void loop() {
  files.update();
  can.events();
  blink.update();
}
