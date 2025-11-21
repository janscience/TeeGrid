#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SDCard.h>
#include <RTClockDS1307.h>
#include <DeviceID.h>
#include <Blink.h>
#include <TestSignals.h>
#include <MicroConfig.h>
#include <LoggerSettings.h>
#include <InputADCSettings.h>
#include <InputMenu.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <DiagnosticMenu.h>
#include <TeensyBoard.h>
#include <Logger.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)

#define SAMPLING_RATE 20000 // samples per second and channel in Hertz
#define BITS          12 // resolution: 10bit 12bit, or 16bit
#define AVERAGING     4  // number of averages per sample: 0, 4, 8, 16, 32
#define CONVERSION    ADC_CONVERSION_SPEED::HIGH_SPEED
#define SAMPLING      ADC_SAMPLING_SPEED::HIGH_SPEED
#define REFERENCE     ADC_REFERENCE::REF_3V3
int8_t channels0 [] = {A4, A5, A6, A7, -1, A4, A5, A6, A7, A8, A9};      // input pins for ADC0
int8_t channels1 [] = {A2, A3, A20, A22, -1, A20, A22, A12, A13};  // input pins for ADC1
#define PREGAIN       1

#define LABEL         "logger"              // may be used for naming files
#define DEVICEID      1                     // may be used for naming files
#define PATH          "LABELID2-SDATETIMEM" // folder where to store the recordings
#define FILENAME      "LABELID2-SDATETIME"  // ".wav" is appended, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 10*60  // seconds
#define INITIAL_DELAY  10     // seconds

#define PULSE_FREQUENCY 230 // Hertz
int signalPins[] = {9, 8, 7, 6, 5, 4, 3, 2, -1}; // pins where to put out test signals

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-logger v3.0"

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

RTClockDS1307 rtclock;
DeviceID deviceid(DEVICEID);
Blink blink("status", LED_BUILTIN);
SDCard sdcard;

Config config("teegrid.cfg", &sdcard);
LoggerSettings settings(config, LABEL, DEVICEID, PATH, FILENAME,
                        FILE_SAVE_TIME, INITIAL_DELAY);
InputADCSettings aisettings(config, SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE, PREGAIN);
RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings);
DiagnosticMenu diagnostic_menu(config, sdcard, 0, &aidata, &rtclock);
HelpAction help_act(config, "Help");

Logger logger(aidata, sdcard, rtclock, blink);


void setupMenu() {
  settings.disable("Path", settings.StreamInput);
  settings.disable("FileName", settings.StreamInput);
  aisettings.disable("Reference");
  aisettings.enable("Pregain");
  sdcard_menu.CleanRecsAct.setRemove(true);
}


void setupBoard() {
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
}


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  setupMenu();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  setupBoard();
  logger.configure(config);
  deviceid.setID(settings.deviceID());
  aisettings.configure(&aidata);
  settings.preparePaths(deviceid);
  setupTestSignals(signalPins, PULSE_FREQUENCY);
  logger.startInput();
  logger.setup(settings.path(), settings.fileName(), SOFTWARE);
  logger.initialDelay(settings.initialDelay());
  diagnostic_menu.updateCPUSpeed();
  logger.start(settings.fileTime(), config);
}


void loop() {
  logger.update();
}
