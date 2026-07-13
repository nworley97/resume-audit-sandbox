import SwiftUI

struct CandidateQuickPreviewSheet: View {
    let candidate: Candidate
    var onViewFullProfile: () -> Void
    @Environment(\.dismiss) var dismiss
    @State private var showArchiveAlert = false

    private let api = APIService.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                AvatarView(initials: candidate.initials, size: 48)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 4) {
                        Text(candidate.fullName).font(.system(size: 16, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                        if candidate.isDiamond {
                            Image(systemName: "diamond.fill").font(.system(size: 11)).foregroundColor(AppTheme.diamond)
                        }
                    }
                    Text(candidate.jobTitle).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                }
                Spacer()
            }

            HStack(spacing: 10) {
                ProfileScoreCard(label: "Relevancy", value: candidate.relevancyScore)
                ProfileScoreCard(label: "Claim Validity", value: candidate.claimValidityScore)
                ProfileTabSwitchCard(value: candidate.tabSwitches)
            }

            if !candidate.qaResponses.isEmpty {
                let avg = candidate.qaResponses.map(\.score).reduce(0, +) / Double(candidate.qaResponses.count)
                HStack(spacing: 10) {
                    Image(systemName: "bubble.left.and.bubble.right")
                        .font(.system(size: 14)).foregroundColor(AppTheme.primary)
                    Text("\(candidate.qaResponses.count) questions · avg \(String(format: "%.1f", avg))/5 · \(candidate.isFlagged ? "flagged" : "no flags")")
                        .font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                    Spacer()
                    Image(systemName: "chevron.right").font(.system(size: 12)).foregroundColor(AppTheme.textTertiary)
                }
                .padding(12)
                .background(AppTheme.primaryLight)
                .cornerRadius(AppTheme.cornerRadius)
            }

            HStack(spacing: 12) {
                Button { showArchiveAlert = true } label: {
                    Text("Archive")
                        .font(.system(size: 15, weight: .medium))
                        .frame(maxWidth: .infinity).frame(height: 46)
                }
                .background(AppTheme.secondaryBackground)
                .foregroundColor(AppTheme.textPrimary)
                .cornerRadius(AppTheme.buttonCornerRadius)

                Button(action: onViewFullProfile) {
                    HStack(spacing: 6) {
                        Text("View full profile").font(.system(size: 15, weight: .semibold))
                        Image(systemName: "arrow.right")
                    }
                    .frame(maxWidth: .infinity).frame(height: 46)
                }
                .background(AppTheme.primary)
                .foregroundColor(.white)
                .cornerRadius(AppTheme.buttonCornerRadius)
            }
        }
        .padding(20)
        .presentationDetents([.medium])
        .alert("Archive candidate?", isPresented: $showArchiveAlert) {
            Button("Archive", role: .destructive) {
                Task { try? await api.setCandidateStatus(id: candidate.id, status: "archived") }
                dismiss()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove \(candidate.firstName) from your active pipeline.")
        }
    }
}
