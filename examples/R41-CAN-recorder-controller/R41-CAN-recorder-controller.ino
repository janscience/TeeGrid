#include <TeeGridBanner.h>
#include <Wire.h>
#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <SDWriter.h>
#include <RTClock.h>
#include <Blink.h>
#include <SetupPCM.h>
#include <CANFileStorage.h>
#include <R41CAN.h>

#define NCHANNELS      16       // number of channels (even, from 2 to 16)
#define PREGAIN        10.0     // gain factor of preamplifier
#define GRID              "grid1"    // unique name of the grid
#define SAMPLING_RATE     48000      // sampling rate in Hz
#define GAIN              40.0       // gain in dB
float   FileTime        = 30.0;      // seconds
#define INITIAL_DELAY     20.0       // seconds

#define PATH           "recordings"   // folder where to store the recordings
String  FileName     = "GRID-SDATETIME-RECCOUNT-DEV.wav";  // may include GRID, DEV, COUNT, DATE, SDATE, TIME, STIME, DATETIME, SDATETIME, ANUM, NUM
String LoggerFileName = "loggergrid-RECNUM4-DEV.wav";
#define DEV            "A"            // we are the first logger in the grid

// ----------------------------------------------------------------------------

#define LED_PIN        26    // R4.1
#define SOFTWARE      "TeeGrid R41-CAN-recorder-controller v1.0"

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

R41CAN can;
SDCard sdcard;
SDWriter file(sdcard, aidata);
RTClock rtclock;
Blink blink(LED_PIN, true, LED_BUILTIN, false);


void setupCAN() {
  can.begin();
  can.detectOtherDevices();
  delay(100);
  can.sendGrid(GRID);
  can.sendTime();
  can.sendSamplingRate(SAMPLING_RATE);
  can.sendGain(GAIN);
  can.sendFileTime(FileTime);
  if (can.numDevices() <= 1)
    FileName = LoggerFileName;
  FileName.replace("GRID", GRID);
  FileName.replace("DEV", DEV);
}


// -----------------------------------------------------------------------------

void setup() {
  blink.switchOn();
  blink.setTiming(3000);
  Serial.begin(9600);
  while (!Serial && millis() < 2000) {};
  blink.switchOff();
  printTeeGridBanner(SOFTWARE);
  rtclock.begin();
  rtclock.check();
  sdcard.begin();
  rtclock.setFromFile(sdcard);
  rtclock.report();
  setupCAN();  
  aidata.setSwapLR();
  Wire.begin();
  Wire1.begin();
  for (int k=0; k<NPCMS; k++) {
    Serial.printf("Setup PCM186x %d on TDM %d: ", k, pcms[k]->TDMBus());
    R4SetupPCM(aidata, *pcms[k], k%2==1, SAMPLING_RATE, NCHANNELS, GAIN, &pcm);
  }
  Serial.println();
  aidata.begin();
  aidata.check(NCHANNELS);
  aidata.start();
  aidata.report();
  char gs[16];
  pcm->gainStr(gs, PREGAIN);
  setupGridStorage(PATH, SOFTWARE, aidata, gs);
  blink.switchOff();
  if (INITIAL_DELAY >= 2.0) {
    delay(1000);
    blink.setDouble();
    blink.delay(uint32_t(1000.0*INITIAL_DELAY)-1000);
  }
  else
    delay(uint32_t(1000.0*INITIAL_DELAY));
  can.sendStart();
  openNextGridFile();
}

void loop() {
  storeGridData(true);
  can.events();
  blink.update();
}
