import SwiftUI

struct CloseRoleSheet: View {
    let job: Job
    @Binding var isPresented: Bool
    let onClose: (String?) -> Void
    @State private var candidates: [Candidate] = []
    @State private var isLoading = true
    @State private var selectedCandidate: String?
    @State private var showConfirmation = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Close role").font(.system(size: 20, weight: .bold))
            Text("Who did you hire? This moves the role to Closed.")
                .font(.system(size: 14)).foregroundColor(AppTheme.textSecondary)
            if isLoading { ProgressView().frame(maxWidth: .infinity) }
            if let error { Text(error).font(.caption).foregroundColor(AppTheme.danger) }
            ScrollView {
                VStack(spacing: 0) {
                    ForEach(candidates) { candidate in
                        Button {
                            selectedCandidate = candidate.fullName
                            showConfirmation = true
                        } label: {
                            HStack(spacing: 12) {
                                AvatarView(initials: candidate.initials, size: 36)
                                Text(candidate.fullName).font(.system(size: 15))
                                    .foregroundColor(AppTheme.textPrimary)
                                Spacer()
                            }
                            .padding(.vertical, 10).contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        Divider()
                    }
                }
            }
            Button("Close without hiring") {
                selectedCandidate = nil
                showConfirmation = true
            }
            .buttonStyle(AlteraButtonStyle(secondary: true))
        }
        .padding(24)
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .task {
            do {
                let response = try await APIService.shared.fetchCandidates(jobCode: job.jobId)
                candidates = response.candidates.map { $0.toDomain() }
            } catch { self.error = error.localizedDescription }
            isLoading = false
        }
        .confirmationDialog("Close this role?", isPresented: $showConfirmation, titleVisibility: .visible) {
            Button("Close role") {
                onClose(selectedCandidate)
                isPresented = false
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text(selectedCandidate.map { "Record \($0) as hired and move this role to Closed." }
                 ?? "Move this role to Closed without recording a hire.")
        }
    }
}
