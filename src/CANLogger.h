/*
  CANLogger - High level handling of CAN synchronized file storage of logger data.
  Created by Jan Benda, September 18th, 2023.
*/

#ifndef CANLogger_h
#define CANLogger_h

#include <TeensyBoard.h>
#include <CANFD.h>
#include <SensorsLogger.h>

class LoggerSettings;
class InputTDMSettings;
class Timing;

  
enum CAN_MODE : uint8_t {
  CAN_NONE,
  CAN_MASTER,
  CAN_SLAVE
};


#ifdef TEENSY4


class CANLogger : public SensorsLogger {

public:

  CANLogger(Input &aiinput, ESensors &sensors, SDCard &sdcard,
	    CANFD &can, RTClock &rtclock, Blink &blink,
	    Blink &errorblink, Blink &syncblink);

  CAN_MODE canMode() const { return CANMode; };

  void setCANMode(CAN_MODE canmode);

  void powerDownCAN() { CAN.powerDown(); };
  
  void powerUpCAN() { CAN.powerUp(); };

  void setupSynchronization(CAN_MODE canmode,
			    LoggerSettings &settings,
			    InputTDMSettings &aisettings,
			    Timing &timing);
  
  void preparePaths(LoggerSettings &settings);
  
  // Delay with double blinks for initial_delay seconds.
  // Initialize a potential stop time.
  void initialDelay(float initial_delay, const char *stop_time=0,
		    Stream &stream=Serial);

  
protected:

  void insertDevice(String &path);
  void synchronizeStart();

  // Use CAN bus to synchronize opening of next file.
  virtual void synchronize(float stopvoltage);

  CANFD &CAN;
  CAN_MODE CANMode;
  
};


#endif

#endif

