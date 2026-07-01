// Speedrun (MCAT) iOS companion.
// License: GNU AGPL, version 3 or later.
//
// A minimal SwiftUI app that runs a real review session on the SAME Anki Rust
// engine as the desktop app, via the anki-ffi C ABI. It bundles a prebuilt
// MCAT collection, opens it through the shared engine, renders/answers cards,
// and shows the honest Memory score (MasteryForDeck) with its give-up rule.

import SwiftUI
import Foundation

// MARK: - Shared-engine wrapper over the C ABI

final class AnkiEngine: ObservableObject {
    private var col: OpaquePointer?
    private let deckId: Int64

    @Published var cardID: Int64 = 0
    @Published var question: String = ""
    @Published var answer: String = ""
    @Published var showingAnswer = false
    @Published var finished = false
    @Published var reviewed = 0
    @Published var memoryLine: String = "…"

    init() {
        self.deckId = AnkiEngine.bundledDeckID()
        openBundledCollection()
        loadNext()
        refreshMemory()
    }

    deinit { if let col { speedrun_close(col) } }

    private static func bundledDeckID() -> Int64 {
        if let url = Bundle.main.url(forResource: "deck_id", withExtension: "txt"),
           let s = try? String(contentsOf: url, encoding: .utf8),
           let id = Int64(s.trimmingCharacters(in: .whitespacesAndNewlines)) {
            return id
        }
        return 1
    }

    // The app bundle is read-only; copy the collection to Documents to open r/w.
    private func openBundledCollection() {
        guard let src = Bundle.main.url(forResource: "collection", withExtension: "anki2") else {
            memoryLine = "bundled collection missing"; return
        }
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

    func loadNext() {
        guard let col else { finished = true; return }
        let json = takeString(speedrun_next_card(col))
        showingAnswer = false
        guard
            let data = json.data(using: .utf8),
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let cid = obj["card_id"] as? Int64 ?? (obj["card_id"] as? Int).map(Int64.init)
        else {
            finished = true; question = ""; answer = ""; return
        }
        cardID = cid
        question = (obj["question"] as? String) ?? ""
        answer = (obj["answer"] as? String) ?? ""
    }

    func answer(_ rating: UInt32) {
        guard let col else { return }
        if speedrun_answer(col, cardID, rating) == 0 { reviewed += 1 }
        refreshMemory()
        loadNext()
    }

    func refreshMemory() {
        guard let col else { return }
        let json = takeString(speedrun_mastery(col, deckId))
        guard
            let data = json.data(using: .utf8),
            let m = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { memoryLine = "—"; return }
        let counted = (m["cards_counted"] as? Int) ?? 0
        let total = (m["cards_total"] as? Int) ?? 0
        let sufficient = (m["sufficient_data"] as? Bool) ?? false
        if sufficient {
            let mean = ((m["mean_retrievability"] as? Double) ?? 0) * 100
            let lo = ((m["lower"] as? Double) ?? 0) * 100
            let hi = ((m["upper"] as? Double) ?? 0) * 100
            memoryLine = String(format: "Memory: %.0f%% (95%% %.0f–%.0f%%) · %d/%d cards",
                                mean, lo, hi, counted, total)
        } else {
            memoryLine = "Memory: not enough data yet (\(counted)/\(total) cards) — study more"
        }
    }
}

// MARK: - UI

private func stripHTML(_ s: String) -> String {
    s.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
     .replacingOccurrences(of: "&nbsp;", with: " ")
     .trimmingCharacters(in: .whitespacesAndNewlines)
}

struct ContentView: View {
    @StateObject private var engine = AnkiEngine()

    var body: some View {
        VStack(spacing: 20) {
            Text("Speedrun · MCAT")
                .font(.headline).foregroundStyle(.secondary)
            Text(engine.memoryLine)
                .font(.footnote).multilineTextAlignment(.center)
                .padding(8).background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 8))

            Divider()

            if engine.finished {
                Spacer()
                Text("All caught up 🎉").font(.title2)
                Text("Reviewed \(engine.reviewed) cards this session on the shared Rust engine.")
                    .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                Spacer()
            } else {
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
                        gradeButton("Again", 1, .red)
                        gradeButton("Hard", 2, .orange)
                        gradeButton("Good", 3, .green)
                        gradeButton("Easy", 4, .blue)
                    }
                } else {
                    Button { engine.showingAnswer = true } label: {
                        Text("Show Answer").frame(maxWidth: .infinity)
                    }.buttonStyle(.borderedProminent).controlSize(.large)
                }
            }
        }
        .padding()
    }

    private func gradeButton(_ label: String, _ rating: UInt32, _ color: Color) -> some View {
        Button { engine.answer(rating) } label: {
            Text(label).frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered).tint(color).controlSize(.large)
    }
}

@main
struct SpeedrunMCATApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}
