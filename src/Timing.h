/*
  Timing - configurable timing settings for loggers (initial delay, start time, etc.).
  Created by Jan Benda, March 26th, 2026.
*/

#ifndef Timing_h
#define Timing_h


#include <MicroConfig.h>


class Timing : public Menu {

public:

  Timing(Menu &menu, float initialdelay=0.0, const char *starttime=0,
	 const char *stoptime=0, float sensorsinterval=30.0);

  /* Time in seconds until recording of data is started. */
  float initialDelay() const { return InitialDelay.value(); };

  /* Set initial delay to time seconds. */
  void setInitialDelay(float time);

  /* Time of day (hh:mm:ss) when recording should start. */
  const char *startTime() const { return StartTime.value(); };

  /* Set time of day (hh:mm:ss) when recording should start. */
  void setStartTime(const char *starttime);

  /* Time of day (hh:mm:ss) when recording should stop. */
  const char *stopTime() const { return StopTime.value(); };

  /* Set time of day (hh:mm:ss) when recording should stop. */
  void setStopTime(const char *stoptime);
  
  /* Time in seconds between sensor readings. */
  float sensorsInterval() const { return SensorsInterval.value(); };

  /* Set time between sensor readings to time seconds. */
  void setSensorsInterval(float time);


protected:

  NumberParameter<float> InitialDelay;
  StringParameter<10> StartTime;
  StringParameter<10> StopTime;
  NumberParameter<float> SensorsInterval;
  
};

#endif
