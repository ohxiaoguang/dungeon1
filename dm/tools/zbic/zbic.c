// SPDX-License-Identifier: MIT
// ZBIC segment decoder for dm/tools/nsoseg.py.
//
// Nintendo's 22.0.0 SDK compresses NSO segments with ZBIC instead of LZ4 and marks it with
// NSO header flag bit 7 (UseZbicCompression). ZBIC is zstd with a customised entropy-table
// reader (binary interpolative coding) and the frame magic 0x4349425A; no stock zstd
// decoder accepts it. zbicdeclib.inc is Meta's zstd 1.5.7 decompression-only amalgamation
// carrying Nintendo's reader (BSD-3-Clause, see LICENSE.zstd), so this file only:
//   * provides the two trace hooks the amalgamation references on Apple platforms, where
//     zstd's weak-symbol path is compiled out (they return "tracing off"),
//   * exposes one bounded, allocation-free one-shot call for ctypes.
//
// The caller always passes the exact output size from the NSO header, so a stream that
// would expand beyond it fails inside zstd instead of being trusted.
//
// Build (dm/tools/nsoseg.py does this lazily, once, into its cache directory):
//   xcrun clang -dynamiclib -O2 -w -o libzbic-<fingerprint>.dylib dm/tools/zbic/zbic.c
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "zbicdeclib.inc"

/* zstd_trace.h is only active where weak symbols exist (not __APPLE__), so the hooks the
 * amalgamation calls must be defined here. Returning 0 means "no trace sink". */
ZSTD_TraceCtx ZSTD_trace_decompress_begin(struct ZSTD_DCtx_s const *dctx) { (void)dctx; return 0; }
void ZSTD_trace_decompress_end(ZSTD_TraceCtx ctx, ZSTD_Trace const *trace) { (void)ctx; (void)trace; }

#define ZBIC_SECONDS_MAX (2u * 1024u * 1024u * 1024u)   /* one NSO segment: refuse anything larger */

/* The amalgamation is built with ZSTD_STRIP_ERROR_STRINGS (Nintendo's own setting), so
 * ZSTD_getErrorName only says "Error strings stripped". Name the codes that a decompression
 * can actually hit instead; the values are the public zstd_errors.h enum. */
static const char *code_name(ZSTD_ErrorCode code) {
    switch (code) {
        case ZSTD_error_prefix_unknown: return "unknown frame prefix (not a ZBIC/zstd frame)";
        case ZSTD_error_version_unsupported: return "unsupported frame version";
        case ZSTD_error_frameParameter_unsupported: return "unsupported frame parameter";
        case ZSTD_error_frameParameter_windowTooLarge: return "frame window too large";
        case ZSTD_error_corruption_detected: return "corrupt frame data";
        case ZSTD_error_checksum_wrong: return "frame checksum mismatch";
        case ZSTD_error_literals_headerWrong: return "corrupt literals header";
        case ZSTD_error_dictionary_corrupted:
        case ZSTD_error_dictionary_wrong: return "unexpected dictionary";
        case ZSTD_error_dstSize_tooSmall: return "decoded data is larger than the header declares";
        case ZSTD_error_srcSize_wrong: return "frame size does not match the input (truncated, or trailing bytes)";
        case ZSTD_error_memory_allocation: return "out of memory";
        default: return NULL;
    }
}

/* Decompress one ZBIC frame into dst, whose capacity is the size the NSO header declares.
 * Returns 0 on success with *out_size == dst_capacity, or -1 with a message in error. */
int zbic_decompress(void *dst, size_t dst_capacity, const void *src, size_t src_size,
                    size_t *out_size, char *error, size_t error_capacity) {
    if (out_size) *out_size = 0;
    if (!dst || !src || !src_size || !dst_capacity) {
        if (error && error_capacity) snprintf(error, error_capacity, "empty input, output or buffer");
        return -1;
    }
    if (dst_capacity > ZBIC_SECONDS_MAX || src_size > ZBIC_SECONDS_MAX) {
        if (error && error_capacity) snprintf(error, error_capacity, "frame too large (%zu -> %zu bytes)", src_size, dst_capacity);
        return -1;
    }
    // ZBIC frames carry Nintendo's magic; reject anything else before zstd's own parsing so
    // that a mislabelled segment (flag bit 7 set on an LZ4 or raw segment) is named as such.
    static const unsigned char magic[4] = {0x5A, 0x42, 0x49, 0x43};   /* "ZBIC" little-endian */
    if (memcmp(src, magic, sizeof magic)) {
        if (error && error_capacity) snprintf(error, error_capacity, "not a ZBIC frame (magic %.2x%.2x%.2x%.2x)",
                                              ((const unsigned char *)src)[0], ((const unsigned char *)src)[1],
                                              ((const unsigned char *)src)[2], ((const unsigned char *)src)[3]);
        return -1;
    }
    size_t produced = ZSTD_decompress(dst, dst_capacity, src, src_size);
    if (ZSTD_isError(produced)) {
        if (error && error_capacity) {
            ZSTD_ErrorCode code = ZSTD_getErrorCode(produced);
            const char *name = code_name(code);
            if (name) snprintf(error, error_capacity, "%s (zstd error %d)", name, (int)code);
            else snprintf(error, error_capacity, "zstd error %d", (int)code);
        }
        return -1;
    }
    if (produced != dst_capacity) {
        if (error && error_capacity) snprintf(error, error_capacity, "decoded %zu bytes, header declares %zu", produced, dst_capacity);
        return -1;
    }
    if (out_size) *out_size = produced;
    if (error && error_capacity) *error = 0;
    return 0;
}
