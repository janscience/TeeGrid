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


void CANLogger::insertDevice(String &path) {
  if (CAN.id() == 0)
    return;
  // ID ID2 ID3 IDA IDAA
  char devs[4];
  devs[1] = '\0';
  devs[0] = char('A' + CAN.id() - 1);
  int idx = path.indexOf("grid");
  if (idx >= 0) {
    idx += 4;
    sprintf(devs, "%02d", CAN.id());
    path[idx++] = devs[0];
    path[idx++] = devs[1];
  }
  else if (path.indexOf("IDAA") >= 0) {
    char ids[10] = "IDAA-";
    strcat(ids, devs);
    path.replace("IDAA", ids);
  }
  else if (path.indexOf("IDA") >= 0) {
    char ids[10] = "IDA-";
    strcat(ids, devs);
    path.replace("IDA", ids);
  }
  else if (path.indexOf("ID3") >= 0) {
    char ids[10] = "ID3";
    strcat(ids, devs);
    path.replace("ID3", ids);
  }
  else if (path.indexOf("ID2") >= 0) {
    char ids[10] = "ID2";
    strcat(ids, devs);
    path.replace("ID2", ids);
  }
  else if (path.indexOf("ID") >= 0) {
    char ids[10] = "ID";
    strcat(ids, devs);
    path.replace("ID", ids);
  }
}


void CANLogger::preparePaths(LoggerSettings &settings) {
  if ((CANMode == CAN_MASTER) || (CANMode == CAN_SLAVE)) {
    String filename(settings.fileName());
    insertDevice(filename);
    settings.setFileName(filename.c_str());
    String path(settings.path());
    insertDevice(path);
    settings.setPath(path.c_str());
  }
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
    //aisettings.transmitSync(CAN);
    //timing.transmitSync(CAN);
    CAN.transmitTime();
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
    //while (aisettings.receive(CAN) > 0) {};
    //while (timing.receive(CAN) > 0) {};
    CAN.receiveTime();
  }
  Serial.println();
  // do not use CAN bus:
  if (CANMode == CAN_NONE) {
    powerDownCAN();
    Serial.println("CAN bus powered down .");
    return;
  }
}


void CANLogger::synchronizeStart() {
  if (CANMode == CAN_MASTER) {
    delay(100);
    CAN.transmitStart();
  }
  if (CANMode == CAN_SLAVE) {
    CAN.receiveStart();
  }
}


void CANLogger::initialDelay(float initial_delay, const char *stop_time,
			     Stream &stream) {
  synchronizeStart();
  SensorsLogger::initialDelay(initial_delay, stop_time, stream);
  synchronizeStart();
}


void CANLogger::synchronize(float stopvoltage) {
  checkVoltage(stopvoltage);
  /*
  if (CANMode == CAN_MASTER) {
    CAN.receiveEndFile();
    CAN.transmitStart();
  }
  if (CANMode == CAN_SLAVE) {
    CAN.transmitEndFile();
    CAN.receiveStart();
  }
  */
}


#endif

