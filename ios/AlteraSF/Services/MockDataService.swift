import Foundation
import SwiftUI

final class MockDataService: ObservableObject {
    static let shared = MockDataService()

    @Published var departments: [Department]
    @Published var candidates: [Candidate]
    @Published var notifications: [AppNotification]

    var allJobs: [Job] { departments.flatMap(\.jobs) }

    init() {
        let now = Date()
        let cal = Calendar.current

        // ── Jobs ──────────────────────────────────────────────────────────
        let sweFE = Job(
            id: "j1", title: "Software Engineer Intern Frontend",
            jobId: "EPD SWE FE-INT-01", department: "Engineering & Product Development",
            location: "Remote", employmentType: .internship, workArrangement: .remote,
            salaryMin: 80_000, salaryMax: 95_000,
            description: "Build delightful, accessible interfaces for our candidate-facing product. Collaborate with design and backend teams.",
            numberOfQuestions: 4, status: .open,
            postedDate: cal.date(byAdding: .day, value: -52, to: now)!,
            applicantCount: 24, diamondCount: 3
        )
        let sweBE = Job(
            id: "j2", title: "Backend Engineer",
            jobId: "EPD-BE-02", department: "Engineering & Product Development",
            location: "Remote", employmentType: .fullTime, workArrangement: .remote,
            salaryMin: 120_000, salaryMax: 150_000,
            description: "Design and build scalable backend systems that power AlteraSF's AI-assisted hiring platform.",
            numberOfQuestions: 3, status: .open,
            postedDate: cal.date(byAdding: .month, value: -5, to: now)!,
            applicantCount: 9, diamondCount: 1
        )
        let sda = Job(
            id: "j3", title: "Software Development Associate",
            jobId: "20250818-ASF SDA-1", department: "Engineering & Product Development",
            location: "San Francisco, CA", employmentType: .fullTime, workArrangement: .hybrid,
            salaryMin: 100_000, salaryMax: 130_000,
            description: "Join our core product team to build and ship features that help recruiters find better candidates faster.",
            numberOfQuestions: 3, status: .open,
            postedDate: cal.date(byAdding: .day, value: -130, to: now)!,
            applicantCount: 18, diamondCount: 2
        )
        let sdr = Job(
            id: "j4", title: "Sales Development Rep (SDR) Intern",
            jobId: "SNM SDR-INT-01", department: "Sales & Marketing",
            location: "Remote", employmentType: .internship, workArrangement: .remote,
            salaryMin: 0, salaryMax: 0,
            description: "Drive top-of-funnel growth and book qualified meetings for our sales team.",
            numberOfQuestions: 3, status: .open,
            postedDate: cal.date(byAdding: .day, value: -54, to: now)!,
            applicantCount: 31, diamondCount: 4
        )
        let gmm = Job(
            id: "j5", title: "Growth Marketing Manager",
            jobId: "SNM-GMM-02", department: "Sales & Marketing",
            location: "San Francisco, CA", employmentType: .fullTime, workArrangement: .hybrid,
            salaryMin: 90_000, salaryMax: 115_000,
            description: "Lead growth experiments across acquisition and retention channels.",
            numberOfQuestions: 4, status: .open,
            postedDate: cal.date(byAdding: .day, value: -42, to: now)!,
            applicantCount: 12, diamondCount: 1
        )
        let uiux = Job(
            id: "j6", title: "UI/UX Designer",
            jobId: "DSG-I-01", department: "Design",
            location: "Remote", employmentType: .fullTime, workArrangement: .remote,
            salaryMin: 85_000, salaryMax: 110_000,
            description: "Design beautiful, user-centered products that delight both recruiters and candidates.",
            numberOfQuestions: 4, status: .open,
            postedDate: cal.date(byAdding: .day, value: -10, to: now)!,
            applicantCount: 27, diamondCount: 2
        )
        let rc = Job(
            id: "j7", title: "Recruiting Coordinator",
            jobId: "POPSRC-01", department: "People & Operations",
            location: "San Francisco, CA", employmentType: .fullTime, workArrangement: .hybrid,
            salaryMin: 65_000, salaryMax: 80_000,
            description: "Support recruiting operations and help build a world-class talent acquisition function.",
            numberOfQuestions: 2, status: .open,
            postedDate: cal.date(byAdding: .day, value: -59, to: now)!,
            applicantCount: 15, diamondCount: 1
        )
        let mobileDraft = Job(
            id: "j8", title: "Mobile Engineer iOS",
            jobId: "EPD-MOB-01", department: "Engineering & Product Development",
            location: "Remote", employmentType: .fullTime, workArrangement: .remote,
            salaryMin: 130_000, salaryMax: 160_000,
            description: "Draft: Build the AlteraSF iOS app.",
            numberOfQuestions: 4, status: .draft,
            postedDate: cal.date(byAdding: .day, value: -2, to: now)!,
            applicantCount: 0, diamondCount: 0
        )
        let seniorFE = Job(
            id: "j9", title: "Senior Frontend Engineer",
            jobId: "EPD-SFE-01", department: "Engineering & Product Development",
            location: "Remote", employmentType: .fullTime, workArrangement: .remote,
            salaryMin: 150_000, salaryMax: 180_000,
            description: "Closed role.",
            numberOfQuestions: 4, status: .closed,
            postedDate: cal.date(byAdding: .month, value: -3, to: now)!,
            applicantCount: 42, diamondCount: 5,
            hiredCandidate: "Alphonse Otieno"
        )
        let pmm = Job(
            id: "j10", title: "Product Marketing Manager",
            jobId: "SNM-PMM-01", department: "Sales & Marketing",
            location: "San Francisco, CA", employmentType: .fullTime, workArrangement: .hybrid,
            salaryMin: 100_000, salaryMax: 130_000,
            description: "Closed role.",
            numberOfQuestions: 3, status: .closed,
            postedDate: cal.date(byAdding: .month, value: -4, to: now)!,
            applicantCount: 28, diamondCount: 3,
            hiredCandidate: "Rachel Morgan"
        )
        let da = Job(
            id: "j11", title: "Data Analyst",
            jobId: "EPD-DA-01", department: "Engineering & Product Development",
            location: "Remote", employmentType: .fullTime, workArrangement: .remote,
            salaryMin: 85_000, salaryMax: 105_000,
            description: "Closed role.",
            numberOfQuestions: 3, status: .closed,
            postedDate: cal.date(byAdding: .month, value: -4, to: now)!,
            applicantCount: 19, diamondCount: 2,
            hiredCandidate: "Priya Nair"
        )

        departments = [
            Department(id: "d1", name: "Engineering & Product Development",
                       jobs: [sweFE, sweBE, sda, mobileDraft, seniorFE, da]),
            Department(id: "d2", name: "Sales & Marketing", jobs: [sdr, gmm, pmm]),
            Department(id: "d3", name: "Design", jobs: [uiux]),
            Department(id: "d4", name: "People & Operations", jobs: [rc]),
        ]

        // ── Candidates ────────────────────────────────────────────────────
        candidates = [
            Candidate(
                id: "c1", firstName: "Manikanta", lastName: "Reddy Venna",
                email: "mvenna@vt.edu", phone: "(314) 555-0148", location: "Blacksburg, VA",
                jobId: "j1", jobTitle: "Software Engineer Intern Frontend",
                relevancyScore: 5.0, claimValidityScore: 4.8, tabSwitches: 7,
                isDiamond: true, isFlagged: false, appliedDate: cal.date(byAdding: .day, value: -54, to: now)!,
                status: .active,
                resumeText: "Virginia Tech — B.S. Computer Science, GPA 3.9\nExpected May 2026 · Dean's List, ACM Member",
                education: "Virginia Tech — B.S. Computer Science, GPA 3.9 · Expected May 2026",
                experience: "SWE Intern, Brightwave (Summer 2025)\nBuilt a React dashboard used by 4k users; cut load time 38% with code-splitting and memoization.\n\nTeaching Assistant, Data Structures (2024–25)\nLed weekly labs for 60 students; authored autograder tests.",
                skills: ["React", "TypeScript", "Node.js", "Python", "GraphQL", "Accessibility (WCAG)", "Jest", "Figma"],
                qaResponses: [
                    QAResponse(question: "Describe a time you optimized a slow React component.",
                               answer: "I profiled the component with React DevTools and noticed unnecessary re-renders on every keystroke. I memoized the expensive list with React.memo and moved derived values into useMemo, then virtualized the list. Using the Profiler flame graph, I isolated a 412ms render caused by an unmemoized child receiving a new array reference each render.",
                               score: 5.0, durationSeconds: 218, hasPastedContent: false),
                    QAResponse(question: "How do you ensure your UIs are accessible?",
                               answer: "I follow WCAG 2.1 AA guidelines — semantic HTML, ARIA labels, keyboard navigation, and sufficient color contrast ratios.",
                               score: 5.0, durationSeconds: 181, hasPastedContent: false),
                    QAResponse(question: "Walk through your approach to API error handling.",
                               answer: "I use a centralized error boundary at the route level plus per-request try/catch. I map HTTP error codes to user-friendly messages and log to Sentry with context.",
                               score: 4.5, durationSeconds: 185, hasPastedContent: true),
                    QAResponse(question: "Describe a tradeoff you made between speed and quality.",
                               answer: "During a hackathon I shipped a feature without tests to meet a deadline, then wrote the test suite post-launch. It was the right call given the stakes.",
                               score: 4.8, durationSeconds: 191, hasPastedContent: false),
                ]
            ),
            Candidate(
                id: "c2", firstName: "Alphonse", lastName: "Otieno",
                email: "aotieno@gmail.com", phone: "(415) 555-0201", location: "San Francisco, CA",
                jobId: "j1", jobTitle: "Software Engineer Intern Frontend",
                relevancyScore: 5.0, claimValidityScore: 4.5, tabSwitches: 12,
                isDiamond: true, isFlagged: true, flagReason: "AI-flagged answers",
                appliedDate: cal.date(byAdding: .day, value: -52, to: now)!,
                status: .active,
                resumeText: "UC Berkeley — B.S. EECS, GPA 3.7 · Expected May 2026",
                education: "UC Berkeley — B.S. EECS, GPA 3.7 · Expected May 2026",
                experience: "Frontend Intern, Stripe (Summer 2025)\nShipped the redesigned payments dashboard; owned 3 A/B experiments.",
                skills: ["React", "TypeScript", "GraphQL", "Figma", "Storybook"],
                qaResponses: [
                    QAResponse(question: "Describe a time you optimized a slow React component.",
                               answer: "I used Chrome DevTools to profile render bottlenecks and applied React.memo with custom equality checks.",
                               score: 4.5, durationSeconds: 142, hasPastedContent: true),
                ]
            ),
            Candidate(
                id: "c3", firstName: "Preshit", lastName: "R. Pimple",
                email: "ppimple@cs.cmu.edu", phone: "(412) 555-0311", location: "Pittsburgh, PA",
                jobId: "j1", jobTitle: "Software Engineer Intern Frontend",
                relevancyScore: 5.0, claimValidityScore: 4.5, tabSwitches: 3,
                isDiamond: true, isFlagged: false,
                appliedDate: cal.date(byAdding: .day, value: -50, to: now)!,
                status: .active,
                resumeText: "Carnegie Mellon — B.S. Computer Science, GPA 3.8",
                education: "Carnegie Mellon University — B.S. CS, GPA 3.8",
                experience: "SWE Intern, Figma (Summer 2025)\nBuilt a collaborative component library used across 5 product teams.",
                skills: ["React", "Vue", "TypeScript", "CSS", "Node.js", "Rust"],
                qaResponses: []
            ),
            Candidate(
                id: "c4", firstName: "Kenan", lastName: "Yavuz",
                email: "kyavuz@gmail.com", phone: "(212) 555-0412", location: "New York, NY",
                jobId: "j4", jobTitle: "Sales Development Rep (SDR) Intern",
                relevancyScore: 4.5, claimValidityScore: 4.3, tabSwitches: 2,
                isDiamond: false, isFlagged: false,
                appliedDate: cal.date(byAdding: .day, value: -53, to: now)!,
                status: .active,
                resumeText: "NYU — B.S. Business, GPA 3.6",
                education: "New York University — B.S. Business, GPA 3.6",
                experience: "SDR Intern, HubSpot (Summer 2025)\nBooked 47 qualified demos in 10 weeks; exceeded quota by 130%.",
                skills: ["Salesforce", "Outreach", "Cold calling", "LinkedIn Sales Nav", "Gong"],
                qaResponses: []
            ),
            Candidate(
                id: "c5", firstName: "Rachel", lastName: "Morgan",
                email: "rmorgan@salesforce.com", phone: "(650) 555-0503", location: "San Francisco, CA",
                jobId: "j4", jobTitle: "Sales Development Rep (SDR) Intern",
                relevancyScore: 4.3, claimValidityScore: 4.1, tabSwitches: 1,
                isDiamond: false, isFlagged: false,
                appliedDate: cal.date(byAdding: .day, value: -51, to: now)!,
                status: .active,
                resumeText: "Stanford — B.A. Communications, GPA 3.5",
                education: "Stanford University — B.A. Communications, GPA 3.5",
                experience: "Marketing Intern, Salesforce (Summer 2025)",
                skills: ["Salesforce", "HubSpot", "Canva", "Content writing"],
                qaResponses: []
            ),
            Candidate(
                id: "c6", firstName: "Mahin", lastName: "Mohan",
                email: "mmohan@gmail.com", phone: "(510) 555-0601", location: "Oakland, CA",
                jobId: "j4", jobTitle: "Sales Development Rep (SDR) Intern",
                relevancyScore: 4.0, claimValidityScore: 3.8, tabSwitches: 5,
                isDiamond: false, isFlagged: false,
                appliedDate: cal.date(byAdding: .day, value: -49, to: now)!,
                status: .active,
                resumeText: "UC Davis — B.S. Business Economics, GPA 3.4",
                education: "UC Davis — B.S. Business Economics, GPA 3.4",
                experience: "Business Analyst Intern, Deloitte (Summer 2025)",
                skills: ["Excel", "Salesforce", "Tableau", "PowerPoint"],
                qaResponses: []
            ),
        ]

        // ── Notifications ─────────────────────────────────────────────────
        notifications = [
            AppNotification(id: UUID(), type: .newApplication,
                            title: "New application received",
                            subtitle: "Software Engineer Intern Frontend",
                            timestamp: cal.date(byAdding: .minute, value: -2, to: now)!,
                            isRead: false),
            AppNotification(id: UUID(), type: .assessmentCompleted,
                            title: "Alphonse Otieno completed assessment",
                            subtitle: "Relevancy 5.0/5",
                            timestamp: cal.date(byAdding: .hour, value: -1, to: now)!,
                            isRead: false),
            AppNotification(id: UUID(), type: .diamondFound,
                            title: "Diamond in the rough found",
                            subtitle: "Sales Development Rep (SDR) Intern",
                            timestamp: cal.date(byAdding: .hour, value: -3, to: now)!,
                            isRead: false),
            AppNotification(id: UUID(), type: .draftSaved,
                            title: "Draft auto saved",
                            subtitle: "Mobile Engineer (iOS)",
                            timestamp: cal.date(byAdding: .day, value: -1, to: now)!,
                            isRead: true),
            AppNotification(id: UUID(), type: .jobBoardViews,
                            title: "Your job board got 142 views",
                            subtitle: "This week",
                            timestamp: cal.date(byAdding: .day, value: -2, to: now)!,
                            isRead: true),
        ]
    }

    func analyticsData() -> OverallAnalytics {
        let jobAnalytics = [
            JobAnalytics(
                id: "a1", jobId: "j1", jobTitle: "Software Engineer Intern Frontend",
                department: "Engineering", status: .open,
                totalApplicants: 901, diamondsFound: 21,
                completionRate: 33.2, timeSavedHours: 148.4,
                screenSpeed: 85, reviewLoad: 82,
                funnelData: FunnelData(applied: 901, started: 307, completed: 302, verified: 299, passed: 5),
                claimScoreDistribution: [
                    ScoreBucket(label: "1", count: 15, score: 1),
                    ScoreBucket(label: "2", count: 22, score: 2),
                    ScoreBucket(label: "3", count: 58, score: 3),
                    ScoreBucket(label: "4", count: 123, score: 4),
                    ScoreBucket(label: "5", count: 84, score: 5),
                ],
                fitScoreDistribution: [
                    ScoreBucket(label: "1", count: 8, score: 1),
                    ScoreBucket(label: "2", count: 19, score: 2),
                    ScoreBucket(label: "3", count: 71, score: 3),
                    ScoreBucket(label: "4", count: 145, score: 4),
                    ScoreBucket(label: "5", count: 59, score: 5),
                ]
            ),
            JobAnalytics(
                id: "a2", jobId: "j4", jobTitle: "Sales Development Rep Intern",
                department: "Sales & Marketing", status: .open,
                totalApplicants: 307, diamondsFound: 8,
                completionRate: 61.2, timeSavedHours: 48.0,
                screenSpeed: 78, reviewLoad: 65,
                funnelData: FunnelData(applied: 307, started: 201, completed: 188, verified: 180, passed: 8),
                claimScoreDistribution: [
                    ScoreBucket(label: "1", count: 5, score: 1),
                    ScoreBucket(label: "2", count: 18, score: 2),
                    ScoreBucket(label: "3", count: 45, score: 3),
                    ScoreBucket(label: "4", count: 87, score: 4),
                    ScoreBucket(label: "5", count: 33, score: 5),
                ],
                fitScoreDistribution: [
                    ScoreBucket(label: "1", count: 3, score: 1),
                    ScoreBucket(label: "2", count: 12, score: 2),
                    ScoreBucket(label: "3", count: 52, score: 3),
                    ScoreBucket(label: "4", count: 98, score: 4),
                    ScoreBucket(label: "5", count: 23, score: 5),
                ]
            ),
            JobAnalytics(
                id: "a3", jobId: "j6", jobTitle: "UI/UX Designer",
                department: "Design", status: .draft,
                totalApplicants: 142, diamondsFound: 5,
                completionRate: 44.0, timeSavedHours: 22.5,
                screenSpeed: 70, reviewLoad: 55,
                funnelData: FunnelData(applied: 142, started: 88, completed: 63, verified: 60, passed: 5),
                claimScoreDistribution: [],
                fitScoreDistribution: []
            ),
            JobAnalytics(
                id: "a4", jobId: "j7", jobTitle: "Recruiting Coordinator",
                department: "People & Ops", status: .draft,
                totalApplicants: 64, diamondsFound: 2,
                completionRate: 51.0, timeSavedHours: 10.2,
                screenSpeed: 68, reviewLoad: 50,
                funnelData: FunnelData(applied: 64, started: 41, completed: 33, verified: 30, passed: 2),
                claimScoreDistribution: [],
                fitScoreDistribution: []
            ),
        ]
        return OverallAnalytics(
            totalApplicants: jobAnalytics.reduce(0) { $0 + $1.totalApplicants },
            totalDiamonds: jobAnalytics.reduce(0) { $0 + $1.diamondsFound },
            jobPostings: jobAnalytics
        )
    }

    func candidates(forJobId id: String) -> [Candidate] {
        candidates.filter { $0.jobId == id }
    }

    func markNotificationsRead() {
        for i in notifications.indices {
            notifications[i].isRead = true
        }
    }

    var unreadCount: Int { notifications.filter { !$0.isRead }.count }
}
