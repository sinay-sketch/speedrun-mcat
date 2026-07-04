// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun (MCAT) addition: read-only **Performance** and **Readiness** scores,
//! the second and third of the three honest, ranged dashboard scores.
//!
//! **Performance** replays the deck's review history as an online Elo game
//! (student vs. card): an `Again` is a loss, `Hard`/`Good`/`Easy` a win. It
//! reports the student's predicted probability of answering an average-difficulty
//! card, a band that narrows as the number of reviews grows, and a give-up flag.
//!
//! **Readiness** is a transparent monotone link of Memory + Performance onto the
//! MCAT scaled-score range (472–528), with a widened band. It is deliberately
//! marked **provisional** (never "confident"): a confident readiness needs scored
//! full-length exams, which flashcard data cannot substitute for. When the inputs
//! are themselves insufficient it abstains entirely (give-up rule).
//!
//! Both are **read-only** — no `transact`/undo, no corruption risk.

use std::collections::HashMap;

use crate::prelude::*;
use crate::revlog::RevlogReviewKind;
use crate::search::SearchNode;

/// Minimum graded reviews before a Performance number is reported (give-up rule).
pub const MIN_REVIEWS_FOR_PERFORMANCE: u32 = 30;

const ELO_K: f32 = 24.0;
const ELO_SCALE: f32 = 400.0;
const ELO_START: f32 = 1500.0;

const MCAT_MIN: f32 = 472.0;
const MCAT_MAX: f32 = 528.0;

/// The honest, aggregated Performance score for a deck.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DeckPerformance {
    /// Predicted probability of correctly answering an average-difficulty card, `[0,1]`.
    pub mastery: f32,
    pub lower: f32,
    pub upper: f32,
    /// Final student Elo rating.
    pub student_rating: f32,
    /// Graded reviews replayed.
    pub reviews_counted: u32,
    /// Cards with at least one graded review.
    pub cards_reviewed: u32,
    /// False when `reviews_counted < MIN_REVIEWS_FOR_PERFORMANCE` (give-up rule).
    pub sufficient_data: bool,
}

/// Expected score (win probability) of `student` against a card of rating `card`.
fn expected(student: f32, card: f32) -> f32 {
    1.0 / (1.0 + 10f32.powf((card - student) / ELO_SCALE))
}

/// Replay a chronological sequence of `(card, won)` reviews as an online Elo
/// game. Returns the final student rating and per-card difficulty. Pure, so it
/// is unit-testable without a collection.
fn elo_replay(events: &[(CardId, bool)]) -> (f32, HashMap<CardId, f32>) {
    let mut student = ELO_START;
    let mut difficulty: HashMap<CardId, f32> = HashMap::new();
    for (cid, won) in events {
        let d = *difficulty.get(cid).unwrap_or(&ELO_START);
        let e = expected(student, d);
        let s = if *won { 1.0 } else { 0.0 };
        student += ELO_K * (s - e);
        difficulty.insert(*cid, d - ELO_K * (s - e));
    }
    (student, difficulty)
}

impl Collection {
    /// Online-Elo Performance score over the deck's review history. Read-only.
    pub fn performance_for_deck(&mut self, did: DeckId) -> Result<DeckPerformance> {
        let cards = self.all_cards_for_search(SearchNode::from_deck_id(did, true))?;
        // Collect every graded review as (revlog_id, card, won), then replay in
        // time order (revlog id is a millisecond timestamp).
        let mut events: Vec<(i64, CardId, bool)> = Vec::new();
        for card in &cards {
            for e in self.storage.get_revlog_entries_for_card(card.id)? {
                let graded = matches!(
                    e.review_kind,
                    RevlogReviewKind::Learning
                        | RevlogReviewKind::Review
                        | RevlogReviewKind::Relearning
                ) && (1..=4).contains(&e.button_chosen);
                if graded {
                    events.push((e.id.0, card.id, e.button_chosen >= 2));
                }
            }
        }
        events.sort_by_key(|e| e.0);
        let ordered: Vec<(CardId, bool)> = events.iter().map(|(_, c, w)| (*c, *w)).collect();
        let (student, difficulty) = elo_replay(&ordered);

        let reviews_counted = ordered.len() as u32;
        let cards_reviewed = difficulty.len() as u32;
        let mean_d = if difficulty.is_empty() {
            ELO_START
        } else {
            difficulty.values().sum::<f32>() / difficulty.len() as f32
        };
        let mastery = expected(student, mean_d);
        // Rating uncertainty shrinks with the number of reviews; propagate to p.
        let sigma = ELO_SCALE / (reviews_counted.max(1) as f32).sqrt();
        Ok(DeckPerformance {
            mastery,
            lower: expected(student - 1.96 * sigma, mean_d).max(0.0),
            upper: expected(student + 1.96 * sigma, mean_d).min(1.0),
            student_rating: student,
            reviews_counted,
            cards_reviewed,
            sufficient_data: reviews_counted >= MIN_REVIEWS_FOR_PERFORMANCE,
        })
    }
}

/// The honest, aggregated Readiness score for a deck (provisional MCAT scaled score).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DeckReadiness {
    /// Provisional MCAT scaled score in `[472, 528]`.
    pub scaled_score: u32,
    pub lower: u32,
    pub upper: u32,
    /// Always false: a *confident* readiness needs scored full-length exams, which
    /// flashcard data cannot substitute for. We only ever show a provisional value.
    pub confident: bool,
    /// False when Memory or Performance is itself insufficient — then we abstain.
    pub sufficient_data: bool,
}

impl Collection {
    /// Transparent monotone link of Memory + Performance onto the MCAT scale, with
    /// a widened band. Provisional by construction. Read-only.
    pub fn readiness_for_deck(&mut self, did: DeckId) -> Result<DeckReadiness> {
        let mem = self.mastery_for_deck(did)?;
        let perf = self.performance_for_deck(did)?;
        if !mem.sufficient_data || !perf.sufficient_data {
            return Ok(DeckReadiness {
                scaled_score: 0,
                lower: 0,
                upper: 0,
                confident: false,
                sufficient_data: false,
            });
        }
        // Equal-weight blend of recall (Memory) and application skill (Performance).
        let frac = |m: f32, p: f32| (0.5 * m + 0.5 * p).clamp(0.0, 1.0);
        let to_scaled = |f: f32| MCAT_MIN + f * (MCAT_MAX - MCAT_MIN);
        let point = frac(mem.mean_retrievability, perf.mastery);
        let lo = frac(mem.lower, perf.lower);
        let hi = frac(mem.upper, perf.upper);
        // Widen the band by 20% (provisional; deliberately wider than AAMC's ±2).
        let widen = 0.2 * (hi - lo);
        Ok(DeckReadiness {
            scaled_score: to_scaled(point).round() as u32,
            lower: to_scaled((lo - widen).max(0.0)).round() as u32,
            upper: to_scaled((hi + widen).min(1.0)).round() as u32,
            confident: false,
            sufficient_data: true,
        })
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn expected_is_symmetric_and_monotonic() {
        assert!((expected(1500.0, 1500.0) - 0.5).abs() < 1e-6);
        assert!(expected(1600.0, 1500.0) > expected(1400.0, 1500.0));
    }

    #[test]
    fn elo_rewards_wins_and_punishes_losses() {
        let c = CardId(1);
        let wins: Vec<(CardId, bool)> = (0..20).map(|_| (c, true)).collect();
        let (s_win, _) = elo_replay(&wins);
        assert!(s_win > ELO_START, "all wins should raise the rating: {s_win}");

        let losses: Vec<(CardId, bool)> = (0..20).map(|_| (c, false)).collect();
        let (s_loss, _) = elo_replay(&losses);
        assert!(s_loss < ELO_START, "all losses should lower the rating: {s_loss}");
    }

    #[test]
    fn empty_deck_gives_up() {
        let mut col = Collection::new();
        let p = col.performance_for_deck(DeckId(1)).unwrap();
        assert_eq!(p.reviews_counted, 0);
        assert!(!p.sufficient_data, "no reviews => Performance give-up fires");
    }

    #[test]
    fn readiness_abstains_without_enough_data() {
        let mut col = Collection::new();
        let r = col.readiness_for_deck(DeckId(1)).unwrap();
        assert!(!r.sufficient_data, "no data => Readiness abstains");
        assert!(!r.confident, "Readiness is never confident without full-lengths");
    }
}
