#include <Blink.h>
#include <LoggerSettings.h>
#include <InputTDMSettings.h>
#include <CANLogger.h>

#ifdef TEENSY4


CANLogger::CANLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard,
		     CANFD &can, RTClock &rtclock, Blink &blink,
		     Blink &errorblink, Blink &syncblink) :
  SensorsLogger(aiinput, sensors, sdcard,
		rtclock, blink, errorblink, syncblink),
  CAN(can),
  CANMode(CAN_NONE) {
}


void CANLogger::setCANMode(CAN_MODE canmode) {
  CANMode = canmode;
}


void CANLogger::setupSynchronization(CAN_MODE canmode,
				     LoggerSettings &settings,
				     InputTDMSettings &aisettings,
				     Blink &blink) {
  CANMode = canmode;
  // do not use CAN bus:
  if (CANMode == CAN_NONE) {
    powerDownCAN();
    Serial.println("Powered down CAN bus.");
    return;
  }
  powerUpCAN();
  // Master mode:
  if (CANMode == CAN_MASTER) {
    Serial.println("CAN Master mode");
    if (CAN.detectDevices() == 0) {
      blink.switchOff();
      halt(5);
    }
    delay(100);
    CAN.transmitLabel(settings.label());
    CAN.transmitTime();
    CAN.transmitSamplingRate(aisettings.rate());
    CAN.transmitGain(aisettings.gainDecibel());
    CAN.transmitFileTime(settings.fileTime());
    return;
  }
  // Slave mode:
  if (CANMode == CAN_SLAVE) {
    Serial.println("CAN Slave mode");
    if (CAN.assignDevice() == 0) {
      blink.switchOff();
      halt(5);
    }
    blink.setMultiple(CAN.id());
    //CAN.setupRecorderMBs();
    char gs[32];
    CAN.receiveLabel(gs);
    /*
      TODO: should receive full file name!!!
      if (strlen(gs) == 0 || CAN.id() > 0)
      strncpy(gs, GRID, 32);
      else
      Serial.printf("  got grid name %s\n", gs);
    */
    CAN.receiveTime();
    int rate = CAN.receiveSamplingRate();
    if (rate > 0 || CAN.id() > 0) {
      aisettings.setRate(rate);
      Serial.printf("  got %dHz sampling rate\n", aisettings.rate());
    }
    float gain = CAN.receiveGain();
    if (gain > -1000 || CAN.id() > 0) {
      aisettings.setGainDecibel(gain);
      Serial.printf("  got gain of %.1fdB\n", aisettings.gainDecibel());
    }
    // TODO: PREGAIN!
    float time = CAN.receiveFileTime();
    if (time > 0.0 && CAN.id() > 0)
      settings.setFileTime(time);
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
}


void CANLogger::synchronize(float stopvoltage) {
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

