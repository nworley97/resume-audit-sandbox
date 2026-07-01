import SwiftUI

struct StatCard: View {
    let icon: String
    let value: String
    let label: String
    var iconColor: Color = AppTheme.primary

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(iconColor)
            Text(value)
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(AppTheme.textPrimary)
            Text(label)
                .font(.caption)
                .foregroundColor(AppTheme.textSecondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.background)
        .cornerRadius(AppTheme.cornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 6, x: 0, y: 2)
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
