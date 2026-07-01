import Foundation

struct JobAnalytics: Identifiable {
    let id: String
    var jobId: String
    var jobTitle: String
    var department: String
    var status: JobStatus
    var totalApplicants: Int
    var diamondsFound: Int
    var completionRate: Double
    var timeSavedHours: Double
    var screenSpeed: Double
    var reviewLoad: Double
    var funnelData: FunnelData
    var claimScoreDistribution: [ScoreBucket]
    var fitScoreDistribution: [ScoreBucket]
}

struct FunnelData {
    var applied: Int
    var started: Int
    var completed: Int
    var verified: Int
    var passed: Int
}

struct ScoreBucket: Identifiable {
    let id = UUID()
    var label: String
    var count: Int
    var score: Double
}

struct OverallAnalytics {
    var totalApplicants: Int
    var totalDiamonds: Int
    var jobPostings: [JobAnalytics]
}
