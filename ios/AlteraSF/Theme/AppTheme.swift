import SwiftUI

enum AppTheme {
    static let primary = Color(red: 0.051, green: 0.537, blue: 0.467)
    static let primaryDark = adaptive(0x167C6D, dark: 0x76D8BF)
    static let primaryLight = adaptive(0xE2F3EC, dark: 0x163D34)

    // Separate the page canvas from cards so the Figma dark screens retain
    // their black canvas and raised charcoal surfaces.
    static let background = adaptive(0xFFFFFF, dark: 0x1C1C1E)
    static let secondaryBackground = adaptive(0xEEEEF0, dark: 0x2C2C2E)
    static let groupedBackground = adaptive(0xF3F2F7, dark: 0x000000)
    static let pageBackground = adaptive(0xFFFFFF, dark: 0x000000)

    static let textPrimary = Color(UIColor.label)
    static let textSecondary = Color(UIColor.secondaryLabel)
    static let textTertiary = adaptive(0x929296, dark: 0x929298)

    static let divider = adaptive(0xE9E9ED, dark: 0x333336)

    static let success = Color(red: 0.204, green: 0.780, blue: 0.349)
    static let warning = Color(red: 1.0, green: 0.624, blue: 0.039)
    static let danger = Color(red: 0.933, green: 0.267, blue: 0.267)

    static let diamond = primary
    static let flagged = Color(red: 0.933, green: 0.267, blue: 0.267)

    static let cardShadow = Color.clear

    static let cornerRadius: CGFloat = 10
    static let cardCornerRadius: CGFloat = 12
    static let buttonCornerRadius: CGFloat = 10
    static let pageTitle: Font = .system(size: 34, weight: .bold)

    private static func adaptive(_ light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 255) / 255,
                           green: CGFloat((hex >> 8) & 255) / 255,
                           blue: CGFloat(hex & 255) / 255, alpha: 1)
        })
    }
}

struct AlteraButtonStyle: ButtonStyle {
    var secondary = false
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 15, weight: .medium))
            .frame(maxWidth: .infinity, minHeight: 48)
            .foregroundColor(secondary ? AppTheme.textPrimary : .white)
            .background(secondary ? AppTheme.secondaryBackground : AppTheme.primary)
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.buttonCornerRadius))
            .opacity(isEnabled ? (configuration.isPressed ? 0.75 : 1) : 0.5)
    }
}

enum AppearanceMode: String, CaseIterable, Identifiable {
    case system, light, dark
    var id: String { rawValue }

    var label: String {
        switch self {
        case .system: return "System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }

    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

extension View {
    func cardStyle() -> some View {
        self
            .background(AppTheme.background)
            .cornerRadius(AppTheme.cardCornerRadius)
            .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}
