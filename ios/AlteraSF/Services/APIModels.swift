import Foundation

// Decodable DTOs that map 1:1 to the JSON the Flask API returns.
// ViewModels convert these into the app's domain models.

struct APIUser: Decodable {
    let username: String
    let initials: String
    let isSuper: Bool
    let tenantSlug: String?
    let tenantDisplayName: String?
    enum CodingKeys: String, CodingKey {
        case username, initials
        case isSuper = "is_super"
        case tenantSlug = "tenant_slug"
        case tenantDisplayName = "tenant_display_name"
    }
}

struct APILoginResponse: Decodable {
    let ok: Bool
    let user: APIUser
}

struct APIJob: Decodable {
    let id: Int
    let code: String
    let title: String
    let department: String
    let location: String
    let employmentType: String
    let workArrangement: String
    let salaryRange: String
    let status: String
    let questionCount: Int
    let startDate: String?
    let endDate: String?
    let postedDate: String?
    let applicantCount: Int
    let diamondCount: Int
    let description: String

    enum CodingKeys: String, CodingKey {
        case id, code, title, department, location, description, status
        case employmentType = "employment_type"
        case workArrangement = "work_arrangement"
        case salaryRange = "salary_range"
        case questionCount = "question_count"
        case startDate = "start_date"
        case endDate = "end_date"
        case postedDate = "posted_date"
        case applicantCount = "applicant_count"
        case diamondCount = "diamond_count"
    }

    var domainStatus: JobStatus {
        switch status.lowercased() {
        case "open": return .open
        case "closed": return .closed
        default: return .draft
        }
    }

    var domainEmploymentType: EmploymentType {
        switch employmentType.lowercased() {
        case "full time", "full-time", "fulltime": return .fullTime
        case "part time", "part-time", "parttime": return .partTime
        case "contract": return .contract
        case "internship": return .internship
        default: return .temporary
        }
    }

    var domainArrangement: WorkArrangement {
        switch workArrangement.lowercased() {
        case "remote": return .remote
        case "hybrid": return .hybrid
        default: return .onSite
        }
    }

    func toDomain() -> Job {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        func parse(_ s: String?) -> Date {
            guard let s else { return Date() }
            return formatter.date(from: s) ?? fallback.date(from: s) ?? Date()
        }
        return Job(
            id: String(id),
            title: title,
            jobId: code,
            department: department,
            location: location,
            employmentType: domainEmploymentType,
            workArrangement: domainArrangement,
            salaryMin: 0,
            salaryMax: 0,
            description: description,
            numberOfQuestions: questionCount,
            status: domainStatus,
            postedDate: parse(postedDate),
            applicantCount: applicantCount,
            diamondCount: diamondCount
        )
    }
}

struct APIDepartment: Decodable {
    let id: Int
    let name: String
    let teamLead: String
    let color: String
    enum CodingKeys: String, CodingKey {
        case id, name, color
        case teamLead = "team_lead"
    }
}

struct APICandidate: Decodable {
    let id: String
    let name: String
    let email: String
    let phone: String
    let jdCode: String
    let jobTitle: String
    let department: String
    let relevancyScore: Double
    let claimValidityScore: Double?
    let tabSwitches: Int
    let isDiamond: Bool
    let isFlagged: Bool
    let status: String
    let appliedDate: String?

    // Detail-only fields (nil on list responses)
    let resumeUrl: String?
    let education: String?
    let experience: String?
    let skills: [String]?
    let qaResponses: [APIQAResponse]?

    enum CodingKeys: String, CodingKey {
        case id, name, email, phone, department, status, education, experience, skills
        case jdCode = "jd_code"
        case jobTitle = "job_title"
        case relevancyScore = "relevancy_score"
        case claimValidityScore = "claim_validity_score"
        case tabSwitches = "tab_switches"
        case isDiamond = "is_diamond"
        case isFlagged = "is_flagged"
        case appliedDate = "applied_date"
        case resumeUrl = "resume_url"
        case qaResponses = "qa_responses"
    }

    func toDomain() -> Candidate {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        func parse(_ s: String?) -> Date {
            guard let s else { return Date() }
            return formatter.date(from: s) ?? fallback.date(from: s) ?? Date()
        }
        let parts = name.split(separator: " ", maxSplits: 1)
        let first = parts.first.map(String.init) ?? name
        let last = parts.count > 1 ? String(parts[1]) : ""
        return Candidate(
            id: id,
            firstName: first,
            lastName: last,
            email: email,
            phone: phone,
            location: "",
            jobId: jdCode,
            jobTitle: jobTitle,
            relevancyScore: relevancyScore,
            claimValidityScore: claimValidityScore ?? 0.0,
            tabSwitches: tabSwitches,
            isDiamond: isDiamond,
            isFlagged: isFlagged,
            appliedDate: parse(appliedDate),
            status: CandidateStatus(rawValue: status) ?? .active,
            resumeText: "",
            education: education ?? "",
            experience: experience ?? "",
            skills: skills ?? [],
            qaResponses: (qaResponses ?? []).map { $0.toDomain() }
        )
    }
}

struct APIQAResponse: Decodable {
    let question: String
    let answer: String
    let score: Double?
    let hasPastedContent: Bool
    let durationSeconds: Int
    enum CodingKeys: String, CodingKey {
        case question, answer, score
        case hasPastedContent = "has_pasted_content"
        case durationSeconds = "duration_seconds"
    }
    func toDomain() -> QAResponse {
        QAResponse(question: question, answer: answer,
                   score: score ?? 0.0,
                   durationSeconds: durationSeconds,
                   hasPastedContent: hasPastedContent)
    }
}

struct APICandidateListResponse: Decodable {
    let total: Int
    let page: Int
    let perPage: Int
    let pages: Int
    let candidates: [APICandidate]
    enum CodingKeys: String, CodingKey {
        case total, page, pages, candidates
        case perPage = "per_page"
    }
}

struct APIAnalyticsOverview: Decodable {
    let totalApplicants: Int
    let totalDiamonds: Int
    let jobPostings: [APIJobAnalyticsSummary]
    enum CodingKeys: String, CodingKey {
        case totalApplicants = "total_applicants"
        case totalDiamonds = "total_diamonds"
        case jobPostings = "job_postings"
    }
}

struct APIJobAnalyticsSummary: Decodable {
    let jobId: Int
    let jobCode: String
    let jobTitle: String
    let department: String
    let status: String
    let totalApplicants: Int
    let diamondsFound: Int
    let completionRate: Double
    let timeSavedHours: Double
    enum CodingKeys: String, CodingKey {
        case department, status
        case jobId = "job_id"
        case jobCode = "job_code"
        case jobTitle = "job_title"
        case totalApplicants = "total_applicants"
        case diamondsFound = "diamonds_found"
        case completionRate = "completion_rate"
        case timeSavedHours = "time_saved_hours"
    }
}

struct APIJobAnalyticsDetail: Decodable {
    let jobId: Int
    let jobCode: String
    let jobTitle: String
    let department: String
    let status: String
    let totalApplicants: Int
    let diamondsFound: Int
    let completionRate: Double
    let timeSavedHours: Double
    let screenSpeed: Double
    let reviewLoadReduction: Double
    let funnel: APIFunnel
    let claimScoreDistribution: [APIScoreBucket]
    let fitScoreDistribution: [APIScoreBucket]
    let diamonds: [APICandidate]
    enum CodingKeys: String, CodingKey {
        case department, status, funnel, diamonds
        case jobId = "job_id"
        case jobCode = "job_code"
        case jobTitle = "job_title"
        case totalApplicants = "total_applicants"
        case diamondsFound = "diamonds_found"
        case completionRate = "completion_rate"
        case timeSavedHours = "time_saved_hours"
        case screenSpeed = "screen_speed"
        case reviewLoadReduction = "review_load_reduction"
        case claimScoreDistribution = "claim_score_distribution"
        case fitScoreDistribution = "fit_score_distribution"
    }

    func toAnalytics() -> JobAnalytics {
        JobAnalytics(
            id: jobCode,
            jobId: jobCode,
            jobTitle: jobTitle,
            department: department,
            status: status.lowercased() == "open" ? .open : (status.lowercased() == "closed" ? .closed : .draft),
            totalApplicants: totalApplicants,
            diamondsFound: diamondsFound,
            completionRate: completionRate,
            timeSavedHours: timeSavedHours,
            screenSpeed: screenSpeed,
            reviewLoad: reviewLoadReduction,
            funnelData: FunnelData(
                applied: funnel.applied, started: funnel.started,
                completed: funnel.completed, verified: funnel.verified, passed: funnel.passed
            ),
            claimScoreDistribution: claimScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) },
            fitScoreDistribution: fitScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) }
        )
    }
}

struct APIFunnel: Decodable {
    let applied, started, completed, verified, passed: Int
}

struct APIScoreBucket: Decodable {
    let label: String
    let count: Int
    let score: Double
}

struct APIErrorResponse: Decodable {
    let description: String?
    let message: String?
    var text: String { description ?? message ?? "Unknown error" }
}
