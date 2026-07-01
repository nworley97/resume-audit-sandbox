import Foundation

enum NotificationType {
    case newApplication
    case assessmentCompleted
    case diamondFound
    case draftSaved
    case jobBoardViews
}

struct AppNotification: Identifiable {
    let id: UUID
    var type: NotificationType
    var title: String
    var subtitle: String
    var timestamp: Date
    var isRead: Bool

    var iconName: String {
        switch type {
        case .newApplication: return "person.badge.plus"
        case .assessmentCompleted: return "checkmark.circle"
        case .diamondFound: return "diamond"
        case .draftSaved: return "square.and.arrow.down"
        case .jobBoardViews: return "megaphone"
        }
    }

    var relativeTime: String {
        let diff = Date().timeIntervalSince(timestamp)
        if diff < 3600 { return "\(Int(diff / 60))m ago" }
        if diff < 86400 { return "\(Int(diff / 3600))h ago" }
        if diff < 604800 { return "\(Int(diff / 86400))d ago" }
        return "Yesterday"
    }

    static let samples: [AppNotification] = [
        AppNotification(id: UUID(), type: .diamondFound, title: "Diamond found", subtitle: "Alex Kim passed verification for Senior Engineer", timestamp: Date().addingTimeInterval(-1800), isRead: false),
        AppNotification(id: UUID(), type: .newApplication, title: "New application", subtitle: "Jordan Lee applied to Product Manager", timestamp: Date().addingTimeInterval(-7200), isRead: false),
        AppNotification(id: UUID(), type: .assessmentCompleted, title: "Assessment completed", subtitle: "Sam Rivera finished the Frontend Engineer assessment", timestamp: Date().addingTimeInterval(-18000), isRead: false),
        AppNotification(id: UUID(), type: .jobBoardViews, title: "Job board traffic spike", subtitle: "Senior Engineer post got 120 views today", timestamp: Date().addingTimeInterval(-86400), isRead: true),
        AppNotification(id: UUID(), type: .draftSaved, title: "Draft saved", subtitle: "Data Analyst role draft was auto-saved", timestamp: Date().addingTimeInterval(-172800), isRead: true),
    ]
}
