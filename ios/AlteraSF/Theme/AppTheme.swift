import SwiftUI

enum AppTheme {
    static let primary = Color(red: 0.055, green: 0.565, blue: 0.471)   // #0E9078 teal-emerald
    static let primaryDark = Color(red: 0.035, green: 0.435, blue: 0.361)
    static let primaryLight = Color(red: 0.878, green: 0.957, blue: 0.941)

    static let background = Color(UIColor.systemBackground)
    static let secondaryBackground = Color(UIColor.secondarySystemBackground)
    static let groupedBackground = Color(UIColor.systemGroupedBackground)

    static let textPrimary = Color(UIColor.label)
    static let textSecondary = Color(UIColor.secondaryLabel)
    static let textTertiary = Color(UIColor.tertiaryLabel)

    static let divider = Color(UIColor.separator)

    static let success = Color(red: 0.204, green: 0.780, blue: 0.349)
    static let warning = Color(red: 1.0, green: 0.624, blue: 0.039)
    static let danger = Color(red: 0.933, green: 0.267, blue: 0.267)

    static let diamond = Color(red: 0.055, green: 0.565, blue: 0.471)
    static let flagged = Color(red: 0.933, green: 0.267, blue: 0.267)

    static let cardShadow = Color.black.opacity(0.06)

    static let cornerRadius: CGFloat = 12
    static let cardCornerRadius: CGFloat = 16
    static let buttonCornerRadius: CGFloat = 12
}

extension View {
    func cardStyle() -> some View {
        self
            .background(AppTheme.background)
            .cornerRadius(AppTheme.cardCornerRadius)
            .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}
