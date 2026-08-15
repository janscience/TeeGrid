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


void I2CEEPROMStorage::read(int idx, uint8_t *dest, size_t len) {
  I2CEEPROM.readBlock(idx, dest, len);
}

  
void I2CEEPROMStorage::update(int idx, const uint8_t *src, size_t len) {
  I2CEEPROM.updateBlock(idx, const_cast<uint8_t*>(src), len);
}

