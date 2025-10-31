#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SDCard.h>
#include <RTClockDS1307.h>
#include <DeviceID.h>
#include <Blink.h>
#include <TestSignals.h>
#include <MicroConfig.h>
#include <Settings.h>
#include <InputADCSettings.h>
#include <InputMenu.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <DiagnosticMenu.h>
#include <TeensyBoard.h>
#include <PowerSave.h>
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

#define LABEL         "logger"           // may be used for naming files
#define DEVICEID      1                  // may be used for naming files
#define PATH          "recordings"       // folder where to store the recordings
#define FILENAME      "LABELID-SDATETIME.wav" // may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 1*60 // seconds
#define INITIAL_DELAY  2.0   // seconds

#define PULSE_FREQUENCY 230 // Hertz
int signalPins[] = {9, 8, 7, 6, 5, 4, 3, 2, -1}; // pins where to put out test signals

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-logger v2.10"

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

RTClockDS1307 rtclock;
DeviceID deviceid(DEVICEID);
Blink blink("status", LED_BUILTIN);
SDCard sdcard;

Config config("teegrid.cfg", &sdcard);
Settings settings(config, LABEL, DEVICEID, PATH, FILENAME, FILE_SAVE_TIME,
	          INITIAL_DELAY, false, PULSE_FREQUENCY);
InputADCSettings aisettings(config, SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE, PREGAIN);
RTClockMenu rtclock_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings);
DiagnosticMenu diagnostic_menu(config, sdcard, 0, &aidata, &rtclock);
HelpAction help_act(config, "Help");

Logger files(aidata, sdcard, rtclock, blink);


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  settings.enable("InitialDelay");
  settings.enable("PulseFreq");
  aisettings.disable("Reference");
  aisettings.enable("Pregain");
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
  files.check(config);
  rtclock.setFromFile(sdcard);
  config.load();
  if (Serial)
    config.execute(Serial, 10000);
  config.report();
  Serial.println();
  deviceid.setID(settings.deviceID());
  aisettings.configure(&aidata);
  setupTestSignals(signalPins, settings.pulseFrequency());
  blink.switchOff();
  if (!aidata.check()) {
    Serial.println("Fix ADC settings and check your hardware.");
    halt();
  }
  aidata.start();
  aidata.report();
  files.report();
  settings.preparePaths(deviceid);
  files.setup(settings.path(), settings.fileName(), SOFTWARE);
  shutdown_usb();   // saves power!
  files.initialDelay(settings.initialDelay());
  files.start(settings.fileTime(), config);
}


void loop() {
  files.update();
}
