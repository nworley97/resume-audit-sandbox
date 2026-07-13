import SwiftUI

struct CloseRoleSheet: View {
    let job: Job
    @Binding var isPresented: Bool
    let onClose: (String?) -> Void

    @State private var candidates: [Candidate] = []
    @State private var isLoading = true
    @State private var selectedCandidate: String? = nil
    @State private var showConfirmation = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 0) {
                if showConfirmation { confirmationView } else { selectionView }
            }
            .navigationTitle("Close this role")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { isPresented = false }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .task {
            let response = try? await APIService.shared.fetchCandidates(jobCode: job.jobId)
            candidates = response?.candidates.map { $0.toDomain() } ?? []
            isLoading = false
        }
    }

    private var selectionView: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Who did you hire? This moves the role to Closed.")
                .font(.subheadline).foregroundColor(AppTheme.textSecondary).padding(16)
            Divider()
            if isLoading {
                HStack { Spacer(); ProgressView(); Spacer() }.padding(.vertical, 24)
            }
            ScrollView {
                VStack(spacing: 10) {
                    ForEach(candidates) { candidate in
                        radioRow(
                            isSelected: selectedCandidate == candidate.fullName,
                            action: { selectedCandidate = candidate.fullName }
                        ) {
                            AvatarView(initials: candidate.initials)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(candidate.fullName).font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                                Text(job.title).font(.caption).foregroundColor(AppTheme.textSecondary)
                            }
                        }
                    }
                    radioRow(isSelected: selectedCandidate == nil, action: { selectedCandidate = nil }) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Nobody").font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                            Text("Close without hiring").font(.caption).foregroundColor(AppTheme.textSecondary)
                        }
                    }
                }
                .padding(16)
            }
            Divider()
            HStack(spacing: 12) {
                Button("Cancel") { isPresented = false }
                    .frame(maxWidth: .infinity).frame(height: 46)
                    .background(AppTheme.secondaryBackground).cornerRadius(AppTheme.buttonCornerRadius)
                    .foregroundColor(AppTheme.textPrimary).font(.system(size: 15, weight: .medium))
                Button("Close role") {
                    showConfirmation = true
                    onClose(selectedCandidate)
                    Task {
                        try? await Task.sleep(nanoseconds: 1_500_000_000)
                        isPresented = false
                    }
                }
                .frame(maxWidth: .infinity).frame(height: 46)
                .background(AppTheme.primary).cornerRadius(AppTheme.buttonCornerRadius)
                .foregroundColor(.white).font(.system(size: 15, weight: .semibold))
            }
            .padding(16)
        }
    }

    private func radioRow<Content: View>(isSelected: Bool, action: @escaping () -> Void, @ViewBuilder content: () -> Content) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 20))
                    .foregroundColor(isSelected ? AppTheme.primary : AppTheme.textTertiary)
                content()
                Spacer()
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? AppTheme.primaryLight : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? AppTheme.primary : AppTheme.divider, lineWidth: isSelected ? 1.5 : 1)
            )
        }
        .buttonStyle(.plain)
    }

    private var confirmationView: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "checkmark.circle.fill").font(.system(size: 56)).foregroundColor(AppTheme.primary)
            Text("Role has been closed").font(.title2.weight(.bold))
            Text("It's been moved to your Closed list and marked as hired.")
                .font(.subheadline).foregroundColor(AppTheme.textSecondary).multilineTextAlignment(.center).padding(.horizontal, 32)
            Spacer()
            Button("Done") { isPresented = false }
                .frame(maxWidth: .infinity).frame(height: 50)
                .background(AppTheme.primary).cornerRadius(AppTheme.buttonCornerRadius)
                .foregroundColor(.white).font(.system(size: 16, weight: .semibold))
                .padding(16)
        }
    }
}
