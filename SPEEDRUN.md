# Speedrun — an MCAT study app built on Anki

**Exam: MCAT** (scored 472–528; four sections each 118–132).

Speedrun is a fork of [Anki](https://apps.ankiweb.net) (© Ankitects Pty Ltd and contributors)
that adds an MCAT-specific study engine: an aggregate **mastery / memory** query in the
Rust core, a three-score dashboard (Memory / Performance / Readiness) with honest ranges and
a give-up rule, cross-discipline interleaving, and a recall→reasoning bridge. See
`../BrainLift_v2_Enhanced.md` for the thesis and `~/.claude/plans/snuggly-spinning-willow.md`
for the full PRD.

## License & credit

This project is licensed under the **GNU AGPL, version 3 or later**, the same license as
upstream Anki, with portions under BSD-3 (see `CONTRIBUTORS`). All original Anki code and
trademarks belong to **Ankitects Pty Ltd and contributors**. This is an independent,
unaffiliated fork created for the Alpha AI Engineering "Speedrun" project.

Upstream: https://github.com/ankitects/anki

## What changed vs. upstream (Wednesday build)

- **Rust core:** new read-only RPC `MasteryForDeck` on `SchedulerService`
  (`proto/anki/scheduler.proto`, `rslib/src/scheduler/mastery.rs`,
  `rslib/src/scheduler/service/mod.rs`) that aggregates per-card FSRS retrievability into a
  deck-level Memory score with a 95% band and a sufficient-data flag. Read-only ⇒ undo and
  collection integrity are unaffected.
- **Mobile:** a thin C-FFI crate (`rslib/ffi/`) exposing the backend's generic
  `run_service_method` dispatch, cross-compiled to an `AnkiRust.xcframework` and driven by a
  minimal SwiftUI companion that reviews the same deck on the shared Rust engine.

## Build

Desktop dev: `just run`  ·  Full check + tests: `just check`  ·  Rust tests: `just test-rust`
(See upstream `docs/` and `CLAUDE.md` for toolchain details: Rust 1.92, Python 3.13 + uv,
Yarn 4, protoc — most are auto-downloaded. macOS needs Xcode + `brew install mpv lame`.)
