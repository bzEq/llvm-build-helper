#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import argparse
import shutil
import logging


def main():
    parser = argparse.ArgumentParser(
        description='Bootstrap Clang/LLVM with minimal configuration')
    parser.add_argument('--install_prefix', required=True)
    parser.add_argument('--src_dir', required=True)
    parser.add_argument('--build_dir', required=True)
    parser.add_argument('--cmake_binary', default=shutil.which('cmake'))
    parser.add_argument('--bootstrap_cc', default=shutil.which('gcc'))
    parser.add_argument('--skip_stage2', default=False, action='store_true')
    parser.add_argument('--skip_stage2_test',
                        action='store_true',
                        default=False)
    config = parser.parse_args()
    CreateDirs(config)
    if not config.skip_stage2:
        return not (RunStage1(config) and RunStage2(config))
    return not (RunStage1(config))


def CreateDirs(config):
    os.makedirs(os.path.join(config.build_dir, 'stage1'), exist_ok=True)
    if not config.skip_stage2:
        os.makedirs(os.path.join(config.build_dir, 'stage2'), exist_ok=True)


def BuildCommonCMakeCommand(config):
    cmd = [
        config.cmake_binary,
        '-GNinja',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_INSTALL_PREFIX={install_prefix}'.format(
            install_prefix=config.install_prefix),
        '-DLLVM_ENABLE_ASSERTIONS=On',
        # Only build clang and lld
        '-DLLVM_ENABLE_PROJECTS=clang;lld',
    ]
    return cmd


def RunStage1(config):
    wd = os.path.join(config.build_dir, 'stage1')
    cmd = BuildCommonCMakeCommand(config)
    cmd.append('-DCMAKE_C_COMPILER={cc}'.format(
        cc=os.path.abspath(config.bootstrap_cc)))
    cmd.append(os.path.abspath(config.src_dir))
    err = subprocess.call(cmd, cwd=wd)
    if err != 0:
        logging.error('cmake failed in stage1')
        return False
    err = subprocess.call([
        'ninja',
    ], cwd=wd)
    if err != 0:
        logging.error('ninja failed in stage1')
        return False
    return True


def RunStage2(config):
    wd = os.path.join(config.build_dir, 'stage2')
    cmd = BuildCommonCMakeCommand(config)
    cmd.append('-DCMAKE_C_COMPILER={cc}'.format(
        cc=shutil.which('clang',
                        path=os.path.join(os.path.abspath(config.build_dir),
                                          'stage1', 'bin'))))
    cmd.append('-DLLVM_USE_LINKER={ld}'.format(
        ld=shutil.which('ld.lld',
                        path=os.path.join(os.path.abspath(config.build_dir),
                                          'stage1', 'bin'))))
    cmd.append(os.path.abspath(config.src_dir))
    err = subprocess.call(cmd, cwd=wd)
    if err != 0:
        logging.error('cmake failed in stage2')
        return False
    ninja_build = [
        'ninja',
    ]
    if not config.skip_stage2_test:
        ninja_build.append('check-all')
    err = subprocess.call(ninja_build, cwd=wd)
    if err != 0:
        logging.error('ninja failed in stage2')
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
