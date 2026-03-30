#include <SetupTLV.h>


bool R5SetupTLV(InputTDM &aidata, ControlTLV320ADC &ctlv, bool offs,
		const InputTDMSettings &aisettings) {
  ctlv.begin();
  if (!ctlv.available()) {
    Serial.println("not available");
    return false;
  }
  uint8_t slot_offs = offs ? 4 : 0;
  ctlv.setRate(aidata, aisettings.rate());
  ctlv.setFilters(ControlTLV320ADC::LINEAR, ControlTLV320ADC::LOW_HP);
  if (aidata.nchannels() < aisettings.nchannels()) {
    if (aisettings.nchannels() - aidata.nchannels() == 2) {
      ctlv.setupChannels(2, ControlTLV320ADC::SINGLE_ENDED_INPUT,
                         ControlTLV320ADC::IMP_025, ControlTLV320ADC::AC_CPL,
			 -1, slot_offs);
      Serial.println("configured for 2 channels");
    }
    else {
      ctlv.setupChannels(4, ControlTLV320ADC::SINGLE_ENDED_INPUT,
                         ControlTLV320ADC::IMP_025, ControlTLV320ADC::AC_CPL,
			 -1, slot_offs);
      Serial.println("configured for 4 channels");
    }
    ctlv.setSmoothGainChange(false);
    ctlv.setGainDecibel(aidata, aisettings.gainDecibel());
    ctlv.setupTDM(aidata);
  }
  else {
    // channels not recorded, but need to be configured to not corrupt TDM bus:
    ctlv.setupChannels(4, ControlTLV320ADC::SINGLE_ENDED_INPUT,
		       ControlTLV320ADC::IMP_025, ControlTLV320ADC::AC_CPL,
		       -1, slot_offs);
    ctlv.setupTDM(aidata);
    ctlv.powerdown();
    Serial.println("powered down");
  }
  return true;
}


void R5SetupTLVs(Input &aidata, const InputSettings &aisettings,
		 Device **controls, size_t ncontrols, Stream &stream) {
  aidata.clearChannels();
  ControlTLV320ADC **tlvs = reinterpret_cast<ControlTLV320ADC**>(controls);
  aisettings.configure(&aidata);
  for (size_t k=0; k<ncontrols; k++) {
    stream.printf("Setup TLV320ADC %d on TDM %d: ", k, tlvs[k]->TDMBus());
    R5SetupTLV(static_cast<InputTDM&>(aidata),
	       static_cast<ControlTLV320ADC&>(*tlvs[k]), k%2==1,
	       static_cast<const InputTDMSettings&>(aisettings));
  }
  stream.println();
}


void powerdownTLVs(Device **controls, size_t ncontrols) {
  ControlTLV320ADC **tlvs = reinterpret_cast<ControlTLV320ADC**>(controls);
  for (size_t k=0; k<ncontrols; k++) {
    ControlTLV320ADC &tlv = static_cast<ControlTLV320ADC&>(*tlvs[k]);
    tlv.powerdown();
  }
}
