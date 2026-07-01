import SwiftUI

struct CloseRoleSheet: View {
    let job: Job
    let candidates: [Candidate]    // pass in from caller (already loaded in JobsVM)
    @Binding var isPresented: Bool
    let onClose: (String?) -> Void

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
    }

    private var selectionView: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Who did you hire? This moves the role to Closed.")
                .font(.subheadline).foregroundColor(AppTheme.textSecondary).padding(16)
            Divider()
            ScrollView {
                VStack(spacing: 0) {
                    ForEach(candidates) { candidate in
                        Button {
                            selectedCandidate = candidate.fullName
                        } label: {
                            HStack {
                                AvatarView(initials: candidate.initials)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(candidate.fullName).font(.system(size: 15, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                                    Text(job.title).font(.caption).foregroundColor(AppTheme.textSecondary)
                                }
                                Spacer()
                                if selectedCandidate == candidate.fullName {
                                    Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.primary)
                                }
                            }
                            .padding(16)
                        }
                        Divider().padding(.leading, 64)
                    }
                    Button {
                        selectedCandidate = nil
                    } label: {
                        HStack {
                            Text("Nobody").font(.system(size: 15)).foregroundColor(AppTheme.textPrimary)
                            Spacer()
                            if selectedCandidate == nil {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.primary)
                            }
                        }
                        .padding(16)
                    }
                    Divider()
                    Text("Close without hiring").font(.caption).foregroundColor(AppTheme.textSecondary).padding(.vertical, 8)
                }
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
