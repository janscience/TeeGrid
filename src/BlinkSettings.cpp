#include <BlinkSettings.h>


BlinkSettings::BlinkSettings(Menu &menu, bool randomblinks,
			     float blinktimeout, float synctimeout,
			     float lightthreshold) :
  Menu(menu, "LED Settings"),
  RandomBlinks(*this, "RandomBlinks", randomblinks),
  BlinkTimeout(*this, "BlinkTimeout", blinktimeout, 0.0, 1e8, "%.0f", "s"),
  SyncTimeout(*this, "SyncTimeout", synctimeout, 0.0, 1e8, "%.0f", "s"),
  LightThreshold(*this, "LightThreshold", lightthreshold, 0.0, 1e8, "%.0f", "lx") {
  BlinkTimeout.disable();
  SyncTimeout.disable();
  LightThreshold.disable();
}


void BlinkSettings::setRandomBlinks(bool random) {
  RandomBlinks.setBoolValue(random);
}


void BlinkSettings::setBlinkTimeout(float time) {
  BlinkTimeout.setValue(time);
}


void BlinkSettings::setSyncTimeout(float time) {
  SyncTimeout.setValue(time);
}


void BlinkSettings::setLightThreshold(float thresh) {
  LightThreshold.setValue(thresh);
}
