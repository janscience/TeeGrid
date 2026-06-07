/*
  CANFileStorage - High level handling of CAN synchronized file storage of logger data.
  Created by Jan Benda, September 18th, 2023.
*/

#ifndef CANFileStorage_h
#define CANFileStorage_h

#include <CANFD.h>
#include <TeensyBoard.h>
#include <Logger.h>

#ifdef TEENSY4

class CANFileStorage : public Logger {
  
public:

  CANFileStorage(Input &aiinput, SDCard &sdcard,
		 CANFD &can, bool master, RTClock &rtclock,
		 Blink &blink);

protected:

  // Use CAN bus to synchronize opening of next file.
  virtual bool synchronize();

  CANFD &CAN;
  bool Master;
  
};

#endif

#endif

