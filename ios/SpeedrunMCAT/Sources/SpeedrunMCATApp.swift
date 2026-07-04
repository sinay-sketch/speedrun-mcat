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
    private var colPath = ""                  // on-disk path (needed to sync)

    // Deck / Memory summary (lifetime, from the shared engine).
    @Published var cardsTotal = 0
    @Published var cardsTracked = 0          // cards with an FSRS memory state
    @Published var sufficient = false
    @Published var memoryPct = 0.0
    @Published var lowerPct = 0.0
    @Published var upperPct = 0.0

    // Performance score (online Elo over review history, from the shared engine).
    @Published var perfSufficient = false
    @Published var perfPct = 0.0
    @Published var perfLower = 0.0
    @Published var perfUpper = 0.0
    @Published var perfReviews = 0

    // Readiness score (provisional MCAT 472–528, transparent link + band).
    @Published var readySufficient = false
    @Published var readyScore = 0
    @Published var readyLower = 0
    @Published var readyUpper = 0

    // Study-queue counts — SAME engine call the desktop deck list uses, so these
    // match the desktop's New / Learn / Due exactly (learn/due are time-sensitive).
    @Published var newCount = 0
    @Published var learnCount = 0
    @Published var dueCount = 0

    // Current study session.
    @Published var cardID: Int64 = 0
    @Published var question = ""
    @Published var answer = ""
    @Published var showingAnswer = false
    @Published var sessionReviewed = 0       // this session only
    @Published var noneDue = false

    // Sync (self-hosted server; two-way, on the shared Rust engine).
    @Published var syncEndpoint = "http://127.0.0.1:8080/"
    @Published var syncUser = "test"
    @Published var syncPassword = "test"
    @Published var isSyncing = false
    @Published var syncStatus = ""

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
        colPath = dst.path
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
        refreshPerformance()
        refreshReadiness()
        refreshCounts()
    }

    /// Refresh the Performance score (online Elo) from the shared engine.
    func refreshPerformance() {
        guard let col else { return }
        let json = takeString(speedrun_performance(col, deckId))
        guard let data = json.data(using: .utf8),
              let p = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return }
        perfSufficient = (p["sufficient_data"] as? Bool) ?? false
        perfPct = ((p["mastery"] as? Double) ?? 0) * 100
        perfLower = ((p["lower"] as? Double) ?? 0) * 100
        perfUpper = ((p["upper"] as? Double) ?? 0) * 100
        perfReviews = (p["reviews"] as? Int) ?? 0
    }

    /// Refresh the Readiness score (provisional MCAT 472–528) from the shared engine.
    func refreshReadiness() {
        guard let col else { return }
        let json = takeString(speedrun_readiness(col, deckId))
        guard let data = json.data(using: .utf8),
              let r = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return }
        readySufficient = (r["sufficient_data"] as? Bool) ?? false
        readyScore = (r["scaled"] as? Int) ?? 0
        readyLower = (r["lower"] as? Int) ?? 0
        readyUpper = (r["upper"] as? Int) ?? 0
    }

    /// Refresh New / Learn / Due from the shared engine's deck tree (identical to
    /// the desktop deck list).
    func refreshCounts() {
        guard let col else { return }
        let json = takeString(speedrun_deck_counts(col, deckId))
        guard let data = json.data(using: .utf8),
              let c = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return }
        newCount = (c["new"] as? Int) ?? 0
        learnCount = (c["learn"] as? Int) ?? 0
        dueCount = (c["due"] as? Int) ?? 0
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

    /// Two-way sync with the self-hosted server on the SHARED Rust engine.
    /// speedrun_sync opens its own handle, so we close ours first, sync off the
    /// main thread, then reopen and refresh. This pushes offline reviews up and
    /// pulls the desktop's changes down (same code path the desktop app uses).
    func sync() {
        guard !isSyncing, !colPath.isEmpty else { return }
        isSyncing = true
        syncStatus = "Syncing…"
        // Close our handle so the sync has exclusive access to the collection.
        if let c = col { speedrun_close(c); col = nil }
        let path = colPath, endpoint = syncEndpoint, user = syncUser, pw = syncPassword
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let code = path.withCString { p in
                endpoint.withCString { e in
                    user.withCString { u in
                        pw.withCString { w in speedrun_sync(p, e, u, w) }
                    }
                }
            }
            DispatchQueue.main.async {
                guard let self else { return }
                // Reopen on the (possibly updated) collection and re-resolve the deck.
                self.col = path.withCString { speedrun_open($0) }
                if let c = self.col { self.deckId = DECK_NAME.withCString { speedrun_deck_id(c, $0) } }
                self.refreshSummary()
                switch code {
                case 0:  self.syncStatus = "In sync ✓"
                case 1:  self.syncStatus = "Uploaded to server ✓"
                case 2:  self.syncStatus = "Downloaded from server ✓"
                default: self.syncStatus = "Sync failed — check server/endpoint"
                }
                self.isSyncing = false
            }
        }
    }
}

// MARK: - Helpers

private func stripHTML(_ s: String) -> String {
    s.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        .replacingOccurrences(of: "&nbsp;", with: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

// MARK: - Home

/// One of the three dashboard scores: a value + 95% range, or a give-up state.
struct ScoreCard: View {
    let title: String
    let accent: Color
    let sufficient: Bool
    let value: String
    let range: String
    let note: String

    var body: some View {
        VStack(spacing: 4) {
            Text(title).font(.caption2).tracking(0.5).foregroundStyle(.secondary)
            if sufficient {
                Text(value).font(.system(size: 26, weight: .bold, design: .rounded)).foregroundStyle(accent)
                Text(range).font(.caption2).foregroundStyle(.secondary)
            } else {
                Text("—").font(.system(size: 26, weight: .bold, design: .rounded)).foregroundStyle(.tertiary)
                Text(note).font(.caption2).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center).lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity).padding(.vertical, 14)
        .background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

struct HomeView: View {
    @EnvironmentObject var engine: AnkiEngine

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                // Three honest, ranged scores (Memory / Performance / Readiness),
                // each with the give-up rule. All computed in the shared Rust engine.
                HStack(spacing: 10) {
                    ScoreCard(title: "MEMORY", accent: .blue, sufficient: engine.sufficient,
                              value: "\(Int(engine.memoryPct.rounded()))%",
                              range: "\(Int(engine.lowerPct.rounded()))–\(Int(engine.upperPct.rounded()))%",
                              note: "need ≥20 cards")
                    ScoreCard(title: "PERFORM", accent: .orange, sufficient: engine.perfSufficient,
                              value: "\(Int(engine.perfPct.rounded()))%",
                              range: "\(Int(engine.perfLower.rounded()))–\(Int(engine.perfUpper.rounded()))%",
                              note: "need ≥30 reviews")
                    ScoreCard(title: "READY", accent: .green, sufficient: engine.readySufficient,
                              value: "\(engine.readyScore)",
                              range: "\(engine.readyLower)–\(engine.readyUpper)",
                              note: "study more")
                }
                Text(engine.readySufficient
                     ? "Memory = predicted recall · Performance = Elo mastery · Readiness = provisional MCAT (472–528), a confident score needs full-length exams."
                     : "Three scores from the shared Rust engine, each with a 95% range and a give-up rule when data is thin.")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)

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

                // Study-queue counts — same New / Learn / Due the desktop shows
                // (read from the shared engine's deck tree, so they match).
                HStack(spacing: 0) {
                    stat("New", engine.newCount, .blue)
                    Divider().frame(height: 34)
                    stat("Learn", engine.learnCount, .red)
                    Divider().frame(height: 34)
                    stat("Due", engine.dueCount, .green)
                }
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity)
                .background(Color(.secondarySystemBackground)).clipShape(RoundedRectangle(cornerRadius: 12))

                NavigationLink { StudyView() } label: {
                    Text("Study").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)

                // Two-way sync with the desktop app via the self-hosted server.
                Button { engine.sync() } label: {
                    HStack {
                        if engine.isSyncing { ProgressView().controlSize(.small) }
                        Image(systemName: "arrow.triangle.2.circlepath")
                        Text(engine.isSyncing ? "Syncing…" : "Sync with desktop")
                    }.frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered).controlSize(.large)
                .disabled(engine.isSyncing)

                if !engine.syncStatus.isEmpty {
                    Text(engine.syncStatus).font(.caption).foregroundStyle(.secondary)
                }

                DisclosureGroup("Sync server") {
                    VStack(spacing: 8) {
                        TextField("Endpoint", text: $engine.syncEndpoint)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .keyboardType(.URL)
                        TextField("Username", text: $engine.syncUser)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                        SecureField("Password", text: $engine.syncPassword)
                    }
                    .textFieldStyle(.roundedBorder).font(.caption).padding(.top, 4)
                }
                .font(.caption).foregroundStyle(.secondary)

                Spacer()
            }
            .padding()
            .navigationTitle("Speedrun · MCAT")
            .navigationBarTitleDisplayMode(.inline)
            // Auto-sync whenever Home appears (app launch, and after a study
            // session when we pop back) so reviews propagate without tapping Sync.
            .onAppear { engine.sync() }
        }
    }

    private func stat(_ label: String, _ value: Int, _ color: Color) -> some View {
        VStack(spacing: 2) {
            Text("\(value)").font(.title2.weight(.bold)).foregroundStyle(color)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
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
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            HomeView()
                .environmentObject(engine)
                // Auto-sync when the app returns to the foreground.
                .onChange(of: scenePhase) { phase in
                    if phase == .active { engine.sync() }
                }
        }
    }
}
