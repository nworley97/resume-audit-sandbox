import SwiftUI

final class AnalyticsViewModel: ObservableObject {
    @Published var overview: APIAnalyticsOverview? = nil
    @Published var isLoading = false
    @Published var error: String? = nil
    @Published var sortNewest = true

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

    var sortedPostings: [APIJobAnalyticsSummary] {
        guard let postings = overview?.jobPostings else { return [] }
        return sortNewest ? postings : postings.sorted { $0.totalApplicants > $1.totalApplicants }
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
}
