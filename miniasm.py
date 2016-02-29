#!/usr/bin/env python
""" Mini-assembler that uses the formatting strings and opcode tables from
udis (the Universal Disassembler for 8-bit microprocessors by Jeff Tranter) to
perform pattern matching to determine the opcode and addressing mode.

Copyright (c) 2016 by Rob McMullen <feedback@playermissile.com>
Licensed under the Apache License 2.0
"""
from __future__ import print_function

import os
import re
from collections import defaultdict

import numpy as np

try:
    import cputables
except ImportError:
    raise RuntimeError("Generate cputables.py using cpugen.py before using the miniassembler")

from disasm import Disassembler

import logging
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


# flags
pcr = 1
und = 2
z80bit = 4
r = 64
w = 128

class FormatSpec(object):
    """ Format specifier that combines info from the udis addressModeTable and
    the opcodeTable.
    
    During the brute force decoding, the patterns contained in the
    addressModeTable format string are checked against the arguments decoded
    from the text to be assembled. The first match is returned as the
    assembled bytes.
    """
    
    # regex to find the argument number in the format string
    fmtargre = re.compile(r'\{[0-9]:')

    def __init__(self, format, opcode, num_bytes, mode_name, flag):
        self.format = format
        self.mode_name = mode_name
        self.num_args = len(re.findall(self.fmtargre, format))
        self.length = len(format)
        if opcode is not None:
            if opcode > 255:
                op1, op2 = divmod(opcode, 256)
                self.opcode_bytes = [op1, op2]
            else:
                self.opcode_bytes = [opcode]
        else:
            self.opcode_bytes = []
        self.num_bytes = num_bytes
        self.flag = flag
    
    def __str__(self):
        return "%s: %s" % (self.mode_name, self.format)
    
    def __repr__(self):
        return "%s: %s" % (self.mode_name, self.format)
    
    def __lt__(self, other):
        # Only need to implement 'less than' for sorting to work
        return (self.length, self.format) < (other.length, other.format)
    
    def get_bytes(self, bytes=None):
        out = list(self.opcode_bytes)
        if bytes is not None:
            out.extend(bytes)
        return tuple(out)
    
    def check_exact(self, operands):
        """ Check all the format strings that have no extra arguments, like
        "NOP" or even 6502's "ASL A"
        
        """
        log.debug("checking %s for exact match %s" % (self.mode_name, self.format))
        if self.format == operands:
            return self.get_bytes()
    
    def check_hex_1x8(self, operands, pc, byte):
        """ Check all the format strings that have one 8-bit hex value
        
        """
        if self.num_args == 0:
            # z80 has some hardcoded values in static opcodes, like $ff = "rst
            # $38" that get parsed as an opcode and a byte value, so we ignore
            # the byte value here because of it being hardcoded.
            gen = self.format
            log.debug("  " + gen + ":" + operands)
            if gen == operands:
                return self.get_bytes()
        elif self.num_args == 1:
            gen = self.format.format(byte)
            log.debug("  " + gen + ":" + operands)
            if gen == operands:
                return self.get_bytes([byte])
    
    def check_hex_1x16(self, operands, pc, low_byte, high_byte):
        """ Check all the format strings that have one 16-bit hex value,
        typically the PC-relative instructions.
        
        """
        if self.num_args != 1:
            return
        if self.flag == pcr:
            addr = low_byte + 256 * high_byte
            offset = addr - (pc + 2)
            log.debug("checking %s for relative branch to %04x (pc=%x, offset=%x)" % (self.mode_name, addr, pc, offset))
            if -128 <= offset <= 127:
                gen = self.format.format(addr)
                log.debug("  gen=%s operands=%s" % (gen, operands))
                if gen == operands:
                    return self.get_bytes([offset & 0xff])  # convert to unsigned representation
    
    def check_hex_2x8(self, operands, pc, low_byte, high_byte):
        """ Check all the format strings that have two 8-bit hex values
        
        """
        if self.num_args != 2:
            return
        log.debug("checking %s for hex values %02x, %02x" % (self.mode_name, low_byte, high_byte))
        gen = self.format.format(low_byte, high_byte)
        log.debug("  " + gen + ":" + operands)
        if gen == operands:
            return self.get_bytes([low_byte, high_byte])


class MiniAssembler(object):
    def __init__(self, cpu_name, allow_undocumented=False):
        self.source = None
        self.setup(cpu_name, allow_undocumented)
    
    def setup(self, cpu_name, allow_undocumented):
        """ Create the opcode lookup tables that store all the possible
        addressing modes for each opcode.
        """
        cpu = cputables.processors[cpu_name]
        self.little = True  # all 8-bit processors little endian???
        
        # Create temporary format dictionary that will be used in the expanded
        # opcode lookup table
        formats = {}
        table = cpu['addressModeTable']
        for mode, fmt in table.items():
            formats[mode] = fmt.lower()
        
        # Create the opcode lookup table that holds a list of possible
        # addressing modes for each opcode. Stores the addressing mode format
        # in each list entry to eliminate a lookup to another table at the
        # cost of some extra space in this lookup table.
        d = defaultdict(list)
        table = cpu['opcodeTable']
        for opcode, optable in table.items():
            try:
                num_bytes, mnemonic, mode_name, flag = optable
            except ValueError:
                num_bytes, mnemonic, mode_name = optable
                flag = 0
            if allow_undocumented or flag & 2 == 0:
                d[mnemonic].append(FormatSpec(formats[mode_name], opcode, num_bytes, mode_name, flag))
        d[".db"].append(FormatSpec("${0:02x}", None, 1, "data_byte", 0))
        
        # Order the lookup table from smallest to largest format specifier for
        # each opcode
        self.ops = {}
        for mnemonic, modelist in d.items():
            log.debug(mnemonic)
            modelist.sort()
            log.debug(modelist)
            self.ops[mnemonic] = modelist
        self.undocumented = allow_undocumented
    
    addrre = re.compile(r'\$[0-9a-fA-F]+')
    immediatere = re.compile(r'#?\$[0-9a-fA-F]+')
    
    def parse_operands(self, opstr, operands, pc):
        log.debug(operands)
        format_specs = self.ops[opstr]
        
        # Check if a single operand matches an address mode exactly
        for f in format_specs:
            bytes = f.check_exact(operands)
            if bytes:
                return bytes
        
        # Check for hex value
        values = re.findall(self.addrre, operands)
        if values:
            log.debug("HEX!: %s" % str(values))
            num = len(values)
            
            if num == 1:
                hexstr = values[0][1:]
                v = int(hexstr, 16)
                if len(hexstr) == 1 or len(hexstr) == 2:
                    for f in format_specs:
                        bytes = f.check_hex_1x8(operands, pc, v)
                        if bytes:
                            return bytes
                if len(hexstr) > 2:
                    vh, vl = divmod(v, 256)
                    for f in format_specs:
                        bytes = f.check_hex_1x16(operands, pc, vl, vh)
                        if bytes:
                            return bytes
                        bytes = f.check_hex_2x8(operands, pc, vl, vh)
                        if bytes:
                            return bytes
            elif num == 2:
                hexstr = values[0][1:]
                vl = int(hexstr, 16)
                hexstr = values[1][1:]
                vh = int(hexstr, 16)
                for f in format_specs:
                    bytes = f.check_hex_2x8(operands, pc, vl, vh)
                    if bytes:
                        return bytes
                
                
        
        return []
    
    def asm(self, origin, text):
        log.debug("input: %s" % text)
        if " " in text:
            opstr, operands = text.split(" ", 1)
        else:
            opstr = text
            operands = ""
        if ";" in operands:
            operands, _ = operands.split(";", 1)
        operands = operands.replace(" ", "")
        opstr = opstr.lower()
        operands = operands.strip()
        log.debug("-->%s<--, -->%s<--: %s" % (opstr, operands, self.ops[opstr]))
        bytes = self.parse_operands(opstr, operands, origin)
        return bytes


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--cpu", help="Specify CPU type (defaults to 6502)", default="6502")
    parser.add_argument("-u", "--undocumented", help="Allow undocumented opcodes", action="store_true")
    parser.add_argument("-a", "--assemble", help="Only assemble", action="store_true")
    parser.add_argument("-d", "--debug", help="Show debug information as the program runs", action="store_true")
    parser.add_argument("-v", "--verbose", help="Show processed instructions as the program runs", action="store_true")
    parser.add_argument("-x", "--hex", help="Assemble a string version of hex digits")
    parser.add_argument("-s", "--string", help="Assemble a single line opcode (implies -a)")
    args, extra = parser.parse_known_args()
    
    if args.debug:
        log.setLevel(logging.DEBUG)
    
    def format_hex(t):
        return "(" + ", ".join(["%02x" % s for s in t]) + ")"
    
    def process(source, filename):
        pc = 0
        miniasm = MiniAssembler(args.cpu, allow_undocumented=args.undocumented)
        if args.assemble:
            for line in source.splitlines():
                if line.startswith("0x"):
                    addr, line = line.split(" ", 1)
                    addr = int(addr, 16)
                    line = line.strip()
                else:
                    addr = pc
                try:
                    bytes = miniasm.asm(addr, line)
                    log.debug(bytes)
                except KeyError:
                    log.debug("unrecognized", line)
                    bytes = []
                print("%s: output=%s" % (line, str(bytes)))
                pc += len(bytes)
        else:
            binary = np.fromstring(source, dtype=np.uint8)
            disasm = Disassembler(args.cpu, allow_undocumented=args.undocumented, hex_lower=True, mnemonic_lower=True)
            disasm.set_pc(binary, 0)
            success = failure = 0
            for addr, disassembled_bytes, opstr, comment, flag in disasm.get_disassembly():
                assembled_bytes = miniasm.asm(addr, opstr)
                if disassembled_bytes == assembled_bytes:
                    success += 1
                    if args.verbose:
                        print("%s:" % opstr, format_hex(disassembled_bytes), format_hex(assembled_bytes))
                else:
                    failure += 1
                    print("%s:" % opstr, format_hex(disassembled_bytes), format_hex(assembled_bytes))
    #            print "0x%04x %-12s ; %s   %s %s" % (addr, opstr, comment, bytes, flag)
            print("%s: %d instructions matched, %d failed" % (filename, success, failure))

    if args.string:
        source = args.string
        args.assemble = True
        process(source, args.string)
    elif args.hex:
        try:
            source = args.hex.decode("hex")
        except TypeError:
            print("Invalid hex digits!")
            sys.exit()
        process(source, args.string)
    else:
        for filename in extra:
            source = []
            with open(filename, 'rb') if filename !="-" else sys.stdin as fh:
                try:
                    chunk_length = 1024
                    while True:
                        chunk = fh.read(chunk_length)
                        source.append(chunk)
                        if len(chunk) < chunk_length:
                            break
                except KeyboardInterrupt:
                    pass
            source = "".join(source)
            if args.verbose:
                print("read %d bytes" % len(source))
            process(source, filename)

