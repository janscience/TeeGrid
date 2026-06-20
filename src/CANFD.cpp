#include <CANFD.h>
#include <RTClock.h>
#include <Blink.h>

#ifdef TEENSY4

#define CAN_ID_CLEAR_DEVICES 0x01
#define CAN_ID_FIND_DEVICES  0x02
#define CAN_ID_REPORT_DEVICE 0x03
#define CAN_ID_GOT_DEVICES   0x04

#define CAN_ID_SET_DATE      0x0A
#define CAN_ID_SET_TIME      0x0B
#define CAN_ID_SET_GRID      0x0C
#define CAN_ID_SET_RATE      0x0D
#define CAN_ID_SET_GAIN      0x0E
#define CAN_ID_SET_FILE_TIME 0x0F

#define CAN_ID_START_REC     0x10
#define CAN_ID_END_FILE      0x11


extern RTClock rtclock;
extern Blink blink;


CANFD::CANFD(uint8_t in_pin, uint8_t out_pin,
	     int8_t shutdown_pin, int8_t standby_pin) :
  InPin(in_pin),
  OutPin(out_pin),
  ShutdownPin(shutdown_pin),
  StandbyPin(standby_pin),
  DeviceID(0),
  NumDevices(0) {
}


void CANFD::begin() {
  pinMode(InPin, INPUT);
  pinMode(OutPin, OUTPUT);
  digitalWrite(OutPin, LOW);
  if (ShutdownPin >= 0) {
    pinMode(ShutdownPin, OUTPUT);
    digitalWrite(ShutdownPin, LOW);
  }
  if (StandbyPin >= 0) {
    pinMode(StandbyPin, OUTPUT);
    digitalWrite(StandbyPin, LOW);
  }
  Can.begin();
  CANFD_timings_t config;
  config.clock = CLK_24MHz;
  config.baudrate = 500000;
  config.baudrateFD = 2000000;
  config.propdelay = 190;
  config.bus_length = 1;
  config.sample = 70;
  Can.setBaudRate(config);
  
}


void CANFD::powerDown() {
  if (ShutdownPin >= 0)
    digitalWrite(ShutdownPin, HIGH);
}


void CANFD::powerUp() {
  if (ShutdownPin >= 0)
    digitalWrite(ShutdownPin, LOW);
}


int CANFD::write20(CANFD_message_t &msg) {
  msg.brs = false;
  msg.edl = false;
  return Can.write(msg);
}


bool CANFD::read(CANFD_message_t &msg, unsigned int id,
		 unsigned int timeout) {
  elapsedMillis timepassed = 0;
  msg.id = 0;
  memset(msg.buf, 0, 8);
  while ((!Can.read(msg) || msg.id != id) &&
	 (timepassed < timeout || timeout == 0)) {
    delay(1);
    blink.update();
  };
  return (msg.id == id);
}

  
int CANFD::detectDevices() {
  CANFD_message_t msg;
  elapsedMillis timeout;

  Serial.println("Detect all devices:");
  digitalWrite(OutPin, HIGH);
  // clear device IDs:
  msg.id = CAN_ID_CLEAR_DEVICES;
  int r = write20(msg);
  Serial.printf("  write clear message, r=%d\n", r);
  delay(10);

  // assign device IDs:
  int id;
  for (id=1; ; id++) {
    Serial.printf("  check for ID=%d\n", id);
    msg.id = CAN_ID_FIND_DEVICES;
    *(int *)(&msg.buf[0]) = id;
    int r = write20(msg);
    Serial.printf("    write find message, r=%d\n", r);
    timeout = 0;
    msg.id = 0;
    while (!Can.read(msg) && timeout < 1000) {
      delay(10);
    };
    if (msg.id != CAN_ID_REPORT_DEVICE) {
      Serial.println("    no device responded");
      break;
    }
    int devid = *(int *)(&msg.buf[0]);
    Serial.printf("    device reported id %d\n", devid);
    if (devid != id)
      Serial.println("WARNING reported device id does not match expectation!");
    delay(10);
  }
  msg.id = CAN_ID_GOT_DEVICES;
  r = write20(msg);
  Serial.printf("  write got devices message, r=%d\n", r);
  digitalWrite(OutPin, LOW);
  delay(10);
  Serial.printf("  got %d devices\n", id-1);
  Serial.println();
  NumDevices = id - 1;
  return NumDevices;
}

  
int CANFD::detectOtherDevices() {
  CANFD_message_t msg;
  elapsedMillis timeout;

  Serial.println("Detect all devices:");
  digitalWrite(OutPin, HIGH);
  // clear device IDs:
  msg.id = CAN_ID_CLEAR_DEVICES;
  int r = write20(msg);
  Serial.printf("  write clear message, r=%d\n", r);
  delay(10);
  // set own ID:
  DeviceID = 1;

  // assign device IDs:
  int id;
  for (id=2; ; id++) {
    Serial.printf("  check for ID=%d\n", id);
    msg.id = CAN_ID_FIND_DEVICES;
    *(int *)(&msg.buf[0]) = id;
    int r = write20(msg);
    Serial.printf("    write find message, r=%d\n", r);
    timeout = 0;
    msg.id = 0;
    while (!Can.read(msg) && timeout < 1000) {
      delay(10);
    };
    if (msg.id != CAN_ID_REPORT_DEVICE) {
      Serial.println("    no device responded");
      break;
    }
    int devid = *(int *)(&msg.buf[0]);
    Serial.printf("    device reported id %d\n", devid);
    if (devid != id)
      Serial.println("WARNING reported device id does not match expectation!");
    delay(10);
  }
  msg.id = CAN_ID_GOT_DEVICES;
  r = write20(msg);
  Serial.printf("  write got devices message, r=%d\n", r);
  digitalWrite(OutPin, LOW);
  delay(10);
  Serial.printf("  got %d devices\n", id-1);
  Serial.println();
  NumDevices = id - 1;
  return NumDevices;
}


int CANFD::assignDevice() {
  CANFD_message_t msg;
  elapsedMillis timeout;

  Serial.println("Setting up device ID:");
  // clear device IDs:
  Serial.printf("  wait for clear devices command 0x%02x\n", CAN_ID_CLEAR_DEVICES);
  timeout = 0;
  msg.id = 0;
  while (!Can.read(msg) && timeout < 2000) {
    delay(10);
  };
  Serial.printf("  got message 0x%02x\n", msg.id);
  if (msg.id != CAN_ID_CLEAR_DEVICES) {
    Serial.println("  timeout");
    Serial.println();
    return 0;
  }
  DeviceID = 0;
  digitalWrite(OutPin, LOW);

  // assign device ID:
  while (true) {
    timeout = 0;
    msg.id = 0;
    Serial.printf("  wait for find devices command 0x%02x\n", CAN_ID_FIND_DEVICES);
    while ((!Can.read(msg) || msg.id == CAN_ID_REPORT_DEVICE) && timeout < 1000) {
      delay(10);
    };
    Serial.printf("    got message 0x%02x\n", msg.id);
    if (msg.id != CAN_ID_FIND_DEVICES)
      break;
    if (digitalRead(InPin)) {
      DeviceID = *(int *)(&msg.buf[0]);
      Serial.printf("    assign ID %d\n", DeviceID);
      msg.id = CAN_ID_REPORT_DEVICE;
      *(int *)(&msg.buf[0]) = DeviceID;
      int r = write20(msg);
      Serial.printf("    write report device message, r=%d\n", r);
      delay(10);
      digitalWrite(OutPin, HIGH);
      break;
    }
    else {
      Serial.println("    IO pin is low");
      delay(10);
    }
  }
  Serial.println("  wait for all devices to be detected");
  while (!Can.read(msg) || msg.id != CAN_ID_GOT_DEVICES) {
    delay(10);
  };
  digitalWrite(OutPin, LOW);
  Serial.println("  done");
  Serial.println();
  return DeviceID;
}


void CANFD::setupControllerMBs() {
  // Can.setMaxMB(10); only for CAN2.0
  int i;
  for (i=0; i<5; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, RX, STD);
  /*
  for (; i<10; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, TX, STD);
  */
  Can.setMBFilter(REJECT_ALL);
  Can.enableMBInterrupts();
  //Can.onReceive(MB0, canSniff);
  //Can.setMBFilter(MB0, 0x001);
  Can.mailboxStatus();
}


void setTime(const CANFD_message_t &msg) {
  time_t t = *(time_t *)(&msg.buf[0]);
  rtclock.set(t);
  rtclock.report();
}


void CANFD::setupRecorderMBs() {
  int i;
  for (i=0; i<5; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, RX, STD);
  /*
  for (; i<10; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, TX, STD);
  */
  Can.setMBFilter(REJECT_ALL);
  Can.enableMBInterrupts();
  Can.onReceive(MB0, setTime);
  Can.setMBFilter(MB0, CAN_ID_SET_TIME);
  Can.mailboxStatus();
}


void CANFD::transmitTime() {
  CANFD_message_t msg;
  time_t t = now();
  char ds[10];
  rtclock.date(ds, t, true);
  char ts[10];
  rtclock.time(ts, t, true);
  msg.id = CAN_ID_SET_DATE;
  memcpy((void *)msg.buf, (void *)ds, 8);
  Can.write(msg);
  delay(5);
  msg.id = CAN_ID_SET_TIME;
  memcpy((void *)msg.buf, (void *)ts, 6);
  Can.write(msg);
  Serial.printf("sent date %s and time %s\n", ds, ts);
}


void CANFD::receiveTime() {
  CANFD_message_t msg;
  if (!read(msg, CAN_ID_SET_DATE))
    return;
  char s[8];
  memcpy((void *)s, (void *)&msg.buf[0], 4);
  s[4] = '\0';
  int year = atoi(s);
  memcpy((void *)s, (void *)&msg.buf[4], 2);
  s[2] = '\0';
  int month = atoi(s);
  memcpy((void *)s, (void *)&msg.buf[6], 2);
  s[2] = '\0';
  int day = atoi(s);
  if (!read(msg, CAN_ID_SET_TIME))
    return;
  memcpy((void *)s, (void *)&msg.buf[0], 2);
  s[2] = '\0';
  int hour = atoi(s);
  memcpy((void *)s, (void *)&msg.buf[2], 2);
  s[2] = '\0';
  int min = atoi(s);
  memcpy((void *)s, (void *)&msg.buf[4], 2);
  s[2] = '\0';
  int sec = atoi(s);
  Serial.printf("received time %04d-%02d-02dT%02d:$02d:%02d\n",
		year, month, day, hour, min, sec);
  rtclock.set(year, month, day, hour, min, sec, false, false);
  rtclock.report();
}


void CANFD::transmitGrid(const char gs[8]) {
  CANFD_message_t msg;
  msg.id = CAN_ID_SET_GRID;
  strncpy((char *)msg.buf, gs, 7);
  Can.write(msg);
  Serial.printf("sent grid name %s\n", gs);
}


void CANFD::receiveGrid(char gs[8]) {
  CANFD_message_t msg;
  Serial.println("wait for grid name message");
  read(msg, CAN_ID_SET_GRID);
  memcpy((void *)&gs[0], (void *)&msg.buf[0], 8);
}


void CANFD::transmitSamplingRate(int rate) {
  CANFD_message_t msg;
  msg.id = CAN_ID_SET_RATE;
  *(int *)(&msg.buf[0]) = rate;
  Can.write(msg);
  Serial.printf("sent sampling rate %dHz\n", rate);
}


int CANFD::receiveSamplingRate() {
  CANFD_message_t msg;
  Serial.println("wait for sampling rate message");
  read(msg, CAN_ID_SET_RATE);
  int rate = *(int *)(&msg.buf[0]);
  return rate;
}


void CANFD::transmitGain(float gain) {
  CANFD_message_t msg;
  msg.id = CAN_ID_SET_GAIN;
  *(float *)(&msg.buf[0]) = gain;
  Can.write(msg);
  Serial.printf("sent gain %.1fdB\n", gain);
}


float CANFD::receiveGain() {
  CANFD_message_t msg;
  Serial.println("wait for gain message");
  float gain = -1000.0;
  if (read(msg, CAN_ID_SET_GAIN)) {
    gain = *(float *)(&msg.buf[0]);
    Serial.printf("  got %.1fdB\n", gain);
  }
  return gain;
}


void CANFD::transmitFileTime(float filetime) {
  CANFD_message_t msg;
  msg.id = CAN_ID_SET_FILE_TIME;
  *(float *)(&msg.buf[0]) = filetime;
  Can.write(msg);
  Serial.printf("sent file time %.0fs\n", filetime);
}


float CANFD::receiveFileTime() {
  CANFD_message_t msg;
  Serial.println("wait for file time message");
  read(msg, CAN_ID_SET_FILE_TIME);
  float filetime = *(float *)(&msg.buf[0]);
  Serial.printf("  got %.0fs\n", filetime);
  return filetime;
}


void CANFD::transmitStart() {
  CANFD_message_t msg;
  msg.id = CAN_ID_START_REC;
  Can.write(msg);
  Serial.println("sent start recording");
}


void CANFD::receiveStart() {
  CANFD_message_t msg;
  Serial.println("wait for start recording message");
  read(msg, CAN_ID_START_REC, 0);
}


void CANFD::transmitEndFile() {
  CANFD_message_t msg;
  msg.id = CAN_ID_END_FILE;
  *(int *)(&msg.buf[0]) = DeviceID;
  Can.write(msg);
  Serial.println("sent end file");
}


bool CANFD::receiveEndFile() {
  CANFD_message_t msg;
  elapsedMillis timepassed = 0;
  Serial.println("wait for end file messages");
  int ndevices = 0;
  for (int k=0; k<NumDevices; k++) {
    msg.id = 0;
    memset(msg.buf, 0, 8);
    while ((!Can.read(msg) || msg.id != CAN_ID_END_FILE) &&
	   timepassed < 1000) {
      delay(1);
    };
    if (msg.id != CAN_ID_END_FILE) {
      Serial.printf("no end file message from device %d\n", k);
      break;
    }
    //int devid = *(int *)(&msg.buf[0]);
    ndevices++;
  }
  Serial.printf("Got end of file message from %d devices\n", ndevices);
  return ((NumDevices > 0) && (ndevices == NumDevices));
}


void CANFD::setOutPin(uint8_t value) {
  digitalWrite(OutPin, value);
}


uint8_t CANFD::readInPin() {
  return digitalRead(InPin);
}


#endif
