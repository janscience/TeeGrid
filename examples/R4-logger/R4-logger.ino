#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SPI.h>
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

#define PATH           "recordings"   // folder where to store the recordings
#define DEVICEID       0              // may be used for naming files
#define FILENAME       "bigtankID2-SDATETIME.wav"  // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 5*60      // seconds
#define INITIAL_DELAY  10.0          // seconds
#define RANDOM_BLINKS  true          // set to true for blinking the LED randomly

// ----------------------------------------------------------------------------

#define LED_PIN        26    // R4.1    warning: this is the MOSI1 pin for the backup SD card
//#define LED_PIN      27    // R4.2

// Device ID pins:
int DIPPins[] = { 34, 35, 36, 37, -1 };

// Secondary backup SD card on SPI bus:
// Not recommended, since it draws a lot more current.
//#define BACKUP_SDCARD 1       // define if you want to use a backup SD card
//#define SDCARD1_CS     10    // CS pin for second SD card on SPI bus
#define SDCARD1_CS     38    // CS pin for second SD card on SPI1 bus


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R4-logger v2.2"

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
Blink blink(LED_PIN, true, LED_BUILTIN, false);
#ifdef BACKUP_SDCARD
SDCard sdcard0("primary");
SDCard sdcard1("secondary");
#else
SDCard sdcard0;
#endif

Config config("logger.cfg", &sdcard0);
Settings settings(config, PATH, DEVICEID, FILENAME, FILE_SAVE_TIME,
                  INITIAL_DELAY, RANDOM_BLINKS);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS, GAIN, PREGAIN);

RTClockMenu datetime_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard0);
SDCardMenu sdcard0_menu(config, sdcard0, settings);
#ifdef BACKUP_SDCARD
SDCardMenu sdcard1_menu(config, sdcard1, settings);
#endif
FirmwareMenu firmware_menu(config, sdcard0);
InputMenu input_menu(config, aidata, aisettings, pcms, NPCMS, R4SetupPCMs);
#ifdef BACKUP_SDCARD
DiagnosticMenu diagnostic_menu(config, sdcard0, sdcard1, &pcm1, &pcm2, &pcm3, &pcm4, &rtclock);
#else
DiagnosticMenu diagnostic_menu(config, sdcard0, &pcm1, &pcm2, &pcm3, &pcm4, &rtclock);
#endif
HelpAction help_act(config, "Help");

#ifdef BACKUP_SDCARD
Logger files(aidata, sdcard0, sdcard1, rtclock, deviceid, blink);
#else
Logger files(aidata, sdcard0, rtclock, deviceid, blink);
#endif

// -----------------------------------------------------------------------------

void setup() {
  //files.R41powerDownCAN();
  deviceid.setPins(DIPPins);
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
  sdcard0.begin();
#ifdef BACKUP_SDCARD
  pinMode(SDCARD1_CS, OUTPUT);
  //SPI.begin();
  SPI1.setMISO(39);    // Use alternate MISO pin for SPI1 bus
  SPI1.begin();
  sdcard1.begin(SDCARD1_CS, DEDICATED_SPI, 40, &SPI1);
#endif
  files.check(config, true);
  rtclock.setFromFile(sdcard0);
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  files.endBackup(&SPI1);
  Serial.println();
  deviceid.setID(settings.deviceID());
  if (deviceid.id() == 0)
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
