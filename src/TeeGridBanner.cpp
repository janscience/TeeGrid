#include <MicroConfigBanner.h>
#include <TeeRecBanner.h>
#include <TeeGridBanner.h>


void printTeeGridBanner(const char *software, Stream &stream) {
  stream.println("\n========================================================");
  // Generated with figlet http://www.figlet.org
  stream.println(R"( _____          ____      _     _ )");
  stream.println(R"(|_   _|__  ___ / ___|_ __(_) __| |)");
  stream.println(R"(  | |/ _ \/ _ \ |  _| '__| |/ _` |)");
  stream.println(R"(  | |  __/  __/ |_| | |  | | (_| |)");
  stream.println(R"(  |_|\___|\___|\____|_|  |_|\__,_|)");
  stream.println();
  if (software != NULL) {
    if (strlen(software) > 7 && strncmp(software, "TeeGrid", 7) == 0)
      software = software + 8;
    stream.print(software);
    stream.print(" ");
  }
  stream.println("by ThunderLab");
  stream.print("based on ");
  stream.println(TEEGRID_SOFTWARE);
  stream.print("     and ");
  stream.println(TEEREC_SOFTWARE);
  stream.print("     and ");
  stream.println(MICROCONFIG_SOFTWARE);
  stream.println("--------------------------------------------------------");
  stream.println();
}
