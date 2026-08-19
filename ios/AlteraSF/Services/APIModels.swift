import Foundation

// Decodable DTOs that map 1:1 to the JSON the Flask API returns.
// ViewModels convert these into the app's domain models.

struct APIUser: Decodable {
    let username: String
    let fullName: String?
    let company: String?
    let initials: String
    let isSuper: Bool
    let tenantSlug: String?
    let tenantDisplayName: String?
    enum CodingKeys: String, CodingKey {
        case username, initials
        case fullName = "full_name"
        case company
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
    let idSurveysEnabled: Bool

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
        case idSurveysEnabled = "id_surveys_enabled"
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
            diamondCount: diamondCount,
            idSurveysEnabled: idSurveysEnabled
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
            resumeUrl: resumeUrl ?? "",
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
    let postedDate: String?
    let totalApplicants: Int
    let diamondsFound: Int
    let completionRate: Double
    let timeSavedHours: Double
    enum CodingKeys: String, CodingKey {
        case department, status
        case jobId = "job_id"
        case jobCode = "job_code"
        case jobTitle = "job_title"
        case postedDate = "posted_date"
        case totalApplicants = "total_applicants"
        case diamondsFound = "diamonds_found"
        case completionRate = "completion_rate"
        case timeSavedHours = "time_saved_hours"
    }

    var postedDateFormatted: String? {
        guard let postedDate else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        guard let date = formatter.date(from: postedDate) ?? fallback.date(from: postedDate) else { return nil }
        return date.formatted(.dateTime.month(.abbreviated).day().year())
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
    let finalists: [APIFinalist]
    let heatmap: APIAnalyticsHeatmap
    enum CodingKeys: String, CodingKey {
        case department, status, funnel, diamonds, finalists, heatmap
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

struct APIFinalist: Decodable, Identifiable {
    let id: String
    let name: String
    let initials: String
    let claimValidityScore: Double
    let relevancyScore: Double
    let flaggedAnswers: Int
    let totalAnswers: Int
    let tabSwitches: Int
    let flagged: Bool
    let flagReason: String?
    let overallScore: Double
    var note: String
    enum CodingKeys: String, CodingKey {
        case id, name, initials, flagged, note
        case claimValidityScore = "claim_validity_score"
        case relevancyScore = "relevancy_score"
        case flaggedAnswers = "flagged_answers"
        case totalAnswers = "total_answers"
        case tabSwitches = "tab_switches"
        case flagReason = "flag_reason"
        case overallScore = "overall_score"
    }
}

struct APIFinalistCandidateOption: Decodable, Identifiable {
    let id: String
    let name: String
    let initials: String
    let claimValidityScore: Double
    let relevancyScore: Double
    enum CodingKeys: String, CodingKey {
        case id, name, initials
        case claimValidityScore = "claim_validity_score"
        case relevancyScore = "relevancy_score"
    }
}

struct APIScoreBucket: Decodable {
    let label: String
    let count: Int
    let score: Double
}

struct APIAnalyticsHeatmap: Decodable {
    let matrix: [[Int]]
    let axes: APIHeatmapAxes
    let cells: [APIHeatmapCell]
}

struct APIHeatmapAxes: Decodable {
    let relevancy: [APIHeatmapRelevancyAxisEntry]
    let claimValidity: [APIHeatmapClaimAxisEntry]
    enum CodingKeys: String, CodingKey {
        case relevancy
        case claimValidity = "claim_validity"
    }
}

struct APIHeatmapRelevancyAxisEntry: Decodable {
    let index: Int
    let label: String
    let value: Int?
    let isNoScore: Bool
    enum CodingKeys: String, CodingKey {
        case index, label, value
        case isNoScore = "is_no_score"
    }
}

struct APIHeatmapClaimAxisEntry: Decodable {
    let index: Int
    let label: String
    let bucket: Int
    let isNoScore: Bool
    enum CodingKeys: String, CodingKey {
        case index, label, bucket
        case isNoScore = "is_no_score"
    }
}

struct APIHeatmapCell: Decodable, Identifiable {
    let relevancy: Int
    let claim: Int
    let candidates: [APIHeatmapCandidate]
    var id: Int { relevancy * 100 + claim }
}

struct APIHeatmapCandidate: Decodable {
    let id: String
    let name: String
    let initials: String
    let relevancyScore: Double
    let claimValidityScore: Double?
    enum CodingKeys: String, CodingKey {
        case id, name, initials
        case relevancyScore = "relevancy_score"
        case claimValidityScore = "claim_validity_score"
    }
}

struct APIErrorResponse: Decodable {
    let description: String?
    let message: String?
    var text: String { description ?? message ?? "Unknown error" }
}

// MARK: – Profile

struct APIProfile: Decodable {
    let username: String
    let fullName: String
    let company: String
    let initials: String
    enum CodingKeys: String, CodingKey {
        case username, initials
        case fullName = "full_name"
        case company
    }
}

// MARK: – Team

struct APITeamMember: Decodable, Identifiable {
    let id: Int
    let name: String
    let email: String
    let role: String
    let initials: String
    let tempPassword: String?
    enum CodingKeys: String, CodingKey {
        case id, name, email, role, initials
        case tempPassword = "temp_password"
    }
}

// MARK: – Notifications

struct APINotification: Decodable, Identifiable {
    let id: String
    let type: String
    let title: String
    let subtitle: String
    let createdAt: String
    let isRead: Bool
    enum CodingKeys: String, CodingKey {
        case id, type, title, subtitle
        case createdAt = "created_at"
        case isRead = "is_read"
    }

    var domainType: NotificationType {
        switch type {
        case "new_application": return .newApplication
        case "assessment_completed": return .assessmentCompleted
        case "diamond_found": return .diamondFound
        case "draft_saved": return .draftSaved
        default: return .jobBoardViews
        }
    }

    func toDomain() -> AppNotification {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        let timestamp = formatter.date(from: createdAt) ?? fallback.date(from: createdAt) ?? Date()
        return AppNotification(id: id, type: domainType, title: title, subtitle: subtitle, timestamp: timestamp, isRead: isRead)
    }
}

// MARK: – Billing

struct APIBillingSummary: Decodable {
    let planTier: String
    let planDisplay: String
    let billingCycle: String
    let status: String
    let isGrandfathered: Bool
    let jobsLimit: Int
    let resumesLimit: Int
    let seatsLimit: Int
    let jobsUsed: Int
    let resumesUsed: Int
    let seatsUsed: Int
    let hasClaimValidity: Bool
    let hasRedFlag: Bool
    let hasAnalytics: Bool
    let periodEnd: String?
    let extraSeats: Int
    enum CodingKeys: String, CodingKey {
        case status
        case planTier = "plan_tier"
        case planDisplay = "plan_display"
        case billingCycle = "billing_cycle"
        case isGrandfathered = "is_grandfathered"
        case jobsLimit = "jobs_limit"
        case resumesLimit = "resumes_limit"
        case seatsLimit = "seats_limit"
        case jobsUsed = "jobs_used"
        case resumesUsed = "resumes_used"
        case seatsUsed = "seats_used"
        case hasClaimValidity = "has_claim_validity"
        case hasRedFlag = "has_red_flag"
        case hasAnalytics = "has_analytics"
        case periodEnd = "period_end"
        case extraSeats = "extra_seats"
    }
}

struct APIPaymentMethod: Decodable {
    let brand: String?
    let last4: String?
    let expMonth: Int?
    let expYear: Int?
    enum CodingKeys: String, CodingKey {
        case brand, last4
        case expMonth = "exp_month"
        case expYear = "exp_year"
    }
}

struct APIInvoice: Decodable, Identifiable {
    let id: Int
    let description: String
    let amount: Double
    let status: String
    let createdAt: String?
    enum CodingKeys: String, CodingKey {
        case id, description, amount, status
        case createdAt = "created_at"
    }
}

struct APIPlanLimits: Decodable {
    let activeJobs: Int
    let monthlyResumes: Int
    let seatsIncluded: Int
    enum CodingKeys: String, CodingKey {
        case activeJobs = "active_jobs"
        case monthlyResumes = "monthly_resumes"
        case seatsIncluded = "seats_included"
    }
}

struct APIPlanFeature: Decodable, Identifiable {
    let key: String
    let name: String
    var id: String { key }
}

struct APIPlan: Decodable, Identifiable {
    let tier: String
    let displayName: String
    let tagline: String
    let monthlyPrice: Double
    let yearlyPrice: Double
    let limits: APIPlanLimits
    let features: [APIPlanFeature]
    var id: String { tier }
    enum CodingKeys: String, CodingKey {
        case tier, tagline, limits, features
        case displayName = "display_name"
        case monthlyPrice = "monthly_price"
        case yearlyPrice = "yearly_price"
    }
}

struct APIBillingResponse: Decodable {
    let summary: APIBillingSummary
    let paymentMethod: APIPaymentMethod
    let hasStripeCustomer: Bool
    let invoices: [APIInvoice]
    let plans: [APIPlan]
    enum CodingKeys: String, CodingKey {
        case summary, invoices, plans
        case paymentMethod = "payment_method"
        case hasStripeCustomer = "has_stripe_customer"
    }
}

struct APIPortalResponse: Decodable {
    let url: String
}
