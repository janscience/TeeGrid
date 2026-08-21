#include <CANFD.h>


#ifdef TEENSY4


#define CAN_ID_CONFIG_MODE   0x01
#define CAN_ID_CONFIG_ID     0x02
#define CAN_ID_CONFIG_VALUE  0x03

#define CAN_ID_CLEAR_DEVICES 0x05
#define CAN_ID_FIND_DEVICES  0x06
#define CAN_ID_REPORT_DEVICE 0x07
#define CAN_ID_GOT_DEVICES   0x08

#define CAN_ID_SET_TIME             0x10
#define CAN_ID_SET_LABEL            0x11
#define CAN_ID_SET_FILENAME         0x12
#define CAN_ID_SET_PATH             0x13
#define CAN_ID_SET_RATE             0x14
#define CAN_ID_SET_GAIN             0x15
#define CAN_ID_SET_FILE_TIME        0x16
#define CAN_ID_SET_SENSORS_INTERVAL 0x17

#define CAN_ID_START_REC     0x20
#define CAN_ID_END_FILE      0x21


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
  // Can.setRegions(32); this puts messages into mailboxes, so that we don not se them?
  CANFD_timings_t config;
  config.clock = CLK_24MHz;
  config.baudrate = 500000;
  config.baudrateFD = 2000000;
  config.propdelay = 190;
  config.bus_length = 1;
  config.sample = 70;
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
  msg.id = 0;
  memset(msg.buf, 0, sizeof(msg.buf));
  while ((!Can.read(msg) || msg.id != idx) &&
	 (timepassed < Timeout || Timeout == 0)) {
    delay(1);
    StatusLED->update();
  };
  if (msg.id == idx) {
    size_t n = len <= sizeof(msg.buf) ? len : sizeof(msg.buf);
    memcpy((void *)dest, (void *)msg.buf, n);
    Serial.printf("\nget %d %d %d %d ", msg.brs, msg.edl, len, n);
    for (size_t k=0; k<20; k++) {
      char c = (char)(msg.buf[k]);
      if (msg.buf[k] < 32)
	Serial.printf("#%02x", msg.buf[k]);
      else
	Serial.print(c);
    }
    Serial.println();
    return n;
  }
  else
    return -1;
}


int CANFD::update(unsigned int idx, const uint8_t *src, size_t len) {
  CANFD_message_t msg;
  msg.id = idx;
  if (len <= 8) {
    msg.brs = false;
    msg.edl = false;
  }
  else {
    msg.brs = true;
    msg.edl = true;
  }
  size_t n = len <= sizeof(msg.buf) ? len : sizeof(msg.buf);
  memcpy((void *)msg.buf, (void *)src, n);
  int r = Can.write(msg);
  Serial.printf("\nupdate %d %d %d %d ", msg.brs, msg.edl, len, n);
  for (size_t k=0; k<20; k++) {
    char c = (char)(msg.buf[k]);
    if (msg.buf[k] < 32)
      Serial.printf("#%02x", msg.buf[k]);
    else
      Serial.print(c);
  }
  Serial.println();
  if (r == 1)
    return n;
  else
    return -1;
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
  Serial.printf("sent time %ul: ", t);
  Clock->print();
  StatusLED->delay(100);
}


void CANFD::receiveTime() {
  time_t t = 0;
  Serial.println("wait for time message");
  Timeout = 1000;
  if (!get(CAN_ID_SET_TIME, t))
    return;
  Clock->set(t);
  Serial.printf("  received time %ul: ", t);
  Clock->print();
}


void CANFD::transmitLabel(const char label[64]) {
  put(CAN_ID_SET_LABEL, label);
  Serial.printf("sent label \"%s\"\n", label);
  StatusLED->delay(100);
}


void CANFD::receiveLabel(char label[64]) {
  Serial.println("wait for label message");
  Timeout = 1000;
  if (get(CAN_ID_SET_LABEL, label) > strlen(label))
    Serial.printf("  got label \"%s\"\n", label);
}


void CANFD::transmitFileName(const char filename[64]) {
  put(CAN_ID_SET_FILENAME, filename);
  Serial.printf("sent filename \"%s\"\n", filename);
  StatusLED->delay(100);
}


void CANFD::receiveFileName(char filename[64]) {
  Serial.println("wait for filename message");
  Timeout = 1000;
  if (get(CAN_ID_SET_FILENAME, filename) > strlen(filename))
    Serial.printf("  got filename \"%s\"\n", filename);
}


void CANFD::transmitPath(const char path[64]) {
  put(CAN_ID_SET_PATH, path);
  Serial.printf("sent path \"%s\"\n", path);
  StatusLED->delay(100);
}


void CANFD::receivePath(char path[64]) {
  Serial.println("wait for path message");
  Timeout = 1000;
  if (get(CAN_ID_SET_PATH, path) < strlen(path))
    Serial.printf("  got path \"%s\"\n", path);
}


void CANFD::transmitSamplingRate(int rate) {
  put(CAN_ID_SET_RATE, rate);
  Serial.printf("sent sampling rate %dHz\n", rate);
  StatusLED->delay(100);
}


int CANFD::receiveSamplingRate() {
  int rate = 0;
  Serial.println("wait for sampling rate message");
  Timeout = 1000;
  if (get(CAN_ID_SET_RATE, rate) == sizeof(int))
    Serial.printf("  got %dHz sampling rate\n", rate);
  return rate;
}


void CANFD::transmitGain(float gain) {
  put(CAN_ID_SET_GAIN, gain);
  Serial.printf("sent gain %.1fdB\n", gain);
  StatusLED->delay(100);
}


float CANFD::receiveGain() {
  float gain = -1000.0;
  Serial.println("wait for gain message");
  Timeout = 1000;
  if (get(CAN_ID_SET_GAIN, gain) == sizeof(float))
    Serial.printf("  got gain of %.1fdB\n", gain);
  return gain;
}


void CANFD::transmitFileTime(float filetime) {
  put(CAN_ID_SET_FILE_TIME, filetime);
  Serial.printf("sent file time %.0fs\n", filetime);
  StatusLED->delay(100);
}


float CANFD::receiveFileTime() {
  float filetime = 0.0;
  Serial.println("wait for file time message");
  Timeout = 1000;
  if (get(CAN_ID_SET_FILE_TIME, filetime) == sizeof(float))
    Serial.printf("  got file time of %.0fs\n", filetime);
  return filetime;
}


void CANFD::transmitSensorsInterval(float sensorsinterval) {
  put(CAN_ID_SET_SENSORS_INTERVAL, sensorsinterval);
  Serial.printf("sent sensors interval %.0fs\n", sensorsinterval);
  StatusLED->delay(100);
}


float CANFD::receiveSensorsInterval() {
  float sensorsinterval = 0.0;
  Serial.println("wait for sensors interval message");
  Timeout = 1000;
  if (get(CAN_ID_SET_SENSORS_INTERVAL, sensorsinterval) == sizeof(float))
    Serial.printf("  got sensors interval of %.0fs\n", sensorsinterval);
  return sensorsinterval;
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
