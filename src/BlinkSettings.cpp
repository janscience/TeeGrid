#include <BlinkSettings.h>


BlinkSettings::BlinkSettings(Menu &menu, bool randomblinks, float blinktimeout,
			     float lightthreshold) :
  Menu(menu, "LED Settings"),
  RandomBlinks(*this, "RandomBlinks", randomblinks),
  BlinkTimeout(*this, "BlinkTimeout", blinktimeout, 0.0, 1e8, "%.0f", "s"),
  LightThreshold(*this, "LightThreshold", lightthreshold, 0.0, 1e8, "%.0f", "lx") {
  BlinkTimeout.disable();
  LightThreshold.disable();
}


void BlinkSettings::setRandomBlinks(bool random) {
  RandomBlinks.setBoolValue(random);
}


void BlinkSettings::setBlinkTimeout(float time) {
  BlinkTimeout.setValue(time);
}


void BlinkSettings::setLightThreshold(float thresh) {
  LightThreshold.setValue(thresh);
}
