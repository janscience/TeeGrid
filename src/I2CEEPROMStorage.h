/*
  I2CEEPROMStorage - Access microchip EEPROMs via I2C bus
  Created by Jan Benda, August 15, 2026.

  Uses Rob Tillaart's I2C_EEPROM library,
  see https://github.com/RobTillaart/I2C_EEPROM for details.
*/

#ifndef I2CEEPROMStorage_h
#define I2CEEPROMStorage_h


#include <Wire.h>
#include <I2C_eeprom.h>
#include <Storage.h>


class I2CEEPROMStorage : public Storage {

 public:

  // Use chip with i2caddr on wire of size.
  I2CEEPROMStorage(uint8_t i2caddr, uint32_t size, TwoWire &wire=Wire);

  // Initialize and set optional write-protect pin.
  bool begin(uint8_t writeProtectPin=-1);

  // Size of storage in bytes.
  virtual uint16_t length();


protected:

  // Read len bytes from storage at idx into buffer at address dest.
  virtual void read(int idx, uint8_t *dest, size_t len);
  
  // Write a len bytes from buffer at address src to storage at idx.
  virtual void update(int idx, const uint8_t *src, size_t len);

  I2C_eeprom I2CEEPROM;

};


#endif
