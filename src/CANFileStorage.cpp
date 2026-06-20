#include <CANFileStorage.h>

#ifdef TEENSY4


CANFileStorage::CANFileStorage(Input &aiinput, SDCard &sdcard,
			       CANFD &can, bool master, RTClock &rtclock,
			       Blink &blink) :
  Logger(aiinput, sdcard, rtclock, blink),
  CAN(can),
  Master(master) {
}


bool CANFileStorage::synchronize() {
  if (!Master)
    CAN.transmitEndFile();
  if (Master)
    CAN.transmitStart();
  else if (CAN.id() > 0)
    CAN.receiveStart();
  return false;
}


#endif

