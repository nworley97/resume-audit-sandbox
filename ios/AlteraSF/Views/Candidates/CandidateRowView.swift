import SwiftUI

struct CandidateRowView: View {
    let candidate: Candidate
    var showsJobTitle = true

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            AvatarView(initials: candidate.initials, size: 48)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(candidate.fullName)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(AppTheme.textPrimary)
                    if candidate.isDiamond {
                        Image(systemName: "diamond.fill")
                            .font(.system(size: 11))
                            .foregroundColor(AppTheme.diamond)
                    }
                    Spacer()
                    if candidate.isFlagged {
                        HStack(spacing: 3) {
                            Image(systemName: "flag.fill").font(.system(size: 9))
                            Text("Flagged").font(.system(size: 11, weight: .semibold))
                        }
                        .foregroundColor(AppTheme.flagged)
                    }
                }

                if candidate.isFlagged, let reason = candidate.flagReason {
                    Text(reason)
                        .font(.system(size: 12))
                        .foregroundColor(AppTheme.flagged)
                } else if showsJobTitle {
                    Text(candidate.jobTitle)
                        .font(.system(size: 12))
                        .foregroundColor(AppTheme.textSecondary)
                }

                HStack(spacing: 6) {
                    ScorePill(label: "Claim", value: candidate.claimValidityScore)
                    ScorePill(label: "Fit", value: candidate.relevancyScore)
                }
                .padding(.top, 2)
            }

            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(AppTheme.textTertiary)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: AppTheme.cardCornerRadius)
                .fill(AppTheme.background)
        )
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.cardCornerRadius)
                .stroke(candidate.isFlagged ? AppTheme.flagged.opacity(0.5) : Color.clear, lineWidth: 1.5)
        )
        .shadow(color: AppTheme.cardShadow, radius: 6, x: 0, y: 2)
        .padding(.horizontal, 16)
        .padding(.vertical, 5)
    }
}

private struct ScorePill: View {
    let label: String
    let value: Double

    var body: some View {
        Text("\(label) \(String(format: "%.1f", value))")
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(value > 0 ? AppTheme.primaryDark : AppTheme.textSecondary)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(value > 0 ? AppTheme.primaryLight : AppTheme.secondaryBackground)
            .cornerRadius(4)
    }
}
