"""Build 16KB-aligned Android wheels from pinned upstream sources on Windows.

Requires the official SDK NDK r28c and CMake 3.31.6. The build never patches ELF
headers: source compilation and linking supply both max/common-page-size flags.
Downloaded sources and outputs stay in the ignored android-downloads directory.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

from tools.bootstrap_android import safe_extract, verify
from tools.check_android_pages import inspect_archive

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'tools/android-downloads/native-16kb'
OUTPUT = WORK/'wheels'
NDK = ROOT/'tools/android-sdk/ndk/28.2.13676358'
CMAKE = ROOT/'tools/android-sdk/cmake/3.31.6/bin/cmake.exe'
NINJA = CMAKE.with_name('ninja.exe')
SOURCES = {
    'opencv-4.12.0': ('https://codeload.github.com/opencv/opencv/zip/refs/tags/4.12.0',
                      'fa3faf7581f1fa943c9e670cf57dd6ba1c5b4178f363a188a2c8bff1eb28b7e4'),
    'freetype-2.9.1': ('https://codeload.github.com/freetype/freetype/zip/refs/tags/VER-2-9-1',
                       '103e018c0451aba6eca6009b39b8a68f768c3e65497ce91bac67ff7d6e2076c8'),
    'libjpeg-turbo-3.1.3': ('https://codeload.github.com/libjpeg-turbo/libjpeg-turbo/zip/refs/tags/3.1.3',
                           '351d21e8a317e89b1eae74b5d7fc5730dbabd6865490a77821cb0940ca4e9cb1'),
    'python.3.13.11': ('https://api.nuget.org/v3-flatcontainer/python/3.13.11/python.3.13.11.nupkg',
                      '56060654f7a552992cf27f64ac427001446f2c3f15b6acb41b1b8f38a75b5403'),
}


def source(name):
    url, digest = SOURCES[name]
    WORK.mkdir(parents=True, exist_ok=True)
    archive = WORK/(name+('.nupkg' if url.endswith('.nupkg') else '.zip'))
    if not archive.exists():
        temporary = archive.with_suffix('.part')
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as stream:
                shutil.copyfileobj(response, stream)
            verify(temporary, digest)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    verify(archive, digest)
    destination = WORK/name
    if not destination.exists():
        safe_extract(archive, destination)
    return destination


def prepare_inputs():
    """Fetch exact official wheels/headers; don't silently select stale mirrors."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = json.loads((ROOT/'tools/android-native-inputs.json').read_text())
    for record in records:
        name = record['url'].rsplit('/', 1)[1]
        directory = OUTPUT if record['kind'] == 'wheel' else WORK
        target = directory/name
        if not target.exists():
            temporary = target.with_suffix('.part')
            try:
                with urllib.request.urlopen(record['url'], timeout=60) as src, temporary.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                verify(temporary, record['sha256'])
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        verify(target, record['sha256'])
        if record['kind'] == 'python-target':
            abi = 'arm64-v8a' if 'arm64-v8a' in name else 'x86_64'
            destination = WORK/('python-'+abi)
            if not destination.exists():
                safe_extract(target, destination)


def fingerprint():
    return hashlib.sha256(Path(__file__).read_bytes()+(ROOT/'tools/android-native-inputs.json').read_bytes()).hexdigest()


def cached():
    manifest = WORK/'native-build.json'
    if not manifest.exists():
        return False
    record = json.loads(manifest.read_text())
    return record.get('fingerprint') == fingerprint() and all(
        (OUTPUT/name).is_file() and hashlib.sha256((OUTPUT/name).read_bytes()).hexdigest() == digest
        for name, digest in record['wheels'].items()) and len(record['wheels']) == 6


def patch(path, old, new):
    text = path.read_text(encoding='utf-8')
    if old not in text:
        if new in text:
            return
        raise ValueError(f'Upstream patch no longer matches: {path.name}')
    path.write_text(text.replace(old, new), encoding='utf-8')


def wheel(name, version, build, tag, files, requires=()):
    """Package built libraries with exact RECORD hashes and upstream licenses."""
    info = f'{name}-{version}.dist-info'
    content = dict(files)
    content[info+'/METADATA'] = ('Metadata-Version: 2.1\nName: '+name.replace('_', '-')+
                                '\nVersion: '+version+'\n'+''.join('Requires-Dist: '+r+'\n' for r in requires)).encode()
    content[info+'/WHEEL'] = (f'Wheel-Version: 1.0\nGenerator: ADOFAI-source-build\nRoot-Is-Purelib: false\nTag: {tag}\n').encode()
    record = io.StringIO(newline='')
    writer = csv.writer(record, lineterminator='\n')
    for path, data in sorted(content.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow([path, 'sha256='+digest, len(data)])
    writer.writerow([info+'/RECORD', '', ''])
    content[info+'/RECORD'] = record.getvalue().encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT/f'{name}-{version}-{build}-{tag}.whl'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path, data in sorted(content.items()):
            bundle.writestr(path, data)
    with zipfile.ZipFile(target) as bundle:
        libraries = inspect_archive(bundle)
    if not libraries or any(r['issues'] for r in libraries):
        raise ValueError(f'Built wheel failed the 16KB ELF audit: {libraries}')
    print('Verified source-built wheel: '+target.name, flush=True)
    return target


def native_bytes(path):
    strip = NDK/'toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-strip.exe'
    subprocess.run([str(strip), '--strip-unneeded', str(path)], check=True)
    data = path.read_bytes()
    if ROOT.as_posix().encode() in data or str(ROOT).encode() in data:
        raise ValueError('A source-built library still contains the local workspace path')
    return data


def cmake_build(source_path, abi, name, target, options):
    build = WORK/'build'/abi/name
    common = [f'-DCMAKE_TOOLCHAIN_FILE={NDK.as_posix()}/build/cmake/android.toolchain.cmake',
              f'-DCMAKE_MAKE_PROGRAM={NINJA.as_posix()}', f'-DANDROID_ABI={abi}', '-DANDROID_PLATFORM=android-24',
              '-DANDROID_STL=c++_static', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
              f'-DCMAKE_C_FLAGS=-ffile-prefix-map={ROOT.as_posix()}=source',
              f'-DCMAKE_CXX_FLAGS=-ffile-prefix-map={ROOT.as_posix()}=source',
              '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG -g0', '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG -g0',
              '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384,-z,common-page-size=16384',
              '-DCMAKE_MODULE_LINKER_FLAGS=-Wl,-z,max-page-size=16384,-z,common-page-size=16384']
    subprocess.run([str(CMAKE), '-S', str(source_path), '-B', str(build), '-G', 'Ninja', *common, *options], check=True)
    for info in (build/'modules/core/version_string.inc', build/'opencv_data_config.hpp'):
        if info.exists():
            # Runtime build information and unused build-tree data lookup paths
            # are generated literals, independent of __FILE__ prefix mapping.
            info.write_text(info.read_text().replace(ROOT.as_posix(), 'source').replace(str(ROOT), 'source'))
    subprocess.run([str(CMAKE), '--build', str(build), '--target', target, '--parallel', '4'], check=True)
    return build


def build(abi):
    suffix = abi.replace('-', '_')
    free = source('freetype-2.9.1')/'freetype-VER-2-9-1'
    patch(free/'CMakeLists.txt', 'VERSION ${LIBRARY_VERSION}\n    SOVERSION ${LIBRARY_SOVERSION}',
          'VERSION ""\n    SOVERSION ""')
    fbuild = cmake_build(free, abi, 'freetype', 'freetype', ['-DBUILD_SHARED_LIBS=ON',
        '-DCMAKE_DISABLE_FIND_PACKAGE_HarfBuzz=ON', '-DCMAKE_DISABLE_FIND_PACKAGE_PNG=ON', '-DCMAKE_DISABLE_FIND_PACKAGE_BZip2=ON'])
    wheel('chaquopy_freetype', '2.9.1', '3', f'py3-none-android_24_{suffix}', {
        'chaquopy/lib/libfreetype.so': native_bytes(fbuild/'libfreetype.so'),
        'chaquopy_freetype-2.9.1.dist-info/licenses/FTL.TXT': (free/'docs/FTL.TXT').read_bytes()})

    jpeg = source('libjpeg-turbo-3.1.3')/'libjpeg-turbo-3.1.3'
    patch(jpeg/'sharedlib/CMakeLists.txt', 'set_target_properties(jpeg PROPERTIES SOVERSION ${SO_MAJOR_VERSION}\n  VERSION ${SO_MAJOR_VERSION}.${SO_AGE}.${SO_MINOR_VERSION})',
          'set_target_properties(jpeg PROPERTIES OUTPUT_NAME jpeg_chaquopy SOVERSION "" VERSION "")')
    jbuild = cmake_build(jpeg, abi, 'jpeg-3.1.3', 'jpeg', ['-DWITH_SIMD=OFF', '-DWITH_TURBOJPEG=OFF', '-DENABLE_STATIC=OFF'])
    wheel('chaquopy_libjpeg', '3.1.3', '1', f'py3-none-android_24_{suffix}', {
        'chaquopy/lib/libjpeg_chaquopy.so': native_bytes(jbuild/'libjpeg_chaquopy.so'),
        'chaquopy_libjpeg-3.1.3.dist-info/licenses/LICENSE.md': (jpeg/'LICENSE.md').read_bytes()})

    cv = source('opencv-4.12.0')/'opencv-4.12.0'
    patch(cv/'modules/python/CMakeLists.txt', 'if(ANDROID OR APPLE_FRAMEWORK OR WINRT)', 'if(APPLE_FRAMEWORK OR WINRT)')
    # OpenCV's substring replacement also corrupts NDK r28's
    # --no-undefined-version into a bare -version. We link libpython explicitly,
    # so retain both of the NDK's undefined-symbol checks instead.
    patch(cv/'modules/python/common.cmake',
          'string(REPLACE "-Wl,--no-undefined" "" CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS}")',
          '# Keep NDK undefined-symbol flags: libpython is linked explicitly.')
    python = source('python.3.13.11')/'tools'
    target_python = WORK/('python-'+abi)
    if not target_python.exists():
        raise FileNotFoundError('Prepare the pinned Chaquopy 3.13.16 target headers first')
    numpy = WORK/('numpy-'+abi)
    if not numpy.exists():
        safe_extract(WORK/'wheels'/f'numpy-1.26.2-0-cp313-cp313-android_24_{suffix}.whl', numpy)
    options = ['-DBUILD_SHARED_LIBS=OFF', '-DBUILD_LIST=core,imgproc,python3', '-DBUILD_opencv_python3=ON',
        '-DBUILD_ANDROID_PROJECTS=OFF', '-DBUILD_ANDROID_EXAMPLES=OFF', '-DBUILD_JAVA=OFF',
        '-DBUILD_TESTS=OFF', '-DBUILD_PERF_TESTS=OFF', '-DBUILD_EXAMPLES=OFF', '-DBUILD_opencv_apps=OFF',
        '-DWITH_IPP=OFF', '-DWITH_OPENCL=OFF', '-DWITH_ITT=OFF', '-DWITH_TBB=OFF',
        '-DWITH_LAPACK=OFF', '-DWITH_EIGEN=OFF', '-DOPENCV_ENABLE_NONFREE=OFF', '-DOPENCV_SKIP_PYTHON_LOADER=ON',
        '-DPYTHON3INTERP_FOUND=TRUE', '-DPYTHON3LIBS_FOUND=TRUE', '-DPYTHON3_VERSION_STRING=3.13.16',
        '-DPYTHON3_VERSION_MAJOR=3', '-DPYTHON3_VERSION_MINOR=13', '-DPYTHON3_NUMPY_VERSION=1.26.2',
        '-DPYTHON3_CVPY_SUFFIX=.so', '-DOPENCV_FORCE_PYTHON_LIBS=ON', '-DOPENCV_PYTHON3_INSTALL_PATH=python3',
        f'-DPYTHON3_EXECUTABLE={python.as_posix()}/python.exe',
        f'-DPYTHON_DEFAULT_EXECUTABLE={python.as_posix()}/python.exe',
        f'-DPYTHON3_INCLUDE_PATH={target_python.as_posix()}/include/python3.13',
        f'-DPYTHON3_LIBRARIES={target_python.as_posix()}/jniLibs/{abi}/libpython3.13.so',
        f'-DPYTHON3_NUMPY_INCLUDE_DIRS={numpy.as_posix()}/numpy/core/include']
    cbuild = cmake_build(cv, abi, 'opencv', 'opencv_python3', options)
    binary = cbuild/'lib'/abi/'python3/cv2.so'
    files = {
        'cv2.so': native_bytes(binary),
        'opencv_python_headless-4.12.0.88.dist-info/licenses/LICENSE': (cv/'LICENSE').read_bytes()}
    for directory in (cv/'3rdparty/cpufeatures', cbuild/'3rdparty/kleidicv'):
        for path in directory.rglob('*'):
            if path.is_file() and path.name.lower().startswith(('license', 'copying', 'notice')):
                files['opencv_python_headless-4.12.0.88.dist-info/licenses/'+directory.name+'/'+path.relative_to(directory).as_posix()] = path.read_bytes()
        for path in directory.rglob('LICENSES/*'):
            if path.is_file():
                files['opencv_python_headless-4.12.0.88.dist-info/licenses/'+directory.name+'/'+path.relative_to(directory).as_posix()] = path.read_bytes()
    wheel('opencv_python_headless', '4.12.0.88', '1', f'cp313-cp313-android_24_{suffix}', files, ['numpy>=1.26.2,<2'])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--abi', choices=['arm64-v8a', 'x86_64', 'all'], default='all')
    args = parser.parse_args()
    if args.abi == 'all' and cached():
        prepare_inputs()
        source('python.3.13.11')
        print('Source-built Android wheels: fingerprint and all six hashes verified', flush=True)
        return
    if not CMAKE.is_file() or not (NDK/'source.properties').is_file():
        raise FileNotFoundError('Install NDK 28.2.13676358 and CMake 3.31.6 with the official SDK manager')
    prepare_inputs()
    for abi in (['arm64-v8a', 'x86_64'] if args.abi == 'all' else [args.abi]):
        build(abi)
    if args.abi == 'all':
        packages = ('chaquopy_freetype-2.9.1-3-', 'chaquopy_libjpeg-3.1.3-1-', 'opencv_python_headless-4.12.0.88-1-')
        wheels = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUT.glob('*.whl') if p.name.startswith(packages)}
        if len(wheels) != 6:
            raise ValueError('Both ABIs must have all three source-built wheels')
        (WORK/'native-build.json').write_text(json.dumps({'fingerprint': fingerprint(), 'wheels': wheels}, indent=2))


if __name__ == '__main__':
    main()
