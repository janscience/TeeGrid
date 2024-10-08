#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SPI.h>
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

#define SDCARD1_CS       10    // CS pin for second SD card on SPI bus, set to 255 if not used

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-logger v2.6"

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

RTClock rtclock;
DeviceID deviceid(DEVICEID);
Blink blink(LED_BUILTIN);
SDCard sdcard0("primary");
SDCard sdcard1("secondary");

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME, PULSE_FREQUENCY,
                  0.0, INITIAL_DELAY);
InputADCSettings aisettings(SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE);
DateTimeMenu datetime_menu(rtclock);
ConfigurationMenu configuration_menu(sdcard0);
SDCardMenu sdcard0_menu("Primary SD card", sdcard0, settings);
SDCardMenu sdcard1_menu("Secondary SD card", sdcard1, settings);
#ifdef FIRMWARE_UPDATE
FirmwareMenu firmware_menu(sdcard0);
#endif
DiagnosticMenu diagnostic_menu("Diagnostics", sdcard0, sdcard1);

LoggerFileStorage files(aidata, sdcard0, sdcard1, rtclock, deviceid, blink);


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.check();
  pinMode(SDCARD1_CS, OUTPUT);
  SPI.begin();
  sdcard0.begin();
  sdcard1.begin(SDCARD1_CS, DEDICATED_SPI, 40, &SPI);
  files.check(true);
  rtclock.setFromFile(sdcard0);
  settings.disable("DisplayTime");
  settings.disable("SensorsInterval");
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
  files.start(settings.path(), settings.fileName(), settings.fileTime(),
              SOFTWARE);
}


void loop() {
  files.update();
  blink.update();
}
