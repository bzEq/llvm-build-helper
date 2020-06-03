#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import argparse
import shutil
import logging

DEFAULT_PROJECTS = [
    'clang',
    'clang-tools-extra',
    'compiler-rt',
    'libcxx',
    'libcxxabi',
    'lld',
    'mlir',
]


def main():
    parser = argparse.ArgumentParser(
        description='Build Clang/LLVM with default configuration')
    parser.add_argument('--bootstrap_clang', default=shutil.which('clang'))
    parser.add_argument('--bootstrap_lld', default=shutil.which('ld.lld'))
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--install_prefix', required=True)
    parser.add_argument('--src_dir', required=True)
    parser.add_argument('--build_dir', required=True)
    parser.add_argument('--cmake_binary', default=shutil.which('cmake'))
    parser.add_argument('--binutils_include')
    parser.add_argument('--config_only', action='store_true', default=False)
    parser.add_argument('--use_newpm', action='store_true', default=False)
    parser.add_argument('--skip_test', action='store_true', default=False)
    config = parser.parse_args()
    return not BuildDefaultClang(config)


def BuildCMakeCommand(config):
    cmd = [
        config.cmake_binary,
        '-GNinja',
        '-DCMAKE_BUILD_TYPE={build}'.format(
            build='Debug' if config.debug else 'Release'),
        '-DCMAKE_C_COMPILER={clang}'.format(
            clang=os.path.abspath(config.bootstrap_clang)),
        '-DLLVM_USE_LINKER={lld}'.format(
            lld=os.path.abspath(config.bootstrap_lld)),
        '-DCMAKE_INSTALL_PREFIX={install_prefix}'.format(
            install_prefix=config.install_prefix),
        '-DLLVM_ENABLE_ASSERTIONS=On',
        '-DLLVM_ENABLE_PROJECTS={projects}'.format(
            projects=';'.join(DEFAULT_PROJECTS)),
        '-DCLANG_DEFAULT_LINKER={ld}'.format(ld=os.path.join(
            os.path.abspath(config.install_prefix), 'bin', 'ld.lld')),
    ]
    if config.binutils_include:
        cmd.append('-DLLVM_BINUTILS_INCDIR={path}'.format(
            path=config.binutils_include))
    if config.use_newpm:
        cmd.append('-DLLVM_USE_NEWPM=On')
    cmd.append(os.path.abspath(config.src_dir))
    return cmd


def BuildDefaultClang(config):
    cmd = BuildCMakeCommand(config)
    err = subprocess.call(cmd, cwd=config.build_dir)
    if err != 0:
        logging.error('cmake failed')
        return False
    if config.config_only:
        return True
    ninja_build = [
        'ninja',
    ]
    if not config.skip_test:
        ninja_build.append('check-all')
    err = subprocess.call(ninja_build, cwd=config.build_dir)
    if err != 0:
        logging.error('ninja failed')
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
