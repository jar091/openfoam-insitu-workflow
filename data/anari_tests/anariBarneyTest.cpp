// Headless ANARI smoke test for Barney (CPU/Embree backend) and helide.
//
// Renders a triangle mesh (a tessellated torus + ground quad) and a structured
// regular volume to a PNG. With --mpi the program runs data-parallel: every
// MPI rank creates only its *own* part of the scene (one slab of the volume
// and one torus) on a barney device of subtype "mpi"; Barney composites the
// frame and rank 0 maps it and writes the PNG.
//
// Usage:
//   anariBarneyTest [--lib barney_cpu] [--out file.png] [--size W H]
//                   [--spp N] [--frames N] [--mpi] [--no-volume] [--no-mesh]
#include <anari/anari_cpp.hpp>
#include <anari/anari_cpp/ext/std.h>

#ifdef WITH_MPI
#include <mpi.h>
#endif

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

using namespace anari::std_types;

static int g_rank = 0;

static void statusFunc(const void *, ANARIDevice, ANARIObject, ANARIDataType,
    ANARIStatusSeverity severity, ANARIStatusCode, const char *message)
{
  const char *tag = nullptr;
  switch (severity) {
  case ANARI_SEVERITY_FATAL_ERROR: tag = "FATAL"; break;
  case ANARI_SEVERITY_ERROR: tag = "ERROR"; break;
  case ANARI_SEVERITY_WARNING: tag = "WARN "; break;
  case ANARI_SEVERITY_PERFORMANCE_WARNING: tag = "PERF "; break;
  default: return; // skip info/debug
  }
  fprintf(stderr, "[rank %d][%s] %s\n", g_rank, tag, message);
}

// Torus centred at c, major radius R, minor radius r, in the xz plane.
static void makeTorus(vec3 c, float R, float r, int nu, int nv,
    std::vector<vec3> &pos, std::vector<vec3> &nrm, std::vector<uvec3> &idx)
{
  const uint32_t base = (uint32_t)pos.size();
  for (int i = 0; i < nu; i++) {
    float u = 2.f * float(M_PI) * i / nu;
    for (int j = 0; j < nv; j++) {
      float v = 2.f * float(M_PI) * j / nv;
      vec3 n = {std::cos(u) * std::cos(v), std::sin(v), std::sin(u) * std::cos(v)};
      pos.push_back({c[0] + (R + r * std::cos(v)) * std::cos(u),
          c[1] + r * std::sin(v),
          c[2] + (R + r * std::cos(v)) * std::sin(u)});
      nrm.push_back(n);
    }
  }
  for (int i = 0; i < nu; i++)
    for (int j = 0; j < nv; j++) {
      uint32_t a = base + i * nv + j;
      uint32_t b = base + ((i + 1) % nu) * nv + j;
      uint32_t c2 = base + ((i + 1) % nu) * nv + (j + 1) % nv;
      uint32_t d = base + i * nv + (j + 1) % nv;
      idx.push_back({a, b, c2});
      idx.push_back({a, c2, d});
    }
}

int main(int argc, char **argv)
{
  std::string libName = "barney_cpu";
  std::string outFile = "anariBarneyTest.png";
  uvec2 size = {800, 600};
  int spp = 4, frames = 8;
  bool useMPI = false, withVolume = true, withMesh = true;

  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--lib" && i + 1 < argc) libName = argv[++i];
    else if (a == "--out" && i + 1 < argc) outFile = argv[++i];
    else if (a == "--size" && i + 2 < argc) {
      size[0] = std::atoi(argv[++i]);
      size[1] = std::atoi(argv[++i]);
    } else if (a == "--spp" && i + 1 < argc) spp = std::atoi(argv[++i]);
    else if (a == "--frames" && i + 1 < argc) frames = std::atoi(argv[++i]);
    else if (a == "--mpi") useMPI = true;
    else if (a == "--no-volume") withVolume = false;
    else if (a == "--no-mesh") withMesh = false;
  }

  int nRanks = 1;
#ifdef WITH_MPI
  if (useMPI) {
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_MULTIPLE, &provided);
    MPI_Comm_rank(MPI_COMM_WORLD, &g_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nRanks);
    if (g_rank == 0)
      printf("MPI thread level provided=%d (MULTIPLE=%d)\n", provided,
          MPI_THREAD_MULTIPLE);
  }
#else
  if (useMPI) {
    fprintf(stderr, "built without MPI\n");
    return 1;
  }
#endif

  auto t0 = std::chrono::steady_clock::now();
  anari::Library lib = anari::loadLibrary(libName.c_str(), statusFunc);
  if (!lib) {
    fprintf(stderr, "could not load ANARI library '%s'\n", libName.c_str());
    return 1;
  }
  anari::Device d = anari::newDevice(lib, useMPI ? "mpi" : "default");
  if (!d) {
    fprintf(stderr, "could not create device\n");
    return 1;
  }
#ifdef WITH_MPI
  MPI_Comm comm = MPI_COMM_WORLD;
  if (useMPI) {
    // Optional: hand our communicator to barney (otherwise it dups WORLD).
    uint64_t commPtr = (uint64_t)&comm;
    anari::setParameter(d, d, "pointer_to_mpi_communicator", commPtr);
  }
#endif
  anari::commitParameters(d, d);

  // ------------------------------------------------------------------
  // Global scene extent: x in [0, 2*nRanks] split into one slab per rank
  // ------------------------------------------------------------------
  const float slabW = 2.f;
  const float X = slabW * nRanks;

  std::vector<anari::Surface> surfaces;
  std::vector<anari::Volume> volumes;

  if (withMesh) {
    // each rank: one torus in its own slab (colour by rank)
    std::vector<vec3> pos, nrm;
    std::vector<uvec3> idx;
    makeTorus({slabW * (g_rank + 0.5f), 0.45f, 1.0f}, 0.6f, 0.18f, 64, 24,
        pos, nrm, idx);
    auto geom = anari::newObject<anari::Geometry>(d, "triangle");
    anari::setParameterArray1D(d, geom, "vertex.position", pos.data(), pos.size());
    anari::setParameterArray1D(d, geom, "vertex.normal", nrm.data(), nrm.size());
    anari::setParameterArray1D(d, geom, "primitive.index", idx.data(), idx.size());
    anari::commitParameters(d, geom);

    const vec3 palette[4] = {{0.9f, 0.3f, 0.2f}, {0.2f, 0.6f, 0.9f},
        {0.3f, 0.85f, 0.3f}, {0.9f, 0.8f, 0.2f}};
    auto mat = anari::newObject<anari::Material>(d, "matte");
    anari::setParameter(d, mat, "color", palette[g_rank % 4]);
    anari::commitParameters(d, mat);

    auto surf = anari::newObject<anari::Surface>(d);
    anari::setAndReleaseParameter(d, surf, "geometry", geom);
    anari::setAndReleaseParameter(d, surf, "material", mat);
    anari::commitParameters(d, surf);
    surfaces.push_back(surf);

    // ground quad (two triangles) under this rank's slab only
    vec3 gp[4] = {{slabW * g_rank, 0.f, -0.5f}, {slabW * (g_rank + 1), 0.f, -0.5f},
        {slabW * (g_rank + 1), 0.f, 3.0f}, {slabW * g_rank, 0.f, 3.0f}};
    uvec3 gi[2] = {{0, 1, 2}, {0, 2, 3}};
    auto ground = anari::newObject<anari::Geometry>(d, "triangle");
    anari::setParameterArray1D(d, ground, "vertex.position", gp, 4);
    anari::setParameterArray1D(d, ground, "primitive.index", gi, 2);
    anari::commitParameters(d, ground);
    auto gmat = anari::newObject<anari::Material>(d, "matte");
    anari::setParameter(d, gmat, "color", vec3{0.75f, 0.75f, 0.75f});
    anari::commitParameters(d, gmat);
    auto gsurf = anari::newObject<anari::Surface>(d);
    anari::setAndReleaseParameter(d, gsurf, "geometry", ground);
    anari::setAndReleaseParameter(d, gsurf, "material", gmat);
    anari::commitParameters(d, gsurf);
    surfaces.push_back(gsurf);
  }

  if (withVolume) {
    // Global logical grid: (N*nRanks) x N x N cells over [0,X]x[0.9,2.4]x[0.25,1.75];
    // each rank owns a slab plus one ghost sample on the +x side so that
    // trilinear interpolation is seamless across rank boundaries.
    const int N = 64;
    const float h = slabW / N;
    const int nxLocal = N + ((g_rank < nRanks - 1) ? 1 : 0);
    const int ny = int(1.5f / h) + 1, nz = ny;
    const vec3 origin = {slabW * g_rank, 0.9f, 0.25f};
    std::vector<float> data(size_t(nxLocal) * ny * nz);
    for (int k = 0; k < nz; k++)
      for (int j = 0; j < ny; j++)
        for (int i = 0; i < nxLocal; i++) {
          float x = origin[0] + i * h, y = origin[1] + j * h, z = origin[2] + k * h;
          // smooth "vortex tube" like blob along x
          float yc = 1.65f + 0.25f * std::sin(2.f * float(M_PI) * x / X * 1.5f);
          float zc = 1.0f;
          float rr = (y - yc) * (y - yc) + (z - zc) * (z - zc);
          float v = std::exp(-rr / 0.08f) * (0.6f + 0.4f * std::cos(4.f * x));
          data[(size_t(k) * ny + j) * nxLocal + i] = v;
        }
    auto field = anari::newObject<anari::SpatialField>(d, "structuredRegular");
    anari::setParameterArray3D(d, field, "data", data.data(), nxLocal, ny, nz);
    anari::setParameter(d, field, "origin", origin);
    anari::setParameter(d, field, "spacing", vec3{h, h, h});
    anari::commitParameters(d, field);

    std::vector<vec3> tfColor = {{0.05f, 0.1f, 0.6f}, {0.1f, 0.7f, 0.8f},
        {0.95f, 0.9f, 0.3f}, {0.9f, 0.2f, 0.1f}};
    std::vector<float> tfOpacity = {0.f, 0.05f, 0.4f, 0.9f};
    auto vol = anari::newObject<anari::Volume>(d, "transferFunction1D");
    anari::setAndReleaseParameter(d, vol, "value", field);
    anari::setParameterArray1D(d, vol, "color", tfColor.data(), tfColor.size());
    anari::setParameterArray1D(d, vol, "opacity", tfOpacity.data(), tfOpacity.size());
    const float valueRange[2] = {0.f, 1.f};
    anari::setParameter(d, vol, "valueRange", ANARI_FLOAT32_BOX1, valueRange);
    anari::setParameter(d, vol, "unitDistance", 0.05f);
    anari::commitParameters(d, vol);
    volumes.push_back(vol);
  }

  auto light = anari::newObject<anari::Light>(d, "directional");
  anari::setParameter(d, light, "direction", vec3{-0.3f, -1.f, 0.5f});
  anari::setParameter(d, light, "irradiance", 2.5f);
  anari::commitParameters(d, light);

  auto world = anari::newObject<anari::World>(d);
  if (!surfaces.empty())
    anari::setParameterArray1D(d, world, "surface", surfaces.data(), surfaces.size());
  if (!volumes.empty())
    anari::setParameterArray1D(d, world, "volume", volumes.data(), volumes.size());
  anari::setParameterArray1D(d, world, "light", &light, 1);
  for (auto s : surfaces) anari::release(d, s);
  for (auto v : volumes) anari::release(d, v);
  anari::release(d, light);
  anari::commitParameters(d, world);

  // Camera: identical on all ranks, sees the whole global scene.
  auto camera = anari::newObject<anari::Camera>(d, "perspective");
  vec3 target = {X * 0.5f, 0.9f, 1.f};
  vec3 eye = {X * 0.5f, 2.2f, -0.9f - 1.0f * X};
  vec3 dir = {target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]};
  anari::setParameter(d, camera, "aspect", float(size[0]) / float(size[1]));
  anari::setParameter(d, camera, "position", eye);
  anari::setParameter(d, camera, "direction", dir);
  anari::setParameter(d, camera, "up", vec3{0.f, 1.f, 0.f});
  anari::setParameter(d, camera, "fovy", float(M_PI) / 4.f);
  anari::commitParameters(d, camera);

  auto renderer = anari::newObject<anari::Renderer>(d, "default");
  anari::setParameter(d, renderer, "background", vec4{0.1f, 0.1f, 0.15f, 1.f});
  anari::setParameter(d, renderer, "ambientRadiance", 0.4f);
  anari::setParameter(d, renderer, "pixelSamples", spp);
  anari::commitParameters(d, renderer);

  auto frame = anari::newObject<anari::Frame>(d);
  anari::setParameter(d, frame, "size", size);
  anari::setParameter(d, frame, "channel.color", ANARI_UFIXED8_RGBA_SRGB);
  anari::setParameter(d, frame, "accumulation", true);
  anari::setAndReleaseParameter(d, frame, "renderer", renderer);
  anari::setAndReleaseParameter(d, frame, "camera", camera);
  anari::setAndReleaseParameter(d, frame, "world", world);
  anari::commitParameters(d, frame);

  auto t1 = std::chrono::steady_clock::now();
  double tFirst = 0.;
  for (int f = 0; f < frames; f++) {
    auto ts = std::chrono::steady_clock::now();
    anari::render(d, frame);
    anari::wait(d, frame);
    auto te = std::chrono::steady_clock::now();
    if (f == 0) tFirst = std::chrono::duration<double>(te - ts).count();
  }
  auto t2 = std::chrono::steady_clock::now();

  double setup = std::chrono::duration<double>(t1 - t0).count();
  double rtime = std::chrono::duration<double>(t2 - t1).count();

  if (g_rank == 0) {
    auto fb = anari::map<uint32_t>(d, frame, "channel.color");
    if (fb.data) {
      stbi_flip_vertically_on_write(1);
      stbi_write_png(outFile.c_str(), int(fb.width), int(fb.height), 4,
          fb.data, 4 * int(fb.width));
      printf("wrote %s (%ux%u)\n", outFile.c_str(), fb.width, fb.height);
    } else {
      fprintf(stderr, "map returned no data\n");
    }
    anari::unmap(d, frame, "channel.color");
    printf("lib=%s ranks=%d setup=%.3fs first_frame=%.3fs total_render=%.3fs "
           "(%d frames x %d spp, %.3f s/frame avg)\n",
        libName.c_str(), nRanks, setup, tFirst, rtime, frames, spp,
        rtime / frames);
  }

  anari::release(d, frame);
  anari::release(d, d);
  anari::unloadLibrary(lib);

#ifdef WITH_MPI
  if (useMPI)
    MPI_Finalize();
#endif
  return 0;
}
