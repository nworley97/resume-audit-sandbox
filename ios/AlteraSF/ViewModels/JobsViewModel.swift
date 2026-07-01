import SwiftUI

final class JobsViewModel: ObservableObject {
    @Published var selectedTab: JobTab = .open
    @Published var departments: [Department] = []
    @Published var isLoading = false
    @Published var error: String? = nil
    @Published var toast: String? = nil

    // Sheet triggers
    @Published var showCloseRole: Job? = nil
    @Published var showEditJob: Job? = nil
    @Published var showAddDept = false

    enum JobTab: String, CaseIterable {
        case open = "Open"
        case drafts = "Drafts"
        case closed = "Closed"
    }

    private let api: APIService

    init(api: APIService = .shared) {
        self.api = api
    }

    var allJobs: [Job] { departments.flatMap(\.jobs) }
    var openCount: Int { allJobs.filter { $0.status == .open }.count }
    var draftCount: Int { allJobs.filter { $0.status == .draft }.count }
    var closedCount: Int { allJobs.filter { $0.status == .closed }.count }
    var applicantCount: Int { allJobs.reduce(0) { $0 + $1.applicantCount } }

    // MARK: – Load

    @MainActor
    func load() async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        do {
            let apiJobs = try await api.fetchJobs()
            let jobs = apiJobs.map { $0.toDomain() }
            rebuildDepartments(from: jobs)
        } catch APIError.notAuthenticated {
            error = "Session expired. Please sign in again."
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func rebuildDepartments(from jobs: [Job]) {
        var deptMap: [String: [Job]] = [:]
        for job in jobs {
            let key = job.department.isEmpty ? "Other" : job.department
            deptMap[key, default: []].append(job)
        }
        departments = deptMap.map { name, jobs in
            Department(id: name, name: name, jobs: jobs)
        }.sorted { $0.name < $1.name }
    }

    // MARK: – Filtered views

    func openDepartments() -> [Department] {
        departments.compactMap { dept in
            let open = dept.jobs.filter { $0.status == .open }
            return open.isEmpty ? nil : Department(id: dept.id, name: dept.name, jobs: open)
        }
    }

    func draftJobs() -> [Job] { allJobs.filter { $0.status == .draft } }
    func closedJobs() -> [Job] { allJobs.filter { $0.status == .closed } }

    // MARK: – Mutating actions

    func closeRole(_ job: Job, hiredCandidate: String?) {
        Task { @MainActor in
            do {
                try await api.closeJob(code: job.jobId)
                await load()
                showToast("Role has been closed")
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    func reopenRole(_ job: Job) {
        Task { @MainActor in
            do {
                try await api.reopenJob(code: job.jobId)
                await load()
                showToast("Role reopened — moved to Open")
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    func deleteRole(_ job: Job) {
        Task { @MainActor in
            do {
                try await api.deleteJob(code: job.jobId)
                await load()
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    func saveJob(_ job: Job?, title: String, code: String, department: String,
                 location: String, employmentType: String, workArrangement: String,
                 salaryRange: String, description: String, questionCount: Int, status: String) {
        let body: [String: Any] = [
            "title": title, "code": code, "department": department,
            "location": location, "employment_type": employmentType,
            "work_arrangement": workArrangement, "salary_range": salaryRange,
            "description": description, "question_count": questionCount, "status": status,
        ]
        Task { @MainActor in
            do {
                if let existing = job {
                    _ = try await api.updateJob(code: existing.jobId, body: body)
                } else {
                    _ = try await api.createJob(body)
                }
                await load()
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    private func showToast(_ msg: String) {
        toast = msg
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            toast = nil
        }
    }
}
