#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlTLV320ADC.h>
#include <InputTDM.h>
#include <SDCard.h>
#include <RTClockDS1307.h>
#include <Blink.h>
#include <MicroConfig.h>
#include <LoggerSettings.h>
#include <BlinkSettings.h>
#include <InputTDMSettings.h>
#include <Timing.h>
#include <SetupTLV.h>
#include <InputMenu.h>
#include <RTClockMenu.h>
#include <SDCardMenu.h>
#include <DiagnosticMenu.h>
#include <BlinkMenu.h>
#include <TeensyBoard.h>
#include <SensorsLogger.h>
#include <ESensors.h>
#include <VoltageADC.h>
#include <TemperatureDS3231.h>
#include <TemperatureSTS4x.h>
#include <LightBH1750.h>
#include <DigitalIOPCA9536.h>
#include <ESensorsMenu.h>


// Default settings: ----------------------------------------------------------
// (may be overwritten by config file logger.cfg)
#define NCHANNELS       8       // number of channels (even, from 2 to 16)
#define SAMPLING_RATE  48000    // samples per second and channel in Hertz
#define SOURCE         Input::SINGLE_ENDED
#define PREGAIN        2.0     // gain factor of preamplifier
#define GAIN           0.0     // dB

#define LABEL          "logger"               // may be used for naming files
#define DEVICEID       1                      // may be used for naming files
#define PATH           "LABELID2-SDATETIMEM"  // folder where to store the recordings, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, NUM
#define FILENAME       "LABELID2-SDATETIME"   // ".wav" is appended, may include LABEL, ID, IDA, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
#define FILE_SAVE_TIME 10       // seconds
#define INITIAL_DELAY   4       // seconds
#define RANDOM_BLINKS    false    // set to true for blinking the status LED randomly (sync LED is always blinked randomly)
#define BLINK_TIMEOUT    0      // time after which internal LEDs are switched off in seconds
#define SYNC_TIMEOUT     0      // time after which synchronization LED is switched off in seconds
#define SENSORS_INTERVAL 30.0     // interval between sensors readings in seconds
#define LIGHT_THRESHOLD  10.0     // threshold for switching off LEDs in lux.

// ----------------------------------------------------------------------------

#define TLV_SHDNZ_PIN    3

#define SYNC_LED_PIN     11
#define ERROR_LED_PIN    12

#define STS4x_ADDR  STS4x_ADDR2   // I2C address of STS4x temperature sensor


// ----------------------------------------------------------------------------

#define SOFTWARE      "TeeGrid R5-logger v0.1"

EXT_DATA_BUFFER(AIBuffer, NAIBuffer, 16*512*256)
InputTDM aidata(AIBuffer, NAIBuffer);
#define NTLVS 6
ControlTLV320ADC tlv1(Wire, TLV320_I2C_ADDR2, InputTDM::TDM1, InputTDM::DATA_A);
ControlTLV320ADC tlv2(Wire, TLV320_I2C_ADDR1, InputTDM::TDM1, InputTDM::DATA_A);
//ControlTLV320ADC tlv3(Wire, TLV320_I2C_ADDR4, InputTDM::TDM1, InputTDM::DATA_B);
//ControlTLV320ADC tlv4(Wire, TLV320_I2C_ADDR3, InputTDM::TDM1, InputTDM::DATA_B);
ControlTLV320ADC tlv5(Wire1, TLV320_I2C_ADDR4, InputTDM::TDM1, InputTDM::DATA_C);
ControlTLV320ADC tlv6(Wire1, TLV320_I2C_ADDR3, InputTDM::TDM1, InputTDM::DATA_C);
ControlTLV320ADC tlv7(Wire1, TLV320_I2C_ADDR2, InputTDM::TDM1, InputTDM::DATA_D);
ControlTLV320ADC tlv8(Wire1, TLV320_I2C_ADDR1, InputTDM::TDM1, InputTDM::DATA_D);
Device *tlvs[NTLVS] = {&tlv1, &tlv2, &tlv5, &tlv6, &tlv7, &tlv8};
#define NPREGAINS 2
float pregains[NPREGAINS] = {2.0, 0.125};

RTClockDS1307 rtclock;
Blink blink("Status", LED_BUILTIN);
Blink errorblink("Error", ERROR_LED_PIN, true);
Blink syncblink("Synchronization", SYNC_LED_PIN, true);
SDCard sdcard;

ESensors sensors;
VoltageADC vbat(&sensors, A0, 2*3.3);
DigitalIOPCA9536 gpio;
TemperatureDS3231 temprtc(&sensors);
TemperatureSTS4x tempsts(&sensors);
LightBH1750 light1(&sensors);
LightBH1750 light2(&sensors);

Config config("logger.cfg", &sdcard);
LoggerSettings settings(config, LABEL, DEVICEID, PATH, FILENAME,
                        FILE_SAVE_TIME, INITIAL_DELAY);
InputTDMSettings aisettings(config, SAMPLING_RATE, NCHANNELS,
                            GAIN, PREGAIN, SOURCE);
Timing timing(config, INITIAL_DELAY, "", "", SENSORS_INTERVAL);
BlinkSettings blinksettings(config, RANDOM_BLINKS, BLINK_TIMEOUT, SYNC_TIMEOUT,
			    LIGHT_THRESHOLD);

RTClockMenu datetime_menu(config, rtclock);
ConfigurationMenu configuration_menu(config, sdcard);
SDCardMenu sdcard_menu(config, sdcard);
FirmwareMenu firmware_menu(config, sdcard);
InputMenu input_menu(config, aidata, aisettings, tlvs, NTLVS, R5SetupTLVs);
ESensorsMenu sensors_menu(config, sensors);
DiagnosticMenu diagnostic_menu(config, &tlv1, &tlv2, &tlv5, &tlv6, &tlv7, &tlv8,
                               &rtclock, &gpio);
BlinkMenu blink_menu(diagnostic_menu, &blink, &errorblink, &syncblink);
Menu ampl_info(diagnostic_menu, "Amplifier board");
HelpAction help_act(config, "Help");

SensorsLogger logger(aidata, sensors, sdcard, rtclock,
                     blink, errorblink, syncblink);


void setupLEDs() {
  Wire2.begin();
  gpio.begin(Wire2);
  if (gpio.available()) {
    blink.setPin(gpio, 0);
    errorblink.setPin(gpio, 1);
    syncblink.setPin(gpio, 3);
  }
  errorblink.switchOff();
  syncblink.switchOff();
  blink.switchOn();
}


void setupMenu() {
  aisettings.setRateSelection(ControlTLV320ADC::SamplingRates,
                              ControlTLV320ADC::MaxSamplingRates);
  aisettings.enable("Source");
  aisettings.enable("Pregain");
  aisettings.setPreGainFormat("%g");
  aisettings.setPreGainSelection(pregains, NPREGAINS);
  //timing.enable("StartTime");
  //timing.enable("StopTime");
  timing.enable("SensorsInterval");
  sdcard_menu.CleanRecsAct.setRemove(true);
  blinksettings.enable("RandomBlinks");
  blinksettings.enable("BlinkTimeout");
  blinksettings.enable("SyncTimeout");
}


void setupBoard() {
  Wire.begin();
  Wire1.begin();
  rtclock.begin();
  rtclock.check();
  ampl_info.addConstString("Version", "R5.0");
  sdcard.begin();
  powerupTLVs(tlvs, NTLVS, TLV_SHDNZ_PIN);
  // TODO: power down CAN
}


void setupSensors() {
  temprtc.begin(Wire);
  temprtc.setName("logger-temperature");
  temprtc.setSymbol("Ti");
  vbat.setName("battery-voltage");
  vbat.setSymbol("Vbat");
  vbat.setAveraging(32);
  gpio.setMode(2, INPUT);
  light1.begin(Wire2, BH1750_TO_GROUND);
  //light1.setAutoRanging();
  light1.setQuality(BH1750_QUALITY_HIGH2);
  light1.setName("illuminance1");
  light1.setSymbol("I1");
  light2.begin(Wire2, BH1750_TO_VCC);
  //light2.setAutoRanging();
  light2.setQuality(BH1750_QUALITY_HIGH2);
  light2.setName("illuminance2");
  light2.setSymbol("I2");
  tempsts.begin(Wire2, STS4x_ADDR);
  tempsts.setPrecision(STS4x_HIGH);
  tempsts.setSymbol("Tw");
  logger.setupSensors();
  if (light1.available() || light2.available())
    blinksettings.enable("LightThreshold");
}


// -----------------------------------------------------------------------------

void setup() {
  setupLEDs();
  setupMenu();
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  printTeeGridBanner(SOFTWARE);
  setupBoard();
  setupSensors();
  logger.configure(config);
  //powerdownTLVs(tlvs, NTLVS, TLV_SHDNZ_PIN);
  //logger.snooze(timing.startTime());
  //powerupTLVs(tlvs, NTLVS, TLV_SHDNZ_PIN);
  logger.startSensors(timing.sensorsInterval(), blinksettings.lightThreshold());
  logger.setCPUSpeed(aisettings.rate());
  settings.preparePaths();
  R5SetupTLVs(aidata, aisettings, tlvs, NTLVS);
  logger.startInput(aisettings.nchannels());
  logger.setup(settings.path(), settings.fileName(),
               SOFTWARE, blinksettings.randomBlinks(),
    	       blinksettings.blinkTimeout(),
	       blinksettings.syncTimeout());
  logger.initialDelay(timing.initialDelay(), timing.stopTime());
  diagnostic_menu.updateCPUSpeed();
  logger.start(settings.fileTime(), config, ampl_info);
}


void loop() {
  logger.update();
}
