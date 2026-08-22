#include <CANFD.h>


#ifdef TEENSY4


#define CAN_ID_CONFIG_MODE   0x01
#define CAN_ID_CONFIG_ID     0x02
#define CAN_ID_CONFIG_VALUE  0x03
#define CAN_ID_SET_TIME      0x04

#define CAN_ID_CLEAR_DEVICES 0x05
#define CAN_ID_FIND_DEVICES  0x06
#define CAN_ID_REPORT_DEVICE 0x07
#define CAN_ID_GOT_DEVICES   0x08

#define CAN_ID_START_REC     0x10
#define CAN_ID_END_FILE      0x11


CANFD::CANFD(uint8_t in_pin, uint8_t out_pin,
	     int8_t shutdown_pin, int8_t standby_pin) :
  InPin(in_pin),
  OutPin(out_pin),
  ShutdownPin(shutdown_pin),
  StandbyPin(standby_pin),
  DeviceID(0),
  NumDevices(0),
  StatusLED(0),
  Clock(0),
  Timeout(1000) {
}


void CANFD::begin() {
  pinMode(InPin, INPUT);
  pinMode(OutPin, OUTPUT);
  setOutPin(LOW);
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
  config.bus_length = 1;     // maximum node-to-node distance in in meters
  config.propdelay = 150;    // TCAN330 total loop delay 135ns
  config.sample = 75;        // standard 75% sample point
  Can.setBaudRate(config);
}


void CANFD::setBlink(Blink &blink) {
  StatusLED = &blink;
}


void CANFD::setRTClock(RTClock &clock) {
  Clock = &clock;
}


void CANFD::powerDown() {
  if (ShutdownPin >= 0)
    digitalWrite(ShutdownPin, HIGH);
}


void CANFD::powerUp() {
  if (ShutdownPin >= 0)
    digitalWrite(ShutdownPin, LOW);
}


uint16_t CANFD::length() {
  return 0;
}


void CANFD::setTimeout(unsigned int timeout) {
  Timeout = timeout;
}


int CANFD::read(unsigned int idx, uint8_t *dest, size_t len) {
  elapsedMillis timepassed = 0;
  CANFD_message_t msg;
  size_t offs = 0;
  msg.id = 0;
  msg.len = 0;
  while (offs < len) {
    while ((!Can.read(msg) || msg.id != idx) &&
	   (timepassed < Timeout || Timeout == 0)) {
      delay(1);
      StatusLED->update();
    };
    if (msg.id == idx) {
      memcpy((void *)(dest + offs), (void *)msg.buf, msg.len);
      offs += msg.len;
    }
    else
      return -1;
  }
  return len;
}


int CANFD::update(unsigned int idx, const uint8_t *src, size_t len) {
  CANFD_message_t msg;
  msg.id = idx;
  msg.flags.extended = 0;
  msg.brs = 0;
  msg.edl = 0;
  size_t offs = 0;
  while (offs < len) {
    size_t n = len - offs > 8 ? 8 : len - offs;
    memcpy((void *)msg.buf, (void *)(src + offs), n);
    if (Can.write(msg))
      offs += n;
    else
      return -1;
    delay(100);
  }
  return len;
}


bool CANFD::write(uint8_t id) {
  CANFD_message_t msg;
  msg.id = id;
  msg.brs = false;
  msg.edl = false;
  return (Can.write(msg) == 1);
}


bool CANFD::read(uint8_t id, unsigned int timeout) {
  elapsedMillis timepassed = 0;
  CANFD_message_t msg;
  msg.id = 0;
  while ((!Can.read(msg) || msg.id != id) &&
	 (timepassed < timeout || timeout == 0)) {
    delay(1);
    StatusLED->update();
  };
  return (msg.id == id);
}

  
int CANFD::detectDevices() {
  Serial.println("Detect all devices:");
  StatusLED->clear();
  StatusLED->delay(500);
  DeviceID = 1;
  setOutPin(HIGH);
  // clear device IDs:
  write(CAN_ID_CLEAR_DEVICES);
  Serial.println("  wrote clear message");
  delay(10);

  // assign device IDs:
  int id;
  for (id=2; ; id++) {
    Serial.printf("  check for ID=%d\n", id);
    put(CAN_ID_FIND_DEVICES, id);
    int devid = -1;
    if (get(CAN_ID_REPORT_DEVICE, devid) <= 0) {
      Serial.println("    no device responded");
      break;
    }
    Serial.printf("    device reported id %d\n", devid);
    if (devid != id)
      Serial.println("WARNING reported device id does not match expectation!");
    StatusLED->blinkMultiple(devid);
    StatusLED->delay(1500);
  }
  StatusLED->delay(1000);
  NumDevices = id - 1;
  Serial.printf("  got %d devices\n", NumDevices);
  StatusLED->setMultiple(NumDevices);
  StatusLED->delay(2000);
  write(CAN_ID_GOT_DEVICES);
  Serial.println("  wrote got all devices message");
  setOutPin(LOW);
  Serial.println("  done");
  Serial.println();
  StatusLED->clear();
  StatusLED->blinkSingle(0, 2000);
  StatusLED->delay(2500);
  return NumDevices;
}


int CANFD::assignDevice() {
  Serial.println("Setting up device ID:");
  StatusLED->clear();
  DeviceID = -1;
  setOutPin(LOW);
  // clear device IDs:
  Serial.println("  wait for clear devices command");
  if (!read(CAN_ID_CLEAR_DEVICES, 0)) {
    Serial.println("  failed");
    Serial.println();
    return -1;
  }

  // assign device ID:
  while (true) {
    Serial.println("  wait for find devices command");
    int id;
    Timeout = 2000;
    if (get(CAN_ID_FIND_DEVICES, id) <= 0) {
      Serial.println("    timed out");
      return -1;
    }
    if (readInPin()) {
      DeviceID = id;
      Serial.printf("    assign ID %d\n", DeviceID);
      put(CAN_ID_REPORT_DEVICE, DeviceID);
      Serial.println("    wrote report device message");
      StatusLED->setMultiple(DeviceID);
      StatusLED->delay(1500);
      setOutPin(HIGH);
      break;
    }
    else {
      Serial.println("    IO pin is low");
      delay(10);
    }
  }
  Serial.println("  wait for all devices to be detected");
  read(CAN_ID_GOT_DEVICES, 0);
  setOutPin(LOW);
  Serial.println("  done");
  Serial.println();
  StatusLED->clear();
  StatusLED->blinkSingle(0, 2000);
  StatusLED->delay(2000);
  return DeviceID;
}


/*
void CANFD::setupControllerMBs() {
  // Can.setMaxMB(10); only for CAN2.0
  int i;
  for (i=0; i<5; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, RX, STD);
  //for (; i<10; i++)
  //  Can.setMB((FLEXCAN_MAILBOX)i, TX, STD);
  Can.setMBFilter(REJECT_ALL);
  Can.enableMBInterrupts();
  //Can.onReceive(MB0, canSniff);
  //Can.setMBFilter(MB0, 0x001);
  Can.mailboxStatus();
}

void setTime(const CANFD_message_t &msg) {
  time_t t = *(time_t *)(&msg.buf[0]);
  Clock->set(t);
  Clock->report();
}


void CANFD::setupRecorderMBs() {
  int i;
  for (i=0; i<5; i++)
    Can.setMB((FLEXCAN_MAILBOX)i, RX, STD);
  //for (; i<10; i++)
  //  Can.setMB((FLEXCAN_MAILBOX)i, TX, STD);
  Can.setMBFilter(REJECT_ALL);
  Can.enableMBInterrupts();
  Can.onReceive(MB0, setTime);
  Can.setMBFilter(MB0, CAN_ID_SET_TIME);
  Can.mailboxStatus();
}
*/

void CANFD::transmitTime() {
  time_t t = now();
  put(CAN_ID_SET_TIME, t);
  delay(1);
  Clock->set(t);
  Serial.printf("sent time %lu: ", t);
  Clock->print();
  StatusLED->delay(100);
}


void CANFD::receiveTime() {
  time_t t = 0;
  Serial.print("wait for time message");
  Timeout = 1000;
  if (!get(CAN_ID_SET_TIME, t)) {
    Serial.println(": failed");
    return;
  }
  Clock->set(t);
  Serial.printf("  received time %lu: ", t);
  Clock->print();
}


void CANFD::transmitStart() {
  write(CAN_ID_START_REC);
  Serial.println("sent start recording");
}


void CANFD::receiveStart() {
  Serial.println("wait for start recording message");
  read(CAN_ID_START_REC, 0);
}


void CANFD::transmitEndFile() {
  put(CAN_ID_END_FILE, DeviceID);
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
