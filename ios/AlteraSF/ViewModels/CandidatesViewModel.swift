import SwiftUI

final class CandidatesViewModel: ObservableObject {
    @Published var candidates: [Candidate] = []
    @Published var totalCount = 0
    @Published var isLoading = false
    @Published var error: String? = nil
    @Published var pageError: String?
    @Published var isLoadingMore = false
    @Published var hasMore = false
    @Published var jobCounts: [String: Int] = [:]
    private var page = 0
    private var requestID = UUID()
    private var loadedSearch: String?
    private var loadedDepartment: String?
    private var loadedSort = "score"
    private var loadedJobCode: String?

    @Published var selectedTab: CandidateTab = .all
    @Published var searchText = ""
    @Published var selectedDepartment: String? = nil
    @Published var sortOption: SortOption = .fitDesc
    @Published var showFilterSheet = false
    @Published var showSortSheet = false

    enum CandidateTab: String, CaseIterable {
        case all = "Candidates"
        case diamonds = "Diamonds"
        case flagged = "Flagged"
    }

    enum SortOption: String, CaseIterable {
        case fitDesc = "Fit: High to low"
        case fitAsc = "Fit: Low to high"
        case claimDesc = "Claim validity: High to low"
        case claimAsc = "Claim validity: Low to high"
        case combinedDesc = "Combined score: High to low"
        case combinedAsc = "Combined score: Low to high"
        case newest = "Newest"
        case flaggedFirst = "Flagged first"

        var apiValue: String {
            switch self {
            case .fitDesc: return "score"
            case .fitAsc: return "fit_asc"
            case .claimDesc: return "claim_desc"
            case .claimAsc: return "claim_asc"
            case .combinedDesc: return "combined_desc"
            case .combinedAsc: return "combined_asc"
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
        let id = UUID()
        requestID = id
        isLoading = true
        isLoadingMore = false
        error = nil
        pageError = nil
        hasMore = false
        let search = searchText.isEmpty ? nil : searchText
        let department = selectedDepartment
        let sort = sortOption.apiValue
        let code = jobCode ?? filterJobId
        do {
            let response = try await api.fetchCandidates(
                jobCode: code, search: search, sort: sort, department: department
            )
            guard requestID == id else { return }
            loadedSearch = search
            loadedDepartment = department
            loadedSort = sort
            loadedJobCode = code
            candidates = response.candidates.map { $0.toDomain() }
            totalCount = response.total
            jobCounts = response.jobCounts ?? [:]
            page = response.page
            hasMore = page < response.pages
        } catch {
            guard requestID == id else { return }
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    @MainActor
    func loadMore(jobCode: String? = nil) async {
        guard hasMore, !isLoading, !isLoadingMore else { return }
        let id = requestID
        isLoadingMore = true
        pageError = nil
        do {
            let response = try await api.fetchCandidates(
                jobCode: loadedJobCode, search: loadedSearch,
                sort: loadedSort, page: page + 1, department: loadedDepartment)
            guard requestID == id else { return }
            let existing = Set(candidates.map(\.id))
            candidates.append(contentsOf: response.candidates.map { $0.toDomain() }.filter { !existing.contains($0.id) })
            totalCount = response.total
            jobCounts = response.jobCounts ?? jobCounts
            page = response.page
            hasMore = page < response.pages
        } catch {
            guard requestID == id else { return }
            pageError = error.localizedDescription
        }
        isLoadingMore = false
    }

    func triggerSearch(jobCode: String? = nil) {
        searchTask?.cancel()
        searchTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 350_000_000)
            guard !Task.isCancelled else { return }
            await load(jobCode: jobCode)
        }
    }

    var displayedCandidates: [Candidate] {
        switch selectedTab {
        case .all: return candidates
        case .diamonds: return candidates.filter(\.isDiamond)
        case .flagged: return candidates.filter(\.isFlagged)
        }
    }

    // For the all-candidates view grouped by job
    func grouped(allJobs: [Job]) -> [(job: Job, candidates: [Candidate], total: Int)] {
        let visible = displayedCandidates
        let jobs = selectedDepartment == nil ? allJobs : allJobs.filter { $0.department == selectedDepartment }
        return jobs.compactMap { job in
            let c = visible.filter { $0.jobId == job.jobId }
            let total = jobCounts[job.jobId] ?? c.count
            return total == 0 ? nil : (job: job, candidates: c, total: total)
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
