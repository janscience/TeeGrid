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


bool R40SetupPCM(InputTDM &tdm, ControlPCM186x &cpcm, bool offs,
		 float pregain, const InputTDMSettings &aisettings,
		 ControlPCM186x **pcm);

bool R4SetupPCM(InputTDM &tdm, ControlPCM186x &cpcm, bool offs,
		uint32_t rate, int nchannels, float gain,
		ControlPCM186x **pcm);
bool R4SetupPCM(InputTDM &tdm, ControlPCM186x &cpcm, bool offs,
		const InputTDMSettings &aisettings, ControlPCM186x **pcm);


#endif
