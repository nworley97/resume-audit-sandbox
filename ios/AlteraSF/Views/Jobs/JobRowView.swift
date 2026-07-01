import SwiftUI

struct JobRowView: View {
    let job: Job
    var onEdit: () -> Void = {}
    var onClose: () -> Void = {}
    var onDelete: () -> Void = {}

    @State private var showActions = false
    @State private var confirmDelete = false
    @State private var navigateToCandidates = false

    var body: some View {
        VStack(spacing: 0) {
            // Title row + three-dot menu
            HStack(alignment: .top) {
                Text(job.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(AppTheme.textPrimary)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button {
                    showActions = true
                } label: {
                    Image(systemName: "ellipsis")
                        .font(.system(size: 16))
                        .foregroundColor(AppTheme.textSecondary)
                        .padding(8)
                        .contentShape(Rectangle())
                }
            }
            .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 2)

            // Job ID + posted date
            Text("\(job.jobId)  ·  Posted \(job.postedDate.formatted(.dateTime.month(.abbreviated).day()))")
                .font(.system(size: 12))
                .foregroundColor(AppTheme.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)

            // Applicants + chevron
            HStack(spacing: 10) {
                StackedAvatars(initials: job.avatarInitials)
                Text("\(job.applicantCount) applicants")
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(AppTheme.textTertiary)
            }
            .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 14)

            Divider().padding(.leading, 16)
        }
        .background(AppTheme.background)
        .contentShape(Rectangle())
        .onTapGesture { navigateToCandidates = true }
        .navigationDestination(isPresented: $navigateToCandidates) {
            CandidatesView(filterJobId: job.jobId)
        }
        .confirmationDialog("", isPresented: $showActions) {
            Button("View candidates") { navigateToCandidates = true }
            Button("Edit role") { onEdit() }
            Button("Close role", role: .destructive) { onClose() }
            Button("Delete role", role: .destructive) { confirmDelete = true }
            Button("Cancel", role: .cancel) {}
        }
        .alert("Delete this role?", isPresented: $confirmDelete) {
            Button("Delete", role: .destructive) { onDelete() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("\"\(job.title)\" and all its data will be permanently removed.")
        }
    }
}
