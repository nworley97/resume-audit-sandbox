import Foundation

enum CandidateStatus: String {
    case active = "Active"
    case archived = "Archived"
    case finalist = "Finalist"
    case hired = "Hired"
}

struct QAResponse: Identifiable, Hashable {
    let id = UUID()
    var question: String
    var answer: String
    var score: Double
    var durationSeconds: Int
    var hasPastedContent: Bool

    var durationFormatted: String {
        let m = durationSeconds / 60
        let s = durationSeconds % 60
        return String(format: "%d:%02d", m, s)
    }
}

struct Candidate: Identifiable, Hashable {
    let id: String
    var firstName: String
    var lastName: String
    var email: String
    var phone: String
    var location: String
    var jobId: String
    var jobTitle: String
    var relevancyScore: Double
    var claimValidityScore: Double
    var tabSwitches: Int
    var isDiamond: Bool
    var isFlagged: Bool
    var flagReason: String?
    var appliedDate: Date
    var status: CandidateStatus
    var resumeText: String
    var education: String
    var experience: String
    var skills: [String]
    var qaResponses: [QAResponse]

    var initials: String {
        let f = firstName.first.map(String.init) ?? ""
        let l = lastName.first.map(String.init) ?? ""
        return f + l
    }

    var fullName: String { "\(firstName) \(lastName)" }

    var overallScore: Double { (relevancyScore + claimValidityScore) / 2 }
}
