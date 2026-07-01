import SwiftUI

struct ScoreBadge: View {
    let label: String
    let value: Double
    var size: CGFloat = 48

    private var color: Color {
        if value >= 4.5 { return AppTheme.primary }
        if value >= 3.5 { return AppTheme.warning }
        return AppTheme.danger
    }

    var body: some View {
        VStack(spacing: 2) {
            ZStack {
                Circle()
                    .stroke(AppTheme.secondaryBackground, lineWidth: 3)
                Circle()
                    .trim(from: 0, to: value / 5.0)
                    .stroke(color, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(String(format: "%.1f", value))
                    .font(.system(size: size * 0.28, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)
            }
            .frame(width: size, height: size)
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(AppTheme.textSecondary)
        }
    }
}

struct InlineScore: View {
    let label: String
    let value: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundColor(AppTheme.textSecondary)
            Text(String(format: "%.1f", value))
                .font(.system(size: 15, weight: .bold))
                .foregroundColor(AppTheme.textPrimary)
            Text("/5")
                .font(.caption2)
                .foregroundColor(AppTheme.textSecondary)
        }
    }
}
