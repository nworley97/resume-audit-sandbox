import SwiftUI

final class AnalyticsViewModel: ObservableObject {
    @Published var overview: APIAnalyticsOverview? = nil
    @Published var isLoading = false
    @Published var error: String? = nil

    private let api: APIService

    init(api: APIService = .shared) {
        self.api = api
    }

    @MainActor
    func load() async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        do {
            overview = try await api.fetchAnalyticsOverview()
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    /// Open roles first, then drafts, then closed — newest posting first within each group.
    var sortedPostings: [APIJobAnalyticsSummary] {
        guard let postings = overview?.jobPostings else { return [] }
        func statusRank(_ status: String) -> Int {
            switch status.lowercased() {
            case "open": return 0
            case "closed": return 2
            default: return 1
            }
        }
        return postings.sorted { a, b in
            let rankA = statusRank(a.status), rankB = statusRank(b.status)
            if rankA != rankB { return rankA < rankB }
            return (a.postedDate ?? "") > (b.postedDate ?? "")
        }
    }
}

final class JobAnalyticsViewModel: ObservableObject {
    @Published var detail: APIJobAnalyticsDetail? = nil
    @Published var isLoading = false
    @Published var error: String? = nil

    private let api: APIService

    init(api: APIService = .shared) {
        self.api = api
    }

    @MainActor
    func load(code: String) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        do {
            detail = try await api.fetchJobAnalytics(code: code)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    @MainActor
    func addFinalist(candidateId: String, jobCode: String) async {
        do {
            try await api.setCandidateStatus(id: candidateId, status: "finalist")
            detail = try await api.fetchJobAnalytics(code: jobCode)
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func removeFinalist(candidateId: String, jobCode: String) async {
        do {
            try await api.setCandidateStatus(id: candidateId, status: "")
            detail = try await api.fetchJobAnalytics(code: jobCode)
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func updateNote(candidateId: String, note: String, jobCode: String) async {
        do {
            try await api.setCandidateNote(id: candidateId, note: note)
            detail = try await api.fetchJobAnalytics(code: jobCode)
        } catch {
            self.error = error.localizedDescription
        }
    }

    @MainActor
    func loadCandidateOptions(jobCode: String) async -> [APIFinalistCandidateOption] {
        (try? await api.fetchFinalistCandidateOptions(jobCode: jobCode)) ?? []
    }
}
