import SwiftUI

struct AvatarView: View {
    let initials: String
    var size: CGFloat = 36
    var color: Color = AppTheme.primary

    var body: some View {
        Text(initials)
            .font(.system(size: size * 0.38, weight: .semibold))
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(color)
            .clipShape(Circle())
    }
}

struct StackedAvatars: View {
    let initials: [String]
    var size: CGFloat = 28

    private let colors: [Color] = [
        AppTheme.primary,
        Color(red: 0.6, green: 0.4, blue: 0.9),
        Color(red: 0.2, green: 0.6, blue: 0.9),
    ]

    var body: some View {
        HStack(spacing: -(size * 0.3)) {
            ForEach(Array(initials.prefix(3).enumerated()), id: \.offset) { idx, init_ in
                AvatarView(initials: init_, size: size, color: colors[idx % colors.count])
                    .overlay(Circle().stroke(Color.white, lineWidth: 1.5))
                    .zIndex(Double(initials.count - idx))
            }
        }
    }
}
