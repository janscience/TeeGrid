#include <TeeGridBanner.h>
#include <InputADC.h>
#include <SDWriter.h>
#include <RTClock.h>
#include <DeviceID.h>
#include <Blink.h>
#include <TestSignals.h>
#include <Configurator.h>
#include <Settings.h>
#include <InputADCSettings.h>
#include <FileStorage.h>


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
#define FILENAME      "gridID-SDATETIME" // may include ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 10*60 // seconds
#define INITIAL_DELAY  2.0   // seconds

#define PULSE_FREQUENCY 230 // Hertz
int signalPins[] = {9, 8, 7, 6, 5, 4, 3, 2, -1}; // pins where to put out test signals

// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid 8channel-logger v2.6"

RTClock rtclock;
DeviceID deviceid(DEVICEID);

DATA_BUFFER(AIBuffer, NAIBuffer, 256*256)
InputADC aidata(AIBuffer, NAIBuffer, channels0, channels1);

SDCard sdcard;
SDWriter file(sdcard, aidata);

Configurator config;
Settings settings(PATH, DEVICEID, FILENAME, FILE_SAVE_TIME, PULSE_FREQUENCY,
                  0.0, INITIAL_DELAY);
InputADCSettings aisettings(SAMPLING_RATE, BITS, AVERAGING,
			    CONVERSION, SAMPLING, REFERENCE);
Blink blink(LED_BUILTIN);


// ----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  rtclock.check();
  sdcard.begin();
  rtclock.setFromFile(sdcard);
  rtclock.report();
  settings.disable("DisplayTime");
  settings.disable("SensorsInterval");
  config.setConfigFile("teegrid.cfg");
  config.load(sdcard);
  if (Serial)
    config.configure(Serial);
  config.report();
  deviceid.report();
  aisettings.configure(&aidata);
  setupTestSignals(signalPins, settings.pulseFrequency());
  aidata.check();
  aidata.start();
  aidata.report();
  blink.switchOff();
  if (settings.initialDelay() >= 2.0) {
    delay(1000);
    blink.setDouble();
    blink.delay(uint32_t(1000.0*settings.initialDelay()) - 1000);
  }
  else
    delay(uint32_t(1000.0*settings.initialDelay()));
  setupStorage(SOFTWARE, aidata);
  openNextFile();
}


void loop() {
  storeData();
  blink.update();
}
