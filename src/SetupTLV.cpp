#include <SetupTLV.h>


bool R5SetupTLV(InputTDM &aidata, ControlTLV320ADC &ctlv, bool offs,
		const InputTDMSettings &aisettings) {
  Input::SOURCE source = aisettings.source();
  ControlTLV320ADC::IMPEDANCE impedance = ControlTLV320ADC::IMP_025;
  ControlTLV320ADC::COUPLING coupling = ControlTLV320ADC::DC_CPL;
  ctlv.begin();
  if (!ctlv.available()) {
    Serial.println("not available");
    return false;
  }
  uint8_t slot_offs = offs ? 4 : 0;
  ctlv.setRate(aidata, aisettings.rate());
  /*
  ControlTLV320ADC::HIGHPASS hp = ControlTLV320ADC::LOW_HP;
  if (aisettings.highpass() < 0.0001*aisettings.rate())
    hp = ControlTLV320ADC::CUSTOM_HP; // all pass
  else if (aisettings.highpass() < 0.001*aisettings.rate())
    hp = ControlTLV320ADC::LOW_HP;    // 0.00025*rate, 12Hz @ 48kHz sampling
  else if (aisettings.highpass() < 0.004*aisettings.rate())
    hp = ControlTLV320ADC::MED_HP;    // 0.002*rate, 96Hz @ 48kHz sampling
  else
    hp = ControlTLV320ADC::HIGH_HP;   // 0.008*rate, 384Hz @ 48kHz sampling
  ctlv.setFilters(ControlTLV320ADC::LINEAR, hp);
  */
  ctlv.setFilters(ControlTLV320ADC::LINEAR, ControlTLV320ADC::CUSTOM_HP,
  		  aisettings.highpass());
  ctlv.setBias(ControlTLV320ADC::BIAS_VREF);  // this does not fix the 40dB gain issue
  if (aidata.nchannels() < aisettings.nchannels()) {
    if (aisettings.nchannels() - aidata.nchannels() == 2) {
      ctlv.setupChannels(2, source, impedance, coupling, -1, slot_offs);
      Serial.println("configured for 2 channels");
    }
    else {
      ctlv.setupChannels(4, source, impedance, coupling, -1, slot_offs);
      Serial.println("configured for 4 channels");
    }
    ctlv.setSmoothGainChange(false);
    ctlv.setGainDecibel(aidata, aisettings.gainDecibel());
    ctlv.setupTDM(aidata);
  }
  else {
    // channels not recorded, but need to be configured to not corrupt TDM bus:
    ctlv.setupChannels(4, source, impedance, coupling, -1, slot_offs);
    ctlv.setupTDM();
    ctlv.powerdown();
    Serial.println("powered down");
  }
  return true;
}


void R5SetupTLVs(Input &aidata, const InputSettings &aisettings,
		 Device **controls, size_t ncontrols, Stream &stream) {
  InputTDM& inputdata = static_cast<InputTDM&>(aidata);
  ControlTLV320ADC **tlvs = reinterpret_cast<ControlTLV320ADC**>(controls);
  inputdata.clearChannels();
  aisettings.configure(&inputdata);
  const InputTDMSettings &aitdmsettings =
    static_cast<const InputTDMSettings&>(aisettings);
  for (size_t k=0; k<ncontrols; k++) {
    stream.printf("Setup TLV320ADC %d on %s address %02x for TDM bus %d data pin %c: ",
		  k, tlvs[k]->busStr(), tlvs[k]->address(),
		  tlvs[k]->TDMBus(), 'A' + tlvs[k]->TDMPin());
    R5SetupTLV(inputdata, *tlvs[k], k%2==1, aitdmsettings);
  }
  if (inputdata.nchannels() > 24)
    static_cast<InputTDM&>(aidata).setRoll(8);
  else
    static_cast<InputTDM&>(aidata).setRoll(0);
  if (aitdmsettings.reverseInputs())
    static_cast<InputTDM&>(aidata).setReverse(4);
  else
    static_cast<InputTDM&>(aidata).setReverse(1);
  stream.println();
}


void powerupTLVs(Device **controls, size_t ncontrols, int8_t shdnzpin) {
  if (shdnzpin >= 0) {
    pinMode(shdnzpin, OUTPUT);
    digitalWrite(shdnzpin, HIGH);
    delay(10);
  }
  ControlTLV320ADC **tlvs = reinterpret_cast<ControlTLV320ADC**>(controls);
  for (size_t k=0; k<ncontrols; k++)
    tlvs[k]->powerup();
}


void powerdownTLVs(Device **controls, size_t ncontrols, int8_t shdnzpin) {
  ControlTLV320ADC **tlvs = reinterpret_cast<ControlTLV320ADC**>(controls);
  for (size_t k=0; k<ncontrols; k++)
    tlvs[k]->powerdown();
  if (shdnzpin >= 0) {
    digitalWrite(shdnzpin, LOW);
    delay(10);
  }
}
