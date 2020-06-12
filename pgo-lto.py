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
    parser.add_argument('--skip_test', action='store_true', default=False)
    config = parser.parse_args()
    CreateDirs(config)
    if config.skip_pass1:
        return not RunPass2(config)
    return not (RunPass1(config) and RunPass2(config))


def CreateDirs(config):
    os.makedirs(os.path.join(config.build_dir, 'pass1'), exist_ok=True)
    os.makedirs(os.path.join(config.build_dir, 'pass2'), exist_ok=True)


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
        '-DLLVM_ENABLE_LIBCXX=On',
    ]
    if config.binutils_include:
        cmd.append('-DLLVM_BINUTILS_INCDIR={path}'.format(
            path=config.binutils_include))
    return cmd


def BuildLDFlags(config):
    flags = [
        '-Wl,-rpath={path}'.format(
            path=os.path.join(os.path.abspath(config.default_clang), 'lib')),
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


def RunPass1(config):
    wd = os.path.join(config.build_dir, 'pass1')
    cmd = BuildCommonCMakeCommand(config)
    # Use clang for training.
    cmd.append('-DLLVM_ENABLE_PROJECTS=clang')
    cmd.append(os.path.abspath(config.src_dir))
    env = os.environ.copy()
    env['LDFLAGS'] = ' '.join(BuildLDFlags(config))
    env['CFLAGS'] = ' '.join(BuildPass1CFlags(config))
    env['CXXFLAGS'] = ' '.join(BuildPass1CXXFlags(config))
    err = subprocess.call(cmd, env=env, cwd=wd)
    if err != 0:
        logging.error('cmake failed in pass1')
        return False
    ninja_build = [
        'ninja',
    ]
    if not config.skip_test:
        ninja_build.append('check-all')
    err = subprocess.call(ninja_build, cwd=wd)
    if err != 0:
        logging.warning('ninja failed in pass1')
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
    if config.clang_default_linker:
        cmd.append('-DCLANG_DEFAULT_LINKER={ld}'.format(
            ld=config.clang_default_linker))
    cmd.append(os.path.abspath(config.src_dir))
    env = os.environ.copy()
    env['LDFLAGS'] = ' '.join(BuildLDFlags(config))
    env['CFLAGS'] = ' '.join(BuildPass2CFlags(config))
    env['CXXFLAGS'] = ' '.join(BuildPass2CXXFlags(config))
    err = subprocess.call(cmd, env=env, cwd=wd)
    if err != 0:
        logging.error('cmake failed in pass2')
        return False
    err = subprocess.call(['ninja'], cwd=wd)
    if err != 0:
        logging.error('ninja failed in pass2')
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
