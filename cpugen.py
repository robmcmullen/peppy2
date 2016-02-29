#!/usr/bin/env python
""" Convert udis module level data into a single dictionary structure for all
known processors and save it into cputables.py

"""
import os
import glob

# flags
pcr = 1
und = 2
z80bit = 4
r = 64
w = 128

def read_udis(pathname):
    """ Read all the processor-specific opcode info and pull into a container
    dictionary keyed on the processor name.
    
    The udis files have module level data, so this pulls the data from multiple
    cpus into a single structure that can then be refereced by processor name.
    For example, to find the opcode table in the generated dictionary for the
    6502 processor, use:
    
    cpus['6502']['opcodeTable']
    """
    files = glob.glob("%s/*.py" % pathname)
    cpus = {}
    for filename in files:
        localfile = os.path.basename(filename)
        with open(filename, "r") as fh:
            source = fh.read()
            if "import cputables" in source:
                continue
            if "addressModeTable" in source and "opcodeTable" in source:
                cpu_name, _ = os.path.splitext(localfile)
                g = {"pcr": pcr, "und": und, "r": r, "w": w, "z80bit": z80bit}
                d = {}
                try:
                    exec(source, g, d)
                    if 'opcodeTable' in d:
                        cpus[cpu_name] = d
                except SyntaxError:
                    # ignore any python 3 files
                    pass
    return cpus


if __name__ == "__main__":
    import sys
    import argparse
    
    supported_cpus = read_udis(".")
    output = []
    import pprint
    output.append("# Autogenerated from udis source! Do not edit here, change udis source instead.")
    output.append("processors =\\")
    for line in pprint.pformat(supported_cpus).splitlines():
        output.append(line.strip())
#    print supported_cpus
    with open("cputables.py", "w") as fh:
        fh.write("\n".join(output))
        fh.write("\n")
