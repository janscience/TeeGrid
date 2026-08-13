/*
  LoggerSettings - common configurable settings for loggers (file name, path, etc.).
  Created by Jan Benda, November 15th, 2025.
*/

#ifndef LoggerSettings_h
#define LoggerSettings_h


#include <MicroConfig.h>

class DeviceID;


class LoggerSettings : public Menu {

public:

  LoggerSettings(Menu &menu, const char *label="logger", int deviceid=0,
		 const char *path="LABELID2-SDATETIMEM",
		 const char *filename="LABELID2-SDATETIME",
		 float filetime=10.0, float initialdelay=-1.0,
		 float startvoltage=0.0, float stopvoltage=0.0);
  
  static const size_t MaxStr = 64;

  /* Label to be used for naming the recordings. */
  const char *label() const { return Label.value(); };

  /* Set label for naming the recordings to label. */
  void setLabel(const char *label);

  /* Device identifier. */
  int deviceID() const { return ID.value(); };

  /* Set device identifier to id. */
  void setDeviceID(int id);

  /* Make device identifier only visible in admin mode. */
  void setDeviceIDAdmin();

  /* Add option to read device ID from a device. */
  void setDeviceIDDevice();

  /* Path on SD card where to store the data. */
  const char *path() const { return Path.value(); };

  /* Set path on SD card where to store the data to path. */
  void setPath(const char *path);

  /* File name to be used to save the recorded data. */
  const char *fileName() const { return FileName.value(); };

  /* Set name template to be used to save the recorded data to fname. */
  void setFileName(const char *fname);

  /* Replace LABEL and ID in path and filename by the respective strings. */
  void preparePaths();

  /* Replace LABEL and ID in path and filename by the respective strings.
     ID is taken from deviceid. */
  void preparePaths(const DeviceID &deviceid);

  /* Time in seconds the files will record data. */
  float fileTime() const { return FileTime.value(); };

  /* Set time the files will record data to time seconds. */
  void setFileTime(float time);

  /* Time in seconds until recording of data is started. */
  float initialDelay() const { return InitialDelay.value(); };

  /* Set initial delay to time seconds. */
  void setInitialDelay(float time);

  /* Minimum battery voltage required to start logging data. */
  float startVoltage() const { return StartVoltage.value(); };

  /* Set minimum battery voltage required to start logging data. */
  void setStartVoltage(float startvoltage);

  /* Minimum battery voltage required to start a new recording file. */
  float stopVoltage() const { return StopVoltage.value(); };

  /* Set minimum battery voltage required to start a new recording file. */
  void setStopVoltage(float stopvoltage);


protected:

  StringParameter<MaxStr> Label;
  NumberParameter<int> ID;
  StringParameter<MaxStr> Path;
  StringParameter<MaxStr> FileName;
  NumberParameter<float> FileTime;
  NumberParameter<float> InitialDelay;
  NumberParameter<float> StartVoltage;
  NumberParameter<float> StopVoltage;
  
};

#endif
