#ifndef CANFD_h
#define CANFD_h

#include <Arduino.h>
#include <FlexCAN_T4.h>
#include <Blink.h>
#include <RTClock.h>
#include <TeensyBoard.h>


#ifdef TEENSY4
// CANFD is only supported on Teensy 4


class CANFD {
  
public:

  CANFD(uint8_t in_pin, uint8_t out_pin,
	int8_t shutdown_pin=-1, int8_t standby_pin=-1);

  void begin();

  void setBlink(Blink &blink);
  void setRTClock(RTClock &clock);
  
  void powerDown();
  void powerUp();

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

  // Wait for maximum timeout ms and poll for a message with specific ID
  bool read(uint8_t id, unsigned int timeout=1000);

  // Write id without payload.
  bool write(uint8_t id);

  // Wait for maximum timeout ms and poll for a message with specific ID.
  // On success return payload in t.
  template<typename T>
  bool read(uint8_t id, T &t, unsigned int timeout=1000);

  // Write message with id and payload t.
  template<typename T>
  bool write(uint8_t id, const T &t);

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
  
};


template<typename T>
bool CANFD::read(uint8_t id, T &t, unsigned int timeout) {
  elapsedMillis timepassed = 0;
  CANFD_message_t msg;
  msg.id = 0;
  memset(msg.buf, 0, sizeof(msg.buf));
  while ((!Can.read(msg) || msg.id != id) &&
	 (timepassed < timeout || timeout == 0)) {
    delay(1);
    StatusLED->update();
  };
  if (msg.id == id) {
    size_t n = sizeof(T) <= sizeof(msg.buf) ? sizeof(T) : sizeof(msg.buf);
    memcpy((void *)&t, (void *)msg.buf, n);
    return true;
  }
  else
    return false;
}


template<typename T>
bool CANFD::write(uint8_t id, const T &t) {
  CANFD_message_t msg;
  msg.id = id;
  if (sizeof(T) <= 8) {
    msg.brs = false;
    msg.edl = false;
  }
  size_t n = sizeof(T) <= sizeof(msg.buf) ? sizeof(T) : sizeof(msg.buf);
  memcpy((void *)msg.buf, (void *)&t, n);
  return (Can.write(msg) == 1);
}


#endif

#endif
