// Speedrun (MCAT) iOS companion.
// License: GNU AGPL, version 3 or later.
//
// Minimal two-screen companion that runs a real review session on the SAME
// Anki Rust engine as the desktop app (via the anki-ffi C ABI):
//   Home  → deck + honest Memory score (MasteryForDeck) + Study button
//   Study → review the due cards, with a Back button
// The heavy lifting (scheduling, FSRS, rendering, the MasteryForDeck query)
// lives in rslib and is reused verbatim; Swift only owns the UI.

import SwiftUI
import Foundation

// MARK: - Shared-engine wrapper over the C ABI

let DECK_NAME = "MCAT::Speedrun Starter"

final class AnkiEngine: ObservableObject {
    private var col: OpaquePointer?
    private var deckId: Int64 = -1

    // Deck / Memory summary (lifetime, from the shared engine).
    @Published var cardsTotal = 0
    @Published var cardsTracked = 0          // cards with an FSRS memory state
    @Published var sufficient = false
    @Published var memoryPct = 0.0
    @Published var lowerPct = 0.0
    @Published var upperPct = 0.0

    // Current study session.
    @Published var cardID: Int64 = 0
    @Published var question = ""
    @Published var answer = ""
    @Published var showingAnswer = false
    @Published var sessionReviewed = 0       // this session only
    @Published var noneDue = false

    init() {
        openBundledCollection()
        if let col {
            // Resolve the deck id by name from whatever collection is loaded —
            // robust to deck ids differing between builds / persisted data.
            deckId = DECK_NAME.withCString { speedrun_deck_id(col, $0) }
        }
        refreshSummary()
    }
    deinit { if let col { speedrun_close(col) } }

    private func openBundledCollection() {
        guard let src = Bundle.main.url(forResource: "collection", withExtension: "anki2") else { return }
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dst = docs.appendingPathComponent("collection.anki2")
        if !FileManager.default.fileExists(atPath: dst.path) {
            try? FileManager.default.copyItem(at: src, to: dst)
        }
        col = dst.path.withCString { speedrun_open($0) }
    }

    private func takeString(_ ptr: UnsafeMutablePointer<CChar>?) -> String {
        guard let ptr else { return "" }
        defer { speedrun_free_string(ptr) }
        return String(cString: ptr)
    }

    /// Refresh the deck/Memory summary from the shared engine.
    func refreshSummary() {
        guard let col else { return }
        let json = takeString(speedrun_mastery(col, deckId))
        guard let data = json.data(using: .utf8),
              let m = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return }
        cardsTotal = (m["cards_total"] as? Int) ?? 0
        cardsTracked = (m["cards_counted"] as? Int) ?? 0
        sufficient = (m["sufficient_data"] as? Bool) ?? false
        memoryPct = ((m["mean_retrievability"] as? Double) ?? 0) * 100
        lowerPct = ((m["lower"] as? Double) ?? 0) * 100
        upperPct = ((m["upper"] as? Double) ?? 0) * 100
    }

    func startSession() {
        sessionReviewed = 0
        noneDue = false
        loadNext()
    }

    func loadNext() {
        showingAnswer = false
        guard let col else { noneDue = true; return }
        let json = takeString(speedrun_next_card(col))
        if let data = json.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let cid = (obj["card_id"] as? Int).map(Int64.init) {
            cardID = cid
            question = (obj["question"] as? String) ?? ""
            answer = (obj["answer"] as? String) ?? ""
            noneDue = false
        } else {
            noneDue = true
        }
    }

    func answer(_ rating: UInt32) {
        guard let col else { return }
        if speedrun_answer(col, cardID, rating) == 0 { sessionReviewed += 1 }
        refreshSummary()
        loadNext()
    }
}

// MARK: - Helpers

private func stripHTML(_ s: String) -> String {
    s.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        .replacingOccurrences(of: "&nbsp;", with: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

// MARK: - Home

struct HomeView: View {
    @EnvironmentObject var engine: AnkiEngine

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                // Memory score card — clearly labelled so it isn't confused
                // with "reviewed this session".
                VStack(spacing: 6) {
                    Text("MEMORY").font(.caption2).tracking(1).foregroundStyle(.secondary)
                    if engine.sufficient {
                        Text("\(Int(engine.memoryPct.rounded()))%")
                            .font(.system(size: 46, weight: .bold, design: .rounded))
                        Text("95% range \(Int(engine.lowerPct.rounded()))–\(Int(engine.upperPct.rounded()))%")
                            .font(.subheadline)
                        Text("across \(engine.cardsTracked) of \(engine.cardsTotal) cards with review history")
                            .font(.caption2).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    } else {
                        Text("Not enough data yet").font(.title3.weight(.semibold))
                        Text("\(engine.cardsTracked) of \(engine.cardsTotal) cards have review history — study more, then check back")
                            .font(.caption).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(20).frame(maxWidth: .infinity)
                .background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 16))

                // Deck row — tappable, opens the study session (like Anki's deck list)
                NavigationLink { StudyView() } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("MCAT · Speedrun Starter").font(.body.weight(.semibold))
                            Text("\(engine.cardsTotal) cards · shared Rust engine")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                    }
                    .padding(16)
                    .background(Color(.secondarySystemBackground)).clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)

                NavigationLink { StudyView() } label: {
                    Text("Study").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)

                Spacer()
            }
            .padding()
            .navigationTitle("Speedrun · MCAT")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { engine.refreshSummary() }
        }
    }
}

// MARK: - Study

struct StudyView: View {
    @EnvironmentObject var engine: AnkiEngine
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 20) {
            if engine.noneDue {
                Spacer()
                Text("Nothing due right now 🎉").font(.title2)
                if engine.sessionReviewed > 0 {
                    Text("Reviewed \(engine.sessionReviewed) card\(engine.sessionReviewed == 1 ? "" : "s") this session on the shared Rust engine.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                } else {
                    Text("You've reviewed all due cards. Come back when more are due.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                Button("Back to deck") { dismiss() }
                    .buttonStyle(.bordered).controlSize(.large)
                Spacer()
            } else {
                if engine.sessionReviewed > 0 {
                    Text("Reviewed \(engine.sessionReviewed) this session")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                ScrollView {
                    Text(stripHTML(engine.question)).font(.title3).multilineTextAlignment(.center)
                    if engine.showingAnswer {
                        Divider().padding(.vertical, 8)
                        Text(stripHTML(engine.answer)).font(.title3).bold().multilineTextAlignment(.center)
                    }
                }.frame(maxWidth: .infinity)
                Spacer()
                if engine.showingAnswer {
                    HStack(spacing: 10) {
                        grade("Again", 1, .red); grade("Hard", 2, .orange)
                        grade("Good", 3, .green); grade("Easy", 4, .blue)
                    }
                } else {
                    Button { engine.showingAnswer = true } label: {
                        Text("Show Answer").frame(maxWidth: .infinity)
                    }.buttonStyle(.borderedProminent).controlSize(.large)
                }
            }
        }
        .padding()
        .navigationTitle("Study")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { engine.startSession() }
    }

    private func grade(_ label: String, _ rating: UInt32, _ color: Color) -> some View {
        Button { engine.answer(rating) } label: {
            Text(label).frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered).tint(color).controlSize(.large)
    }
}

@main
struct SpeedrunMCATApp: App {
    @StateObject private var engine = AnkiEngine()
    var body: some Scene {
        WindowGroup { HomeView().environmentObject(engine) }
    }
}
