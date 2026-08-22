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
    Serial.println("MASTER MODE");
    if (CAN.detectDevices() == 0)
      CANMode = CAN_NONE;
  }
  if (CANMode == CAN_MASTER) {
    delay(100);
    //settings.transmitSync(CAN);
    //delay(100);
    aisettings.transmitSync(CAN);
    delay(100);
    //timing.transmitSync(CAN);
    CAN.transmitTime();
    delay(100);
  }
  // Slave mode:
  if (CANMode == CAN_SLAVE) {
    Serial.println("SLAVE MODE");
    if (CAN.assignDevice() < 0) {
      StatusLED.switchOff();
      halt(5);
    }
    CAN.setTimeout(2000);
    //while (settings.receive(CAN) > 0) {};
    while (aisettings.receive(CAN) > 0) {};
    //while (timing.receive(CAN) > 0) {};
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

