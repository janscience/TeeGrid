#include <SetupPCM.h>


bool R40SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		 const InputTDMSettings &aisettings) {
  cpcm.begin();
  bool r = cpcm.setMicBias(false, true);
  if (!r) {
    Serial.println("not available");
    return false;
  }
  cpcm.setRate(aidata, aisettings.rate());
  if (aidata.nchannels() < aisettings.nchannels()) {
    if (aisettings.nchannels() - aidata.nchannels() == 2) {
      if (aisettings.pregain() == 1.0) {
        cpcm.setupTDM(aidata, ControlPCM186x::CH3L, ControlPCM186x::CH3R,
	              offs, ControlPCM186x::INVERTED);
        Serial.println("configured for 2 channels without preamplifier");
      }
      else {
        cpcm.setupTDM(aidata, ControlPCM186x::CH1L, ControlPCM186x::CH1R,
	              offs, ControlPCM186x::INVERTED);
        Serial.printf("configured for 2 channels with preamplifier x%.0f\n",
		      aisettings.pregain());
      }
    }
    else {
      if (aisettings.pregain() == 1.0) {
        cpcm.setupTDM(aidata, ControlPCM186x::CH3L, ControlPCM186x::CH3R,
                      ControlPCM186x::CH4L, ControlPCM186x::CH4R,
		      offs, ControlPCM186x::INVERTED);
        Serial.println("configured for 4 channels without preamplifier");
      }
      else {
        cpcm.setupTDM(aidata, ControlPCM186x::CH1L, ControlPCM186x::CH1R,
                      ControlPCM186x::CH2L, ControlPCM186x::CH2R,
		      offs, ControlPCM186x::INVERTED);
        Serial.printf("configured for 4 channels with preamplifier x%.0f\n",
		      aisettings.pregain());
      }
    }
    cpcm.setSmoothGainChange(false);
    cpcm.setGain(aisettings.gain());
    cpcm.setFilters(ControlPCM186x::FIR, false);
  }
  else {
    // channels not recorded, but need to be configured to not corupt TDM bus:
    cpcm.setupTDM(ControlPCM186x::CH1L, ControlPCM186x::CH1R, offs);
    cpcm.powerdown();
    Serial.println("powered down");
  }
  return true;
}


bool R4SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		uint32_t rate, int nchannels, float gain) {
  cpcm.begin();
  bool r = cpcm.setMicBias(false, true);
  if (!r) {
    Serial.println("not available");
    return false;
  }
  cpcm.setRate(aidata, rate);
  if (aidata.nchannels() < nchannels) {
    if (nchannels - aidata.nchannels() == 2) {
      cpcm.setupTDM(aidata, ControlPCM186x::CH2L, ControlPCM186x::CH2R,
                    offs, ControlPCM186x::INVERTED);
      Serial.println("configured for 2 channels");
    }
    else {
      cpcm.setupTDM(aidata, ControlPCM186x::CH2L, ControlPCM186x::CH2R,
                    ControlPCM186x::CH3L, ControlPCM186x::CH3R,
                    offs, ControlPCM186x::INVERTED);
      Serial.println("configured for 4 channels");
    }
    cpcm.setSmoothGainChange(false);
    cpcm.setGain(gain);
    cpcm.setFilters(ControlPCM186x::FIR, false);
  }
  else {
    // channels not recorded, but need to be configured to not corupt TDM bus:
    cpcm.setupTDM(ControlPCM186x::CH2L, ControlPCM186x::CH2R, offs);
    cpcm.powerdown();
    Serial.println("powered down");
  }
  return true;
}


bool R4SetupPCM(InputTDM &aidata, ControlPCM186x &cpcm, bool offs,
		const InputTDMSettings &aisettings) {
  return R4SetupPCM(aidata, cpcm, offs, aisettings.rate(),
		    aisettings.nchannels(), aisettings.gain());
}


void R4SetupPCMs(Input &aidata, const InputSettings &aisettings,
		 Device **controls, size_t ncontrols, Stream &stream) {
  aidata.clearChannels();
  ControlPCM186x **pcms = reinterpret_cast<ControlPCM186x**>(controls);
  static_cast<InputTDM&>(aidata).setSwapLR();
  for (size_t k=0; k<ncontrols; k++) {
    stream.printf("Setup PCM186x %d on TDM %d: ", k, pcms[k]->TDMBus());
    R4SetupPCM(static_cast<InputTDM&>(aidata),
	       static_cast<ControlPCM186x&>(*pcms[k]), k%2==1,
	       static_cast<const InputTDMSettings&>(aisettings));
  }
  stream.println();
}

