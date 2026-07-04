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
use anki::sync::collection::normal::SyncActionRequired;
use anki::sync::login::sync_login;

fn to_c_string(s: String) -> *mut c_char {
    CString::new(s)
        .map(CString::into_raw)
        .unwrap_or(ptr::null_mut())
}

/// Log in and sync the collection at `path` against a self-hosted sync server
/// at `endpoint` (e.g. "http://127.0.0.1:8080/"), using the SAME Rust sync
/// engine the desktop app uses. The caller must CLOSE any open handle to this
/// collection first (this opens its own, then closes it).
///
/// Returns: 0 = normal sync done / already in sync, 1 = full upload done,
/// 2 = full download done, -1 = error.
///
/// # Safety
/// All pointers must be valid, NUL-terminated C strings.
#[no_mangle]
pub unsafe extern "C" fn speedrun_sync(
    path: *const c_char,
    endpoint: *const c_char,
    username: *const c_char,
    password: *const c_char,
) -> i32 {
    let s = |p: *const c_char| -> Option<String> {
        (!p.is_null())
            .then(|| CStr::from_ptr(p).to_str().ok().map(str::to_string))
            .flatten()
    };
    match (s(path), s(endpoint), s(username), s(password)) {
        (Some(path), Some(endpoint), Some(username), Some(password)) => {
            match do_sync(&path, &endpoint, &username, &password) {
                Ok(code) => code,
                Err(_) => -1,
            }
        }
        _ => -1,
    }
}

fn do_sync(
    path: &str,
    endpoint: &str,
    username: &str,
    password: &str,
) -> std::result::Result<i32, Box<dyn std::error::Error>> {
    // The async sync methods need a Tokio runtime (a raw Collection has none).
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(1)
        .enable_all()
        .build()?;
    // http1-only, matching what Anki's backend uses.
    let client = reqwest::Client::builder().http1_only().build()?;
    let base = if endpoint.ends_with('/') {
        endpoint.to_string()
    } else {
        format!("{endpoint}/")
    };

    let mut col = CollectionBuilder::new(path).build()?;
    let mut auth = rt.block_on(sync_login(
        username.to_string(),
        password.to_string(),
        Some(base.clone()),
        client.clone(),
    ))?;
    auth.endpoint = Some(reqwest::Url::parse(&base)?);

    let out = rt.block_on(col.normal_sync(auth.clone(), client.clone()))?;
    match out.required {
        SyncActionRequired::NoChanges | SyncActionRequired::NormalSyncRequired => Ok(0),
        SyncActionRequired::FullSyncRequired {
            upload_ok,
            download_ok,
        } => {
            // Prefer whichever direction is exclusively allowed (initial seed):
            // server empty => upload; local empty => download.
            if download_ok && !upload_ok {
                rt.block_on(col.full_download(auth, client))?;
                Ok(2)
            } else if upload_ok {
                rt.block_on(col.full_upload(auth, client))?;
                Ok(1)
            } else if download_ok {
                rt.block_on(col.full_download(auth, client))?;
                Ok(2)
            } else {
                Err("full sync required but neither direction allowed".into())
            }
        }
    }
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

/// Resolve a deck id by its human name (e.g. "MCAT::Speedrun Starter") in the
/// open collection. Returns the id, or -1 if not found. Lets the app avoid a
/// hard-coded deck id, so it works against whatever collection is loaded.
///
/// # Safety
/// `col` must be a pointer from [`speedrun_open`]; `name` a valid C string.
#[no_mangle]
pub unsafe extern "C" fn speedrun_deck_id(col: *mut Collection, name: *const c_char) -> i64 {
    let Some(col) = col.as_mut() else {
        return -1;
    };
    if name.is_null() {
        return -1;
    }
    let Ok(name) = CStr::from_ptr(name).to_str() else {
        return -1;
    };
    match col.get_deck_id(name) {
        Ok(Some(did)) => did.0,
        _ => -1,
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

/// Return JSON for a deck's honest **Performance** score (online Elo over the
/// review history): `{"mastery":f,"lower":f,"upper":f,"reviews":N,
/// "sufficient_data":bool}`. Free with [`speedrun_free_string`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_performance(col: *mut Collection, did: i64) -> *mut c_char {
    let Some(col) = col.as_mut() else {
        return to_c_string("{}".into());
    };
    let json = match col.performance_for_deck(DeckId(did)) {
        Ok(p) => serde_json::json!({
            "mastery": p.mastery,
            "lower": p.lower,
            "upper": p.upper,
            "reviews": p.reviews_counted,
            "cards_reviewed": p.cards_reviewed,
            "sufficient_data": p.sufficient_data,
        })
        .to_string(),
        Err(_) => "{}".into(),
    };
    to_c_string(json)
}

/// Return JSON for a deck's honest **Readiness** score (provisional MCAT scaled
/// score, 472–528): `{"scaled":N,"lower":N,"upper":N,"confident":bool,
/// "sufficient_data":bool}`. Free with [`speedrun_free_string`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_readiness(col: *mut Collection, did: i64) -> *mut c_char {
    let Some(col) = col.as_mut() else {
        return to_c_string("{}".into());
    };
    let json = match col.readiness_for_deck(DeckId(did)) {
        Ok(r) => serde_json::json!({
            "scaled": r.scaled_score,
            "lower": r.lower,
            "upper": r.upper,
            "confident": r.confident,
            "sufficient_data": r.sufficient_data,
            "full_lengths": r.full_lengths,
        })
        .to_string(),
        Err(_) => "{}".into(),
    };
    to_c_string(json)
}

/// Return JSON with a deck's study-queue counts: `{"new":N,"learn":N,"due":N,
/// "total":N}`. These come from `Collection::deck_tree` — the SAME engine call
/// the desktop deck list uses (daily limits applied) — so the phone shows the
/// exact same New / Learn / Due numbers as the desktop. Free with
/// [`speedrun_free_string`].
///
/// # Safety
/// `col` must be a pointer returned by [`speedrun_open`].
#[no_mangle]
pub unsafe extern "C" fn speedrun_deck_counts(col: *mut Collection, did: i64) -> *mut c_char {
    let Some(col) = col.as_mut() else {
        return to_c_string("{}".into());
    };
    to_c_string(deck_counts_json(col, DeckId(did)).unwrap_or_else(|_| "{}".into()))
}

fn deck_counts_json(col: &mut Collection, did: DeckId) -> Result<String> {
    use anki_proto::decks::DeckTreeNode;
    // Recursively locate this deck's node in the due tree.
    fn find<'a>(node: &'a DeckTreeNode, did: i64) -> Option<&'a DeckTreeNode> {
        if node.deck_id == did {
            return Some(node);
        }
        node.children.iter().find_map(|c| find(c, did))
    }
    let tree = col.deck_tree(Some(TimestampSecs::now()))?;
    let (new, learn, due, total) = match find(&tree, did.0) {
        Some(n) => (n.new_count, n.learn_count, n.review_count, n.total_in_deck),
        None => (0, 0, 0, 0),
    };
    Ok(serde_json::json!({
        "new": new,
        "learn": learn,
        "due": due,
        "total": total,
    })
    .to_string())
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
