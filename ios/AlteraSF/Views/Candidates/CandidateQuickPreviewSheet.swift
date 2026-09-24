import SwiftUI

struct CandidateQuickPreviewSheet: View {
    @EnvironmentObject var authVM: AuthViewModel
    let candidate: Candidate
    var onViewFullProfile: () -> Void
    @State private var isAdding = false
    @State private var added = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(spacing: 14) {
                    AvatarView(initials: candidate.initials, size: 64)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(candidate.fullName)
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(AppTheme.textPrimary)
                        Text(candidate.jobTitle)
                            .font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                        if candidate.isDiamond {
                            Label("Diamond in the Rough", systemImage: "diamond.fill")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundColor(AppTheme.primaryDark)
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(AppTheme.primaryLight).clipShape(Capsule())
                        }
                    }
                    Spacer(minLength: 0)
                }
                HStack(spacing: 10) {
                    ProfileScoreCard(label: "Relevancy", value: candidate.relevancyScore, background: AppTheme.groupedBackground)
                    ProfileScoreCard(label: "Claim Validity", value: candidate.claimValidityScore, background: AppTheme.groupedBackground)
                    ProfileTabSwitchCard(value: candidate.tabSwitches, background: AppTheme.groupedBackground)
                }
                Text("Applied \(candidate.appliedDate.formatted(.dateTime.month(.abbreviated).day().year()))")
                    .font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                if let error {
                    Text(error).font(.caption).foregroundColor(AppTheme.danger)
                }
                VStack(spacing: 10) {
                    Button("View full profile", action: onViewFullProfile)
                        .buttonStyle(AlteraButtonStyle())
                    if authVM.canManageHiring {
                        Button {
                            Task { await addFinalist() }
                        } label: {
                            if isAdding { ProgressView() }
                            else { Text(added || candidate.status == .finalist ? "Added to Finalists" : "Add to Finalists") }
                        }
                        .buttonStyle(AlteraButtonStyle(secondary: true))
                        .disabled(isAdding || added || candidate.status == .finalist)
                    }
                }
            }
            .padding(24)
        }
        .presentationDetents([.height(460), .large])
        .presentationDragIndicator(.visible)
    }

    @MainActor
    private func addFinalist() async {
        isAdding = true
        error = nil
        defer { isAdding = false }
        do {
            try await APIService.shared.setCandidateStatus(id: candidate.id, status: "finalist")
            added = true
        } catch {
            self.error = error.localizedDescription
        }
    }
}
