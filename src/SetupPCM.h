/*
  SetupPCM - Setup PCM186x chips for specific channels of the 
  Teensy_Amp 4.x PCBs.
  Created by Jan Benda, Octoner 21th, 2023.
*/

#ifndef SetupPCM_h
#define SetupPCM_h

#include <ControlPCM186x.h>
#include <InputTDM.h>
#include <InputTDMSettings.h>


bool R40SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		 const InputTDMSettings &aisettings);

// This variant is still in R41-CAN-recorder-controller.ino,
// but should be changed for the second variant taking aisettings:
bool R4SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		uint32_t rate, int nchannels, float gain);
bool R4SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		const InputTDMSettings &aisettings);
void R4SetupPCMs(InputTDM &aidata, ControlPCM186x **pcms, size_t ncontrols,
		 const InputTDMSettings &aisettings, Stream &stream=Serial);


#endif
