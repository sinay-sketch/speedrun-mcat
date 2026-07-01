// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun (MCAT): a thin C FFI over Anki's Rust engine so an iOS companion
//! can drive review sessions on the **same shared engine** as the desktop app.
//!
//! The heavy lifting (scheduling, FSRS, rendering, storage, and the new
//! `MasteryForDeck` query) all live in `rslib` and are reused verbatim — the
//! Swift layer only owns the UI. Everything is exposed as a handful of
//! `extern "C"` functions returning simple types / JSON strings, so the mobile
//! side needs no protobuf tooling.

use std::ffi::c_char;
use std::ffi::c_uint;
use std::ffi::CStr;
use std::ffi::CString;
use std::ptr;

use anki::collection::CollectionBuilder;
use anki::error::Result;
use anki::prelude::*;
use anki::scheduler::answering::CardAnswer;
use anki::scheduler::answering::Rating;

fn to_c_string(s: String) -> *mut c_char {
    CString::new(s)
        .map(CString::into_raw)
        .unwrap_or(ptr::null_mut())
}

/// Open (or create) a collection at `path`. Returns a pointer owned by the
/// caller — free it with [`speedrun_close`]. Returns null on error.
///
/// # Safety
/// `path` must be a valid, NUL-terminated C string.
#[no_mangle]
pub unsafe extern "C" fn speedrun_open(path: *const c_char) -> *mut Collection {
    if path.is_null() {
        return ptr::null_mut();
    }
    let path = match CStr::from_ptr(path).to_str() {
        Ok(p) => p,
        Err(_) => return ptr::null_mut(),
    };
    match CollectionBuilder::new(path).build() {
        Ok(col) => Box::into_raw(Box::new(col)),
        Err(_) => ptr::null_mut(),
    }
}

/// Return JSON for the next due card:
/// `{"card_id":N,"question":"…","answer":"…"}`, or `{}` when nothing is due.
/// Free the result with [`speedrun_free_string`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_next_card(col: *mut Collection) -> *mut c_char {
    let Some(col) = col.as_mut() else {
        return to_c_string("{}".into());
    };
    to_c_string(next_card_json(col).unwrap_or_else(|_| "{}".into()))
}

fn next_card_json(col: &mut Collection) -> Result<String> {
    // Build a full session queue and take the top card. (Fetching a single card
    // can under-report the queue after an answer clears/rebuilds it.)
    let queued = col.get_queued_cards(50, false)?;
    let Some(qc) = queued.cards.first() else {
        return Ok("{}".into());
    };
    let cid = qc.card.id();
    let render = col.render_existing_card(cid, false, false)?;
    Ok(serde_json::json!({
        "card_id": cid.0,
        "question": render.question().into_owned(),
        "answer": render.answer().into_owned(),
    })
    .to_string())
}

/// Answer `card_id` with `rating` (1=Again, 2=Hard, 3=Good, 4=Easy) through the
/// shared scheduler. Returns 0 on success, -1 on error / bad rating.
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_answer(
    col: *mut Collection,
    card_id: i64,
    rating: c_uint,
) -> i32 {
    let Some(col) = col.as_mut() else {
        return -1;
    };
    let rating = match rating {
        1 => Rating::Again,
        2 => Rating::Hard,
        3 => Rating::Good,
        4 => Rating::Easy,
        _ => return -1,
    };
    match answer_card(col, CardId(card_id), rating) {
        Ok(()) => 0,
        Err(_) => -1,
    }
}

fn answer_card(col: &mut Collection, cid: CardId, rating: Rating) -> Result<()> {
    let states = col.get_scheduling_states(cid)?;
    let new_state = match rating {
        Rating::Again => states.again,
        Rating::Hard => states.hard,
        Rating::Good => states.good,
        Rating::Easy => states.easy,
    };
    let mut answer = CardAnswer {
        card_id: cid,
        current_state: states.current,
        new_state,
        rating,
        answered_at: TimestampMillis::now(),
        milliseconds_taken: 0,
        custom_data: None,
        from_queue: true,
    };
    col.answer_card(&mut answer)?;
    Ok(())
}

/// Return JSON for a deck's honest Memory score (the new `MasteryForDeck`
/// query): mean retrievability, 95% band, counts, and the give-up flag.
/// Free the result with [`speedrun_free_string`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_mastery(col: *mut Collection, did: i64) -> *mut c_char {
    let Some(col) = col.as_mut() else {
        return to_c_string("{}".into());
    };
    let json = match col.mastery_for_deck(DeckId(did)) {
        Ok(m) => serde_json::json!({
            "mean_retrievability": m.mean_retrievability,
            "lower": m.lower,
            "upper": m.upper,
            "cards_counted": m.cards_counted,
            "cards_total": m.cards_total,
            "mature": m.mature,
            "sufficient_data": m.sufficient_data,
        })
        .to_string(),
        Err(_) => "{}".into(),
    };
    to_c_string(json)
}

/// Free a string returned by this library.
///
/// # Safety
/// `s` must be a pointer returned by one of this library's functions, freed once.
#[no_mangle]
pub unsafe extern "C" fn speedrun_free_string(s: *mut c_char) {
    if !s.is_null() {
        drop(CString::from_raw(s));
    }
}

/// Close a collection opened with [`speedrun_open`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`], closed once.
#[no_mangle]
pub unsafe extern "C" fn speedrun_close(col: *mut Collection) {
    if !col.is_null() {
        drop(Box::from_raw(col));
    }
}
