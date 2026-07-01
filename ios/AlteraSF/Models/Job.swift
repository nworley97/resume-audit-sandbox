import Foundation

enum JobStatus: String, CaseIterable {
    case open = "Open"
    case draft = "Draft"
    case closed = "Closed"
}

enum EmploymentType: String, CaseIterable {
    case fullTime = "Full time"
    case partTime = "Part time"
    case contract = "Contract"
    case internship = "Internship"
    case temporary = "Temporary"
}

enum WorkArrangement: String, CaseIterable {
    case remote = "Remote"
    case hybrid = "Hybrid"
    case onSite = "On site"
}

struct Job: Identifiable, Hashable {
    let id: String
    var title: String
    var jobId: String
    var department: String
    var location: String
    var employmentType: EmploymentType
    var workArrangement: WorkArrangement
    var salaryMin: Int
    var salaryMax: Int
    var description: String
    var numberOfQuestions: Int
    var status: JobStatus
    var postedDate: Date
    var applicantCount: Int
    var diamondCount: Int
    var hiredCandidate: String?

    var avatarInitials: [String] {
        ["AB", "MK", "JS"]
    }
}

struct Department: Identifiable, Hashable {
    let id: String
    var name: String
    var jobs: [Job]

    var openCount: Int { jobs.filter { $0.status == .open }.count }
}
