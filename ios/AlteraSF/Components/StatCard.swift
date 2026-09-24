import SwiftUI

struct StatCard: View {
    let icon: String
    let value: String
    let label: String
    var iconColor: Color = AppTheme.primary
    var outlined = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(iconColor)
                .padding(.bottom, 8)
            Text(value)
                .font(.system(size: 28, weight: .bold))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .foregroundColor(AppTheme.textPrimary)
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(AppTheme.textSecondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.background)
        .cornerRadius(AppTheme.cornerRadius)
        .overlay(RoundedRectangle(cornerRadius: AppTheme.cornerRadius)
            .stroke(outlined ? AppTheme.divider : .clear, lineWidth: 1))
        .accessibilityElement(children: .combine)
    }
}

struct SummaryStatRow: View {
    let stats: [(icon: String, value: String, label: String, color: Color)]

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            ForEach(stats.indices, id: \.self) { i in
                StatCard(icon: stats[i].icon, value: stats[i].value,
                         label: stats[i].label, iconColor: stats[i].color)
            }
        }
    }
}
