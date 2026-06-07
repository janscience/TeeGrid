#ifndef CANFD_h
#define CANFD_h

#include <Arduino.h>
#include <FlexCAN_T4.h>
#include <TeensyBoard.h>


#ifdef TEENSY4
// CANFD is only supported on Teensy 4


class CANFD {
  
public:

  CANFD(uint8_t up_pin, uint8_t down_pin,
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

  void sendTime();
  void receiveTime();

  void sendGrid(const char gs[8]);
  void receiveGrid(char gs[8]);

  void sendSamplingRate(int rate);
  int receiveSamplingRate();

  void sendGain(float gain);
  float receiveGain();

  void sendFileTime(float filetime);
  float receiveFileTime();

  void sendStart();
  void receiveStart();

  void sendEndFile();
  bool receiveEndFile();

  uint64_t events() { return Can.events(); };

  
protected:

  FlexCAN_T4FD<CAN3, RX_SIZE_16, TX_SIZE_8> Can;
  uint8_t UpPin;
  uint8_t DownPin;
  int8_t ShutdownPin;
  int8_t StandbyPin;

  int DeviceID;
  int NumDevices;
  
};

#endif

#endif
