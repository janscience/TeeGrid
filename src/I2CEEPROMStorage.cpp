#include <I2CEEPROMStorage.h>


I2CEEPROMStorage::I2CEEPROMStorage(uint8_t i2caddr, uint32_t size,
				   TwoWire &wire) :
  I2CEEPROM(i2caddr, size, &wire) {
}


bool I2CEEPROMStorage::begin(uint8_t writeProtectPin) {
  return I2CEEPROM.begin(writeProtectPin);
}


uint16_t I2CEEPROMStorage::length() {
  return I2CEEPROM.getDeviceSize();
}


int I2CEEPROMStorage::read(unsigned int idx, uint8_t *dest, size_t len) {
  return I2CEEPROM.readBlock(idx, dest, len);
}

  
int I2CEEPROMStorage::update(unsigned int idx, const uint8_t *src, size_t len) {
  return I2CEEPROM.updateBlock(idx, const_cast<uint8_t*>(src), len);
}

