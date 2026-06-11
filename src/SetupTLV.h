/*
  SetupTLV - Setup TLV320ADC chips for specific channels of the 
  Teensy_Amp 5.x PCBs.
  Created by Jan Benda, March 24th, 2026.
*/

#ifndef SetupTLV_h
#define SetupTLV_h

#include <ControlTLV320ADC.h>
#include <InputTDM.h>
#include <InputTDMSettings.h>


bool R5SetupTLV(InputTDM &aidata, ControlTLV320ADC &ctlv, bool offs,
		const InputTDMSettings &aisettings);
void R5SetupTLVs(Input &aidata, const InputSettings &aisettings,
		 Device **controls, size_t ncontrols,
		 Stream &stream=Serial);
void powerupTLVs(Device **controls, size_t ncontrols, int8_t shdnzpin=-1);
void powerdownTLVs(Device **controls, size_t ncontrols, int8_t shdnzpin=-1);


#endif
