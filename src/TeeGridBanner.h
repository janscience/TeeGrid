/*
  TeeGridBanner - ASCII art banner for serial output.
  Created by Jan Benda, August 16th, 2024.
*/

#ifndef TeeGridBanner_h
#define TeeGridBanner_h


#include <Arduino.h>


#define TEEGRID_SOFTWARE "TeeGrid version 1.2.0"


void printTeeGridBanner(const char *software=NULL, Stream &stream=Serial);


#endif

