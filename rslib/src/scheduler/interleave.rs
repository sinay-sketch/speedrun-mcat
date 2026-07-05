// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun (MCAT) addition: **discrimination-aware interleaving**, the
//! learning-science feature measured by the ablation in
//! `tools/speedrun/ablation/interleaving_ablation.py`.
//!
//! It composes a study session so that *confusable cross-topic* cards sit next
//! to each other (round-robin across topics) instead of being blocked by topic.
//! Adjacent contrast is what builds the ability to tell similar items apart
//! (Kornell & Bjork 2008; Rohrer 2012). This is a **read-only** reordering — it
//! does not change scheduling or spacing (the ablation holds FSRS spacing
//! constant), so it can't corrupt data or affect undo.

use crate::prelude::*;

/// Reorder `cards` (each tagged with a `topic` key) by round-robin across topics,
/// so adjacent cards tend to come from different (confusable) topics rather than
/// being grouped by topic. Returns a deterministic permutation of the input ids.
pub fn interleave_by_topic(cards: &[(CardId, u32)]) -> Vec<CardId> {
    use std::collections::BTreeMap;
    let mut buckets: BTreeMap<u32, Vec<CardId>> = BTreeMap::new();
    for (cid, topic) in cards {
        buckets.entry(*topic).or_default().push(*cid);
    }
    // Take one card from each topic in turn until all buckets are drained.
    let mut queues: Vec<std::collections::VecDeque<CardId>> =
        buckets.into_values().map(std::collections::VecDeque::from).collect();
    let mut out = Vec::with_capacity(cards.len());
    let mut progressed = true;
    while progressed {
        progressed = false;
        for q in &mut queues {
            if let Some(cid) = q.pop_front() {
                out.push(cid);
                progressed = true;
            }
        }
    }
    out
}

/// Count adjacent same-topic pairs in an ordering (lower = better interleaving).
#[cfg(test)]
fn adjacent_same_topic(order: &[CardId], topic_of: &std::collections::HashMap<i64, u32>) -> usize {
    order
        .windows(2)
        .filter(|w| topic_of[&w[0].0] == topic_of[&w[1].0])
        .count()
}

#[cfg(test)]
mod test {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn interleave_is_a_permutation() {
        let cards: Vec<(CardId, u32)> = (0..9).map(|i| (CardId(i), (i / 3) as u32)).collect();
        let out = interleave_by_topic(&cards);
        let mut ids: Vec<i64> = out.iter().map(|c| c.0).collect();
        ids.sort();
        assert_eq!(ids, (0..9).collect::<Vec<_>>(), "must be a permutation of the input");
    }

    #[test]
    fn interleave_spreads_topics_vs_blocked() {
        // 3 topics × 3 cards, presented blocked (0,0,0,1,1,1,2,2,2).
        let cards: Vec<(CardId, u32)> = (0..9).map(|i| (CardId(i), (i / 3) as u32)).collect();
        let topic_of: HashMap<i64, u32> = cards.iter().map(|(c, t)| (c.0, *t)).collect();

        let blocked: Vec<CardId> = cards.iter().map(|(c, _)| *c).collect();
        let interleaved = interleave_by_topic(&cards);

        let blocked_adj = adjacent_same_topic(&blocked, &topic_of); // 6
        let inter_adj = adjacent_same_topic(&interleaved, &topic_of);
        assert_eq!(blocked_adj, 6, "blocked input has every same-topic pair adjacent");
        assert_eq!(inter_adj, 0, "round-robin interleaving puts no two same-topic cards adjacent");
        assert!(inter_adj < blocked_adj);
    }

    #[test]
    fn handles_uneven_topics() {
        // topic 0 has 4 cards, topic 1 has 1 — must still be a full permutation.
        let cards = vec![
            (CardId(1), 0),
            (CardId(2), 0),
            (CardId(3), 0),
            (CardId(4), 0),
            (CardId(5), 1),
        ];
        let out = interleave_by_topic(&cards);
        assert_eq!(out.len(), 5);
        let mut ids: Vec<i64> = out.iter().map(|c| c.0).collect();
        ids.sort();
        assert_eq!(ids, vec![1, 2, 3, 4, 5]);
    }
}
