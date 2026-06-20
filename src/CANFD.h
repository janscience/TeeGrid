#ifndef CANFD_h
#define CANFD_h

#include <Arduino.h>
#include <FlexCAN_T4.h>
#include <TeensyBoard.h>


#ifdef TEENSY4
// CANFD is only supported on Teensy 4


class CANFD {
  
public:

  CANFD(uint8_t in_pin, uint8_t out_pin,
	int8_t shutdown_pin=-1, int8_t standby_pin=-1);

  void begin();
  
  void powerDown();
  void powerUp();

  int id() const { return DeviceID; };
  int numDevices() const { return NumDevices; };

  // write CAN2.0 messages (brs = edl = false)
  virtual int write20(CANFD_message_t &msg);

  // wait for maximum timeout ms and poll for a message with specific ID
  bool read(CANFD_message_t &msg, unsigned int id, unsigned int timeout=1000);
  
  int detectDevices();
  int detectOtherDevices();
  int assignDevice();

  void setupControllerMBs();
  void setupRecorderMBs();

  void transmitTime();
  void receiveTime();

  void transmitGrid(const char gs[8]);
  void receiveGrid(char gs[8]);

  void transmitSamplingRate(int rate);
  int receiveSamplingRate();

  void transmitGain(float gain);
  float receiveGain();

  void transmitFileTime(float filetime);
  float receiveFileTime();

  void transmitStart();
  void receiveStart();

  void transmitEndFile();
  bool receiveEndFile();

  void setOutPin(uint8_t value);
  uint8_t readInPin();

  uint64_t events() { return Can.events(); };

  
protected:

  FlexCAN_T4FD<CAN3, RX_SIZE_16, TX_SIZE_8> Can;
  uint8_t InPin;
  uint8_t OutPin;
  int8_t ShutdownPin;
  int8_t StandbyPin;

  int DeviceID;
  int NumDevices;
  
};

#endif

#endif
