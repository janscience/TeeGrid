#include <CANFileStorage.h>

#ifdef TEENSY4


CANFileStorage::CANFileStorage(Input &aiinput, SDCard &sdcard0, SDCard &sdcard1,
			       R41CAN &can, bool master, const RTClock &rtclock,
			       const DeviceID &deviceid, Blink &blink) :
  Logger(aiinput, sdcard0, sdcard1, rtclock, deviceid, blink),
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

