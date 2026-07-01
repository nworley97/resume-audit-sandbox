import SwiftUI

struct CandidateRowView: View {
    let candidate: Candidate

    var body: some View {
        HStack(spacing: 12) {
            ZStack(alignment: .bottomTrailing) {
                AvatarView(initials: candidate.initials, size: 44)
                if candidate.isDiamond {
                    Image(systemName: "diamond.fill")
                        .font(.system(size: 10))
                        .foregroundColor(AppTheme.diamond)
                        .background(Circle().fill(Color.white).frame(width: 16, height: 16))
                        .offset(x: 2, y: 2)
                }
            }

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(candidate.fullName)
                        .font(.system(size: 15, weight: .medium))
                        .foregroundColor(AppTheme.textPrimary)
                    if candidate.isFlagged {
                        FlagBadge(size: 11)
                    }
                }
                Text(candidate.jobTitle)
                    .font(.system(size: 12))
                    .foregroundColor(AppTheme.textSecondary)
                if candidate.isFlagged, let reason = candidate.flagReason {
                    Text(reason)
                        .font(.system(size: 11))
                        .foregroundColor(AppTheme.flagged)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 3) {
                    Text(String(format: "%.1f", candidate.claimValidityScore))
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(AppTheme.textPrimary)
                }
                Text("Claim")
                    .font(.system(size: 10))
                    .foregroundColor(AppTheme.textSecondary)
                HStack(spacing: 3) {
                    Text(String(format: "%.1f", candidate.relevancyScore))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(AppTheme.primary)
                }
                Text("Fit")
                    .font(.system(size: 10))
                    .foregroundColor(AppTheme.textSecondary)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(AppTheme.background)
        .overlay(alignment: .bottom) {
            Divider().padding(.leading, 72)
        }
    }
}
