#ifndef LIBUDIS_H
#define LIBUDIS_H
#include <stdint.h>

/* The history structure must match the definition in omni8bit/udis_fast/dtypes.py */

/* default 32k entries, plenty for one frame */
#define HISTORY_ENTRIES (256 * 128)

typedef struct {
	uint8_t num_bytes;
	uint8_t flag;
	uint8_t disassembler_type;
	uint8_t high_offset;
	uint16_t low_offset;  /* index = (high_offset << 16 + low_offset) */
	uint16_t pc;
	uint16_t target_addr;
} history_entry_t; /* 10 bytes */

typedef struct {
	uint8_t instruction[3];
} disassembly_6502_t; /* 3 bytes */

typedef struct {
	uint8_t instruction[3];
	uint8_t a;
	uint8_t x;
	uint8_t y;
	uint8_t sp;
	uint8_t sr;
} history_6502_t; /* 8 bytes */

typedef struct {
	uint8_t instruction[3];
	uint8_t a;
	uint8_t x;
	uint8_t y;
	uint8_t sp;
	uint8_t sr;
	uint8_t before1;
	uint8_t after1;
} history_write_one_6502_t; /* 10 bytes */

typedef struct {
	uint8_t instruction[3];
	uint8_t a;
	uint8_t x;
	uint8_t y;
	uint8_t sp;
	uint8_t sr;
	uint8_t before1;
	uint8_t after1;
	uint8_t before2;
	uint8_t after2;
} history_write_two_6502_t; /* 12 bytes */

typedef struct {
	uint8_t instruction[3];
	uint8_t a;
	uint8_t x;
	uint8_t y;
	uint8_t sp;
	uint8_t sr;
	uint8_t before1;
	uint8_t after1;
	uint8_t before2;
	uint8_t after2;
	uint8_t before3;
	uint8_t after3;
} history_write_three_6502_t; /* 14 bytes */

/* flags */
#define FLAG_BRANCH 1
#define FLAG_JUMP 2
#define FLAG_RTS 3
#define FLAG_RTI 4
#define FLAG_ORIGIN 5
#define FLAG_DATA_BYTES 6
#define FLAG_WRITE_ONE 7
#define FLAG_WRITE_TWO 8
#define FLAG_WRITE_THREE 9
#define FLAG_VALID_TARGET_ADDR 32
#define FLAG_LABEL 64
#define FLAG_UNDOC 128

/* disassembler types */
#define DISASM_CODE 0
#define DISASM_DATA 1
#define DISASM_ANTIC 2
#define DISASM_JUMPMAN_LEVEL 3
#define DISASM_JUMPMAN_HARVEST 4
#define DISASM_UNINITIALIZED_DATA 5

#endif /* LIBUDIS_H */
