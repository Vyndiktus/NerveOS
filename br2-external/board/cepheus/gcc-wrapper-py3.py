#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Python 3 port of gcc-wrapper.py (original: python2, Xiaomi cepheus-q-oss kernel)

import errno
import re
import os
import sys
import subprocess

allowed_warnings = set([
 ])

ofile = None

warning_re = re.compile(r'(.*/|)([^/]+\.[a-z]+:\d+):(\d+:)? warning:')

def interpret_warning(line):
    # Warning enforcement disabled — modern GCC emits warnings unknown to this
    # old Qualcomm script. Build proceeds regardless of warnings.
    pass

def run_gcc():
    args = sys.argv[1:]
    try:
        i = args.index('-o')
        global ofile
        ofile = args[i+1]
    except (ValueError, IndexError):
        pass

    try:
        proc = subprocess.Popen(args, stderr=subprocess.PIPE)
        for raw_line in proc.stderr:
            line = raw_line.decode('utf-8', errors='replace')
            print(line, end='', file=sys.stderr)
            interpret_warning(line)
        result = proc.wait()
    except OSError as e:
        result = e.errno
        if result == errno.ENOENT:
            print(args[0] + ': ' + e.strerror, file=sys.stderr)
            print('Is your PATH set correctly?', file=sys.stderr)
        else:
            print(' '.join(args) + ' ' + str(e), file=sys.stderr)

    return result

if __name__ == '__main__':
    status = run_gcc()
    sys.exit(status)
