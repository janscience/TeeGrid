#include <Electrodes.h>


const char *Electrodes::Geometries[NGeometries] = {
  "line", "grid", "cube" };

const char *Electrodes::Materials[NMaterials] = {
  "stainless steel", "copper", "carbon" };


Electrodes::Electrodes(Menu &menu, const char *geometry,
		       float spacing, const char *material,
		       float depth, const char *description) :
  Menu(menu, "Electrodes"),
  Geometry(*this, "Geometry", geometry, Geometries, NGeometries, Admin),
  Spacing(*this, "Spacing", spacing, 0.0, 10.0, "%.0f", "m", "cm", Admin),
  Material(*this, "Material", material, Materials, NMaterials, Admin),
  Depth(*this, "Depth", depth, 0.0, 100.0, "%.0f", "m", "cm"),
  Description(*this, "Description", description) {
}


void Electrodes::setGeometry(const char *geometry) {
  Geometry.setValue(geometry);
}


void Electrodes::setSpacing(float spacing) {
  Spacing.setValue(spacing);
}


void Electrodes::setMaterial(const char *material) {
  Material.setValue(material);
}


void Electrodes::setDepth(float depth) {
  Depth.setValue(depth);
}


void Electrodes::setDescription(const char *description) {
  Description.setValue(description);
}

