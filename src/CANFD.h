#ifndef CANFD_h
#define CANFD_h

#include <Arduino.h>
#include <FlexCAN_T4.h>
#include <Blink.h>
#include <RTClock.h>
#include <TeensyBoard.h>
#include <Storage.h>


#ifdef TEENSY4
// CANFD is only supported on Teensy 4


class CANFD : public Storage {
  
public:

  CANFD(uint8_t in_pin, uint8_t out_pin,
	int8_t shutdown_pin=-1, int8_t standby_pin=-1);

  void begin();

  void setBlink(Blink &blink);
  void setRTClock(RTClock &clock);
  
  void powerDown();
  void powerUp();

  // Size of storage in bytes.
  virtual uint16_t length();

  void setTimeout(unsigned int timeout);

  // Wait for maximum timeout ms and poll for a message with specific ID
  bool read(uint8_t id, unsigned int timeout=1000);

  // Write id without payload.
  bool write(uint8_t id);

  int id() const { return DeviceID; };
  int numDevices() const { return NumDevices; };
  
  int detectDevices();
  int assignDevice();

  //void setupControllerMBs();
  //void setupRecorderMBs();

  void transmitTime();
  void receiveTime();

  void transmitLabel(const char label[64]);
  void receiveLabel(char label[64]);

  void transmitFileName(const char filename[64]);
  void receiveFileName(char filename[64]);

  void transmitPath(const char path[64]);
  void receivePath(char path[64]);

  void transmitSamplingRate(int rate);
  int receiveSamplingRate();

  void transmitGain(float gain);
  float receiveGain();

  void transmitFileTime(float filetime);
  float receiveFileTime();

  void transmitSensorsInterval(float sensorsinterval);
  float receiveSensorsInterval();

  void transmitStart();
  void receiveStart();

  void transmitEndFile();
  bool receiveEndFile();

  uint64_t events() { return Can.events(); };

  
protected:

  // Read len bytes from storage at idx into buffer at address dest.
  virtual int read(unsigned int idx, uint8_t *dest, size_t len);
  
  // Write len bytes from buffer at address src to storage at idx.
  virtual int update(unsigned int idx, const uint8_t *src, size_t len);

  void setOutPin(uint8_t value);
  uint8_t readInPin();

  FlexCAN_T4FD<CAN3, RX_SIZE_16, TX_SIZE_8> Can;
  uint8_t InPin;
  uint8_t OutPin;
  int8_t ShutdownPin;
  int8_t StandbyPin;

  int DeviceID;
  int NumDevices;

  Blink *StatusLED;
  RTClock *Clock;

  unsigned int Timeout;
  
};


#endif

#endif
