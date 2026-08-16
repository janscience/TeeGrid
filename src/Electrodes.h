/*
  Electrodes - description of the electrode configuration.
  Created by Jan Benda, August 16th, 2026.
*/

#ifndef Electrodes_h
#define Electrodes_h


#include <MicroConfig.h>


class Electrodes : public Menu {

public:

  static const int NGeometries = 3;
  static const char *Geometries[NGeometries];

  static const int NMaterials = 3;
  static const char *Materials[NMaterials];

  Electrodes(Menu &menu, const char *geometry=Geometries[0],
	     float spacing=0.5,
	     const char *material=Materials[0],
	     float depth=0.0,
	     const char *description="");
  
  static const size_t MaxStr = 32;
  static const size_t MaxDescription = 64;

  /* Description of the geometry of electrode positions. */
  const char *geometry() const { return Geometry.value(); };

  /* Set description of the geometry of electrode positions. */
  void setGeometry(const char *geometry);

  /* Spacing between electrodes in meter. */
  float spacing() const { return Spacing.value(); };

  /* Set spacing between electrodes in meter. */
  void setSpacing(float spacing);

  /* Description of electrode material. */
  const char *material() const { return Material.value(); };

  /* Set description of  electrode material. */
  void setMaterial(const char *material);

  /* Depth of electrodes below water surface. */
  float depth() const { return Depth.value(); };

  /* Set depth of electrodes below water surface. */
  void setDepth(float depth);

  /* Optional additional description of electrode configuration. */
  const char *description() const { return Description.value(); };

  /* Set optional description of electrode configuration. */
  void setDescription(const char *description);


protected:

  StringParameter<MaxStr> Geometry;
  NumberParameter<float> Spacing;
  StringParameter<MaxStr> Material;
  NumberParameter<float> Depth;
  StringParameter<MaxDescription> Description;
  
};

#endif
