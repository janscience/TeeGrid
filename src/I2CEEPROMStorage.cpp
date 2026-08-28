#include <I2CEEPROMStorage.h>


I2CEEPROMStorage::I2CEEPROMStorage(uint8_t i2caddr, uint32_t size,
				   TwoWire &wire) :
  I2CEEPROM(i2caddr, size, &wire),
  Available(false) {
}


bool I2CEEPROMStorage::begin(uint8_t writeProtectPin) {
  Available = I2CEEPROM.begin(writeProtectPin);
  return Available;
}


uint16_t I2CEEPROMStorage::length() {
  if (Available)
    return I2CEEPROM.getDeviceSize();
  else
    return 0;
}


int I2CEEPROMStorage::read(unsigned int idx, uint8_t *dest, size_t len) {
  if (!Available)
    return -1;
  return I2CEEPROM.readBlock(idx, dest, len);
}

  
int I2CEEPROMStorage::update(unsigned int idx, const uint8_t *src, size_t len) {
  if (!Available) {
    Serial.println("EEPROM not connected");
    return -1;
  }
  I2CEEPROM.updateBlock(idx, const_cast<uint8_t*>(src), len);
  return len;
}

