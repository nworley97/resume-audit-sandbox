import SwiftUI

final class CandidatesViewModel: ObservableObject {
    @Published var candidates: [Candidate] = []
    @Published var totalCount = 0
    @Published var isLoading = false
    @Published var error: String? = nil

    @Published var selectedTab: CandidateTab = .all
    @Published var searchText = ""
    @Published var selectedDepartment: String? = nil
    @Published var sortOption: SortOption = .topScore
    @Published var showFilterSheet = false
    @Published var showSortSheet = false

    enum CandidateTab: String, CaseIterable {
        case all = "Candidates"
        case diamonds = "Diamonds"
        case flagged = "Flagged"
    }

    enum SortOption: String, CaseIterable {
        case topScore = "Top score"
        case newest = "Newest"
        case flaggedFirst = "Flagged first"

        var apiValue: String {
            switch self {
            case .topScore: return "score"
            case .newest: return "newest"
            case .flaggedFirst: return "flagged"
            }
        }
    }

    private let api: APIService
    private var filterJobId: String?
    private var searchTask: Task<Void, Never>?

    init(api: APIService = .shared, filterJobId: String? = nil) {
        self.api = api
        self.filterJobId = filterJobId
    }

    @MainActor
    func load(jobCode: String? = nil) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        do {
            let response = try await api.fetchCandidates(
                jobCode: jobCode ?? filterJobId,
                search: searchText.isEmpty ? nil : searchText,
                sort: sortOption.apiValue
            )
            candidates = response.candidates.map { $0.toDomain() }
            totalCount = response.total
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    func triggerSearch(jobCode: String? = nil) {
        searchTask?.cancel()
        searchTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 350_000_000)
            guard !Task.isCancelled else { return }
            await load(jobCode: jobCode)
        }
    }

    var diamondCount: Int { candidates.filter(\.isDiamond).count }
    var flaggedCount: Int { candidates.filter(\.isFlagged).count }

    var displayedCandidates: [Candidate] {
        switch selectedTab {
        case .all: return candidates
        case .diamonds: return candidates.filter(\.isDiamond)
        case .flagged: return candidates.filter(\.isFlagged)
        }
    }

    // For the all-candidates view grouped by job
    func grouped(allJobs: [Job]) -> [(job: Job, candidates: [Candidate])] {
        let visible = displayedCandidates
        return allJobs.compactMap { job in
            let c = visible.filter { $0.jobId == job.jobId }
            return c.isEmpty ? nil : (job: job, candidates: c)
        }
    }

    func setCandidateStatus(id: String, status: String) {
        Task { @MainActor in
            try? await api.setCandidateStatus(id: id, status: status)
            // Update locally
            if let idx = candidates.firstIndex(where: { $0.id == id }) {
                candidates[idx].status = CandidateStatus(rawValue: status) ?? .active
            }
        }
    }
}
