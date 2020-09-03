#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# My typical configuration for building LLVM with PGO and LTO enabled.

import os
import sys
import subprocess
import argparse
import shutil
import logging
import glob
from pathlib import Path

DEFAULT_PROJECTS = [
    'clang',
    'clang-tools-extra',
    'compiler-rt',
    'libcxx',
    'libcxxabi',
    'lld',
    'mlir',
]


def FindTool(clang_path, name):
    return shutil.which(name, path=os.path.join(clang_path, 'bin'))


def main():
    parser = argparse.ArgumentParser(
        description='Build Clang/LLVM with pgo and lto enabled')
    parser.add_argument('--default_clang', required=True)
    parser.add_argument('--install_prefix', required=True)
    parser.add_argument('--binutils_include', required=False)
    parser.add_argument('--src_dir', required=True)
    parser.add_argument('--build_dir', required=True)
    parser.add_argument('--native', action='store_true', default=False)
    parser.add_argument('--cmake_binary', default=shutil.which('cmake'))
    parser.add_argument('--skip_pass1', action='store_true', default=False)
    parser.add_argument('--llvm_test_suite_path')
    config = parser.parse_args()
    CreateDirs(config)
    if config.skip_pass1:
        return not RunPass2(config)
    return not (RunPass1(config) and RunPass2(config))


def CreateDirs(config):
    os.makedirs(os.path.join(config.build_dir, 'pass1'), exist_ok=True)
    os.makedirs(os.path.join(config.build_dir, 'pass2'), exist_ok=True)
    if config.llvm_test_suite_path:
        os.makedirs(os.path.join(config.build_dir, 'test_suite'),
                    exist_ok=True)


def GlobPass1Profiles(config):
    p = os.path.join(os.path.abspath(config.build_dir), 'pass1', 'profiles',
                     '*.profraw')
    return glob.glob(p)


def BuildCommonCMakeCommand(config):
    cmd = [
        config.cmake_binary,
        '-GNinja',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_COMPILER={clang}'.format(
            clang=FindTool(config.default_clang, 'clang')),
        '-DCMAKE_INSTALL_PREFIX={install_prefix}'.format(
            install_prefix=config.install_prefix),
        '-DLLVM_ENABLE_ASSERTIONS=On',
        '-DLLVM_USE_LINKER={lld}'.format(
            lld=FindTool(config.default_clang, 'ld.lld')),
    ]
    if config.binutils_include:
        cmd.append('-DLLVM_BINUTILS_INCDIR={path}'.format(
            path=config.binutils_include))
    return cmd


def BuildPass1LDFlags(config):
    flags = [
        '-Wl,-rpath={path}'.format(
            path=os.path.join(os.path.abspath(config.default_clang), 'lib')),
    ]
    return flags


def BuildPass2LDFlags(config):
    flags = [
        '-Wl,-rpath={path}'.format(
            path=os.path.join(os.path.abspath(config.install_prefix), 'lib')),
    ]
    return flags


def BuildPass1CFlags(config):
    flags = [
        '-fprofile-generate={path}'.format(path=os.path.join(
            os.path.abspath(config.build_dir), 'pass1', 'profiles')),
    ]
    if config.native:
        flags.append('-march=native')
    return flags


def BuildPass1CXXFlags(config):
    return BuildPass1CFlags(config)


def BuildPass2CFlags(config):
    flags = [
        '-fprofile-use={path}'.format(path=os.path.join(
            os.path.abspath(config.build_dir), 'pass2', 'default.profdata')),
    ]
    if config.native:
        flags.append('-march=native')
    return flags


def BuildPass2CXXFlags(config):
    return BuildPass2CFlags(config)


def BuildLLVMTestSuiteWithPass1Driver(config):
    pass1_path = os.path.abspath(os.path.join(config.build_dir, 'pass1'))
    build_path = os.path.abspath(os.path.join(config.build_dir, 'test_suite'))
    configure_cmake = [
        config.cmake_binary,
        '-GNinja',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_COMPILER={cc}'.format(cc=FindTool(pass1_path, 'clang')),
        '-DCMAKE_CXX_COMPILER={cxx}'.format(
            cxx=FindTool(pass1_path, 'clang++')),
        '-S',
        os.path.abspath(config.llvm_test_suite_path),
        '-B',
        build_path,
    ]
    err = subprocess.call(configure_cmake)
    if err != 0:
        logging.error('cmake failed configuring test suite')
        return False
    cmd = [
        'ninja',
        '-C',
        build_path,
    ]
    err = subprocess.call(cmd)
    if err != 0:
        logging.error('ninja failed building test suite')
        return False
    run_tests = [
        FindTool(pass1_path, 'llvm-lit'),
        build_path,
    ]
    err = subprocess.call(run_tests)
    if err != 0:
        logging.error('Failed to run test suite')
        return False
    return True


def RunPass1(config):
    wd = os.path.join(config.build_dir, 'pass1')
    cmd = BuildCommonCMakeCommand(config)
    # Use clang for training.
    cmd.append('-DLLVM_ENABLE_PROJECTS=clang')
    cmd.append('-DLLVM_ENABLE_RUNTIMES=compiler-rt')
    cmd.append('-DCLANG_DEFAULT_LINKER={ld}'.format(
        ld=FindTool(config.default_clang, 'ld.lld')))
    cmd.append('-DCMAKE_C_FLAGS={flags}'.format(
        flags=' '.join(BuildPass1CFlags(config))))
    cmd.append('-DCMAKE_CXX_FLAGS={flags}'.format(
        flags=' '.join(BuildPass1CXXFlags(config))))
    cmd.append(os.path.abspath(config.src_dir))
    err = subprocess.call(cmd, cwd=wd)
    if err != 0:
        logging.error('cmake failed in pass1')
        return False
    ninja_build = [
        'ninja',
    ]
    if not config.llvm_test_suite_path:
        ninja_build.append('check-all')
    err = subprocess.call(ninja_build, cwd=wd)
    if err != 0:
        logging.warning('ninja failed in pass1')
    if config.llvm_test_suite_path:
        return BuildLLVMTestSuiteWithPass1Driver(config)
    return True


def RunPass2(config):
    wd = os.path.join(config.build_dir, 'pass2')
    merge_profiles_cmd = [
        FindTool(config.default_clang, 'llvm-profdata'),
        'merge',
        '-o',
        os.path.join(wd, 'default.profdata'),
    ] + GlobPass1Profiles(config)
    err = subprocess.call(merge_profiles_cmd)
    if err != 0:
        logging.error('Merge profiles failed')
        return False
    cmd = BuildCommonCMakeCommand(config)
    cmd.append('-DLLVM_ENABLE_LTO=Thin')
    cmd.append('-DLLVM_ENABLE_PROJECTS={projects}'.format(
        projects=';'.join(DEFAULT_PROJECTS)))
    cmd.append('-DCMAKE_C_FLAGS={flags}'.format(
        flags=' '.join(BuildPass2CFlags(config))))
    cmd.append('-DCMAKE_CXX_FLAGS={flags}'.format(
        flags=' '.join(BuildPass2CXXFlags(config))))
    cmd.append(os.path.abspath(config.src_dir))
    err = subprocess.call(cmd, cwd=wd)
    if err != 0:
        logging.error('cmake failed in pass2')
        return False
    err = subprocess.call([
        'ninja',
        'package',
    ], cwd=wd)
    if err != 0:
        logging.error('ninja failed in pass2')
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
