#include <CANFileStorage.h>

#ifdef TEENSY4


CANFileStorage::CANFileStorage(Input &aiinput, SDCard &sdcard,
			       R41CAN &can, bool master, RTClock &rtclock,
			       Blink &blink) :
  Logger(aiinput, sdcard, rtclock, blink),
  CAN(can),
  Master(master) {
}


bool CANFileStorage::synchronize() {
  if (!Master)
    CAN.sendEndFile();
  if (Master)
    CAN.sendStart();
  else if (CAN.id() > 0)
    CAN.receiveStart();
  return false;
}


#endif

