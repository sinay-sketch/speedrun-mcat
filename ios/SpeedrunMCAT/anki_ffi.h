// Speedrun (MCAT): C ABI over Anki's shared Rust engine (see rslib/ffi).
// License: GNU AGPL, version 3 or later.
#ifndef ANKI_FFI_H
#define ANKI_FFI_H

#include <stdint.h>

// Opaque handle to an Anki Collection living in the Rust engine.
typedef struct Collection Collection;

// Open (or create) a collection at `path`. Free with speedrun_close. NULL on error.
Collection *speedrun_open(const char *path);

// Resolve a deck id by its human name (e.g. "MCAT::Speedrun Starter"), or -1.
int64_t speedrun_deck_id(Collection *col, const char *name);

// JSON for the next due card: {"card_id":N,"question":"..","answer":".."} or {}.
// Caller must free with speedrun_free_string.
char *speedrun_next_card(Collection *col);

// Answer `card_id` with rating 1..4 (Again/Hard/Good/Easy). 0 ok, -1 error.
int32_t speedrun_answer(Collection *col, int64_t card_id, unsigned int rating);

// JSON for a deck's honest Memory score (MasteryForDeck). Free with speedrun_free_string.
char *speedrun_mastery(Collection *col, int64_t did);

// Free a string returned by this library.
void speedrun_free_string(char *s);

// Close a collection opened with speedrun_open.
void speedrun_close(Collection *col);

#endif // ANKI_FFI_H
