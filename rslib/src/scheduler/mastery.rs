// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun (MCAT) addition: a read-only aggregate "mastery" query.
//!
//! Aggregates the per-card FSRS retrievability of the cards in a deck (and its
//! children) into an honest deck-level **Memory score**: a point estimate (the
//! mean predicted probability of recall), a 95% band derived from the
//! Poisson-binomial variance of the per-card recall probabilities, and a
//! `sufficient_data` flag that implements the "give-up rule" — below a minimum
//! number of cards with an FSRS memory state we refuse to report a number.
//!
//! This is deliberately **read-only**: it never mutates the collection, so it
//! needs no `transact`/undo entry and cannot corrupt data. It reuses the same
//! retrievability computation the browser uses (see `browser_table.rs`).

use fsrs::FSRS5_DEFAULT_DECAY;
use fsrs::FSRS;

use crate::prelude::*;
use crate::search::SearchNode;

/// Minimum number of cards with an FSRS memory state required before we report
/// a Memory score. Below this, the estimate is too noisy to be honest, so the
/// give-up rule fires (`sufficient_data = false`). Chosen to match the
/// cold-start guidance that knowledge estimates are unstable under ~10-20
/// observations.
pub const MIN_CARDS_FOR_MASTERY: u32 = 20;

/// A card is "mature" once its interval reaches this many days (Anki
/// convention).
pub const MATURE_INTERVAL_DAYS: u32 = 21;

/// The honest, aggregated Memory score for a deck.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DeckMastery {
    /// Point estimate: mean predicted probability of recall across the counted
    /// cards, in `[0, 1]`.
    pub mean_retrievability: f32,
    /// Lower bound of the 95% band, in `[0, 1]`.
    pub lower: f32,
    /// Upper bound of the 95% band, in `[0, 1]`.
    pub upper: f32,
    /// Number of cards that had an FSRS memory state (the denominator of the
    /// estimate; also drives the give-up rule).
    pub cards_counted: u32,
    /// Total cards in the deck and its children.
    pub cards_total: u32,
    /// Cards whose interval is at least [`MATURE_INTERVAL_DAYS`].
    pub mature: u32,
    /// False when `cards_counted < MIN_CARDS_FOR_MASTERY` (give-up rule).
    pub sufficient_data: bool,
}

impl Collection {
    /// Aggregate the FSRS retrievability of the cards in `did` (including
    /// child decks) into a [`DeckMastery`]. Read-only.
    pub fn mastery_for_deck(&mut self, did: DeckId) -> Result<DeckMastery> {
        let timing = self.timing_today()?;
        let fsrs = FSRS::new(None)?;
        let cards = self.all_cards_for_search(SearchNode::from_deck_id(did, true))?;
        let cards_total = cards.len() as u32;

        let mut mature = 0u32;
        let mut retrievabilities: Vec<f32> = Vec::with_capacity(cards.len());
        for card in &cards {
            if card.interval >= MATURE_INTERVAL_DAYS {
                mature += 1;
            }
            if let (Some(state), Some(seconds)) =
                (card.memory_state, card.seconds_since_last_review(&timing))
            {
                let decay = card.decay.unwrap_or(FSRS5_DEFAULT_DECAY);
                let r = fsrs.current_retrievability_seconds(state.into(), seconds, decay);
                retrievabilities.push(r);
            }
        }

        let cards_counted = retrievabilities.len() as u32;
        let (mean, lower, upper) = poisson_binomial_band(&retrievabilities);
        Ok(DeckMastery {
            mean_retrievability: mean,
            lower,
            upper,
            cards_counted,
            cards_total,
            mature,
            sufficient_data: cards_counted >= MIN_CARDS_FOR_MASTERY,
        })
    }
}

/// Given per-card recall probabilities, return `(mean, lower, upper)` where the
/// band is a 95% normal approximation of the mean of a Poisson-binomial
/// distribution (variance = Σ pᵢ(1-pᵢ)). All three values are clamped to
/// `[0, 1]`. An empty input yields `(0, 0, 0)`.
fn poisson_binomial_band(ps: &[f32]) -> (f32, f32, f32) {
    let n = ps.len();
    if n == 0 {
        return (0.0, 0.0, 0.0);
    }
    let n_f = n as f32;
    let mean = ps.iter().sum::<f32>() / n_f;
    // Variance of the *mean* of independent Bernoulli(pᵢ): Σ pᵢ(1-pᵢ) / n².
    let var = ps.iter().map(|p| p * (1.0 - p)).sum::<f32>() / (n_f * n_f);
    let margin = 1.96 * var.sqrt();
    (mean, (mean - margin).max(0.0), (mean + margin).min(1.0))
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::card::Card;
    use crate::card::FsrsMemoryState;

    #[test]
    fn band_is_empty_for_no_cards() {
        assert_eq!(poisson_binomial_band(&[]), (0.0, 0.0, 0.0));
    }

    #[test]
    fn band_collapses_when_recall_is_certain() {
        // With all probabilities at 1.0 the variance is zero, so the band
        // collapses onto the mean and stays within [0, 1].
        let (mean, lower, upper) = poisson_binomial_band(&[1.0, 1.0, 1.0]);
        assert_eq!(mean, 1.0);
        assert_eq!(lower, 1.0);
        assert_eq!(upper, 1.0);

        // A mix averages correctly and produces a non-degenerate, ordered band.
        let (mean, lower, upper) = poisson_binomial_band(&[0.5, 0.5, 0.5, 0.5]);
        assert!((mean - 0.5).abs() < 1e-6);
        assert!(lower < mean && mean < upper);
        assert!(lower >= 0.0 && upper <= 1.0);
    }

    #[test]
    fn empty_deck_gives_up() {
        let mut col = Collection::new();
        // Default deck (id 1) exists but has no cards.
        let m = col.mastery_for_deck(DeckId(1)).unwrap();
        assert_eq!(m.cards_total, 0);
        assert_eq!(m.cards_counted, 0);
        assert!(!m.sufficient_data, "no cards => give-up rule fires");
    }

    #[test]
    fn counts_cards_and_applies_give_up_threshold() {
        let mut col = Collection::new();
        let now = TimestampSecs::now();
        // Add MIN_CARDS_FOR_MASTERY reviewed cards, each with a memory state and
        // a last-review time one day ago, to the default deck.
        for _ in 0..MIN_CARDS_FOR_MASTERY {
            let mut card = Card::new(NoteId(0), 0, DeckId(1), 0);
            card.interval = 30; // mature
            card.memory_state = Some(FsrsMemoryState {
                stability: 100.0,
                difficulty: 5.0,
            });
            card.last_review_time = Some(TimestampSecs(now.0 - 86_400));
            col.add_card(&mut card).unwrap();
        }
        let m = col.mastery_for_deck(DeckId(1)).unwrap();
        assert_eq!(m.cards_total, MIN_CARDS_FOR_MASTERY);
        assert_eq!(m.cards_counted, MIN_CARDS_FOR_MASTERY);
        assert_eq!(m.mature, MIN_CARDS_FOR_MASTERY);
        assert!(m.sufficient_data, "enough cards => report a score");
        // A day after a review with high stability, recall should stay very high.
        assert!(
            m.mean_retrievability > 0.9,
            "got {}",
            m.mean_retrievability
        );
        assert!(m.lower <= m.mean_retrievability && m.mean_retrievability <= m.upper);
    }
}
