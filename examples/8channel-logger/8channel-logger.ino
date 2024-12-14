#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SDCard.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <TestSignals.h>
#include <Configurator.h>
#include <Settings.h>
#include <InputADCSettings.h>
#include <ToolMenus.h>
#include <LoggerFileStorage.h>

// Default settings: ----------------------------------------------------------
// (may be overwritten by config file teegrid.cfg)

#define SAMPLING_RATE 20000 // samples per second and channel in Hertz
#define BITS             12 // resolution: 10bit 12bit, or 16bit
#define AVERAGING         4 // number of averages per sample: 0, 4, 8, 16, 32
#define CONVERSION    ADC_CONVERSION_SPEED::HIGH_SPEED
#define SAMPLING      ADC_SAMPLING_SPEED::HIGH_SPEED
#define REFERENCE     ADC_REFERENCE::REF_3V3
int8_t channels0 [] =  {A4, A5, A6, A7, -1, A4, A5, A6, A7, A8, A9};      // input pins for ADC0
int8_t channels1 [] =  {A2, A3, A20, A22, -1, A20, A22, A12, A13};  // input pins for ADC1

#define PATH          "recordings"       // folder where to store the recordings
#define DEVICEID      1                  // may be used for naming files
#define FILENAME      "gridID-SDATETIME.wav" // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 1*60 // seconds
#define INITIAL_DELAY  2.0   // seconds

#define PULSE_FREQUENCY 230 // Hertz
int signalPins[] = {9, 8, 7, 6, 5, 4, 3, 2, -1}; // pins where to put out test signals

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-logger v2.6"

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_BUILTIN);
SDCard sdcard0;

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME, INITIAL_DELAY,
                  false, PULSE_FREQUENCY);
InputADCSettings aisettings(SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE);
DateTimeMenu datetime_menu(rtclock);
ConfigurationMenu configuration_menu(sdcard0);
SDCardMenu sdcard0_menu(sdcard0, settings);
#ifdef FIRMWARE_UPDATE
FirmwareMenu firmware_menu(sdcard0);
#endif
DiagnosticMenu diagnostic_menu("Diagnostics", sdcard0);

LoggerFileStorage files(aidata, sdcard0, rtclock, deviceid, blink);


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.check();
  sdcard0.begin();
  files.check(true);
  rtclock.setFromFile(sdcard0);
  settings.enable("InitialDelay");
  settings.enable("PulseFreq");
  config.setConfigFile("teegrid.cfg");
  config.load(sdcard0);
  if (Serial)
    config.configure(Serial, 10000);
  config.report();
  Serial.println();
  aisettings.configure(&aidata);
  setupTestSignals(signalPins, settings.pulseFrequency());
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
  // TODO: provide gain string!
  files.start(settings.path(), settings.fileName(), settings.fileTime(),
              SOFTWARE);
}


void loop() {
  files.update();
  blink.update();
}
