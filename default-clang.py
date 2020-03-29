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
]


def main():
    parser = argparse.ArgumentParser(
        description='Build Clang/LLVM with default configuration')
    parser.add_argument('--bootstrap_clang', default=shutil.which('clang'))
    parser.add_argument('--install_prefix', required=True)
    parser.add_argument('--src_dir', required=True)
    parser.add_argument('--build_dir', required=True)
    parser.add_argument('--cmake_binary', default=shutil.which('cmake'))
    parser.add_argument('--binutils_include')
    parser.add_argument('--config_only', action='store_true', default=False)
    config = parser.parse_args()
    return not BuildDefaultClang(config)


def BuildCMakeCommand(config):
    cmd = [
        config.cmake_binary,
        '-GNinja',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_COMPILER={clang}'.format(
            clang=os.path.abspath(config.bootstrap_clang)),
        '-DLLVM_USE_LINKER=lld',
        '-DCMAKE_INSTALL_PREFIX={install_prefix}'.format(
            install_prefix=config.install_prefix),
        '-DLLVM_ENABLE_ASSERTIONS=On',
        '-DLLVM_ENABLE_PROJECTS={projects}'.format(
            projects=';'.join(DEFAULT_PROJECTS)),
    ]
    if config.binutils_include:
        cmd.append('-DLLVM_BINUTILS_INCDIR={path}'.format(
            path=config.binutils_include))
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
    err = subprocess.call([
        'ninja',
        'check-all',
    ], cwd=config.build_dir)
    if err != 0:
        logging.error('ninja failed')
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
