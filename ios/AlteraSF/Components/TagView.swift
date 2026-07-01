import SwiftUI

struct TagView: View {
    let text: String
    var color: Color = AppTheme.primary
    var filled: Bool = false

    var body: some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(filled ? .white : color)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(filled ? color : color.opacity(0.12))
            .cornerRadius(6)
    }
}

struct JobStatusTag: View {
    let status: JobStatus

    private var color: Color {
        switch status {
        case .open: return AppTheme.primary
        case .draft: return AppTheme.warning
        case .closed: return AppTheme.textSecondary
        }
    }

    var body: some View {
        TagView(text: status.rawValue, color: color, filled: status == .open)
    }
}

struct DiamondBadge: View {
    var size: CGFloat = 16

    var body: some View {
        Image(systemName: "diamond.fill")
            .font(.system(size: size))
            .foregroundColor(AppTheme.diamond)
    }
}

struct FlagBadge: View {
    var size: CGFloat = 16

    var body: some View {
        Image(systemName: "flag.fill")
            .font(.system(size: size))
            .foregroundColor(AppTheme.flagged)
    }
}
