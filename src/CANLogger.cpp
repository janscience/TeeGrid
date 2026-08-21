#include <Blink.h>
#include <LoggerSettings.h>
#include <InputTDMSettings.h>
#include <Timing.h>
#include <CANLogger.h>

#ifdef TEENSY4


CANLogger::CANLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard,
		     CANFD &can, RTClock &rtclock, Blink &blink,
		     Blink &errorblink, Blink &syncblink) :
  SensorsLogger(aiinput, sensors, sdcard,
		rtclock, blink, errorblink, syncblink),
  CAN(can),
  CANMode(CAN_NONE) {
  CAN.setRTClock(rtclock);
  CAN.setBlink(blink);
}


void CANLogger::setCANMode(CAN_MODE canmode) {
  CANMode = canmode;
}


void CANLogger::setupSynchronization(CAN_MODE canmode,
				     LoggerSettings &settings,
				     InputTDMSettings &aisettings,
				     Timing &timing) {
  CANMode = canmode;
  powerUpCAN();
  // Master mode:
  if (CANMode == CAN_MASTER) {
    Serial.println("CAN MASTER MODE ---");
    if (CAN.detectDevices() == 0)
      CANMode = CAN_NONE;
  }
  if (CANMode == CAN_MASTER) {
    delay(100);
    CAN.transmitConfigStart();
    settings.transmit(CAN);
    CAN.transmitConfigEnd();
    //CAN.transmitLabel(settings.label());
    //CAN.transmitFileName(settings.fileName());
    //CAN.transmitPath(settings.path());
    CAN.transmitConfigStart();
    aisettings.transmit(CAN);
    CAN.transmitConfigEnd();
    CAN.transmitConfigStart();
    timing.transmit(CAN);
    CAN.transmitConfigEnd();
    CAN.transmitTime();
    //CAN.transmitSamplingRate(aisettings.rate());
    //CAN.transmitGain(aisettings.gainDecibel());
    //CAN.transmitFileTime(settings.fileTime());
    //CAN.transmitSensorsInterval(timing.sensorsInterval());
  }
  // Slave mode:
  if (CANMode == CAN_SLAVE) {
    Serial.println("CAN Slave mode");
    if (CAN.assignDevice() < 0) {
      StatusLED.switchOff();
      halt(5);
    }
    /*
    char buffer[64];
    buffer[0] = '\0';
    CAN.receiveLabel(buffer);
    if (strlen(buffer) > 0)
      settings.setLabel(buffer);
    buffer[0] = '\0';
    CAN.receiveFileName(buffer);
    if (strlen(buffer) > 0)
      settings.setFileName(buffer);
    buffer[0] = '\0';
    CAN.receivePath(buffer);
    if (strlen(buffer) > 0)
      settings.setPath(buffer);
    int rate = CAN.receiveSamplingRate();
    if (rate > 0)
      aisettings.setRate(rate);
    float gain = CAN.receiveGain();
    if (gain > -100)
      aisettings.setGainDecibel(gain);
    float time = CAN.receiveFileTime();
    if (time > 0.0)
      settings.setFileTime(time);
    float interval = CAN.receiveSensorsInterval();
    if (time > 0.0)
      timing.setSensorsInterval(interval);
    */
    CAN.setTimeout(2000);
    CAN.receiveConfigStart();
    while (settings.receive(CAN) >= 0) {};
    CAN.receiveConfigStart();
    while (aisettings.receive(CAN) >= 0) {};
    CAN.receiveConfigStart();
    while (timing.receive(CAN) >= 0) {};
    CAN.receiveTime();
    /*
      if (CAN.id() == 0)
      FileName = settings.fileName();
      FileName.replace("GRID", gs);
      if (CAN.id() == 0)
      FileName.replace("DEV", DEV);
      else {
      char devs[2];
      devs[1] = '\0';
      devs[0] = char('A' + CAN.id() - 1);
      FileName.replace("DEV", devs);
      }
    */
  }
  Serial.println();
  // do not use CAN bus:
  if (CANMode == CAN_NONE) {
    powerDownCAN();
    Serial.println("Powered down CAN bus.");
    return;
  }
}


void CANLogger::synchronize(float stopvoltage) {
  checkVoltage(stopvoltage);
  /*
  if (CANMode != CAN_MASTER)
    CAN.transmitEndFile();
  if (CANMode == CAN_MASTER)
    CAN.transmitStart();
  else if (CAN.id() > 0)
    CAN.receiveStart();
  */
}


#endif

