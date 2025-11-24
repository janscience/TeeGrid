/*
  BlinkSettings - settings for blinking LEDs.
  Created by Jan Benda, November 21th, 2025.
*/

#ifndef BlinkSettings_h
#define BlinkSettings_h


#include <MicroConfig.h>


class BlinkSettings : public Menu {

public:

  BlinkSettings(Menu &menu, bool randomblinks=false,
		float blinktimeout=0.0, float synctimeout=0.0,
		float lightthreshold=0.0);

  /* Whether LED should blink randomly and be stored to file. */
  bool randomBlinks() const { return RandomBlinks.value(); };

  /* Set whether LED should blink randomly. */
  void setRandomBlinks(bool random);

  /* Time in seconds after which the status LEDs are switched off. */
  float blinkTimeout() const { return BlinkTimeout.value(); };

  /* Set time after which the status LEDs are switched off to time seconds. */
  void setBlinkTimeout(float time);

  /* Time in seconds after which the synchronization LEDs are switched off. */
  float syncTimeout() const { return BlinkTimeout.value(); };

  /* Set time after which the synchronization LEDs are switched off
     to time seconds. */
  void setSyncTimeout(float time);
  
  /* Threshold in lux for turing of status and syn LEDs. */
  float lightThreshold() const { return LightThreshold.value(); };

  /* Set threshold for turing of LEDs to thresh lux. */
  void setLightThreshold(float thresh);


protected:

  BoolParameter RandomBlinks;
  NumberParameter<float> BlinkTimeout;
  NumberParameter<float> SyncTimeout;
  NumberParameter<float> LightThreshold;
  
};

#endif
